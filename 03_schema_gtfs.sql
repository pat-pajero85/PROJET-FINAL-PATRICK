PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

DROP VIEW IF EXISTS v_departures_by_stop_day;
DROP VIEW IF EXISTS v_departures_by_route_day;
DROP TABLE IF EXISTS weather_observation;
DROP TABLE IF EXISTS transfer;
DROP TABLE IF EXISTS stop_time;
DROP TABLE IF EXISTS trip;
DROP TABLE IF EXISTS service_date;
DROP TABLE IF EXISTS service;
DROP TABLE IF EXISTS shape;
DROP TABLE IF EXISTS stop;
DROP TABLE IF EXISTS route;
DROP TABLE IF EXISTS agency;
DROP TABLE IF EXISTS stg_weather;
DROP TABLE IF EXISTS stg_transfers;
DROP TABLE IF EXISTS stg_stop_times;
DROP TABLE IF EXISTS stg_trips;
DROP TABLE IF EXISTS stg_shapes;
DROP TABLE IF EXISTS stg_stops;
DROP TABLE IF EXISTS stg_routes;
DROP TABLE IF EXISTS stg_calendar_dates;
DROP TABLE IF EXISTS stg_agency;

CREATE TABLE stg_agency (
    agency_id TEXT,
    agency_name TEXT,
    agency_url TEXT,
    agency_timezone TEXT,
    agency_lang TEXT,
    agency_phone TEXT,
    agency_fare_url TEXT,
    agency_email TEXT
);

CREATE TABLE stg_routes (
    route_id TEXT,
    agency_id TEXT,
    route_short_name TEXT,
    route_long_name TEXT,
    route_desc TEXT,
    route_type INTEGER,
    route_url TEXT,
    route_color TEXT,
    route_text_color TEXT
);

CREATE TABLE stg_stops (
    stop_id TEXT,
    stop_name TEXT,
    stop_lat REAL,
    stop_lon REAL,
    location_type INTEGER,
    wheelchair_boarding INTEGER,
    coordinate_status TEXT
);

CREATE TABLE stg_calendar_dates (
    service_id TEXT,
    date TEXT,
    exception_type INTEGER
);

CREATE TABLE stg_shapes (shape_id TEXT);

CREATE TABLE stg_trips (
    route_id TEXT,
    service_id TEXT,
    trip_id TEXT,
    trip_headsign TEXT,
    trip_short_name TEXT,
    direction_id INTEGER,
    block_id TEXT,
    wheelchair_accessible INTEGER,
    bikes_allowed INTEGER,
    shape_id TEXT
);

CREATE TABLE stg_stop_times (
    trip_id TEXT,
    service_id TEXT,
    route_id TEXT,
    shape_id TEXT,
    stop_id TEXT,
    stop_sequence INTEGER,
    arrival_seconds INTEGER,
    departure_seconds INTEGER,
    pickup_type INTEGER,
    drop_off_type INTEGER
);

CREATE TABLE stg_transfers (
    from_stop_id TEXT,
    to_stop_id TEXT,
    transfer_type INTEGER,
    min_transfer_time INTEGER
);

CREATE TABLE stg_weather (
    observed_at TEXT,
    temperature_c REAL,
    latitude REAL,
    longitude REAL,
    timezone TEXT
);

-- BEGIN_FINAL_SCHEMA
CREATE TABLE agency (
    agency_id TEXT PRIMARY KEY,
    agency_name TEXT NOT NULL,
    agency_url TEXT,
    agency_timezone TEXT NOT NULL,
    agency_lang TEXT,
    agency_phone TEXT,
    agency_fare_url TEXT,
    agency_email TEXT
);

CREATE TABLE route (
    route_id TEXT PRIMARY KEY,
    agency_id TEXT NOT NULL REFERENCES agency(agency_id),
    route_short_name TEXT,
    route_long_name TEXT NOT NULL,
    route_desc TEXT,
    route_type INTEGER NOT NULL CHECK (route_type IN (0, 2, 3, 4)),
    route_url TEXT,
    route_color TEXT,
    route_text_color TEXT
);

CREATE TABLE stop (
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT NOT NULL,
        stop_lat REAL NOT NULL CHECK (stop_lat BETWEEN -90 AND 90),
        stop_lon REAL NOT NULL CHECK (stop_lon BETWEEN -180 AND 180),
        location_type INTEGER NOT NULL DEFAULT 0 CHECK (location_type IN (0, 1, 2, 3, 4)),
        wheelchair_boarding INTEGER CHECK (wheelchair_boarding IN (0, 1, 2)),
        coordinate_status TEXT NOT NULL CHECK (coordinate_status IN ('within_pdl_bbox', 'outside_pdl_bbox', 'invalid_coordinate'))
);

