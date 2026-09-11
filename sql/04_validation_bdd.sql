PRAGMA foreign_keys = ON;

-- Controle global d'integrite : le resultat attendu est "ok"
PRAGMA integrity_check;

-- Controle generique des cles etrangeres : le resultat attendu est 0
SELECT COUNT(*) AS foreign_key_anomaly_count
FROM pragma_foreign_key_check;

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

-- Orphelins : chaque requete doit renvoyer 0
SELECT 'orphan_route_agency' AS check_name, COUNT(*) AS anomaly_count
FROM route AS r LEFT JOIN agency AS a ON a.agency_id = r.agency_id
WHERE a.agency_id IS NULL
UNION ALL
SELECT 'orphan_service_date_service', COUNT(*)
FROM service_date AS sd LEFT JOIN service AS s ON s.service_id = sd.service_id
WHERE s.service_id IS NULL
UNION ALL
SELECT 'orphan_trip_route', COUNT(*)
FROM trip AS t LEFT JOIN route AS r ON r.route_id = t.route_id
WHERE r.route_id IS NULL
UNION ALL
SELECT 'orphan_trip_service', COUNT(*)
FROM trip AS t LEFT JOIN service AS s ON s.service_id = t.service_id
WHERE s.service_id IS NULL
UNION ALL
SELECT 'orphan_trip_shape', COUNT(*)
FROM trip AS t LEFT JOIN shape AS sh ON sh.shape_id = t.shape_id
WHERE t.shape_id IS NOT NULL AND sh.shape_id IS NULL
UNION ALL
SELECT 'orphan_stop_time_trip', COUNT(*)
FROM stop_time AS st LEFT JOIN trip AS t ON t.trip_id = st.trip_id
WHERE t.trip_id IS NULL
UNION ALL
SELECT 'orphan_stop_time_stop', COUNT(*)
FROM stop_time AS st LEFT JOIN stop AS s ON s.stop_id = st.stop_id
WHERE s.stop_id IS NULL
UNION ALL
SELECT 'orphan_transfer_from_stop', COUNT(*)
FROM transfer AS tr LEFT JOIN stop AS s ON s.stop_id = tr.from_stop_id
WHERE s.stop_id IS NULL
UNION ALL
SELECT 'orphan_transfer_to_stop', COUNT(*)
FROM transfer AS tr LEFT JOIN stop AS s ON s.stop_id = tr.to_stop_id
WHERE s.stop_id IS NULL;

-- Indicateur metier : arrets les moins desservis sur les dates actives
SELECT service_date, stop_id, stop_name, planned_departures, route_count
FROM v_departures_by_stop_day
ORDER BY planned_departures ASC, service_date, stop_id
LIMIT 20;

-- Indicateur metier : lignes avec le plus de departs planifies
SELECT service_date, route_id, route_name, planned_departures, served_stop_count
FROM v_departures_by_route_day
ORDER BY planned_departures DESC, service_date, route_id
LIMIT 20;