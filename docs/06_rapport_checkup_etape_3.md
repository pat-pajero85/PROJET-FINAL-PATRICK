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

La suite automatisee passe avec 6 tests reussis. L'API expose une documentation
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

Resultat : **6 passed en 5,20 secondes**.

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

### Priorite haute - PATCH avec valeurs nulles

`StopPatch` autorise par exemple `{"stop_name": null}` car ses champs sont
optionnels et nullable. Le code transmet ensuite cette valeur a SQLite, alors
que plusieurs colonnes de `stop` sont `NOT NULL`. Le client peut donc obtenir
une erreur serveur au lieu d'une reponse de validation propre.

**Correction recommandee :** refuser explicitement les valeurs `null` pour les
champs presents dans un PATCH, ou convertir l'erreur d'integrite en `422`.
Ajouter un test de regression.

### Priorite haute - performance de l'analytics

`v_departures_by_stop_day` joint les dates de service, les trajets et les
passages avant d'agreger. Une requete sans filtre peut parcourir plusieurs
millions de passages, meme avec une petite limite de resultat.

**Correction recommandee :** materialiser les agregats, ajouter une table
analytique dediee ou imposer un filtre de date/arret avant execution. Ajouter
un controle de temps de reponse avec un budget explicite.

### Priorite moyenne - endpoint `/health` trop optimiste

`/health` verifie que l'application repond et renvoie le nom du fichier, mais
n'ouvre pas la base et n'execute pas `SELECT 1`. Une base absente, inaccessible
ou corrompue peut donc laisser apparaitre un statut `200`.

**Correction recommandee :** ouvrir la base, executer une requete minimale et
retourner `503` si la dependance SQLite est indisponible.

### Priorite moyenne - couverture analytics incomplete

Les tests verifient uniquement qu'une date mal formee renvoie `422`. Ils ne
verifient pas le schema ni le contenu d'une reponse analytics valide.

**Correction recommandee :** utiliser une petite base SQLite de test ou une
vue de test pour verifier une reponse positive sans parcourir la base complete.

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

1. Ajouter le refus des valeurs `null` dans PATCH et son test.
2. Rendre `/health` dependant d'un vrai controle SQLite.
3. Optimiser ou materialiser l'agregation analytics.
4. Ajouter un test positif de l'endpoint analytics sur une base minimale.
5. Renforcer la validation des statuts geographiques et des dates.
6. Conserver la cle API locale et documenter ses limites de securite.

## 7. Conclusion

L'etape 3 repond aux attentes du brief de formation : l'API demarre, expose un
contrat documente, valide les entrees, fournit un CRUD et passe sa suite de six
tests automatises.

Le resultat est donc **presentable pour la soutenance et la demonstration
locale**. Les corrections restantes concernent principalement la robustesse,
la performance et la securite necessaires a un usage de production ; elles ne
remettent pas en cause la validation pedagogique de l'etape.
