# Check-up complet - Etape 3 API GTFS

## 1. Date et perimetre

- Date du controle : 18 septembre 2026
- Application controlee : API FastAPI locale dans `api/main.py`
- Base utilisee : `data/database/gtfs_pays_loire.sqlite`
- Tests : `tests/test_api.py`
- Documentation comparee : `docs/04_api.md`, `docs/05_jalon_api_fonctionnelle.md` et `README.md`

Le controle porte sur le demarrage, le contrat HTTP, la validation des donnees,
les lectures, les mutations, la securite locale, les tests et les limites de
performance.

## 2. Verdict global

**Etape 3 validee pour une demonstration et un usage pedagogique local.**

La suite automatisee passe avec 8 tests reussis. L'API expose une documentation
OpenAPI, des endpoints de consultation des donnees GTFS et un CRUD complet sur
les arrets. Les requetes SQL utilisent des parametres pour les valeurs fournies
par le client et les mutations peuvent etre protegees par `GTFS_API_KEY`.

L'API n'est pas encore prete pour une exposition de production sans corriger
les points de robustesse identifies ci-dessous.

## 3. Resultats des controles

### 3.1 Tests automatises

Commande executee :

```powershell
.\mon_env\Scripts\python.exe -m pytest tests/test_api.py -q
```

Resultat : **8 passed en 11,35 secondes**.

Les tests couvrent :

- `/health` et `/openapi.json` ;
- les endpoints des lignes et des agences ;
- la validation d'un parametre analytics invalide ;
- les filtres, la pagination et les erreurs des arrets ;
- POST, PATCH, PUT et DELETE sur les arrets ;
- le refus d'une mutation sans cle lorsque `GTFS_API_KEY` est configuree.

Un avertissement de deprecation provenant de `starlette.testclient` et AnyIO
est affiche. Il ne fait pas echouer les tests, mais devra etre surveille lors
d'une mise a jour des dependances.

### 3.2 Contrat HTTP

Le contrat est coherent sur les points suivants :

- versionnement des routes sous `/api/v1` ;
- documentation Swagger sur `/docs` ;
- schema OpenAPI sur `/openapi.json` ;
- modeles Pydantic pour les corps et les reponses ;
- codes `201`, `204`, `401`, `404`, `409` et `422` utilises selon les cas ;
- pagination par `limit` et `offset` sur les collections principales.

### 3.3 Validation et acces aux donnees

Les modeles controlent les longueurs, les coordonnees geographiques, les types
GTFS et les champs inattendus. Les requetes utilisent des placeholders SQLite
`?`, ce qui evite de concatener les valeurs utilisateur dans le SQL.

Les cles etrangeres sont activees dans les connexions API. Les mutations sont
executees dans une transaction puis validees par `commit()`.

### 3.4 Endpoints verifies

| Domaine | Resultat |
| --- | --- |
| Racine et sante | Conforme pour une verification basique |
| Arrets en lecture | Conforme : recherche, filtre, pagination et 404 |
| CRUD des arrets | Conforme dans les tests sur une copie de la base |
| Lignes et agences | Conforme en lecture seule |
| Analytics | Validation du parametre testee ; reponse complete non testee en test rapide |
| Authentification locale | Conforme pour la protection optionnelle des mutations |

## 4. Anomalies et risques

### Correction appliquee - PATCH avec valeurs nulles

`StopPatch` conserve des champs optionnels pour permettre les modifications
partielles, mais les valeurs explicitement envoyees a `null` sont maintenant
refusees par Pydantic avec une reponse `422` avant l'ecriture SQLite.

**Validation :** un test de regression couvre le PATCH avec `{"stop_name": null}`.

### Priorite haute - performance de l'analytics

`v_departures_by_stop_day` joint les dates de service, les trajets et les
passages avant d'agreger. Une requete sans filtre peut parcourir plusieurs
millions de passages, meme avec une petite limite de resultat.

**Correction recommandee :** materialiser les agregats, ajouter une table
analytique dediee ou imposer un filtre de date/arret avant execution. Ajouter
un controle de temps de reponse avec un budget explicite.

### Correction appliquee - endpoint `/health`

`/health` verifie maintenant l'existence de la base, ouvre une connexion et
execute `SELECT 1`. Une base absente ou indisponible renvoie `503`.

**Validation :** un test couvre l'absence de la base.

### Correction appliquee - couverture analytics

Les tests vérifient maintenant une date mal formée, le refus d'une requête sans
filtre et une réponse valide sur la date `20250402`.

La requête sans filtre est refusée avec `422`, ce qui évite de déclencher une
agrégation complète de la vue SQLite depuis l'API.

### Priorite basse - validations de filtres perfectibles

`coordinate_status` accepte une chaine libre et `service_date` verifie le
format `YYYYMMDD` mais pas directement la validite calendaire. Une valeur comme
le 31 fevrier peut donc etre acceptee puis renvoyer une liste vide.

**Correction recommandee :** utiliser une enumeration pour `coordinate_status`
et une validation stricte de la date.

### Priorite basse - authentification adaptee au local uniquement

La cle API optionnelle protege les mutations, mais les lectures restent
publiques et le secret est fourni par variable d'environnement. Ce choix est
acceptable pour une demonstration locale, pas pour une API exposee sur
internet.

**Correction recommandee :** HTTPS, gestion de secrets, authentification
standardisee, roles et journalisation avant toute exposition externe.

## 5. Points de coherence documentaire

Les documents de l'etape 3 sont globalement alignes avec l'implementation :
les routes, la pagination, Pydantic, la cle API et la commande de test sont
bien decrits.

La formulation doit rester prudente : le jalon est valide fonctionnellement,
mais les limites de performance de l'analytics et de robustesse de `/health`
doivent etre presentes dans toute soutenance ou documentation de projet.

## 6. Plan d'action priorise

1. Materialiser ou optimiser davantage l'agregation analytics si le volume
   augmente.
2. Renforcer les validations des statuts geographiques.
3. Conserver la cle API locale et documenter ses limites de securite.

## 7. Conclusion

L'etape 3 repond aux attentes du brief de formation : l'API demarre, expose un
contrat documente, valide les entrees, fournit un CRUD et passe sa suite de huit
tests automatises.

Le resultat est donc **presentable pour la soutenance et la demonstration
locale**. Les corrections restantes concernent principalement la robustesse,
la performance et la securite necessaires a un usage de production ; elles ne
remettent pas en cause la validation pedagogique de l'etape.
