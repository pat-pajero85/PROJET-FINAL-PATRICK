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

Une série météo Open-Meteo est disponible dans [open-meteo-47.42N0.74W45m.csv](open-meteo-47.42N0.74W45m.csv). Elle correspond à une maille située au centre régional : `47.41652, -0.7377014`, fuseau `Europe/Paris`.

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

## Fichiers principaux

- [01_cadrage_diagnostic.md](01_cadrage_diagnostic.md) : problématique, processus de collecte, limites et conclusions ;
- [01_diagnostic_initial.py](01_diagnostic_initial.py) : inventaire et diagnostic initial ;
- [02_controle_nettoyage_gtfs.py](02_controle_nettoyage_gtfs.py) : contrôles des clés, horaires et coordonnées ;
- [diagnostic_initial.json](diagnostic_initial.json) : résultats du diagnostic initial ;
- [rapport_qualite_gtfs.json](rapport_qualite_gtfs.json) : rapport des contrôles qualité ;
- `stops_clean.csv` : arrêts normalisés et statut géographique ;
- `stop_times_clean.csv` : passages normalisés avec horaires en secondes.

## Reproduire les contrôles

Depuis la racine du projet :

```powershell
python .\01_diagnostic_initial.py
python .\02_controle_nettoyage_gtfs.py
```

Les scripts utilisent uniquement la bibliothèque standard Python pour les contrôles actuels. Les dépendances de l'environnement sont listées dans [requirements.txt](requirements.txt).

## Limites actuelles

Le GTFS décrit l'offre planifiée, pas la mobilité réellement observée. Le projet ne dispose pas encore de fréquentation, de validations, de retards, de suppressions ou de taux de remplissage. Les coordonnées hors emprise peuvent correspondre à des dessertes interrégionales et ne sont donc pas supprimées automatiquement.

La météo ne couvre pour l'instant qu'un point régional et une journée. L'OSM, les données socio-économiques et les données d'exploitation réelle seront étudiés comme enrichissements ultérieurs.

Les fichiers très volumineux, notamment `stop_times.txt`, `shapes.txt` et le fichier OSM `.pbf`, sont exclus du dépôt GitHub par [.gitignore](.gitignore) et restent disponibles localement.

## Prochaine étape

Construire la table analytique des départs par arrêt, date, ligne et période horaire, puis établir une baseline avant de tester un modèle prédictif avec une séparation temporelle entre entraînement et test.