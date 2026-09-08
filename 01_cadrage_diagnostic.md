# Analyse et prédiction de la mobilité dans le Pays de la Loire

## 1. Problématique métier proposée

Les autorités organisatrices et les opérateurs de transport doivent adapter l'offre de mobilité aux jours, horaires, territoires et modes de transport. La question retenue pour le projet est :

> **Comment identifier les secteurs et créneaux où l'offre théorique de transport collectif est la plus faible, puis prédire le niveau d'offre attendu afin d'aider à prioriser les ajustements de desserte ?**

Cette formulation est directement exploitable avec le feed GTFS : elle permet d'abord de décrire l'offre planifiée, puis de construire une prédiction sur un indicateur défini à l'échelle d'un arrêt, d'une ligne ou d'un territoire.

### Indicateur cible de première version

Le niveau d'offre sera mesuré par le nombre de départs planifiés par jour et par arrêt. Les agrégations complémentaires seront :

- nombre de lignes et de trajets actifs ;
- amplitude horaire et nombre de passages par tranche horaire ;
- accessibilité déclarée des arrêts ;
- répartition par mode (`route_type`) et par territoire ;
- évolution entre jours ouvrés, week-ends et périodes de calendrier.

La cible prédictive pourra être le nombre de départs d'un arrêt pour une date future, ou une classe de tension de l'offre (faible, intermédiaire, forte). La précision et l'intérêt métier devront être validés après le diagnostic exploratoire.

## 2. Processus de collecte de bout en bout

| Étape                    | Source / action                                                                                                         | Sortie attendue                | Contrôle                               |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------------------- |
| 1. Définir le périmètre  | Pays de la Loire, dates de service, modes couverts                                                                      | dictionnaire métier            | cohérence géographique et temporelle   |
| 2. Collecter l'offre     | export GTFS Destineo : `routes`, `trips`, `stop_times`, `stops`, `calendar_dates`, `shapes`, `transfers`                | fichiers bruts versionnés      | présence des tables et en-têtes GTFS   |
| 3. Collecter le contexte | météo à des coordonnées des Pays de la Loire, calendrier scolaire/jours fériés, éventuellement population et événements | tables externes documentées    | coordonnées, fuseau et dates cohérents |
| 4. Stocker les bruts     | conserver les fichiers reçus sans modification                                                                          | zone `raw` et date de collecte | empreinte, taille, date de collecte    |
| 5. Contrôler             | volumes, doublons, clés étrangères, dates, horaires, coordonnées                                                        | rapport qualité                | seuils d'anomalie tracés               |
| 6. Nettoyer et enrichir  | normaliser dates/heures, joindre calendrier et arrêts, dériver jour/semaine/heure                                       | table analytique               | règles de transformation documentées   |
| 7. Agréger               | départs par arrêt, date, heure, ligne et territoire                                                                     | table de modélisation          | réconciliation avec les bruts          |
| 8. Analyser et prédire   | diagnostic, baseline puis modèle                                                                                        | indicateurs et prédictions     | séparation temporelle train/test       |

## 3. Premier diagnostic du périmètre actuel

Le diagnostic est généré par `01_diagnostic_initial.py` et sauvegardé dans `diagnostic_initial.json`. Les premiers constats sont :

- le feed est publié par DESTINEO et couvre théoriquement du `2023-09-01` au `2027-04-02` selon `feed_info` ;
- `calendar_dates` contient des dates de service du `2025-04-02` au `2027-04-02` et uniquement des exceptions de type `1` ;
- les tables sont volumineuses : environ 182 725 trajets, 4 millions de passages, 20 170 arrêts, 899 601 points de géométrie et 1 029 lignes ;
- plusieurs colonnes facultatives sont presque ou totalement vides : `stop_times.stop_headsign`, `stop_times.timepoint`, `trips.trip_headsign`, `trips.trip_short_name`, `routes.route_desc` et `routes.route_url` ;
- les champs `bikes_allowed` sont actuellement à `0` pour les trajets observés : cela signifie « information non disponible », pas nécessairement « vélos interdits » ;
- la météo a été remplacée par une série Open-Meteo située au centre régional (`47.41652, -0.7377014`, altitude `45 m`, fuseau `Europe/Paris`) ; elle reste un point représentatif et non une mesure à chaque arrêt ;
- les coordonnées d'arrêts doivent être contrôlées : le fichier contient déjà des valeurs incompatibles avec une emprise Pays de la Loire dans les modalités observées.

## 4. Nettoyage à engager

1. Vérifier l'emprise géographique des arrêts et isoler les coordonnées invalides ou hors région.
2. Vérifier les clés : chaque `stop_id` de `stop_times` doit exister dans `stops`, chaque `trip_id` dans `trips`, chaque `route_id` dans `routes` et chaque `shape_id` utilisé dans `shapes`.
3. Convertir les dates `YYYYMMDD` en dates, et les horaires GTFS en durée depuis minuit ; accepter les horaires supérieurs à `24:00:00`.
4. Détecter doublons, trajets sans passage, passages sans trajet, séquences non croissantes et arrivées après départ.
5. Documenter les valeurs codées `0` comme « non renseigné » lorsque le standard GTFS le prévoit.
6. Enrichir la météo régionale par plusieurs points ou stations couvrant les arrêts si l'effet météorologique est conservé dans la modélisation.

