# Parcours détaillé du projet (étapes 1 à 7)

Retour au [README](../README.md). Les résultats de référence sont ceux de l'étape 7 ([09_revision_methodologique.md](09_revision_methodologique.md)) ; les étapes 5 et 6 sont conservées pour montrer la démarche et ce que l'audit a corrigé.

Le périmètre prédictif porte sur l'offre planifiée GTFS. Il ne s'agit pas d'une
prédiction de fréquentation ou de demande réelle.

## Données sources

La source principale est un export GTFS publié par DESTINEO :

- `routes.txt` : lignes et modes de transport ;
- `trips.txt` : trajets planifiés ;
- `stop_times.txt` : horaires de passage ;
- `stops.txt` : arrêts et coordonnées ;
- `calendar_dates.txt` : dates de circulation ;
- `shapes.txt` : géométries des itinéraires ;
- `transfers.txt` : correspondances ;
- `agency.txt` et `feed_info.txt` : métadonnées du feed.

Une série météo Open-Meteo est disponible dans [data/raw/external/open-meteo-47.42N0.74W45m.csv](../data/raw/external/open-meteo-47.42N0.74W45m.csv). Elle correspond à une maille située au centre régional : `47.41652, -0.7377014`, fuseau `Europe/Paris`.

Le fichier OSM `.pbf` est conservé localement pour un enrichissement géographique ultérieur.

## Étape 1 : cadrage, collecte et diagnostic

Cette étape est finalisée :

- problématique métier et indicateur cible définis ;
- processus de collecte documenté ;
- source météo remplacée par une source localisée en Pays de la Loire ;
- diagnostic initial exécuté ;
- contrôles des clés et nettoyage minimal réalisés ;
- limites métier et techniques documentées.

## Étape 2 : nettoyage et structuration relationnelle

Cette étape est également réalisée avec SQLite :

- tables de staging conservant les données importées ;
- schéma relationnel normalisé avec clés primaires, clés étrangères et contraintes ;
- nettoyage final exécuté par `INSERT ... SELECT` en SQL ;
- index et vues analytiques pour les départs par arrêt et par ligne ;
- base locale `gtfs_pays_loire.sqlite` construite et contrôlée.

La base validée contient 14 agences, 1 029 lignes, 20 170 arrêts, 6 090 services, 182 725 trajets, 4 000 625 passages, 22 286 correspondances et 24 observations météo. Les contrôles d'orphelins entre trajets, lignes, passages et arrêts renvoient zéro anomalie.

## Étape 3 : API locale

L'API FastAPI expose les arrêts en CRUD, les référentiels lignes/agences et les
indicateurs de départs (détails dans la section [API locale FastAPI](10_guide_execution.md#api-locale-fastapi)).

## Étape 4 : analyse exploratoire et veille

Trois hypothèses sont testées sur `v_departures_by_stop_period` :

- l'offre varie selon la période horaire ;
- elle est plus importante les jours ouvrés que le week-end ;
- le nombre de lignes desservantes est positivement associé aux départs.

Les résultats confirment H1 et H2. H3 est partiellement confirmée, avec une
corrélation positive modérée : Pearson `0,4036` et Spearman `0,4319`.
Les tableaux et graphiques sont produits dans `reports/`.

> Ces chiffres portent sur tout le calendrier du feed et ignorent les créneaux sans départ. L'étape 7
> recalcule H1 et H2 sur la fenêtre valide avec une grille complète (`profil_offre`,
> `reports/etape7_profil_horaire.png`) : −27 % le samedi et −73 % le dimanche par rapport à un jour ouvré.

## Étape 5 : baseline et analyse de l'offre

> Résultats de la première version, **remplacés par l'étape 7** : le test portait sur des dates où le feed
> ne contient presque plus d'offre.

Le script `src/05_analyse_offre.py` travaille au grain arrêt-date-période,
identifie les niveaux moyens d'offre les plus faibles et évalue une baseline
fondée sur la moyenne historique par arrêt et période. Sur `588` observations
de test, cette baseline obtient une MAE de `0,7059` et une RMSE de `0,7069`.

## Étape 6 : modélisation et risques

> Première version, **remplacée par l'étape 7** pour la partie évaluation (holdout de 588 observations
> toutes égales à 1). L'analyse des risques reste valable.

Le script `src/07_modelisation_risques.py` compare un
`RandomForestRegressor` et un `HistGradientBoostingRegressor`, avec une
baseline historique. La cible est `planned_departures`, avec une séparation
temporelle entre l'entraînement et les dates futures. La baseline historique
est retenue dans l'exécution actuelle (MAE moyenne de validation : `0,5168`,
contre `0,7641` pour le Random Forest).

