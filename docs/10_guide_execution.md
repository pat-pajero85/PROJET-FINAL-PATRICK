# Guide d'exécution : reproduire le projet, lancer l'API et les tests

Retour au [README](../README.md).

## Reproduire les contrôles

Depuis la racine du projet :

```powershell
python .\src\01_diagnostic_initial.py
python .\src\02_controle_nettoyage_gtfs.py
python .\src\03_charger_bdd_gtfs.py
python .\src\05_analyse_offre.py
python .\src\06_analyse_exploratoire.py
python .\src\07_modelisation_risques.py
python .\src\08_offre_fenetre_valide.py
```

Avec l'environnement fourni, utiliser de préférence :

```powershell
.\mon_env\Scripts\python.exe .\src\01_diagnostic_initial.py
.\mon_env\Scripts\python.exe .\src\02_controle_nettoyage_gtfs.py
.\mon_env\Scripts\python.exe .\src\03_charger_bdd_gtfs.py
.\mon_env\Scripts\python.exe .\src\05_analyse_offre.py
.\mon_env\Scripts\python.exe .\src\06_analyse_exploratoire.py
.\mon_env\Scripts\python.exe .\src\07_modelisation_risques.py
.\mon_env\Scripts\python.exe .\src\08_offre_fenetre_valide.py
```

Pour les scripts utilisant pandas, matplotlib ou scikit-learn sur une machine
à mémoire limitée, limiter les threads numériques avant l'exécution :

```powershell
$env:OPENBLAS_NUM_THREADS="1"
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
```

Les scripts 01 à 03 et 05 n'utilisent que la bibliothèque standard Python ; les scripts 06 à 08, l'API et
les tests utilisent les dépendances listées dans [requirements.txt](../requirements.txt). Le script 08 lit
directement les fichiers GTFS et n'a pas besoin de la base SQLite.

Le traitement de nettoyage et de structuration est réalisé en SQL dans [sql/03_schema_gtfs.sql](../sql/03_schema_gtfs.sql). Python sert uniquement de passerelle d'import des fichiers CSV, SQLite ne disposant pas d'une commande CSV portable native.

## Placer la base SQLite hors de OneDrive

Une base de 1,4 Go dans un dossier synchronisé (OneDrive, Dropbox…) est souvent verrouillée
(`database is locked`, `PermissionError: [WinError 33]`). Les scripts, l'API et les tests lisent la
variable d'environnement `GTFS_DB_PATH` ; sans elle, ils utilisent `data/database/gtfs_pays_loire.sqlite`.

```powershell
New-Item -ItemType Directory -Force C:\data | Out-Null
Copy-Item .\data\database\gtfs_pays_loire.sqlite C:\data\   # ou relancer 03_charger_bdd_gtfs.py
$env:GTFS_DB_PATH = "C:\data\gtfs_pays_loire.sqlite"            # pour la session en cours
setx GTFS_DB_PATH "C:\data\gtfs_pays_loire.sqlite"              # pour les prochaines sessions
```

## API locale FastAPI

L'API expose la base SQLite et les indicateurs d'offre sans dépendre d'une plateforme cloud. Elle est construite avec FastAPI, Pydantic et Uvicorn.

**Statut du jalon : validé pour démonstration et soutenance.** La checklist est disponible dans [05_jalon_api_fonctionnelle.md](05_jalon_api_fonctionnelle.md) et le contrôle détaillé dans [06_rapport_checkup_etape_3.md](06_rapport_checkup_etape_3.md).

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

La documentation détaillée et les exemples Python avec `requests` sont disponibles dans [04_api.md](04_api.md).

### Tester l'API

Les tests utilisent `FastAPI TestClient` et une copie temporaire de la base SQLite. Ils couvrent les endpoints système, les référentiels, la validation des paramètres, le CRUD des arrêts et la protection par clé API, sans modifier la base de référence.

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q
```

Résultat de référence : **8 tests réussis**.

Les tests des étapes 6 et 7 n'ont besoin ni de la base ni du GTFS complet :

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_modelisation_risques.py tests/test_offre_fenetre_valide.py -q
```

Pour lancer toute la suite : `.\mon_env\Scripts\python.exe -m pytest tests -q` (20 tests attendus).

## Parcours de vérification recommandé

1. Vérifier la présence de `data/raw/gtfs`, des fichiers nettoyés et de la base SQLite.
2. Exécuter les scripts 01 à 03 pour reconstruire les contrôles et la base.
3. Exécuter les scripts 05 à 08 pour régénérer les analyses et les rapports.
4. Lancer les tests avec `.\mon_env\Scripts\python.exe -m pytest tests -q`.
5. Démarrer l'API et ouvrir `/docs` pour vérifier le contrat OpenAPI.
6. Régénérer la présentation avec `.\mon_env\Scripts\python.exe .\generer_presentation.py`.

Fichiers produits dans `reports/` :

| Étape | Fichiers |
|---|---|
| 1 | `diagnostic_initial.json`, `rapport_qualite_gtfs.json` |
| 2 | `04_resultats_validation_bdd.json` |
| 4 | `etape4_h1_*`, `etape4_h2_*`, `etape4_h3_*` (CSV et PNG) |
| 5 | `analyse_offre.json` (première version) |
| 6 | `etape6_modeles_risques.json` (première version ; risques toujours valables) |
| 7 | `etape7_offre_fenetre_valide.json`, `etape7_offre_par_arret.csv`, `etape7_*.png` (**résultats de référence**) |
| 7 (Power BI) | `powerbi/*.csv` : tables prêtes à importer, voir [11_guide_power_bi.md](11_guide_power_bi.md) |
| Restitution | `presentation_analyse_mobilite.pptx`, `DASHBOARD.pbix` |

## Fichiers exclus du dépôt

Les fichiers très volumineux, notamment `stop_times.txt`, `shapes.txt` et le fichier OSM `.pbf`, sont exclus du dépôt GitHub par [.gitignore](../.gitignore) et restent disponibles localement.