CREATE TABLE service (
        service_id TEXT PRIMARY KEY
);

CREATE TABLE service_date (
        service_id TEXT NOT NULL REFERENCES service(service_id),
        service_date TEXT NOT NULL CHECK (
                service_date GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
                AND date(substr(service_date, 1, 4) || '-' || substr(service_date, 5, 2) || '-' || substr(service_date, 7, 2)) IS NOT NULL
        ),
        exception_type INTEGER NOT NULL CHECK (exception_type IN (1, 2)),
        PRIMARY KEY (service_id, service_date)
);

CREATE TABLE shape (
        shape_id TEXT PRIMARY KEY
);

CREATE TABLE trip (
        trip_id TEXT PRIMARY KEY,
        route_id TEXT NOT NULL REFERENCES route(route_id),
        service_id TEXT NOT NULL REFERENCES service(service_id),
        trip_headsign TEXT,
        trip_short_name TEXT,
        direction_id INTEGER CHECK (direction_id IN (0, 1)),
        block_id TEXT,
        wheelchair_accessible INTEGER CHECK (wheelchair_accessible IN (0, 1, 2)),
        bikes_allowed INTEGER CHECK (bikes_allowed IN (0, 1, 2)),
        shape_id TEXT REFERENCES shape(shape_id)
);

CREATE TABLE stop_time (
        trip_id TEXT NOT NULL REFERENCES trip(trip_id),
        stop_id TEXT NOT NULL REFERENCES stop(stop_id),
        stop_sequence INTEGER NOT NULL CHECK (stop_sequence > 0),
        arrival_seconds INTEGER NOT NULL CHECK (arrival_seconds >= 0),
        departure_seconds INTEGER NOT NULL CHECK (departure_seconds >= arrival_seconds),
        pickup_type INTEGER CHECK (pickup_type IN (0, 1, 2, 3)),
        drop_off_type INTEGER CHECK (drop_off_type IN (0, 1, 2, 3)),
        PRIMARY KEY (trip_id, stop_sequence)
);

CREATE TABLE transfer (
        from_stop_id TEXT NOT NULL REFERENCES stop(stop_id),
        to_stop_id TEXT NOT NULL REFERENCES stop(stop_id),
        transfer_type INTEGER NOT NULL CHECK (transfer_type IN (0, 1, 2, 3)),
        min_transfer_time INTEGER CHECK (min_transfer_time >= 0),
        PRIMARY KEY (from_stop_id, to_stop_id, transfer_type)
);

CREATE TABLE weather_observation (
        observed_at TEXT PRIMARY KEY,
        temperature_c REAL NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        timezone TEXT NOT NULL
);

-- BEGIN_TRANSFORM
INSERT INTO agency
SELECT DISTINCT NULLIF(TRIM(agency_id), ''), NULLIF(TRIM(agency_name), ''), NULLIF(TRIM(agency_url), ''),
             NULLIF(TRIM(agency_timezone), ''), NULLIF(TRIM(agency_lang), ''), NULLIF(TRIM(agency_phone), ''),
             NULLIF(TRIM(agency_fare_url), ''), NULLIF(TRIM(agency_email), '')
FROM stg_agency
WHERE NULLIF(TRIM(agency_id), '') IS NOT NULL
    AND NULLIF(TRIM(agency_name), '') IS NOT NULL
    AND NULLIF(TRIM(agency_timezone), '') IS NOT NULL;

INSERT INTO route
SELECT DISTINCT NULLIF(TRIM(route_id), ''), NULLIF(TRIM(agency_id), ''), NULLIF(TRIM(route_short_name), ''),
             NULLIF(TRIM(route_long_name), ''), NULLIF(TRIM(route_desc), ''), route_type,
             NULLIF(TRIM(route_url), ''), NULLIF(TRIM(route_color), ''), NULLIF(TRIM(route_text_color), '')
FROM stg_routes
WHERE NULLIF(TRIM(route_id), '') IS NOT NULL
    AND NULLIF(TRIM(route_long_name), '') IS NOT NULL
    AND NULLIF(TRIM(agency_id), '') IN (SELECT agency_id FROM agency);

