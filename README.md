# Analyse et prédiction de la mobilité dans le Pays de la Loire

Projet final de formation Data Analyst consacré à l'analyse de l'offre de transport collectif dans les Pays de la Loire.

## Problématique métier

**Comment identifier les secteurs et créneaux où l'offre théorique de transport collectif est la plus faible, puis prédire le niveau d'offre attendu afin d'aider à prioriser les ajustements de desserte ?**

Le projet commence par l'analyse de l'offre planifiée : nombre de départs par arrêt, ligne, date, mode et période horaire. La prédiction portera d'abord sur le nombre de départs attendus ou sur une classe de niveau d'offre.

## Vue d'ensemble du parcours

Le projet suit une chaîne complète, de l'audit des fichiers GTFS à la
consultation par API et à l'évaluation d'un modèle prédictif :

1. cadrer la question métier et diagnostiquer les fichiers sources ;
2. contrôler, nettoyer et charger les données dans SQLite ;
3. exposer la base et les indicateurs avec une API FastAPI ;
4. analyser les tendances de l'offre et produire les visualisations ;
5. construire une baseline temporelle et repérer les situations de faible offre ;
6. comparer deux modèles et mesurer leur stabilité sur plusieurs périodes futures.

Le périmètre prédictif porte sur l'offre planifiée GTFS. Il ne s'agit pas d'une
prédiction de fréquentation ou de demande réelle.

## Données

La source principale est un export GTFS publié par DESTINEO :

- `routes.txt` : lignes et modes de transport ;
- `trips.txt` : trajets planifiés ;
- `stop_times.txt` : horaires de passage ;
- `stops.txt` : arrêts et coordonnées ;
- `calendar_dates.txt` : dates de circulation ;
- `shapes.txt` : géométries des itinéraires ;
- `transfers.txt` : correspondances ;
- `agency.txt` et `feed_info.txt` : métadonnées du feed.

Une série météo Open-Meteo est disponible dans [data/raw/external/open-meteo-47.42N0.74W45m.csv](data/raw/external/open-meteo-47.42N0.74W45m.csv). Elle correspond à une maille située au centre régional : `47.41652, -0.7377014`, fuseau `Europe/Paris`.

Le fichier OSM `.pbf` est conservé localement pour un enrichissement géographique ultérieur.

## État d'avancement

### Étape 1 : cadrage, collecte et diagnostic

Cette étape est finalisée :

- problématique métier et indicateur cible définis ;
- processus de collecte documenté ;
- source météo remplacée par une source localisée en Pays de la Loire ;
- diagnostic initial exécuté ;
- contrôles des clés et nettoyage minimal réalisés ;
- limites métier et techniques documentées.

### Étape 2 : nettoyage et structuration relationnelle

Cette étape est également réalisée avec SQLite :

- tables de staging conservant les données importées ;
- schéma relationnel normalisé avec clés primaires, clés étrangères et contraintes ;
- nettoyage final exécuté par `INSERT ... SELECT` en SQL ;
- index et vues analytiques pour les départs par arrêt et par ligne ;
- base locale `gtfs_pays_loire.sqlite` construite et contrôlée.

La base validée contient 14 agences, 1 029 lignes, 20 170 arrêts, 6 090 services, 182 725 trajets, 4 000 625 passages, 22 286 correspondances et 24 observations météo. Les contrôles d'orphelins entre trajets, lignes, passages et arrêts renvoient zéro anomalie.

### Étape 3 : API locale

L'API FastAPI expose les arrêts en CRUD, les référentiels lignes/agences et les
indicateurs de départs. Les entrées sont validées par Pydantic, les requêtes
SQL sont paramétrées et les écritures peuvent être protégées par `GTFS_API_KEY`.
Les tests utilisent une copie temporaire de la base pour ne pas modifier la
référence.

### Étape 4 : analyse exploratoire et veille

Trois hypothèses sont testées sur `v_departures_by_stop_period` :

- l'offre varie selon la période horaire ;
- elle est plus importante les jours ouvrés que le week-end ;
- le nombre de lignes desservantes est positivement associé aux départs.

Les résultats confirment H1 et H2. H3 est partiellement confirmée, avec une
corrélation positive modérée : Pearson `0,4036` et Spearman `0,4319`.
Les tableaux et graphiques sont produits dans `reports/`.

### Étape 5 : baseline et analyse de l'offre

Le script `src/05_analyse_offre.py` travaille au grain arrêt-date-période,
identifie les niveaux moyens d'offre les plus faibles et évalue une baseline
fondée sur la moyenne historique par arrêt et période. Sur `588` observations
de test, cette baseline obtient une MAE de `0,7059` et une RMSE de `0,7069`.

