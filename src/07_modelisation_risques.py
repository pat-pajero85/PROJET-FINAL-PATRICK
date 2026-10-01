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
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "data" / "database" / "gtfs_pays_loire.sqlite"
OUTPUT = ROOT / "reports" / "etape6_modeles_risques.json"
RANDOM_STATE = 42
MAX_TRAIN_ROWS = 10_000
MAX_TEST_ROWS = 30_000
MAX_TRAIN_DATES = 80

NUMERIC_FEATURES = [
    "stop_lat",
    "stop_lon",
    "day_of_week",
    "month",
]
CATEGORICAL_FEATURES = ["time_period", "coordinate_status"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def select_dates(dates: list[str], limit: int) -> list[str]:
    """Selectionne des dates regulierement espacees dans une periode."""
    if len(dates) <= limit:
        return dates
    positions = np.linspace(0, len(dates) - 1, num=limit, dtype=int)
    return [dates[position] for position in positions]


def sample_by_date(data: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    """Echantillonne chaque date pour conserver une couverture temporelle."""
    if data.empty:
        return data.copy()

    dates = sorted(data["service_date"].unique())
    rows_per_date = max(1, max_rows // len(dates))
    samples = []
    for index, (_, group) in enumerate(data.groupby("service_date", sort=True)):
        samples.append(
            group.sample(
                n=min(len(group), rows_per_date),
                random_state=RANDOM_STATE + index,
            )
        )
    return pd.concat(samples, ignore_index=True).sort_values(
        "service_date"
    ).reset_index(drop=True)


def load_data(connection: sqlite3.Connection) -> tuple[pd.DataFrame, str]:
    """Charge des dates espacees sans variables calculees a partir de la cible."""
    available_dates = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT service_date FROM v_departures_by_stop_period "
            "ORDER BY service_date"
        )
    ]
    if len(available_dates) < 10:
        raise RuntimeError("Il faut au moins dix dates pour une evaluation temporelle.")
    split_index = max(1, int(len(available_dates) * 0.8))
    split_date = available_dates[split_index]
    train_dates = select_dates(available_dates[:split_index], MAX_TRAIN_DATES)
    test_dates = available_dates[split_index:]
    selected_dates = train_dates + test_dates
    placeholders = ", ".join("?" for _ in selected_dates)
    query = """
        SELECT v.service_date,
               v.stop_id,
               s.stop_lat,
               s.stop_lon,
               v.coordinate_status,
               v.time_period,
               v.planned_departures
        FROM v_departures_by_stop_period AS v
        JOIN stop AS s ON s.stop_id = v.stop_id
        WHERE v.service_date IN ({placeholders})
        ORDER BY v.service_date, v.stop_id, v.time_period
    """
    data = pd.read_sql_query(
        query.format(placeholders=placeholders), connection, params=selected_dates
    )
    if data.empty:
        raise RuntimeError("La vue de modelisation ne contient aucune observation.")

    dates = pd.to_datetime(data["service_date"], format="%Y%m%d")
    data["day_of_week"] = dates.dt.dayofweek
    data["month"] = dates.dt.month
    train = sample_by_date(data[data["service_date"] < split_date], MAX_TRAIN_ROWS)
    test = sample_by_date(data[data["service_date"] >= split_date], MAX_TEST_ROWS)
    data = pd.concat([train, test], ignore_index=True)
    if train.empty or test.empty:
        raise RuntimeError("Le chargement produit un train ou un test vide.")
    return data, split_date


def chronological_splits(data: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    """Construit trois validations expansives sans separer une meme date."""
    dates = sorted(data["service_date"].unique())
    if len(dates) < 10:
        raise RuntimeError("Il faut au moins dix dates pour la validation temporelle.")

    splits = []
    for train_ratio, validation_ratio in ((0.5, 0.67), (0.67, 0.83), (0.83, 1.0)):
        train_end = max(2, int(len(dates) * train_ratio))
        validation_end = min(len(dates), max(train_end + 1, int(len(dates) * validation_ratio)))
        train_dates = dates[:train_end]
        validation_dates = dates[train_end:validation_end]
        if not validation_dates:
            continue
        train_indices = np.flatnonzero(data["service_date"].isin(train_dates))
        validation_indices = np.flatnonzero(data["service_date"].isin(validation_dates))
        if len(train_indices) and len(validation_indices):
            splits.append((train_indices, validation_indices))
    if len(splits) != 3:
        raise RuntimeError("Impossible de construire trois fenetres temporelles completes.")
    return splits


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
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
) -> dict[str, object]:
    """Choisit les parametres en validation temporelle et mesure le holdout."""
    pipeline = Pipeline(
        [("preprocessor", make_preprocessor()), ("model", estimator)]
    )
    search = GridSearchCV(
        pipeline,
        {f"model__{key}": values for key, values in parameters.items()},
        scoring="neg_mean_absolute_error",
        cv=cv_splits,
        # Un seul processus evite de dupliquer les matrices en memoire sur la machine locale.
        n_jobs=1,
        refit=True,
    )
    search.fit(train[FEATURES], train["planned_departures"])
    predictions = np.maximum(search.predict(test[FEATURES]), 0)
    actual = test["planned_departures"]
    best_index = search.best_index_
    return {
        "name": name,
        "best_params": search.best_params_,
        "cv_mae": round(float(-search.best_score_), 4),
        "cv_fold_mae": [
            round(float(-search.cv_results_[f"split{index}_test_score"][best_index]), 4)
            for index in range(len(cv_splits))
        ],
        "test_mae": round(float(mean_absolute_error(actual, predictions)), 4),
        "test_rmse": round(float(mean_squared_error(actual, predictions) ** 0.5), 4),
        "test_r2": round(float(r2_score(actual, predictions)), 4),
    }


def score_predictions(actual: pd.Series, predictions: np.ndarray) -> dict[str, float | None]:
    """Calcule les indicateurs communs aux modeles et a la baseline."""
    return {
        "mae": round(float(mean_absolute_error(actual, predictions)), 4),
        "rmse": round(float(mean_squared_error(actual, predictions) ** 0.5), 4),
        "r2": round(float(r2_score(actual, predictions)), 4)
        if actual.nunique() > 1
        else None,
    }


def evaluate_baseline(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, float]:
    """Predit la moyenne historique de l'arret et de la periode horaire."""
    stop_period_means = train.groupby(["stop_id", "time_period"])[
        "planned_departures"
    ].mean()
    period_means = train.groupby("time_period")["planned_departures"].mean()
    fallback = float(train["planned_departures"].mean())
    keys = pd.MultiIndex.from_frame(test[["stop_id", "time_period"]])
    predictions = stop_period_means.reindex(keys).to_numpy()
    period_fallback = test["time_period"].map(period_means).to_numpy()
    predictions = np.where(pd.isna(predictions), period_fallback, predictions)
    predictions = np.where(pd.isna(predictions), fallback, predictions)
    return score_predictions(test["planned_departures"], predictions)


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
            "mitigation": f"Comparer le modele {selected_model} a une baseline sur des validations chronologiques, garder un holdout final intact, puis recalibrer a chaque nouveau feed.",
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
        data, split_date = load_data(connection)

    train = data[data["service_date"] < split_date].copy()
    test = data[data["service_date"] >= split_date].copy()
    cv_splits = chronological_splits(train)

    models = [
        evaluate_model(
            "random_forest",
            RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=1),
            {"n_estimators": [40, 60], "max_depth": [18]},
            train,
            test,
            cv_splits,
        ),
        evaluate_model(
            "hist_gradient_boosting",
            HistGradientBoostingRegressor(random_state=RANDOM_STATE),
            {"max_iter": [80, 120], "max_leaf_nodes": [15]},
            train,
            test,
            cv_splits,
        ),
    ]
    baseline_cv_folds = [
        evaluate_baseline(train.iloc[train_indices], train.iloc[validation_indices])["mae"]
        for train_indices, validation_indices in cv_splits
    ]
    baseline_cv_mae = round(float(np.mean(baseline_cv_folds)), 4)
    selection_scores = [(item["name"], item["cv_mae"]) for item in models]
    selection_scores.append(("historical_baseline", baseline_cv_mae))
    selected_model, selected_cv_mae = min(selection_scores, key=lambda item: item[1])
    selected_cv_folds = (
        baseline_cv_folds
        if selected_model == "historical_baseline"
        else next(item["cv_fold_mae"] for item in models if item["name"] == selected_model)
    )
    temporal_windows = []
    for window_number, (train_indices, validation_indices) in enumerate(cv_splits, start=1):
        validation = train.iloc[validation_indices]
        temporal_windows.append(
            {
                "window": window_number,
                "train_date_max": str(train.iloc[train_indices]["service_date"].max()),
                "validation_date_min": str(validation["service_date"].min()),
                "validation_date_max": str(validation["service_date"].max()),
                "validation_rows": int(len(validation)),
                "selected_model_mae": selected_cv_folds[window_number - 1],
            }
        )
    baseline = evaluate_baseline(train, test)
    result = {
        "grain": "stop_date_time_period",
        "target": "planned_departures",
        "features": FEATURES,
        "feature_policy": "Aucune variable agregee a partir des departs de la meme date n'est utilisee; stop_id ne sert qu'a la baseline historique.",
        "selection_rule": "Le meilleur candidat (deux modeles et baseline historique) est choisi sur la MAE moyenne des trois validations chronologiques; le holdout final ne participe pas a la selection.",
        "observation_count": int(len(data)),
        "train_rows_used": int(len(train)),
        "test_rows": int(len(test)),
        "train_date_count": int(train["service_date"].nunique()),
        "test_date_count": int(test["service_date"].nunique()),
        "date_min": str(data["service_date"].min()),
        "date_max": str(data["service_date"].max()),
        "split_date": split_date,
        "models": models,
        "selected_model": selected_model,
        "selected_cv_mae": selected_cv_mae,
        "baseline_cv": {
            "fold_mae": baseline_cv_folds,
            "mean_mae": baseline_cv_mae,
        },
        "baseline_holdout": {
            "name": "historical_mean_by_stop_and_period",
            **baseline,
        },
        "holdout_target_summary": {
            "minimum": float(test["planned_departures"].min()),
            "maximum": float(test["planned_departures"].max()),
            "mean": round(float(test["planned_departures"].mean()), 4),
            "unique_values": int(test["planned_departures"].nunique()),
            "value_counts": {
                str(value): int(count)
                for value, count in test["planned_departures"].value_counts().sort_index().items()
            },
        },
        "temporal_evaluation": {
            "method": "trois validations chronologiques expansives par date, puis un holdout final reserve a l'evaluation",
            "windows": temporal_windows,
            "holdout_date_min": str(test["service_date"].min()),
            "holdout_date_max": str(test["service_date"].max()),
        },
        "selection_justification": "Le candidat retenu minimise la MAE moyenne de validation parmi les deux modeles et la baseline historique. Les scores du holdout sont rapportes apres selection, sans ajustement ulterieur.",
        "risks": build_risk_assessment(selected_model),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Rapport ecrit dans {OUTPUT.name}")
    print(f"Candidat retenu: {selected_model} | MAE validation: {selected_cv_mae}")
    print(f"MAE baseline holdout: {baseline['mae']}")


if __name__ == "__main__":
    main()