INSERT INTO stop
SELECT DISTINCT NULLIF(TRIM(stop_id), ''), NULLIF(TRIM(stop_name), ''), stop_lat, stop_lon,
             COALESCE(location_type, 0), wheelchair_boarding, coordinate_status
FROM stg_stops
WHERE NULLIF(TRIM(stop_id), '') IS NOT NULL
    AND stop_lat IS NOT NULL AND stop_lon IS NOT NULL
    AND coordinate_status IN ('within_pdl_bbox', 'outside_pdl_bbox');

INSERT INTO service
SELECT DISTINCT NULLIF(TRIM(service_id), '')
FROM stg_calendar_dates
WHERE NULLIF(TRIM(service_id), '') IS NOT NULL;

INSERT INTO service_date
SELECT DISTINCT service_id, date, exception_type
FROM stg_calendar_dates
WHERE service_id IN (SELECT service_id FROM service)
    AND date GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]';

INSERT INTO shape
SELECT DISTINCT NULLIF(TRIM(shape_id), '')
FROM stg_shapes
WHERE NULLIF(TRIM(shape_id), '') IS NOT NULL;

INSERT INTO trip
SELECT DISTINCT trip_id, route_id, service_id, NULLIF(TRIM(trip_headsign), ''),
             NULLIF(TRIM(trip_short_name), ''), direction_id, NULLIF(TRIM(block_id), ''),
             wheelchair_accessible, bikes_allowed, NULLIF(TRIM(shape_id), '')
FROM stg_trips
WHERE trip_id IS NOT NULL
    AND route_id IN (SELECT route_id FROM route)
    AND service_id IN (SELECT service_id FROM service);

INSERT INTO stop_time
SELECT DISTINCT trip_id, stop_id, stop_sequence, arrival_seconds, departure_seconds,
             pickup_type, drop_off_type
FROM stg_stop_times
WHERE trip_id IN (SELECT trip_id FROM trip)
    AND stop_id IN (SELECT stop_id FROM stop)
    AND arrival_seconds IS NOT NULL
    AND departure_seconds IS NOT NULL
    AND departure_seconds >= arrival_seconds
    AND stop_sequence > 0;

INSERT INTO transfer
SELECT DISTINCT from_stop_id, to_stop_id, transfer_type, min_transfer_time
FROM stg_transfers
WHERE from_stop_id IN (SELECT stop_id FROM stop)
    AND to_stop_id IN (SELECT stop_id FROM stop);

INSERT INTO weather_observation
SELECT DISTINCT observed_at, temperature_c, latitude, longitude, timezone
FROM stg_weather
WHERE observed_at IS NOT NULL;

CREATE INDEX idx_route_agency ON route(agency_id);
CREATE INDEX idx_stop_time_stop ON stop_time(stop_id);
CREATE INDEX idx_stop_time_trip ON stop_time(trip_id);
CREATE INDEX idx_trip_route ON trip(route_id);
CREATE INDEX idx_trip_service ON trip(service_id);
CREATE INDEX idx_service_date_date ON service_date(service_date);
CREATE INDEX idx_transfer_to_stop ON transfer(to_stop_id);

CREATE VIEW v_departures_by_stop_day AS
SELECT sd.service_date,
       st.stop_id,
       s.stop_name,
       COUNT(*) AS planned_departures,
       COUNT(DISTINCT t.route_id) AS route_count,
       MIN(st.departure_seconds) AS first_departure_seconds,
       MAX(st.departure_seconds) AS last_departure_seconds
FROM service_date AS sd
JOIN trip AS t ON t.service_id = sd.service_id
JOIN stop_time AS st ON st.trip_id = t.trip_id
JOIN stop AS s ON s.stop_id = st.stop_id
WHERE sd.exception_type = 1
GROUP BY sd.service_date, st.stop_id, s.stop_name;

CREATE VIEW v_departures_by_route_day AS
SELECT sd.service_date,
       r.route_id,
       COALESCE(r.route_short_name, r.route_long_name) AS route_name,
       COUNT(*) AS planned_departures,
       COUNT(DISTINCT t.trip_id) AS trip_count,
       COUNT(DISTINCT st.stop_id) AS served_stop_count
FROM service_date AS sd
JOIN trip AS t ON t.service_id = sd.service_id
JOIN route AS r ON r.route_id = t.route_id
JOIN stop_time AS st ON st.trip_id = t.trip_id
WHERE sd.exception_type = 1
GROUP BY sd.service_date, r.route_id, route_name;

COMMIT;