### Étape 6 : modélisation et risques

Le script `src/07_modelisation_risques.py` compare un
`RandomForestRegressor` et un `HistGradientBoostingRegressor`. La cible est
`planned_departures`, avec une séparation temporelle entre l'entraînement et
les dates futures. Le Random Forest est retenu dans l'exécution actuelle.

Une évaluation complémentaire utilise trois fenêtres temporelles futures et
compare le modèle à une baseline par moyenne de période horaire. Les résultats
détaillés, les métriques et les risques de données, de modèle, de déploiement
et d'éthique sont enregistrés dans
`reports/etape6_modeles_risques.json`.

### Résultats du diagnostic

- 1 029 lignes ;
- 182 725 trajets ;
- 20 170 arrêts ;
- 4 000 625 passages ;
- 899 601 points de géométrie ;
- aucune clé primaire dupliquée dans `routes`, `stops` et `trips` ;
- 4 000 625 passages conservés après contrôle ;
- 11 862 arrêts dans l'emprise indicative des Pays de la Loire ;
- 8 308 arrêts signalés hors emprise et conservés pour analyse métier.

## Organisation du projet

- [src](src) : scripts Python de diagnostic, nettoyage, chargement SQLite et analyse ;
- [data/raw/gtfs](data/raw/gtfs) : export GTFS source inchangé ;
- [data/raw/external](data/raw/external) : fichiers météo et OSM ;
- [data/processed](data/processed) : fichiers GTFS nettoyés ;
- [data/database](data/database) : bases SQLite locales ;
- [sql](sql) : schéma relationnel et requêtes de validation ;
- [reports](reports) : résultats JSON et journaux d'exécution ;
- [docs](docs) : cadrage, méthode et documentation du schéma.
- [docs/05_jalon_api_fonctionnelle.md](docs/05_jalon_api_fonctionnelle.md) : validation du jalon API fonctionnelle.
- [docs/06_rapport_checkup_etape_3.md](docs/06_rapport_checkup_etape_3.md) : rapport complet de contrôle de l'étape 3.
- [docs/07_analyse_exploratoire_et_veille.md](docs/07_analyse_exploratoire_et_veille.md) : résultats de l'étape 4 et sources de veille.
- [docs/08_rapport_checkup_etape_4.md](docs/08_rapport_checkup_etape_4.md) : contrôle qualité de l'étape 4.
- [api](api) : API FastAPI locale de consultation et de gestion.
- [tests](tests) : tests automatisés des endpoints de l'API.

## Reproduire les contrôles

Depuis la racine du projet :

```powershell
python .\src\01_diagnostic_initial.py
python .\src\02_controle_nettoyage_gtfs.py
python .\src\03_charger_bdd_gtfs.py
python .\src\05_analyse_offre.py
python .\src\06_analyse_exploratoire.py
python .\src\07_modelisation_risques.py
```

Avec l'environnement fourni, utiliser de préférence :

```powershell
.\mon_env\Scripts\python.exe .\src\01_diagnostic_initial.py
.\mon_env\Scripts\python.exe .\src\02_controle_nettoyage_gtfs.py
.\mon_env\Scripts\python.exe .\src\03_charger_bdd_gtfs.py
.\mon_env\Scripts\python.exe .\src\05_analyse_offre.py
.\mon_env\Scripts\python.exe .\src\06_analyse_exploratoire.py
.\mon_env\Scripts\python.exe .\src\07_modelisation_risques.py
```

Pour les scripts utilisant pandas, matplotlib ou scikit-learn sur une machine
à mémoire limitée, limiter les threads numériques avant l'exécution :

```powershell
$env:OPENBLAS_NUM_THREADS="1"
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
```

Les scripts utilisent uniquement la bibliothèque standard Python pour les contrôles actuels. Les dépendances de l'environnement sont listées dans [requirements.txt](requirements.txt).

Le traitement de nettoyage et de structuration est réalisé en SQL dans [sql/03_schema_gtfs.sql](sql/03_schema_gtfs.sql). Python sert uniquement de passerelle d'import des fichiers CSV, SQLite ne disposant pas d'une commande CSV portable native.

## Étape 3 : API locale FastAPI

L'API expose la base SQLite et les indicateurs d'offre sans dépendre d'une plateforme cloud. Elle est construite avec FastAPI, Pydantic et Uvicorn.

**Statut du jalon : validé pour démonstration et soutenance.** La checklist est disponible dans [docs/05_jalon_api_fonctionnelle.md](docs/05_jalon_api_fonctionnelle.md) et le contrôle détaillé dans [docs/06_rapport_checkup_etape_3.md](docs/06_rapport_checkup_etape_3.md).

