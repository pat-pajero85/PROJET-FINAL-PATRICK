"""Premiere analyse exploratoire de l'offre GTFS pour l'etape 4."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "data" / "database" / "gtfs_pays_loire.sqlite"
REPORTS = ROOT / "reports"


def load_summaries() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calcule les indicateurs en SQLite sans charger toute la vue."""
    with sqlite3.connect(DATABASE) as connection:
        # Les agrégations restent côté SQLite pour éviter de transférer 4 millions de lignes.
        h1 = pd.read_sql_query(
            """
            SELECT time_period,
                   AVG(planned_departures) AS average_departures,
                   COUNT(*) AS observation_count
            FROM v_departures_by_stop_period
            GROUP BY time_period
            """,
            connection,
        )
        h2 = pd.read_sql_query(
            """
            SELECT CASE
                       WHEN CAST(strftime('%w', substr(service_date, 1, 4) || '-' ||
                                  substr(service_date, 5, 2) || '-' ||
                                  substr(service_date, 7, 2)) AS INTEGER) IN (0, 6)
                       THEN 'Week-end'
                       ELSE 'Jour ouvré'
                   END AS day_type,
                   AVG(planned_departures) AS average_departures,
                   COUNT(*) AS observation_count
            FROM v_departures_by_stop_period
            GROUP BY day_type
            """,
            connection,
        )
        h3 = pd.read_sql_query(
            """
            SELECT route_count, planned_departures,
                   COUNT(*) AS observation_count
            FROM v_departures_by_stop_period
            GROUP BY route_count, planned_departures
            """,
            connection,
        )
    return h1, h2, h3


def analyse_h1(data: pd.DataFrame) -> pd.DataFrame:
    """Calcule l'offre moyenne par période horaire."""
    period_order = [
        "night",
        "morning_peak",
        "morning",
        "midday",
        "afternoon",
        "evening_peak",
        "night_service",
    ]
    result = data[["time_period", "average_departures", "observation_count"]].copy()
    result["time_period"] = pd.Categorical(
        result["time_period"], categories=period_order, ordered=True
    )
    return result.sort_values("time_period").reset_index(drop=True)


def analyse_h2(data: pd.DataFrame) -> pd.DataFrame:
    """Compare l'offre moyenne entre jours ouvrés et week-end."""
    return (
        data[["day_type", "average_departures", "observation_count"]]
        .sort_values("day_type")
        .reset_index(drop=True)
    )


def analyse_h3(data: pd.DataFrame) -> dict[str, float]:
    """Mesure la correlation entre lignes desservantes et departs."""
    # Le regroupement SQL fournit un effectif par couple de valeurs : il faut donc
    # pondérer les moyennes et covariances par le nombre d'observations.
    weights = data["observation_count"]
    route_counts = data["route_count"]
    departures = data["planned_departures"]
    total = weights.sum()
    route_mean = (route_counts * weights).sum() / total
    departure_mean = (departures * weights).sum() / total
    covariance = (
        weights * (route_counts - route_mean) * (departures - departure_mean)
    ).sum() / total
    route_variance = (weights * (route_counts - route_mean) ** 2).sum() / total
    departure_variance = (weights * (departures - departure_mean) ** 2).sum() / total
    pearson = covariance / (route_variance * departure_variance) ** 0.5
    ranked = data.copy()
    # Le classement des valeurs regroupées permet d'obtenir une approximation pondérée de Spearman.
    ranked["route_rank"] = ranked["route_count"].rank(method="average")
    ranked["departure_rank"] = ranked["planned_departures"].rank(method="average")
    rank_route_mean = (ranked["route_rank"] * weights).sum() / total
    rank_departure_mean = (ranked["departure_rank"] * weights).sum() / total
    rank_covariance = (
        weights
        * (ranked["route_rank"] - rank_route_mean)
        * (ranked["departure_rank"] - rank_departure_mean)
    ).sum() / total
    rank_route_variance = (weights * (ranked["route_rank"] - rank_route_mean) ** 2).sum() / total
    rank_departure_variance = (
        weights * (ranked["departure_rank"] - rank_departure_mean) ** 2
    ).sum() / total
    spearman = rank_covariance / (rank_route_variance * rank_departure_variance) ** 0.5
    return {
        "pearson_correlation": round(float(pearson), 4),
        "spearman_correlation": round(float(spearman), 4),
        "observation_count": int(total),
    }


