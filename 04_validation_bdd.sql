PRAGMA foreign_keys = ON;

-- Volumes des tables finales
SELECT 'agency' AS table_name, COUNT(*) AS row_count FROM agency
UNION ALL SELECT 'route', COUNT(*) FROM route
UNION ALL SELECT 'stop', COUNT(*) FROM stop
UNION ALL SELECT 'service', COUNT(*) FROM service
UNION ALL SELECT 'service_date', COUNT(*) FROM service_date
UNION ALL SELECT 'shape', COUNT(*) FROM shape
UNION ALL SELECT 'trip', COUNT(*) FROM trip
UNION ALL SELECT 'stop_time', COUNT(*) FROM stop_time
UNION ALL SELECT 'transfer', COUNT(*) FROM transfer
UNION ALL SELECT 'weather_observation', COUNT(*) FROM weather_observation;

-- Orphelins : chaque requête doit renvoyer 0
SELECT 'orphan_trip_route' AS check_name, COUNT(*) AS anomaly_count
FROM trip AS t LEFT JOIN route AS r ON r.route_id = t.route_id
WHERE r.route_id IS NULL
UNION ALL
SELECT 'orphan_trip_service', COUNT(*)
FROM trip AS t LEFT JOIN service AS s ON s.service_id = t.service_id
WHERE s.service_id IS NULL
UNION ALL
SELECT 'orphan_stop_time_trip', COUNT(*)
FROM stop_time AS st LEFT JOIN trip AS t ON t.trip_id = st.trip_id
WHERE t.trip_id IS NULL
UNION ALL
SELECT 'orphan_stop_time_stop', COUNT(*)
FROM stop_time AS st LEFT JOIN stop AS s ON s.stop_id = st.stop_id
WHERE s.stop_id IS NULL;

-- Indicateur métier : arrêts les moins desservis sur les dates actives
SELECT service_date, stop_id, stop_name, planned_departures, route_count
FROM v_departures_by_stop_day
ORDER BY planned_departures ASC, service_date, stop_id
LIMIT 20;

-- Indicateur métier : lignes avec le plus de départs planifiés
SELECT service_date, route_id, route_name, planned_departures, served_stop_count
FROM v_departures_by_route_day
ORDER BY planned_departures DESC, service_date, route_id
LIMIT 20;