### Lancer l'API

Depuis la racine du projet :

```powershell
.\mon_env\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 4000
```

Les URLs utiles sont alors :

- API : [http://127.0.0.1:4000](http://127.0.0.1:4000) ;
- documentation interactive Swagger : [http://127.0.0.1:4000/docs](http://127.0.0.1:4000/docs) ;
- schéma OpenAPI : [http://127.0.0.1:4000/openapi.json](http://127.0.0.1:4000/openapi.json) ;
- état de santé : [http://127.0.0.1:4000/health](http://127.0.0.1:4000/health).

### Routes disponibles

Les arrêts sont la ressource exposée en CRUD complet :

| Méthode | Endpoint                  | Fonction                           |
| ------- | ------------------------- | ---------------------------------- |
| GET     | `/api/v1/stops`           | Lister et filtrer les arrêts       |
| GET     | `/api/v1/stops/{stop_id}` | Consulter un arrêt précis          |
| POST    | `/api/v1/stops`           | Créer un arrêt validé par Pydantic |
| PUT     | `/api/v1/stops/{stop_id}` | Remplacer un arrêt                 |
| PATCH   | `/api/v1/stops/{stop_id}` | Modifier certains champs           |
| DELETE  | `/api/v1/stops/{stop_id}` | Supprimer un arrêt non référencé   |

Les référentiels GTFS et les indicateurs sont disponibles en lecture seule :

- `GET /api/v1/routes` : lignes de transport ;
- `GET /api/v1/agencies` : opérateurs ;
- `GET /api/v1/analytics/departures-by-stop-day` : départs planifiés par arrêt et par jour.

Les paramètres de chemin et de requête sont validés par FastAPI. Les corps JSON sont contrôlés avec Pydantic. Les requêtes SQL sont paramétrées et les mutations peuvent être protégées par la variable d'environnement `GTFS_API_KEY` envoyée dans l'en-tête `X-API-Key`.

La documentation détaillée et les exemples Python avec `requests` sont disponibles dans [docs/04_api.md](docs/04_api.md).

### Tester l'API

Les tests utilisent `FastAPI TestClient` et une copie temporaire de la base SQLite. Ils couvrent les endpoints système, les référentiels, la validation des paramètres, le CRUD des arrêts et la protection par clé API, sans modifier la base de référence.

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q
```

Résultat de référence : **8 tests réussis**. Les tests utilisent une copie temporaire de la base et ne modifient pas les données de référence.

## Parcours de vérification recommandé

1. Vérifier la présence de `data/raw/gtfs`, des fichiers nettoyés et de la base SQLite.
2. Exécuter les scripts 01 à 03 pour reconstruire les contrôles et la base.
3. Exécuter les scripts 05 à 07 pour régénérer les analyses et les rapports.
4. Lancer les tests API avec `.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q` dans PowerShell.
5. Démarrer l'API et ouvrir `/docs` pour vérifier le contrat OpenAPI.

Les fichiers attendus dans `reports/` sont les rapports JSON de diagnostic,
qualité, analyse d'offre et modélisation, ainsi que les CSV et PNG de l'étape 4.

## Limites actuelles

Le GTFS décrit l'offre planifiée, pas la mobilité réellement observée. Le projet ne dispose pas encore de fréquentation, de validations, de retards, de suppressions ou de taux de remplissage. Les coordonnées hors emprise peuvent correspondre à des dessertes interrégionales et ne sont donc pas supprimées automatiquement.

La météo ne couvre pour l'instant qu'un point régional et une journée. L'OSM, les données socio-économiques et les données d'exploitation réelle seront étudiés comme enrichissements ultérieurs.

Les fichiers très volumineux, notamment `stop_times.txt`, `shapes.txt` et le fichier OSM `.pbf`, sont exclus du dépôt GitHub par [.gitignore](.gitignore) et restent disponibles localement.

Pour une utilisation au-delà du contexte local, la vue analytique des départs
reste coûteuse, le modèle est entraîné sur un feed local et les observations de
test restent limitées. Les résultats de modélisation doivent donc être lus
comme une évaluation de l'offre planifiée, pas comme une mesure de la demande.

## Suite du projet

Le parcours principal est terminé pour le périmètre local. Les prolongements
prioritaires sont :

- ajouter des données de fréquentation, de retards et de suppressions ;
- enrichir la météo avec plusieurs points et plusieurs dates ;
- intégrer l'OSM et des variables territoriales ou socio-économiques ;
- évaluer le modèle sur davantage de fenêtres temporelles et de jeux de test ;
- versionner le modèle et ajouter un endpoint de prédiction seulement après
  validation de sa généralisation.
