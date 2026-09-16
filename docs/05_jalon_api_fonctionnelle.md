# Jalon - API fonctionnelle

## Statut

Le jalon est valide. L'API FastAPI permet de consulter les donnees GTFS, de consulter les indicateurs et de gerer les arrets avec un CRUD complet.

## Criteres d'acceptation

- [x] L'API demarre avec Uvicorn depuis la racine du projet.
- [x] `/health` confirme que l'application repond.
- [x] `/docs` et `/openapi.json` exposent le contrat HTTP.
- [x] Les arrets sont consultables avec recherche, filtre et pagination.
- [x] Les arrets disposent des operations POST, PUT, PATCH et DELETE.
- [x] Les lignes, agences et indicateurs sont exposes en lecture seule.
- [x] Les donnees entrantes sont validees par Pydantic.
- [x] Les requetes SQL utilisent des parametres.
- [x] Les mutations peuvent etre protegees par `GTFS_API_KEY`.
- [x] Les tests automatises couvrent les endpoints principaux et le CRUD.

## Demonstration

Depuis la racine :

```powershell
.\mon_env\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 4000
```

Puis ouvrir :

- API : `http://127.0.0.1:4000` ;
- documentation interactive : `http://127.0.0.1:4000/docs` ;
- schema OpenAPI : `http://127.0.0.1:4000/openapi.json` ;
- verification : `http://127.0.0.1:4000/health`.

La suite de validation se lance avec :

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q
```

Resultat de reference : `6 passed`.

## Perimetre et limites

L'API expose l'offre planifiee GTFS, pas les validations voyageurs, les retards ou les suppressions en temps reel. La vue analytique des departs porte sur plusieurs millions de passages ; son execution complete est un controle d'integration et n'est pas executee dans chaque test rapide.

Les ecritures restent adaptees a un usage local ou pedagogique. Une exposition de production demanderait au minimum HTTPS, une authentification standardisee, une gestion de secrets et une journalisation.

## Suite logique

Le prochain jalon peut consister a construire une table analytique plus legere par periode horaire, puis a fournir ces indicateurs a un tableau de bord ou a une baseline predictive.