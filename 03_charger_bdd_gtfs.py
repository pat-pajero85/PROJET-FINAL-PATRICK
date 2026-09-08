"""Charge les CSV nettoyés puis exécute tout le traitement SQL."""

import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).parent
DATABASE = ROOT / "gtfs_pays_loire.sqlite"


FILES = {
    "stg_agency": ("agency.txt", None),
    "stg_routes": ("routes.txt", None),
    "stg_stops": ("stops_clean.csv", None),
    "stg_calendar_dates": ("calendar_dates.txt", None),
    "stg_trips": ("trips.txt", None),
    "stg_stop_times": ("stop_times_clean.csv", None),
    "stg_transfers": ("transfers.txt", None),
    "stg_weather": ("open-meteo-47.42N0.74W45m.csv", "weather"),
}


def insert_csv(connection: sqlite3.Connection, table: str, filename: str) -> None:
    path = ROOT / filename
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        batch = []
        for row in reader:
            batch.append([value if value != "" else None for value in row.values()])
            if len(batch) == 10_000:
                connection.executemany(sql, batch)
                batch.clear()
        if batch:
            connection.executemany(sql, batch)


def insert_shapes(connection: sqlite3.Connection) -> None:
    with (ROOT / "trips.txt").open(encoding="utf-8-sig", newline="") as source:
        rows = {(row.get("shape_id") or "").strip() for row in csv.DictReader(source)}
    connection.executemany(
        "INSERT INTO stg_shapes (shape_id) VALUES (?)",
        [(shape_id,) for shape_id in rows if shape_id],
    )


def insert_weather(connection: sqlite3.Connection) -> None:
    with (ROOT / FILES["stg_weather"][0]).open(encoding="utf-8-sig", newline="") as source:
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


def main() -> None:
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")
    schema = (ROOT / "03_schema_gtfs.sql").read_text(encoding="utf-8")
    staging_sql, transform_sql = schema.split("-- BEGIN_TRANSFORM", 1)
    connection.executescript(staging_sql.replace("BEGIN TRANSACTION;", ""))

    for table, (filename, special) in FILES.items():
        if special == "weather":
            insert_weather(connection)
        else:
            insert_csv(connection, table, filename)
    insert_shapes(connection)
    connection.executescript(
        ("-- BEGIN_TRANSFORM" + transform_sql).replace("COMMIT;", "")
    )
    connection.commit()
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
    connection.close()


if __name__ == "__main__":
    main()