### Résultats du premier nettoyage

Le script `02_controle_nettoyage_gtfs.py` produit `rapport_qualite_gtfs.json`, `stops_clean.csv` et `stop_times_clean.csv`. Les contrôles effectués donnent les résultats suivants :

- aucune clé primaire dupliquée dans `routes`, `stops` et `trips` ;
- les identifiants répétés de `calendar_dates.service_id` et `shapes.shape_id` sont conservés car ils sont attendus par le modèle GTFS ;
- les 4 000 625 lignes de `stop_times` sont conservées après contrôle des références, des horaires et des séquences ;
- les horaires ont été convertis en secondes depuis minuit, en conservant la possibilité d'horaires supérieurs à `24:00:00` ;
- 11 862 arrêts sont dans l'emprise indicative et 8 308 sont marqués `outside_pdl_bbox` sans être supprimés, car ils peuvent correspondre à des dessertes interrégionales.

Le nettoyage est donc non destructif pour les coordonnées : les anomalies sont signalées afin de permettre une décision métier ultérieure, plutôt que supprimées automatiquement.

## 5. Décision de cadrage

La première itération sera centrée sur l'offre planifiée GTFS. La météo et l'OSM seront traités comme enrichissements après validation du périmètre et des clés GTFS. Cette décision limite le risque de construire un modèle sur des sources géographiquement incompatibles et permet d'obtenir rapidement un indicateur métier fiable.

## 6. Réponse à la question d'analyse

### En quoi le dataset répond-il à une problématique métier réaliste ?

Le dataset est un export GTFS de DESTINEO. Il décrit l'offre théorique de transport collectif dans et autour des Pays de la Loire : lignes, trajets, arrêts, horaires, calendriers de circulation, correspondances et géométries. Ces informations correspondent à des décisions opérationnelles réelles prises par les autorités organisatrices et les opérateurs.

Il permet notamment de répondre à des questions utiles pour :

- repérer les arrêts ou territoires dont la fréquence de desserte est faible ;
- comparer l'offre entre jours ouvrés, week-ends, périodes et modes de transport ;
- identifier les plages horaires présentant une faible amplitude ou peu de départs ;
- mesurer la couverture spatiale des lignes et les possibilités de correspondance ;
- simuler ou prévoir le niveau d'offre théorique pour aider à prioriser une évolution de desserte.

La problématique est donc réaliste car elle peut soutenir la planification des horaires, la comparaison territoriale et la détection de secteurs potentiellement moins bien desservis. Le nombre de départs planifiés par arrêt et par jour constitue un premier indicateur simple, interprétable et actionnable.

En revanche, il faut préciser que le dataset mesure principalement **l'offre disponible**, et non la mobilité réellement observée. Il permet de répondre à la question « où et quand un service est-il planifié ? », mais pas directement aux questions « combien de personnes l'utilisent ? » ou « le service est-il réellement ponctuel ? ».

### Quelles limites sont déjà identifiées ?

**Limites métier**

- Il n'y a pas de fréquentation, de validations de titres, de comptage de voyageurs ni de taux de remplissage : l'offre ne peut pas être assimilée à la demande.
- Il n'y a pas de données d'exploitation réelle : retards, suppressions, incidents et écarts entre horaires prévus et horaires réalisés sont absents.
- Il manque des variables explicatives socio-économiques et territoriales : population, emploi, établissements scolaires, revenus, pôles d'attractivité et distance au domicile.

**Limites temporelles et géographiques**

- `feed_info` annonce une période théorique du `2023-09-01` au `2027-04-02`, alors que `calendar_dates` observé commence le `2025-04-02` : cette différence doit être expliquée avant toute analyse temporelle.
- La météo disponible ne contient qu'un point représentatif du centre régional et une seule journée ; elle ne permet pas encore d'étudier un effet météorologique robuste à l'échelle des arrêts.
- Des coordonnées d'arrêts sortent de l'emprise indicative des Pays de la Loire ; elles peuvent correspondre à des dessertes interrégionales, mais doivent être distinguées des erreurs de géocodage.
- Le fichier OSM est disponible mais n'est pas encore relié aux arrêts et aux lignes ; l'accessibilité routière, les distances et les temps de parcours ne sont donc pas encore exploitables.

**Limites de qualité et de modélisation**

- Plusieurs champs facultatifs sont totalement ou presque vides, notamment les destinations de trajets, les descriptions de lignes et les informations détaillées de temps de passage.
- Certaines valeurs codées `0`, par exemple `bikes_allowed`, signifient « information non disponible » selon le standard GTFS et ne doivent pas être interprétées comme une interdiction.
- Les calendriers, horaires après minuit, doublons et clés entre les tables doivent encore être contrôlés avant agrégation.
- La prédiction portera d'abord sur un indicateur construit à partir de l'offre planifiée. Elle devra être évaluée avec une séparation temporelle et comparée à une baseline simple.

Ces limites ne rendent pas le projet irréaliste. Elles définissent son périmètre : une première version solide peut analyser et prédire l'offre théorique, tandis qu'une version plus complète nécessiterait des données de fréquentation, d'exploitation réelle et de contexte territorial.