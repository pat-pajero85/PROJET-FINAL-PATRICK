# Rapport de check-up - Etape 3

## 1. Perimetre audite

Le controle porte sur l'API FastAPI locale et ses dependances directes :

- implementation dans `api/main.py` ;
- base SQLite `data/database/gtfs_pays_loire.sqlite` ;
- schema SQL et vues analytiques ;
- tests dans `tests/test_api.py` ;
- documentation dans `docs/04_api.md`, `docs/05_jalon_api_fonctionnelle.md` et `README.md` ;
- dependances Python dans `requirements.txt`.

## 2. Verdict global

**Etape fonctionnelle et presentable pour le projet de formation.**

L'API demarre avec Uvicorn, expose un contrat OpenAPI, valide les donnees avec Pydantic, fournit un CRUD complet sur les arrets et protege les mutations par une cle API optionnelle. La suite automatisée passe avec **6 tests reussis** en environ 6 secondes.

Le jalon n'est toutefois pas pret pour une exposition de production sans traiter la performance de l'analytics, le controle de sante de la base et le durcissement de quelques cas limites.

## 3. Points controles

### Fonctionnement

- `GET /` expose le point d'entree et la documentation.
- `GET /health` repond.
- Uvicorn demarre sur une adresse locale.
- `/docs` et `/openapi.json` sont generes par FastAPI.
- Les endpoints utilisent la base configuree par `GTFS_DATABASE`.

### Contrat HTTP

- Versionnement coherent sous `/api/v1`.
- Tags OpenAPI : systeme, arrets, catalogue et analytics.
- Schemas Pydantic avec types, bornes geographiques et champs interdits.
- Codes utilises : `201` pour creation, `204` pour suppression, `401` pour cle absente ou invalide, `404` pour ressource absente, `409` pour conflit d'integrite et `422` pour validation.

### Fonctionnalites

- Liste des arrets avec `name`, `coordinate_status`, `limit` et `offset`.
- Consultation d'un arret par identifiant.
- Creation, remplacement, modification partielle et suppression.
- Consultation des lignes et agences.
- Consultation de la vue des departs par arret et par jour.

### Donnees et SQL

- Requetes SQL parametrees pour les valeurs fournies par le client.
- Clefs et contraintes du schema relationnel reutilisees par l'API.
- Activation de `PRAGMA foreign_keys = ON` pour chaque connexion.
- Transactions explicites sur les mutations.
- Les tests CRUD utilisent une copie temporaire de la base et ne modifient pas la base de reference.

### Tests

La suite couvre :

- sante et OpenAPI ;
- lignes et agences ;
- validation d'un parametre analytics invalide ;
- filtres, pagination et erreurs `404`/`422` des arrets ;
- POST, PATCH, PUT, DELETE ;
- refus d'une mutation sans `X-API-Key` lorsque la cle est configuree.

Commande :

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q
```

Resultat observe : `6 passed`, avec un avertissement de deprecation interne a Starlette/AnyIO. L'avertissement lie a `httpx` a ete supprime par l'ajout de `httpx2`.

## 4. Constats et risques

### Priorite haute - vue analytics couteuse

La vue `v_departures_by_stop_day` joint les dates de service, trajets et passages, puis groupe les resultats. La requete peut traiter plusieurs millions de passages avant de renvoyer une petite page `LIMIT 1`. Elle ne doit pas etre appelee sans filtre dans une interface interactive ou un service expose.

**Action recommandee :** materialiser les agregats dans une table construite lors du chargement, ou creer une strategie d'agregation par date et ajouter des index adaptes. Ajouter ensuite un test d'integration mesure avec un budget de latence explicite.

### Priorite haute - PATCH avec valeurs nulles

`StopPatch` autorise des champs optionnels de type nullable. Un client peut donc envoyer par exemple `{"stop_name": null}` alors que la colonne SQLite est `NOT NULL`. Le code du PATCH ne capture pas cette erreur d'integrite, ce qui peut produire une erreur serveur `500` au lieu d'une reponse `422` propre.

**Action recommandee :** refuser explicitement les valeurs `null` pour les champs envoyes, ou intercepter `sqlite3.IntegrityError` dans le PATCH et la convertir en erreur HTTP contractuelle. Ajouter un test de regression.

### Priorite moyenne - health trop optimiste

`GET /health` renvoie `200` et le nom du fichier sans ouvrir la base. Une base absente, inaccessible ou corrompue peut donc laisser croire que le service est sain, alors que les endpoints metier renverront ensuite `503` ou une erreur SQL.

**Action recommandee :** verifier l'existence, l'ouverture et un `SELECT 1` dans la base, avec un statut `503` si la dependance n'est pas disponible.

### Priorite moyenne - couverture analytics incomplete

La suite teste la validation d'une date invalide, mais pas une reponse analytics valide, volontairement pour eviter l'agregation lourde de la vue.

**Action recommandee :** ajouter une base SQLite minimale dediee aux tests ou une table materialisee de test afin de verifier le schema et le contenu d'une reponse valide sans utiliser les 4 millions de passages.

### Priorite basse - validations de filtres perfectibles

`coordinate_status` est filtre comme une chaine libre et `service_date` accepte huit chiffres sans verifier que la date est calendairement valide. Ces entrées invalides renvoient simplement une liste vide ou peuvent lancer une requete inutile.

**Action recommandee :** utiliser des valeurs enumerees pour les statuts et un validateur de date stricte.

### Priorite basse - authentification locale minimale

La cle API protege les mutations, mais les lectures restent publiques et le secret est lu au demarrage depuis une variable d'environnement. C'est adapte a un usage local pedagogique, pas a une API exposee sur internet.

**Action recommandee :** conserver ce choix pour le projet local et documenter clairement qu'une authentification standard, HTTPS, gestion de secrets et journalisation sont necessaires en production.

## 5. Organisation du projet

L'organisation est lisible et suffisante pour l'etape :

- `api/` contient le service ;
- `tests/` contient les tests de contrat et de comportement ;
- `docs/04_api.md` explique l'utilisation ;
- `docs/05_jalon_api_fonctionnelle.md` formalise le jalon ;
- `requirements.txt` declare les dependances ;
- `README.md` donne les commandes de lancement et de test.

Pour une prochaine iteration, `api/main.py` pourra etre decoupe en routeurs, schemas et acces aux donnees. Ce refactoring n'est pas necessaire pour valider l'etape 3 et ne doit pas passer avant la correction des risques performance et PATCH.

## 6. Plan d'action priorise

1. Corriger le PATCH nullable et ajouter le test de regression.
2. Rendre `/health` dependant d'un vrai controle SQLite.
3. Materialiser ou optimiser l'agregation analytics.
4. Ajouter un test analytics positif sur une base minimale.
5. Ajouter les validations enum/date strictes.
6. Reevaluer l'authentification uniquement si l'API sort du contexte local.

## Conclusion

L'etape 3 est **validee fonctionnellement pour une demonstration et une soutenance**. Les controles automatises sont verts et la documentation est presente. Les travaux restants concernent principalement la robustesse d'exploitation et la performance, pas la mise en place du socle API.
