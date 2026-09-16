# Analyse et prédiction de la mobilité dans le Pays de la Loire

Projet final de formation Data Analyst consacré à l'analyse de l'offre de transport collectif dans les Pays de la Loire.

## Problématique métier

**Comment identifier les secteurs et créneaux où l'offre théorique de transport collectif est la plus faible, puis prédire le niveau d'offre attendu afin d'aider à prioriser les ajustements de desserte ?**

Le projet commence par l'analyse de l'offre planifiée : nombre de départs par arrêt, ligne, date, mode et période horaire. La prédiction portera d'abord sur le nombre de départs attendus ou sur une classe de niveau d'offre.

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
- [api](api) : API FastAPI locale de consultation et de gestion.
- [tests](tests) : tests automatisés des endpoints de l'API.

## Reproduire les contrôles

Depuis la racine du projet :

```powershell
python .\src\01_diagnostic_initial.py
python .\src\02_controle_nettoyage_gtfs.py
python .\src\03_charger_bdd_gtfs.py
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

- API : http://127.0.0.1:4000 ;
- documentation interactive Swagger : http://127.0.0.1:4000/docs ;
- schéma OpenAPI : http://127.0.0.1:4000/openapi.json ;
- état de santé : http://127.0.0.1:4000/health.

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

Résultat de référence : **6 tests réussis**. Les tests utilisent une copie temporaire de la base et ne modifient pas les données de référence.

## Limites actuelles

Le GTFS décrit l'offre planifiée, pas la mobilité réellement observée. Le projet ne dispose pas encore de fréquentation, de validations, de retards, de suppressions ou de taux de remplissage. Les coordonnées hors emprise peuvent correspondre à des dessertes interrégionales et ne sont donc pas supprimées automatiquement.

La météo ne couvre pour l'instant qu'un point régional et une journée. L'OSM, les données socio-économiques et les données d'exploitation réelle seront étudiés comme enrichissements ultérieurs.

Les fichiers très volumineux, notamment `stop_times.txt`, `shapes.txt` et le fichier OSM `.pbf`, sont exclus du dépôt GitHub par [.gitignore](.gitignore) et restent disponibles localement.

Pour une utilisation au-delà du contexte local, trois points restent à traiter : optimiser la vue analytique des départs, refuser proprement les valeurs `null` dans les modifications partielles et renforcer le contrôle de disponibilité de la base dans `/health`.

## Suite du projet

L'étape 3 fournit une API locale FastAPI documentée dans [docs/04_api.md](docs/04_api.md). Elle expose les données GTFS et les indicateurs analytiques, avec un CRUD complet sur les arrêts.

La suite prioritaire consiste à fiabiliser ces trois points, puis à construire la table analytique des départs par arrêt, date, ligne et période horaire avant d'établir une baseline et de tester un modèle prédictif avec une séparation temporelle entre entraînement et test.