"""Contrôles de qualité et nettoyage minimal du feed GTFS."""

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = ROOT / "data" / "raw" / "gtfs"
PROCESSED_DATA_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
PDL_BBOX = (46.0, 48.6, -2.4, 0.5)


def read_ids(filename: str, column: str) -> tuple[set[str], int]:
    """Charge les identifiants et compte les doublons de clé primaire."""
    values = set()
    duplicates = 0
    with (GTFS_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            value = (row.get(column) or "").strip()
            if value in values:
                duplicates += 1
            elif value:
                values.add(value)
    return values, duplicates


def parse_gtfs_time(value: str) -> int | None:
    """Convertit une heure GTFS en secondes depuis minuit, y compris au-delà de 24 h."""
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return None
    if minutes not in range(60) or seconds not in range(60) or hours < 0:
        return None
    return hours * 3600 + minutes * 60 + seconds


def load_trips() -> tuple[dict[str, dict[str, str]], int]:
    """Construit un index des trajets pour contrôler les références de stop_times."""
    trips = {}
    duplicates = 0
    with (GTFS_DIR / "trips.txt").open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            trip_id = (row.get("trip_id") or "").strip()
            if trip_id in trips:
                duplicates += 1
                continue
            trips[trip_id] = {
                "route_id": (row.get("route_id") or "").strip(),
                "service_id": (row.get("service_id") or "").strip(),
                "shape_id": (row.get("shape_id") or "").strip(),
            }
    return trips, duplicates


def clean_stops(stop_ids: set[str]) -> dict[str, int]:
    output = PROCESSED_DATA_DIR / "stops_clean.csv"
    counters = Counter()
    with (GTFS_DIR / "stops.txt").open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        with output.open("w", encoding="utf-8", newline="") as target:
            # Le statut conserve les arrêts hors emprise pour permettre l'analyse
            # des dessertes interrégionales au lieu de les supprimer.
            fields = ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "wheelchair_boarding", "coordinate_status"]
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                stop_id = (row.get("stop_id") or "").strip()
                try:
                    latitude = float(row["stop_lat"])
                    longitude = float(row["stop_lon"])
                    inside = PDL_BBOX[0] <= latitude <= PDL_BBOX[1] and PDL_BBOX[2] <= longitude <= PDL_BBOX[3]
                    status = "within_pdl_bbox" if inside else "outside_pdl_bbox"
                except (KeyError, TypeError, ValueError):
                    status = "invalid_coordinate"
                counters[status] += 1
                writer.writerow({
                    "stop_id": stop_id,
                    "stop_name": (row.get("stop_name") or "").strip(),
                    "stop_lat": (row.get("stop_lat") or "").strip(),
                    "stop_lon": (row.get("stop_lon") or "").strip(),
                    "location_type": (row.get("location_type") or "").strip(),
                    "wheelchair_boarding": (row.get("wheelchair_boarding") or "").strip(),
                    "coordinate_status": status,
                })
    counters["stop_ids_loaded"] = len(stop_ids)
    return dict(counters)


