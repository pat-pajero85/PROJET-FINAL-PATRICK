"""Construit l'analyse de l'offre et evalue une baseline temporelle."""

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).parent
DATABASE = ROOT / "gtfs_pays_loire.sqlite"
OUTPUT = ROOT / "analyse_offre.json"


def mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT service_date, stop_id, stop_name, coordinate_status, "
        "time_period, planned_departures "
        "FROM v_departures_by_stop_period "
        "ORDER BY service_date, stop_id, time_period"
    ).fetchall()
    if not rows:
        raise RuntimeError("La vue analytique ne contient aucune observation")

    dates = sorted({row["service_date"] for row in rows})
    split_index = max(1, math.floor(len(dates) * 0.8))
    train_dates = set(dates[:split_index])
    test_dates = set(dates[split_index:])
    train_rows = [row for row in rows if row["service_date"] in train_dates]
    test_rows = [row for row in rows if row["service_date"] in test_dates]

    by_stop_period = defaultdict(list)
    by_period = defaultdict(list)
    for row in train_rows:
        key = (row["stop_id"], row["time_period"])
        by_stop_period[key].append(row["planned_departures"])
        by_period[row["time_period"]].append(row["planned_departures"])

    errors = []
    fallback_count = 0
    for row in test_rows:
        key = (row["stop_id"], row["time_period"])
        values = by_stop_period.get(key)
        if values:
            prediction = mean(values)
        else:
            prediction = mean(by_period[row["time_period"]])
            fallback_count += 1
        error = prediction - row["planned_departures"]
        errors.append((abs(error), error * error))

    low_service = connection.execute(
        "SELECT stop_id, stop_name, coordinate_status, time_period, "
        "ROUND(AVG(planned_departures), 2) AS average_departures "
        "FROM v_departures_by_stop_period "
        "WHERE service_date IN (SELECT service_date FROM service_date "
        "WHERE exception_type = 1) "
        "GROUP BY stop_id, stop_name, coordinate_status, time_period "
        "ORDER BY average_departures, stop_id, time_period LIMIT 20"
    ).fetchall()
    result = {
        "grain": "stop_date_time_period",
        "time_periods": [
            "night", "morning_peak", "morning", "midday",
            "afternoon", "evening_peak", "night_service",
        ],
        "observation_count": len(rows),
        "date_count": len(dates),
        "date_min": dates[0],
        "date_max": dates[-1],
        "train_date_count": len(train_dates),
        "test_date_count": len(test_dates),
        "baseline": {
            "name": "mean_by_stop_and_period_with_period_fallback",
            "test_observation_count": len(test_rows),
            "fallback_observation_count": fallback_count,
            "mae": round(mean([item[0] for item in errors]), 4),
            "rmse": round(math.sqrt(mean([item[1] for item in errors])), 4),
        },
        "lowest_average_offer": [dict(row) for row in low_service],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    connection.close()
    print(f"Analyse écrite dans {OUTPUT.name}")
    print(f"Observations: {len(rows):,}; MAE baseline: {result['baseline']['mae']}")


if __name__ == "__main__":
    main()
