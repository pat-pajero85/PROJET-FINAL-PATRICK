"""Compare deux modèles de regression et documente les risques du projet."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

# Le GridSearch est volontairement borne pour rester executable sur une machine locale.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "data" / "database" / "gtfs_pays_loire.sqlite"
OUTPUT = ROOT / "reports" / "etape6_modeles_risques.json"
RANDOM_STATE = 42
MAX_TRAIN_ROWS = 10_000
TEMPORAL_TRAIN_ROWS = 10_000
MAX_TEST_ROWS = 30_000

NUMERIC_FEATURES = [
    "stop_lat",
    "stop_lon",
    "route_count",
    "first_departure_hours",
    "last_departure_hours",
    "day_of_week",
    "day_of_month",
    "month",
]
CATEGORICAL_FEATURES = ["time_period", "coordinate_status"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_data(connection: sqlite3.Connection) -> pd.DataFrame:
    """Charge l'agregat avec les coordonnees des arrets et derive le calendrier."""
    available_dates = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT service_date FROM v_departures_by_stop_period "
            "ORDER BY service_date"
        )
    ]
    if len(available_dates) < 10:
        raise RuntimeError("Il faut au moins dix dates pour une evaluation temporelle.")
    split_date = available_dates[max(1, int(len(available_dates) * 0.8))]
    query = """
        SELECT v.service_date,
               v.stop_id,
               s.stop_lat,
               s.stop_lon,
               v.coordinate_status,
               v.time_period,
               v.planned_departures,
               v.route_count,
               v.first_departure_seconds / 3600.0 AS first_departure_hours,
               v.last_departure_seconds / 3600.0 AS last_departure_hours
        FROM v_departures_by_stop_period AS v
        JOIN stop AS s ON s.stop_id = v.stop_id
        WHERE v.service_date >= ? AND v.service_date < ?
        ORDER BY v.service_date, v.stop_id, v.time_period
        LIMIT ?
    """
    train = pd.read_sql_query(query, connection, params=[available_dates[0], split_date, MAX_TRAIN_ROWS])
    test_query = query.replace(
        "v.service_date >= ? AND v.service_date < ?", "v.service_date >= ?"
    )
    test = pd.read_sql_query(test_query, connection, params=[split_date, MAX_TEST_ROWS])
    data = pd.concat([train, test], ignore_index=True)
    if data.empty:
        raise RuntimeError("La vue de modelisation ne contient aucune observation.")

    dates = pd.to_datetime(data["service_date"], format="%Y%m%d")
    data["day_of_week"] = dates.dt.dayofweek
    data["day_of_month"] = dates.dt.day
    data["month"] = dates.dt.month
    return data