def clean_stop_times(
    stop_ids: set[str],
    trips: dict[str, dict[str, str]],
    route_ids: set[str],
    service_ids: set[str],
    shape_ids: set[str],
) -> dict[str, int]:
    output = PROCESSED_DATA_DIR / "stop_times_clean.csv"
    counters = Counter()
    previous_sequences = {}
    trip_stop_counts = Counter()
    trips_seen = set()
    fields = [
        "trip_id", "service_id", "route_id", "shape_id", "stop_id",
        "stop_sequence", "arrival_seconds", "departure_seconds",
        "pickup_type", "drop_off_type",
    ]
    with (GTFS_DIR / "stop_times.txt").open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        with output.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                counters["rows_read"] += 1
                trip_id = (row.get("trip_id") or "").strip()
                stop_id = (row.get("stop_id") or "").strip()
                trip = trips.get(trip_id)
                missing_reference = (
                    # Un passage n'est conservé que si son trajet et ses
                    # référentiels associés existent dans les tables contrôlées.
                    trip is None
                    or stop_id not in stop_ids
                    or trip["route_id"] not in route_ids
                    or trip["service_id"] not in service_ids
                    or (trip["shape_id"] and trip["shape_id"] not in shape_ids)
                )
                if missing_reference:
                    counters["rows_with_missing_reference"] += 1
                    continue

                arrival = parse_gtfs_time(row.get("arrival_time") or "")
                departure = parse_gtfs_time(row.get("departure_time") or "")
                try:
                    sequence = int(row.get("stop_sequence") or "")
                except ValueError:
                    sequence = None
                if arrival is None or departure is None or sequence is None:
                    counters["rows_with_invalid_time_or_sequence"] += 1
                    continue
                if arrival > departure:
                    counters["rows_with_arrival_after_departure"] += 1
                    continue
                previous = previous_sequences.get(trip_id)
                # Les séquences doivent progresser pour conserver l'ordre des arrêts.
                if previous is not None and sequence <= previous:
                    counters["rows_with_non_increasing_sequence"] += 1
                    continue

                previous_sequences[trip_id] = sequence
                trip_stop_counts[trip_id] += 1
                trips_seen.add(trip_id)
                writer.writerow({
                    "trip_id": trip_id,
                    "service_id": trip["service_id"],
                    "route_id": trip["route_id"],
                    "shape_id": trip["shape_id"],
                    "stop_id": stop_id,
                    "stop_sequence": sequence,
                    "arrival_seconds": arrival,
                    "departure_seconds": departure,
                    "pickup_type": (row.get("pickup_type") or "").strip(),
                    "drop_off_type": (row.get("drop_off_type") or "").strip(),
                })
                counters["rows_written"] += 1
    counters["trips_with_stop_times"] = len(trips_seen)
    counters["trips_with_fewer_than_two_stops"] = sum(
        trip_stop_counts[trip_id] < 2 for trip_id in trips
    )
    counters["trips_without_stop_times"] = len(set(trips) - trips_seen)
    return dict(counters)


def main() -> None:
    # Les identifiants de référence sont chargés avant le nettoyage des fichiers
    # volumineux afin d'effectuer les contrôles en mémoire pendant la lecture.
    route_ids, duplicate_routes = read_ids("routes.txt", "route_id")
    stop_ids, duplicate_stops = read_ids("stops.txt", "stop_id")
    service_ids, _ = read_ids("calendar_dates.txt", "service_id")
    shape_ids, _ = read_ids("shapes.txt", "shape_id")
    trips, duplicate_trips = load_trips()

    report = {
        "reference_counts": {
            "routes": len(route_ids),
            "stops": len(stop_ids),
            "services": len(service_ids),
            "shapes": len(shape_ids),
            "trips": len(trips),
        },
        "duplicate_primary_keys": {
            "routes": duplicate_routes,
            "stops": duplicate_stops,
            "trips": duplicate_trips,
        },
        "expected_repeated_identifiers": {
            "calendar_dates_service_id": "service_id repeats across dates by design",
            "shapes_shape_id": "shape_id repeats across geometry points by design",
        },
        "stops": clean_stops(stop_ids),
        "stop_times": clean_stop_times(stop_ids, trips, route_ids, service_ids, shape_ids),
        "rules": {
            # Ces règles rendent les choix de nettoyage explicites dans le rapport JSON.
            "coordinate_bbox": PDL_BBOX,
            "outside_coordinates_are_flagged_not_deleted": True,
            "gtfs_time_is_stored_as_seconds_after_midnight": True,
            "hours_over_24_are_accepted": True,
        },
        "interpretation": {
            "outside_pdl_bbox": "kept_for_interregional_service_review",
            "trip_with_fewer_than_two_stops": "reported_not_deleted",
        },
    }
    (REPORTS_DIR / "rapport_qualite_gtfs.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print("Rapport qualité écrit dans rapport_qualite_gtfs.json")
    print("Table arrêts écrite dans stops_clean.csv")
    print("Table passages écrite dans stop_times_clean.csv")


if __name__ == "__main__":
    main()