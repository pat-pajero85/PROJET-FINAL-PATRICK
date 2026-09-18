"""Charge les CSV nettoyés puis exécute tout le traitement SQL."""

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = ROOT / "data" / "raw" / "gtfs"
EXTERNAL_DATA_DIR = ROOT / "data" / "raw" / "external"
PROCESSED_DATA_DIR = ROOT / "data" / "processed"
DATABASE = ROOT / "data" / "database" / "gtfs_pays_loire.sqlite"
VALIDATION_REPORT = ROOT / "reports" / "04_resultats_validation_bdd.json"
SCHEMA_FILE = ROOT / "sql" / "03_schema_gtfs.sql"


FILES = {
    "stg_agency": (GTFS_DIR / "agency.txt", None),
    "stg_routes": (GTFS_DIR / "routes.txt", None),
    "stg_stops": (PROCESSED_DATA_DIR / "stops_clean.csv", None),
    "stg_calendar_dates": (GTFS_DIR / "calendar_dates.txt", None),
    "stg_trips": (GTFS_DIR / "trips.txt", None),
    "stg_stop_times": (PROCESSED_DATA_DIR / "stop_times_clean.csv", None),
    "stg_transfers": (GTFS_DIR / "transfers.txt", None),
    "stg_weather": (EXTERNAL_DATA_DIR / "open-meteo-47.42N0.74W45m.csv", "weather"),
}


