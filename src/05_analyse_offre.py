"""Construit l'analyse de l'offre et évalue une baseline temporelle."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "data" / "database" / "gtfs_pays_loire.sqlite"
OUTPUT = ROOT / "reports" / "analyse_offre.json"
TIME_PERIODS = [
    "night",
    "morning_peak",
    "morning",
    "midday",
    "afternoon",
    "evening_peak",
    "night_service",
]


def mean(values: list[float]) -> float:
    """Calcule une moyenne avec une valeur de repli pour une liste vide."""
    return sum(values) / len(values) if values else 0.0


def load_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Charge le niveau d'offre au grain arrêt-date-période."""
    rows = connection.execute(
        "SELECT service_date, stop_id, stop_name, coordinate_status, "
        "time_period, planned_departures "
        "FROM v_departures_by_stop_period "
        "ORDER BY service_date, stop_id, time_period"
    ).fetchall()
    if not rows:
        raise RuntimeError("La vue analytique ne contient aucune observation.")
    return rows


def split_dates(rows: list[sqlite3.Row]) -> tuple[set[str], set[str]]:
    """Sépare chronologiquement les dates en entraînement et test."""
    dates = sorted({row["service_date"] for row in rows})
    if len(dates) < 2:
        raise RuntimeError("Le jeu de données ne contient pas assez de dates pour un split train/test.")
    # Une séparation temporelle évite de donner au modèle des dates futures
    # pendant l'entraînement, contrairement à un échantillonnage aléatoire.
    split_index = max(1, math.floor(len(dates) * 0.8))
    train_dates = set(dates[:split_index])
    test_dates = set(dates[split_index:])
    if not test_dates:
        raise RuntimeError("Le split train/test est vide. Vérifier la couverture temporelle de la base.")
    return train_dates, test_dates


def build_baseline(rows: list[sqlite3.Row], train_dates: set[str], test_dates: set[str]) -> tuple[dict, int]:
    """Construit une baseline par arrêt et période avec repli global."""
    train_rows = [row for row in rows if row["service_date"] in train_dates]
    test_rows = [row for row in rows if row["service_date"] in test_dates]

    by_stop_period: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    by_period: defaultdict[str, list[int]] = defaultdict(list)
    for row in train_rows:
        key = (row["stop_id"], row["time_period"])
        by_stop_period[key].append(int(row["planned_departures"]))
        by_period[row["time_period"]].append(int(row["planned_departures"]))

    errors: list[tuple[float, float]] = []
    fallback_count = 0
    for row in test_rows:
        key = (row["stop_id"], row["time_period"])
        values = by_stop_period.get(key)
        if values:
            prediction = mean([float(value) for value in values])
        else:
            # Le repli par période permet de prédire même un arrêt absent de l'historique.
            if row["time_period"] not in by_period:
                raise RuntimeError(f"Aucune donnée historique pour la période {row['time_period']}.")
            prediction = mean([float(value) for value in by_period[row["time_period"]]])
            fallback_count += 1
        # MAE mesure l'erreur moyenne absolue ; RMSE pénalise davantage les gros écarts.
        error = prediction - float(row["planned_departures"])
        errors.append((abs(error), error * error))

    return {
        "name": "mean_by_stop_and_period_with_period_fallback",
        "test_observation_count": len(test_rows),
        "fallback_observation_count": fallback_count,
        "mae": round(mean([item[0] for item in errors]), 4),
        "rmse": round(math.sqrt(mean([item[1] for item in errors])), 4),
    }, fallback_count


def main() -> None:
    if not DATABASE.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {DATABASE}")

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    # La vue SQL centralise l'indicateur d'offre utilisé par la baseline.
    rows = load_rows(connection)
    train_dates, test_dates = split_dates(rows)
    baseline, _ = build_baseline(rows, train_dates, test_dates)

    dates = sorted({row["service_date"] for row in rows})
    # Cette sélection sert à repérer les zones où l'offre moyenne est la plus faible.
    low_service = connection.execute(
        "SELECT stop_id, stop_name, coordinate_status, time_period, "
        "ROUND(AVG(planned_departures), 2) AS average_departures "
        "FROM v_departures_by_stop_period "
        "GROUP BY stop_id, stop_name, coordinate_status, time_period "
        "ORDER BY average_departures, stop_id, time_period LIMIT 20"
    ).fetchall()

    result = {
        "grain": "stop_date_time_period",
        "time_periods": TIME_PERIODS,
        "observation_count": len(rows),
        "date_count": len(dates),
        "date_min": dates[0],
        "date_max": dates[-1],
        "train_date_count": len(train_dates),
        "test_date_count": len(test_dates),
        "baseline": baseline,
        "lowest_average_offer": [dict(row) for row in low_service],
    }

    OUTPUT.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    connection.close()

    print(f"Analyse écrite dans {OUTPUT.name}")
    print(f"Observations: {len(rows):,}; MAE baseline: {result['baseline']['mae']}")


if __name__ == "__main__":
    main()
