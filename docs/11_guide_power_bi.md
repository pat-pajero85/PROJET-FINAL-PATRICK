# Construire le tableau de bord Power BI

Retour au [README](../README.md). Durée : environ 45 minutes dans Power BI Desktop.

Les données viennent de l'étape 7 : le script `src/08_offre_fenetre_valide.py` écrit six tables dans
`reports/powerbi/` (séparateur `;`, virgule décimale). Le tableau de bord se sauvegarde dans
`reports/DASHBOARD.pbix`.

| Fichier | Une ligne = | Sert à |
|---|---|---|
| `arrets.csv` | un arrêt régional actif (7 654) | carte, indicateurs de faible desserte, liste des arrêts |
| `reseaux.csv` | un réseau | comparaison des réseaux |
| `profil_horaire.csv` | une période horaire × un type de jour | profil de l'offre |
| `prevision_par_jour.csv` | un jour de la période de test | prévision et offre réelle |
| `modeles.csv` | une méthode de prévision | comparaison des 5 méthodes |
| `offre_par_jour_feed.csv` | un jour du calendrier du feed | courbe de l'audit (fenêtre valide) |

## 1. Importer les données

1. **Accueil › Obtenir les données › Texte/CSV**, puis choisir `reports/powerbi/arrets.csv`.
2. Vérifier l'aperçu : délimiteur **Point-virgule**, et `departs_jour` affiché avec des décimales
   (4,0 ; 3,0…). Cliquer sur **Charger**.
3. Répéter pour les cinq autres fichiers.
4. Si un nombre s'affiche mal (par exemple 47090012 au lieu de 47,09) : **Transformer les données**,
   clic droit sur la colonne › **Modifier le type › Utilisation des paramètres régionaux** › Nombre décimal,
   Français (France).

Les tables sont indépendantes : il n'y a **aucune relation** à créer.

## 2. Préparer le modèle

Dans la vue **Données** :

- `arrets` : colonne `latitude` › **Outils de colonne › Catégorie de données › Latitude** ; idem pour
  `longitude` (Longitude).
- `profil_horaire` : sélectionner `periode` › **Trier par colonne › ordre_periode** ; `type_jour` › trier par
  `ordre_type_jour`.
- `modeles` : `methode` › trier par `ordre`.
- `reseaux` : `part_moins_de_5_departs` et `part_sans_pointe_matin` › format **Pourcentage**.

## 3. Créer les mesures

Sélectionner la table `arrets`, puis **Nouvelle mesure** pour chacune, dans l'ordre (les suivantes utilisent
`[Arrêts]`). Avec Power BI en français, les arguments sont séparés par **`;`** ; si Power BI est en
anglais, remplacer `;` par `,`.

```dax
Arrêts = COUNTROWS ( arrets )

% arrêts < 5 départs =
DIVIDE ( CALCULATE ( [Arrêts] ; arrets[departs_jour] < 5 ) ; [Arrêts] )

% sans départ 6 h-9 h =
DIVIDE ( CALCULATE ( [Arrêts] ; arrets[sans_depart_pointe_matin] = "Oui" ) ; [Arrêts] )

Départs médians par arrêt = MEDIAN ( arrets[departs_jour] )
```

Dans la table `modeles` :

```dax
MAE retenue = CALCULATE ( MIN ( modeles[mae] ) ; modeles[retenue] = "Oui" )

Erreur divisée par =
DIVIDE ( CALCULATE ( MIN ( modeles[mae] ) ; modeles[ordre] = 1 ) ; [MAE retenue] )
```

Formats : les deux mesures en % en **Pourcentage, 0 décimale** ; `MAE retenue` en 3 décimales ;
`Erreur divisée par` en 0 décimale.

## 4. Page 1 « Où l'offre est-elle la plus faible ? »