def plot_h1(result: pd.DataFrame) -> None:
    """Produit le graphique de l'offre moyenne par période."""
    labels = {
        "night": "Nuit",
        "morning_peak": "Pointe matin",
        "morning": "Matinée",
        "midday": "Midi",
        "afternoon": "Après-midi",
        "evening_peak": "Pointe soir",
        "night_service": "Soirée",
    }
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.bar(
        result["time_period"].map(labels),
        result["average_departures"],
        color="#176b87",
    )
    axis.set_title("Offre moyenne par période horaire")
    axis.set_xlabel("Période")
    axis.set_ylabel("Départs planifiés moyens par observation")
    axis.tick_params(axis="x", rotation=25)
    figure.tight_layout()
    figure.savefig(REPORTS / "etape4_h1_offre_par_periode.png", dpi=150)
    plt.close(figure)


def plot_h2(result: pd.DataFrame) -> None:
    """Produit le graphique de l'offre moyenne par type de jour."""
    figure, axis = plt.subplots(figsize=(7, 5))
    axis.bar(
        result["day_type"],
        result["average_departures"],
        color=["#176b87", "#d97941"],
    )
    axis.set_title("Offre moyenne : jours ouvrés et week-end")
    axis.set_xlabel("Type de jour")
    axis.set_ylabel("Départs planifiés moyens par observation")
    figure.tight_layout()
    figure.savefig(REPORTS / "etape4_h2_offre_jours_ouvres_weekend.png", dpi=150)
    plt.close(figure)


def plot_h3(data: pd.DataFrame) -> None:
    """Produit un nuage de points entre lignes et departs."""
    figure, axis = plt.subplots(figsize=(8, 5))
    # La taille des points représente le nombre d'observations regroupées.
    axis.scatter(
        data["route_count"],
        data["planned_departures"],
        alpha=0.45,
        s=data["observation_count"].clip(lower=1).pow(0.5),
        color="#176b87",
    )
    axis.set_title("Lignes desservantes et départs planifiés")
    axis.set_xlabel("Nombre de lignes desservant l'arrêt")
    axis.set_ylabel("Départs planifiés")
    figure.tight_layout()
    figure.savefig(REPORTS / "etape4_h3_correlation_lignes_departs.png", dpi=150)
    plt.close(figure)


def main() -> None:
    if not DATABASE.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {DATABASE}")

    h1_data, h2_data, h3_data = load_summaries()
    h1_result = analyse_h1(h1_data)
    h1_result.to_csv(REPORTS / "etape4_h1_offre_par_periode.csv", index=False)
    plot_h1(h1_result)

    h2_result = analyse_h2(h2_data)
    h2_result.to_csv(REPORTS / "etape4_h2_offre_jours_ouvres_weekend.csv", index=False)
    plot_h2(h2_result)

    h3_result = analyse_h3(h3_data)
    pd.DataFrame([h3_result]).to_csv(
        REPORTS / "etape4_h3_correlation_lignes_departs.csv", index=False
    )
    plot_h3(h3_data)

    print("H1 - Offre par période")
    print(h1_result.to_string(index=False))
    print("\nH2 - Offre par type de jour")
    print(h2_result.to_string(index=False))
    print("\nH3 - Corrélation lignes et départs")
    print(h3_result)
    print("\nFichiers produits dans reports/ : tableaux CSV et graphiques PNG")


if __name__ == "__main__":
    main()