from importlib import import_module

import pandas as pd


model = import_module("src.07_modelisation_risques")


def test_features_exclude_fields_derived_from_target_aggregation() -> None:
    excluded = {"route_count", "first_departure_hours", "last_departure_hours"}

    assert excluded.isdisjoint(model.FEATURES)
    assert "stop_id" not in model.FEATURES


def test_chronological_splits_keep_each_date_in_one_side() -> None:
    data = pd.DataFrame(
        {
            "service_date": [f"202501{day:02d}" for day in range(1, 21)],
            "planned_departures": range(1, 21),
        }
    )

    splits = model.chronological_splits(data)

    assert len(splits) == 3
    for train_indices, validation_indices in splits:
        train_dates = data.iloc[train_indices]["service_date"]
        validation_dates = data.iloc[validation_indices]["service_date"]
        assert train_dates.max() < validation_dates.min()


def test_sample_by_date_is_reproducible_and_preserves_date_coverage() -> None:
    data = pd.DataFrame(
        [
            {"service_date": f"202501{day:02d}", "stop_id": str(stop_id)}
            for day in range(1, 5)
            for stop_id in range(10)
        ]
    )

    first = model.sample_by_date(data, max_rows=8)
    second = model.sample_by_date(data, max_rows=8)

    assert len(first) == 8
    assert first.equals(second)
    assert first["service_date"].nunique() == 4


def test_r2_is_undefined_for_a_constant_holdout_target() -> None:
    actual = pd.Series([1, 1, 1])
    predictions = [0.8, 1.0, 1.2]

    scores = model.score_predictions(actual, predictions)

    assert scores["r2"] is None