def split_temporally(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Reserve les 20 pour cent de dates les plus recentes pour le test."""
    dates = sorted(data["service_date"].unique())
    if len(dates) < 10:
        raise RuntimeError("Il faut au moins dix dates pour une evaluation temporelle.")
    split_index = max(1, int(len(dates) * 0.8))
    split_date = dates[split_index]
    train = data[data["service_date"] < split_date].copy()
    test = data[data["service_date"] >= split_date].copy()
    if train.empty or test.empty:
        raise RuntimeError("Le split temporel produit un train ou un test vide.")
    return train, test, str(split_date)


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("numeric", "passthrough", NUMERIC_FEATURES),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def evaluate_model(
    name: str,
    estimator: object,
    parameters: dict[str, list[object]],
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> dict[str, object]:
    """Optimise un modele sur le train puis mesure sa performance sur le futur."""
    pipeline = Pipeline(
        [("preprocessor", make_preprocessor()), ("model", estimator)]
    )
    search = GridSearchCV(
        pipeline,
        {f"model__{key}": values for key, values in parameters.items()},
        scoring="neg_mean_absolute_error",
        cv=TimeSeriesSplit(n_splits=3),
        # Un seul processus evite de dupliquer les matrices en memoire sur la machine locale.
        n_jobs=1,
        refit=True,
    )
    search.fit(train[FEATURES], train["planned_departures"])
    predictions = np.maximum(search.predict(test[FEATURES]), 0)
    actual = test["planned_departures"]
    return {
        "name": name,
        "best_params": search.best_params_,
        "cv_mae": round(float(-search.best_score_), 4),
        "test_mae": round(float(mean_absolute_error(actual, predictions)), 4),
        "test_rmse": round(float(mean_squared_error(actual, predictions) ** 0.5), 4),
        "test_r2": round(float(r2_score(actual, predictions)), 4),
    }


def score_predictions(actual: pd.Series, predictions: np.ndarray) -> dict[str, float]:
    """Calcule les indicateurs communs aux modeles et a la baseline."""
    return {
        "mae": round(float(mean_absolute_error(actual, predictions)), 4),
        "rmse": round(float(mean_squared_error(actual, predictions) ** 0.5), 4),
        "r2": round(float(r2_score(actual, predictions)), 4),
    }


def evaluate_baseline(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, float]:
    """Predit la moyenne historique des departs pour chaque periode horaire."""
    period_means = train.groupby("time_period")["planned_departures"].mean()
    fallback = float(train["planned_departures"].mean())
    predictions = test["time_period"].map(period_means).fillna(fallback).to_numpy()
    return score_predictions(test["planned_departures"], predictions)


def evaluate_temporal_windows(
    data: pd.DataFrame,
    model_parameters: dict[str, object],
) -> list[dict[str, object]]:
    """Compare le modele retenu et la baseline sur trois periodes futures."""
    dates = sorted(data["service_date"].unique())
    if len(dates) < 10:
        raise RuntimeError("Il faut au moins dix dates pour les fenetres temporelles.")

    windows = []
    for window_number, start_ratio in enumerate((0.6, 0.7, 0.8), start=1):
        test_start_index = max(1, int(len(dates) * start_ratio))
        test_end_index = min(len(dates), test_start_index + max(1, int(len(dates) * 0.1)))
        train = data[data["service_date"] < dates[test_start_index]].copy()
        test = data[
            (data["service_date"] >= dates[test_start_index])
            & (data["service_date"] < dates[test_end_index])
        ].copy()
        if train.empty or test.empty:
            continue
        if len(train) > TEMPORAL_TRAIN_ROWS:
            train = train.sample(TEMPORAL_TRAIN_ROWS, random_state=RANDOM_STATE).sort_values("service_date")

        pipeline = Pipeline(
            [
                ("preprocessor", make_preprocessor()),
                (
                    "model",
                    RandomForestRegressor(
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                        max_depth=int(model_parameters["model__max_depth"]),
                        n_estimators=min(10, int(model_parameters["model__n_estimators"])),
                    ),
                ),
            ]
        )
        pipeline.fit(train[FEATURES], train["planned_departures"])
        predictions = np.maximum(pipeline.predict(test[FEATURES]), 0)
        windows.append(
            {
                "window": window_number,
                "train_date_max": str(train["service_date"].max()),
                "test_date_min": str(test["service_date"].min()),
                "test_date_max": str(test["service_date"].max()),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "random_forest": score_predictions(test["planned_departures"], predictions),
                "baseline_period_mean": evaluate_baseline(train, test),
            }
        )
    return windows


def build_risk_assessment(selected_model: str) -> list[dict[str, object]]:
    return [
        {
            "category": "qualite_et_biais_des_donnees",
            "risk": "Le GTFS decrit une offre planifiee, avec des arrets hors emprise et des champs facultatifs incomplets.",
            "impact": "Une prediction peut etre precise sur le planning sans representer la desserte reellement assuree ni la demande.",
            "mitigation": "Controler les cles et les dates a chaque import, conserver les statuts geographiques, segmenter les resultats par territoire et completer avec frequentation et donnees temps reel.",
        },
        {
            "category": "risque_modele",
            "risk": "Les variables de calendrier et de planning expliquent l'offre mais ne prouvent pas un besoin de mobilite; un changement de reseau peut rendre le modele obsolete.",
            "impact": "Risque de generalisation faible et de priorisation injustifiee des secteurs faiblement desservis.",
            "mitigation": f"Comparer au modele retenu ({selected_model}) une baseline, utiliser un split temporel, suivre MAE/RMSE par periode et recalibrer a chaque nouveau feed.",
        },
        {
            "category": "deploiement",
            "risk": "Un modele entraine sur un feed local peut recevoir des colonnes, des dates ou des modalites inconnues en production.",
            "impact": "Predictions silencieusement degradees ou service indisponible.",
            "mitigation": "Versionner le schema et le modele, valider les types et distributions en entree, journaliser les erreurs, tester la prediction sur un jeu de reference et prevoir un repli baseline.",
        },
        {
            "category": "ethique",
            "risk": "Un indicateur de faible offre peut concentrer les arbitrages sur des territoires deja moins desservis sans mesurer les populations concernees.",
            "impact": "Renforcement d'inegalites territoriales et decision publique difficilement explicable.",
            "mitigation": "Utiliser le modele comme aide a la decision, publier les limites, analyser les erreurs par zone et accessibilite, puis faire valider les arbitrages par les acteurs locaux.",
        },
    ]


def main() -> None:
    if not DATABASE.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {DATABASE}")

    with sqlite3.connect(DATABASE) as connection:
        data = load_data(connection)

    train, test, split_date = split_temporally(data)
    if len(train) > MAX_TRAIN_ROWS:
        train = train.sample(MAX_TRAIN_ROWS, random_state=RANDOM_STATE).sort_values("service_date")

    models = [
        evaluate_model(
            "random_forest",
            RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=1),
            {"n_estimators": [40, 60], "max_depth": [18]},
            train,
            test,
        ),
        evaluate_model(
            "hist_gradient_boosting",
            HistGradientBoostingRegressor(random_state=RANDOM_STATE),
            {"max_iter": [80, 120], "max_leaf_nodes": [15]},
            train,
            test,
        ),
    ]
    selected = min(models, key=lambda item: (item["test_mae"], item["test_rmse"]))
    temporal_windows = evaluate_temporal_windows(data, selected["best_params"])
    result = {
        "grain": "stop_date_time_period",
        "target": "planned_departures",
        "features": FEATURES,
        "observation_count": int(len(data)),
        "train_rows_used": int(len(train)),
        "test_rows": int(len(test)),
        "date_min": str(data["service_date"].min()),
        "date_max": str(data["service_date"].max()),
        "split_date": split_date,
        "models": models,
        "selected_model": selected["name"],
        "temporal_evaluation": {
            "method": "trois fenetres futures successives de dix pour cent des dates, avec entrainement uniquement sur les dates precedentes",
            "windows": temporal_windows,
        },
        "selection_justification": "Le modele retenu minimise d'abord la MAE sur les dates futures, puis la RMSE en cas d'egalite. La MAE est directement interpretable en nombre de departs.",
        "risks": build_risk_assessment(str(selected["name"])),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Rapport ecrit dans {OUTPUT.name}")
    print(f"Modele retenu: {selected['name']} | MAE test: {selected['test_mae']}")


if __name__ == "__main__":
    main()