Renommer la page (double-clic sur l'onglet). Disposition conseillée :

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Titre                                                                 │
├──────────┬──────────┬──────────┬──────────┬───────────────────────────┤
│ Arrêts   │ % < 5    │ % sans   │ Médiane  │ Segments : réseau,        │
│          │ départs  │ 6 h-9 h  │          │ classe de desserte        │
├──────────┴──────────┴──────────┴──────────┼───────────────────────────┤
│                                           │ Barres 100 % : classes    │
│ Carte des arrêts                          │ de desserte par réseau    │
│ (couleur = classe de desserte)            ├───────────────────────────┤
│                                           │ Tableau : arrêts les      │
│                                           │ moins desservis           │
└───────────────────────────────────────────┴───────────────────────────┘
```

1. **Zone de texte** : « Où l'offre de transport est-elle la plus faible ? Pays de la Loire, jour ouvré,
   mai 2025 ».
2. **4 cartes** (visuel *Carte*) : `Arrêts`, `% arrêts < 5 départs`, `% sans départ 6 h-9 h`,
   `Départs médians par arrêt`. Renommer chaque titre (clic droit sur le champ › *Renommer pour ce visuel*).
   Valeurs attendues : 7 654 ; 34 % ; 20 % ; 9,2.
3. **Carte des arrêts** : visuel **Azure Maps** (ou *Carte*). Latitude = `latitude`, Longitude = `longitude`,
   Légende = `classe_desserte`, Info-bulles = `nom_arret`, `reseau`, `departs_jour`.
   Couleurs conseillées : Très faible `#D97941`, Faible `#F2C29B`, Moyenne `#7FB3C8`, Forte `#176B87`.
   Si les cartes sont désactivées : **Fichier › Options et paramètres › Options › Sécurité › Visuels Carte et
   Carte choroplèthe**. À défaut, un *Nuage de points* (X = longitude, Y = latitude) donne le même rendu.
4. **Histogramme à barres empilées 100 %** : Axe Y = `reseau`, Légende = `classe_desserte`,
   Axe X = `Arrêts`. Filtre du visuel : garder ALEOP, TAN, CHOLETBUS, SNCF, LILAPRESQUILE.
5. **Segments** : un sur `reseau`, un sur `classe_desserte` (style *Vignette* ou *Liste déroulante*).
6. **Tableau** : `nom_arret`, `reseau`, `departs_jour`, `departs_pointe_matin`, trié par `departs_jour`
   croissant. Titre : « Arrêts les moins desservis ».

## 5. Page 2 « Profil de l'offre et prévision »

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Titre                                                                 │
├───────────────────────────────────┬───────────────────────────────────┤
│ Histogramme groupé : départs par  │ Courbes : offre réelle, prévision │
│ heure × période × type de jour    │ retenue et baseline V1 par jour   │
├──────────┬──────────┬─────────────┴───────────────────────────────────┤
│ MAE      │ Erreur   │ Tableau des 5 méthodes (MAE, RMSE, fériés,      │
│ retenue  │ ÷ 11     │ jours normaux), méthode retenue mise en avant   │
└──────────┴──────────┴─────────────────────────────────────────────────┘
```

1. **Histogramme groupé** : Axe X = `periode`, Axe Y = `departs_par_heure` (Somme), Légende = `type_jour`.
   Couleurs : Jour ouvré `#16304A`, Samedi `#176B87`, Dimanche et férié `#D97941`. Titre : « Départs par
   heure : deux pointes en semaine, −73 % le dimanche ».
2. **Graphique en courbes** : Axe X = `date` (choisir `date` et non la *Hiérarchie de dates*),
   Axe Y = `offre_reelle`, `prevision_retenue`, `baseline_v1`. Titre : « La prévision suit l'offre réelle ».
   Mettre `baseline_v1` en pointillés (*Format › Lignes › Série › Style*).
3. **2 cartes** : `MAE retenue` (0,115) et `Erreur divisée par` (11), avec le titre « Erreur divisée par
   rapport à la baseline V1 ».
4. **Tableau** `modeles` : `methode`, `mae`, `rmse`, `mae_feries_ponts`, `mae_jours_normaux`.
   **Mise en forme conditionnelle › Couleur d'arrière-plan** sur `mae` (vert = faible). Trier par `ordre`.

Facultatif, page 3 « Pourquoi seulement avril-juin 2025 ? » : courbe `offre_par_jour_feed`
(Axe X = `date`, Axe Y = `departs_planifies`, **échelle logarithmique** dans *Format › Axe Y*), avec
`dans_fenetre_retenue` en légende.

## 6. Finitions et export

- **Affichage › Thèmes** : un thème sobre ; même police partout ; titres de visuels explicites.
- Vérifier les valeurs attendues (7 654 arrêts ; 34 % ; 20 % ; MAE 0,115).
- **Fichier › Enregistrer sous** › `reports/DASHBOARD.pbix` (remplacer l'ancien fichier vide).
- Faire une capture de chaque page (**Fichier › Exporter › Exporter au format PDF**, ou Win + Maj + S) et
  l'enregistrer en `reports/dashboard_page1.png` et `reports/dashboard_page2.png` : elle sera affichée dans
  le README, car GitHub ne sait pas ouvrir un `.pbix`.
- `git add reports/DASHBOARD.pbix reports/dashboard_page*.png` puis commit et push.
