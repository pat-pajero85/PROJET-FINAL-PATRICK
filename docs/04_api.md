# Étape 3 - API locale GTFS

## Objectif

L'API expose la base SQLite locale `data/database/gtfs_pays_loire.sqlite` sans dépendre d'une plateforme cloud. Elle est construite avec FastAPI et fournit automatiquement une documentation interactive sur `/docs`.

## Lancer l'API

Depuis la racine du projet, dans l'environnement virtuel :

```powershell
.\mon_env\Scripts\python.exe -m uvicorn api.main:app --reload
```

L'API est alors accessible à `http://127.0.0.1:8000`.

Pour utiliser un autre fichier SQLite :

```powershell
$env:GTFS_DATABASE = "C:\chemin\vers\gtfs_pays_loire.sqlite"
.\mon_env\Scripts\python.exe -m uvicorn api.main:app --reload
```

## Endpoints

| Méthode | Endpoint                                   | Usage                                         |
| ------- | ------------------------------------------ | --------------------------------------------- |
| GET     | `/health`                                  | Vérifier que l'API répond                     |
| GET     | `/api/v1/stops`                            | Lister les arrêts, avec pagination et filtres |
| GET     | `/api/v1/stops/{stop_id}`                  | Consulter un arrêt                            |
| POST    | `/api/v1/stops`                            | Créer un arrêt                                |
| PUT     | `/api/v1/stops/{stop_id}`                  | Remplacer tous les attributs modifiables      |
| PATCH   | `/api/v1/stops/{stop_id}`                  | Modifier seulement certains attributs         |
| DELETE  | `/api/v1/stops/{stop_id}`                  | Supprimer un arrêt non référencé              |
| GET     | `/api/v1/routes`                           | Consulter les lignes                          |
| GET     | `/api/v1/agencies`                         | Consulter les opérateurs                      |
| GET     | `/api/v1/analytics/departures-by-stop-day` | Consulter la vue analytique des départs       |

Les réponses d'erreur utilisent les statuts HTTP usuels : `404` si la ressource est absente, `409` en cas de conflit d'intégrité ou de suppression d'une ressource encore référencée, et `422` si le corps ne respecte pas le contrat de données.

## Mise en pratique du cours FastAPI

L'API reprend les notions du cours sur une ressource réelle du projet :

- `@app.get` et `@app.post` déclarent les endpoints GET et POST ;
- `FastAPIPath` valide le paramètre de chemin `{stop_id}` pour récupérer un arrêt précis ;
- `Query` valide les paramètres de requête `name`, `coordinate_status`, `limit` et `offset` ;
- les modèles Pydantic `StopCreate`, `StopUpdate` et `StopPatch` définissent le corps JSON attendu ;
- `response_model` définit la structure JSON retournée ;
- les docstrings, tags et métadonnées de `FastAPI` alimentent Swagger UI et OpenAPI.

Exemples de requêtes depuis Python :

```python
import requests

# Paramètre de requête : recherche paginée dans les noms d'arrêts.
r = requests.get(
    "http://127.0.0.1:8000/api/v1/stops",
    params={"name": "Gare", "limit": 5},
)
print(r.json())

# Paramètre de chemin : récupération d'un arrêt précis.
r = requests.get("http://127.0.0.1:8000/api/v1/stops/STOP_ID")
print(r.json())

# Corps de requête Pydantic : création d'un arrêt.
r = requests.post(
    "http://127.0.0.1:8000/api/v1/stops",
    json={
        "stop_id": "API-TEST-001",
        "stop_name": "Arret API",
        "stop_lat": 47.2184,
        "stop_lon": -1.5536,
        "location_type": 0,
        "wheelchair_boarding": 1,
        "coordinate_status": "within_pdl_bbox",
    },
)
print(r.status_code, r.json())
```

La documentation interactive est disponible sur `http://127.0.0.1:8000/docs`, comme dans le cours. Elle permet de voir les schémas Pydantic, les paramètres `Path`/`Query` et de tester chaque endpoint avec **Try it out**.

## Tests automatises

La suite [tests/test_api.py](../tests/test_api.py) utilise `TestClient` et une copie temporaire de la base SQLite. Elle couvre les endpoints systeme, les catalogues, la validation des parametres, le CRUD des arrets et la protection des ecritures par cle API.

Depuis la racine du projet :

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q
```

Le endpoint analytique est volontairement teste ici sur la validation de sa date : l'agregation complete de la vue SQLite porte sur plusieurs millions de passages et doit rester un controle d'integration separe, pas un test rapide execute a chaque modification.

Exemple de création :

```powershell
$body = @{
    stop_id = "API-TEST-001"
    stop_name = "Arrêt API"
    stop_lat = 47.2184
    stop_lon = -1.5536
    location_type = 0
    wheelchair_boarding = 1
    coordinate_status = "within_pdl_bbox"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/stops -ContentType "application/json" -Body $body
```

## Choix d'organisation

- La version `/api/v1` évite de casser les clients si le contrat évolue.
- La ressource `stop` porte le CRUD complet : sa clé est simple et ses champs sont contrôlés par les contraintes déjà présentes dans SQLite.
- Les routes, agences et indicateurs sont exposés en lecture seule, car ils proviennent du référentiel GTFS et ne doivent pas être modifiés arbitrairement par ce premier client.
- La pagination par `limit` et `offset` empêche de renvoyer les 20 170 arrêts en une seule réponse.
- Les vues SQL existantes sont réutilisées pour les indicateurs : la logique métier reste dans la base et n'est pas dupliquée dans Python.
- Les commits sont limités à une mutation et les clés étrangères SQLite restent actives.

## Choix de sécurité

- Les requêtes SQL utilisent des paramètres `?` : les valeurs fournies par le client ne sont jamais concaténées dans les requêtes.
- Pydantic valide les types, les bornes géographiques, les valeurs GTFS autorisées et refuse les champs inattendus.
- Les écritures peuvent être protégées par une clé API passée dans `X-API-Key` :

```powershell
$env:GTFS_API_KEY = "une-cle-locale-longue-et-secrete"
```

Sans cette variable, le mode reste pratique pour le développement local ; avec elle, POST/PUT/PATCH/DELETE renvoient `401` sans clé correcte. En production, il faudrait remplacer ce mécanisme simple par une authentification standardisée, du HTTPS, une gestion de secrets et un contrôle des rôles.

## Pourquoi une API plutôt qu'un accès direct à la base ?

Une API fournit un contrat stable entre la donnée et les consommateurs : une application, un tableau de bord ou un script n'a pas besoin de connaître les tables internes ni les jointures SQL. Elle centralise la validation, la pagination, les codes d'erreur et les règles d'écriture. Elle réduit donc le couplage et évite de donner à chaque client un accès direct au fichier SQLite.

Dans ce projet sans cloud, l'API répond aussi au besoin de partage local ou réseau avec un coût d'installation réduit. L'accès direct à SQLite reste utile pour l'administration, les contrôles et les analyses lourdes ; il est moins adapté à l'exposition d'un service, car il donne trop de droits, expose le schéma interne et rend la sécurité et l'évolution du modèle plus difficiles à maîtriser.