Une évaluation complémentaire utilise trois fenêtres temporelles futures et
compare le modèle à une baseline par moyenne de période horaire. Les résultats
détaillés, les métriques et les risques de données, de modèle, de déploiement
et d'éthique sont enregistrés dans
`reports/etape6_modeles_risques.json`.

### Réponse à la question d'analyse de l'étape 6

L'étape 6 répond à la question sur le périmètre de l'offre théorique : elle
permet d'identifier les arrêts et créneaux faiblement desservis à partir du
nombre de départs planifiés, puis de prévoir le niveau d'offre attendu pour
des dates futures. La baseline historique est meilleure que les deux modèles
sur les trois fenêtres temporelles évaluées.

La réponse reste toutefois partielle pour une décision métier complète. Le
GTFS décrit une offre planifiée, et non la fréquentation, la demande, les
retards ou les suppressions réelles. Le modèle ne prédit donc pas directement
le besoin de mobilité. Il constitue une aide au repérage des secteurs à
examiner, mais ses résultats doivent être complétés par des données de
fréquentation et validés par une analyse territoriale et métier avant toute
décision de renforcement de desserte.

## Étape 7 : révision méthodologique

Le script `src/08_offre_fenetre_valide.py` reprend l'analyse directement depuis les fichiers GTFS :

- fenêtre de 12 semaines où le feed est complet (7 avril → 29 juin 2025) ;
- grille complète arrêt × date × période (4,5 millions d'observations), **avec les créneaux sans départ**
  (50 % des créneaux) que la vue SQL ne faisait pas apparaître ;
- arrêts limités aux Pays de la Loire (4 434 gares SNCF hors région exclues, soit 24 % des départs) ;
- passages sans montée possible (`pickup_type = 1`) exclus, aussi corrigé dans les vues SQL et l'API ;
- jours fériés, ponts et vacances scolaires pris en compte ;
- 5 méthodes comparées sur 5 semaines de test, voir le tableau dans
  [docs/09_revision_methodologique.md](09_revision_methodologique.md).

## Résultats du diagnostic

- 1 029 lignes ;
- 182 725 trajets ;
- 20 170 arrêts ;
- 4 000 625 passages ;
- 899 601 points de géométrie ;
- aucune clé primaire dupliquée dans `routes`, `stops` et `trips` ;
- 4 000 625 passages conservés après contrôle ;
- 11 862 arrêts dans l'emprise indicative des Pays de la Loire ;
- 8 308 arrêts signalés hors emprise et conservés pour analyse métier.

## Documents par étape

| Document | Contenu |
|---|---|
| [01_cadrage_diagnostic.md](01_cadrage_diagnostic.md) | Étape 1 : cadrage, collecte et diagnostic |
| [03_schema_relationnel.md](03_schema_relationnel.md) | Étape 2 : schéma relationnel SQLite |
| [04_api.md](04_api.md) | Étape 3 : documentation de l'API et exemples |
| [05_jalon_api_fonctionnelle.md](05_jalon_api_fonctionnelle.md) | Étape 3 : validation du jalon API |
| [06_rapport_checkup_etape_3.md](06_rapport_checkup_etape_3.md) | Étape 3 : rapport de contrôle |
| [07_analyse_exploratoire_et_veille.md](07_analyse_exploratoire_et_veille.md) | Étape 4 : résultats et sources de veille |
| [08_rapport_checkup_etape_4.md](08_rapport_checkup_etape_4.md) | Étape 4 : contrôle qualité (instantané avant la révision de l'étape 7) |
| [09_revision_methodologique.md](09_revision_methodologique.md) | Étape 7 : révision méthodologique et résultats de référence |

Correspondance scripts / étapes : `01`-`02` → étape 1, `03` → étape 2, `06` → étape 4,
`05` → étape 5, `07` → étape 6, `08` → étape 7.