def insert_csv(connection: sqlite3.Connection, table: str, path: Path) -> None:
    """Insere un CSV dans une table de staging par lots pour limiter la memoire."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        batch = []
        for row in reader:
            batch.append([value if value != "" else None for value in row.values()])
            if len(batch) == 10_000:
            # executemany réduit le coût des écritures répétées sur les gros fichiers.
                connection.executemany(sql, batch)
                batch.clear()
        if batch:
            connection.executemany(sql, batch)


def insert_shapes(connection: sqlite3.Connection) -> None:
    """Charge les identifiants de formes derives du fichier trips."""
    with (GTFS_DIR / "trips.txt").open(encoding="utf-8-sig", newline="") as source:
        rows = {(row.get("shape_id") or "").strip() for row in csv.DictReader(source)}
    connection.executemany(
        "INSERT INTO stg_shapes (shape_id) VALUES (?)",
        [(shape_id,) for shape_id in rows if shape_id],
    )


def insert_weather(connection: sqlite3.Connection) -> None:
    """Extrait les metadonnees et observations du format CSV Open-Meteo."""
    with FILES["stg_weather"][0].open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.reader(source))
    metadata = dict(zip(rows[0], rows[1]))
    observation_header_index = next(index for index, row in enumerate(rows) if row and row[0] == "time")
    observation_reader = csv.DictReader(
        [",".join(row) for row in rows[observation_header_index:]]
    )
    observations = list(observation_reader)
    connection.executemany(
        "INSERT INTO stg_weather VALUES (?, ?, ?, ?, ?)",
        [
            (row["time"], row["temperature_2m (°C)"], metadata["latitude"], metadata["longitude"], metadata["timezone"])
            for row in observations
            if row.get("time")
        ],
    )


def build_validation_report(connection: sqlite3.Connection) -> dict:
    """Compare staging et tables finales et controle les references orphelines."""
    table_pairs = {
        "agency": "stg_agency",
        "route": "stg_routes",
        "stop": "stg_stops",
        "service_date": "stg_calendar_dates",
        "trip": "stg_trips",
        "stop_time": "stg_stop_times",
        "transfer": "stg_transfers",
        "weather_observation": "stg_weather",
    }
    counts = {}
    for final_table, staging_table in table_pairs.items():
        counts[final_table] = {
            "staging": connection.execute(
                f"SELECT COUNT(*) FROM {staging_table}"
            ).fetchone()[0],
            "final": connection.execute(
                f"SELECT COUNT(*) FROM {final_table}"
            ).fetchone()[0],
        }

    # Chaque contrôle recherche une clé étrangère présente dans la table enfant
    # mais absente de la table parent.
    orphan_checks = connection.execute(
        "SELECT 'orphan_route_agency', COUNT(*) FROM route AS r "
        "LEFT JOIN agency AS a ON a.agency_id = r.agency_id "
        "WHERE a.agency_id IS NULL UNION ALL "
        "SELECT 'orphan_trip_route', COUNT(*) FROM trip AS t "
        "LEFT JOIN route AS r ON r.route_id = t.route_id "
        "WHERE r.route_id IS NULL UNION ALL "
        "SELECT 'orphan_trip_service', COUNT(*) FROM trip AS t "
        "LEFT JOIN service AS s ON s.service_id = t.service_id "
        "WHERE s.service_id IS NULL UNION ALL "
        "SELECT 'orphan_stop_time_trip', COUNT(*) FROM stop_time AS st "
        "LEFT JOIN trip AS t ON t.trip_id = st.trip_id "
        "WHERE t.trip_id IS NULL UNION ALL "
        "SELECT 'orphan_stop_time_stop', COUNT(*) FROM stop_time AS st "
        "LEFT JOIN stop AS s ON s.stop_id = st.stop_id "
        "WHERE s.stop_id IS NULL UNION ALL "
        "SELECT 'orphan_transfer_from_stop', COUNT(*) FROM transfer AS tr "
        "LEFT JOIN stop AS s ON s.stop_id = tr.from_stop_id "
        "WHERE s.stop_id IS NULL UNION ALL "
        "SELECT 'orphan_transfer_to_stop', COUNT(*) FROM transfer AS tr "
        "LEFT JOIN stop AS s ON s.stop_id = tr.to_stop_id "
        "WHERE s.stop_id IS NULL"
    ).fetchall()
    active_weather_dates = connection.execute(
        "SELECT COUNT(DISTINCT substr(observed_at, 1, 10)) "
        "FROM weather_observation AS w "
        "WHERE EXISTS (SELECT 1 FROM service_date AS sd "
        "WHERE sd.service_date = replace(substr(w.observed_at, 1, 10), '-', '') "
        "AND sd.exception_type = 1)"
    ).fetchone()[0]
    return {
        "integrity_check": connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0],
        "foreign_key_anomaly_count": connection.execute(
            "SELECT COUNT(*) FROM pragma_foreign_key_check"
        ).fetchone()[0],
        "orphan_checks": dict(orphan_checks),
        "counts": counts,
        "service_date_exception_types": dict(connection.execute(
            "SELECT exception_type, COUNT(*) FROM service_date "
            "GROUP BY exception_type"
        ).fetchall()),
        "weather_active_service_dates": active_weather_dates,
        "analytical_views": {
            "departures_by_stop_day": connection.execute(
                "SELECT COUNT(*) FROM v_departures_by_stop_day"
            ).fetchone()[0],
            "departures_by_stop_period": connection.execute(
                "SELECT COUNT(*) FROM v_departures_by_stop_period"
            ).fetchone()[0],
            "departures_by_route_day": connection.execute(
                "SELECT COUNT(*) FROM v_departures_by_route_day"
            ).fetchone()[0],
        },
    }


def main() -> None:
    # Les fichiers sont d'abord chargés en staging, puis le SQL applique les
    # nettoyages, contraintes et transformations du schéma final.
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    staging_sql, transform_sql = schema.split("-- BEGIN_TRANSFORM", 1)
    connection.executescript(staging_sql.replace("BEGIN TRANSACTION;", ""))

    for table, (filename, special) in FILES.items():
        if special == "weather":
            insert_weather(connection)
        else:
            insert_csv(connection, table, filename)
    insert_shapes(connection)
    # La seconde partie du schéma transforme les staging tables en tables métier.
    connection.executescript(
        ("-- BEGIN_TRANSFORM" + transform_sql).replace("COMMIT;", "")
    )
    connection.commit()
    VALIDATION_REPORT.write_text(
        json.dumps(build_validation_report(connection), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(f"Base SQLite créée : {DATABASE.name}")
    for table in ["agency", "route", "stop", "service", "trip", "stop_time", "transfer", "weather_observation"]:
        count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count:,} lignes")
    print(
        "Validation: orphelins trip-route =",
        connection.execute(
            "SELECT COUNT(*) FROM trip AS t "
            "LEFT JOIN route AS r ON r.route_id = t.route_id "
            "WHERE r.route_id IS NULL"
        ).fetchone()[0],
    )
    print(
        "Validation: orphelins stop_time-stop =",
        connection.execute(
            "SELECT COUNT(*) FROM stop_time AS st "
            "LEFT JOIN stop AS s ON s.stop_id = st.stop_id "
            "WHERE s.stop_id IS NULL"
        ).fetchone()[0],
    )
    print(
        "Vue departures_by_stop_day:",
        connection.execute("SELECT COUNT(*) FROM v_departures_by_stop_day").fetchone()[0],
        "lignes",
    )
    print(f"Rapport de validation écrit : {VALIDATION_REPORT.name}")
    connection.close()


if __name__ == "__main__":
    main()