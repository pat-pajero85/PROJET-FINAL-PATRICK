# Étape 2 - Nettoyage et structuration en base relationnelle

## Choix de SQLite

SQLite est adapté à ce projet de formation : la base est un fichier local, sans serveur à administrer, et accepte les clés étrangères, contraintes, index, transactions et vues SQL. Le nettoyage et les transformations sont exécutés par `sql/03_schema_gtfs.sql`. Le script Python ne sert qu'à importer les CSV, car SQLite ne possède pas nativement de commande SQL portable pour lire directement un fichier CSV.

## Schéma retenu

Le modèle sépare les dimensions descriptives des faits de mobilité :

- `agency` décrit les opérateurs ;
- `route` décrit les lignes et référence `agency` ;
- `stop` décrit les arrêts et leurs coordonnées ;
- `service` décrit un service de circulation ;
- `service_date` relie un service à ses dates et conserve le type d'exception ;
- `shape` référence les géométries utilisées par les trajets ;
- `trip` décrit un trajet et référence une ligne, un service et éventuellement une géométrie ;
- `stop_time` est la table de faits : un passage d'un trajet à un arrêt ;
- `transfer` décrit les correspondances entre arrêts ;
- `weather_observation` contient l'enrichissement météo régional.

Les tables `stg_*` sont des tables de staging. Elles permettent de recharger les fichiers sans modifier la source et de réaliser le nettoyage par `INSERT ... SELECT` vers les tables finales.

## Pourquoi ce schéma est adapté ?

La normalisation évite de répéter le nom d'une ligne, d'un arrêt ou d'un opérateur sur des millions de passages. Une modification d'un arrêt se fait à un seul endroit et les clés étrangères empêchent les références orphelines. Les clés composites de `service_date` et `stop_time` représentent le grain réel des données : un service à une date, puis un passage à une séquence d'arrêt.

Cette structure respecte également les usages futurs :

- compter les départs par arrêt et par jour avec `v_departures_by_stop_day` ;
- comparer les lignes avec `v_departures_by_route_day` ;
- filtrer les modes via `route.route_type` ;
- joindre la météo par date et heure ;
- enrichir les arrêts avec OSM ou des données socio-économiques sans dupliquer les passages.

## Nettoyage SQL appliqué

- espaces vides convertis en `NULL` avec `NULLIF(TRIM(...), '')` ;
- horaires déjà normalisés en secondes depuis minuit ;
- horaires après `24:00:00` acceptés ;
- références inexistantes écartées lors des insertions finales ;
- coordonnées invalides exclues des dimensions finales, tandis que les arrêts hors emprise sont conservés avec `coordinate_status` ;
- contraintes `PRIMARY KEY`, `FOREIGN KEY`, `CHECK` et index ajoutées ;
- dates de service conservées avec leur `exception_type`.

## Exécution

```powershell
python .\src\03_charger_bdd_gtfs.py
```

La base produite est `data/database/gtfs_pays_loire.sqlite`. Les requêtes finales peuvent ensuite être exécutées directement dans SQLite :

```sql
SELECT * FROM v_departures_by_stop_day LIMIT 20;
SELECT * FROM v_departures_by_route_day LIMIT 20;
```