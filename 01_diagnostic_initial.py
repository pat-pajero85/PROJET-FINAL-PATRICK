"""Diagnostic initial du feed GTFS Destineo Pays de la Loire."""

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = ROOT / "data" / "raw" / "gtfs"
EXTERNAL_DATA_DIR = ROOT / "data" / "raw" / "external"
REPORTS_DIR = ROOT / "reports"
GTFS_FILES = [
    "agency.txt",
    "calendar_dates.txt",
    "feed_info.txt",
    "routes.txt",
    "shapes.txt",
    "stops.txt",
    "stop_times.txt",
    "transfers.txt",
    "trips.txt",
]


def inspect_table(path: Path) -> dict:
    row_count = 0
    blank_counts = Counter()
    unique_values = {"service_id": set(), "route_type": set()}
    coordinate_issues = Counter()
    min_date = None
    max_date = None

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []
        for row in reader:
            row_count += 1
            for column, value in row.items():
                if value is None or not value.strip():
                    blank_counts[column] += 1

            for column in unique_values:
                value = (row.get(column) or "").strip()
                if value:
                    unique_values[column].add(value)

            date = (row.get("date") or "").strip()
            if date:
                min_date = date if min_date is None or date < min_date else min_date
                max_date = date if max_date is None or date > max_date else max_date

            if path.name == "stops.txt":
                try:
                    latitude = float(row["stop_lat"])
                    longitude = float(row["stop_lon"])
                    if not 46.0 <= latitude <= 48.6:
                        coordinate_issues["latitude_outside_pdl_bbox"] += 1
                    if not -2.4 <= longitude <= 0.5:
                        coordinate_issues["longitude_outside_pdl_bbox"] += 1
                except (KeyError, TypeError, ValueError):
                    coordinate_issues["invalid_coordinate"] += 1

    result = {
        "rows": row_count,
        "columns": columns,
        "blank_counts": dict(blank_counts),
    }
    if unique_values["service_id"]:
        result["unique_service_id"] = len(unique_values["service_id"])
    if unique_values["route_type"]:
        result["unique_route_type"] = sorted(unique_values["route_type"])
    if min_date is not None:
        result["min_date"] = min_date
        result["max_date"] = max_date
    if coordinate_issues:
        result["coordinate_issues"] = dict(coordinate_issues)
    return result


def main() -> None:
    diagnostic = {
        filename: inspect_table(GTFS_DIR / filename)
        for filename in GTFS_FILES
    }

    weather_file = EXTERNAL_DATA_DIR / "open-meteo-47.42N0.74W45m.csv"
    with weather_file.open(encoding="utf-8-sig", newline="") as file:
        weather_reader = csv.DictReader(file)
        weather_location = next(weather_reader)
        weather_observations = sum(1 for row in weather_reader if row.get("time"))

    diagnostic["weather_source"] = {
        "latitude": float(weather_location["latitude"]),
        "longitude": float(weather_location["longitude"]),
        "timezone": weather_location["timezone"],
        "observation_count": weather_observations,
        "status": "regional_reference_point_one_day",
    }

    output = REPORTS_DIR / "diagnostic_initial.json"
    output.write_text(
        json.dumps(diagnostic, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(f"Diagnostic écrit dans {output.name}")


if __name__ == "__main__":
    main()