# Check-up complet - Etape 4 Analyse exploratoire et veille

## 1. Date et perimetre

- Date du controle : 18 septembre 2026
- Document controle : `docs/07_analyse_exploratoire_et_veille.md`
- Script controle : `src/06_analyse_exploratoire.py`
- Resultats controles : fichiers CSV et PNG dans `reports/`
- Donnees : vue SQLite `v_departures_by_stop_period`

Le controle porte sur la couverture du brief, la reproductibilite du script, les
resultats statistiques, les visualisations, l'interpretation et la veille IA /
Big Data.

## 2. Verdict global

**Etape 4 partiellement validee, avec quelques corrections documentaires a
faire avant remise.**

Le coeur analytique est realise : trois hypotheses sont testees, les indicateurs
sont calcules, les correlations sont presentes et les trois visualisations sont
produites. La veille est egalement structuree autour d'un sujet coherent avec le
projet.

Le document n'est toutefois pas totalement finalise : les objectifs et la
methode sont vides, l'interpretation de H1 est incomplete, aucune source de
veille n'est citee et le controle Markdown signale trois doubles lignes vides.

## 3. Resultats des controles

### 3.1 Analyse H1 - periodes horaires

Le fichier `reports/etape4_h1_offre_par_periode.csv` contient 7 periodes et
4340584 observations au total.

| Periode | Departs moyens planifies |
| --- | ---: |
| Nuit | 2,54 |
| Pointe matin | 8,48 |
| Matinee | 7,78 |
| Midi | 5,16 |
| Apres-midi | 8,11 |
| Pointe soir | 8,82 |
| Soiree | 6,76 |

**Conclusion : H1 est confirmee.** L'offre moyenne est la plus elevee en
pointe du soir et en pointe du matin. Elle est la plus faible la nuit et
baisse egalement autour de midi.

Visualisation presente : `reports/etape4_h1_offre_par_periode.png`.

### 3.2 Analyse H2 - jours ouvres et week-end

Le fichier `reports/etape4_h2_offre_jours_ouvres_weekend.csv` contient :

- jours ouvres : 7,78 departs moyens, pour 3373399 observations ;
- week-end : 6,02 departs moyens, pour 967185 observations.

La baisse moyenne du week-end est d'environ 22,7 % par rapport aux jours
ouvres.

**Conclusion : H2 est confirmee.** L'offre planifiee est plus importante les
jours ouvres.

Visualisation presente : `reports/etape4_h2_offre_jours_ouvres_weekend.png`.

### 3.3 Analyse H3 - lignes desservantes et departs

Le fichier `reports/etape4_h3_correlation_lignes_departs.csv` contient :

- correlation de Pearson : `0,4036` ;
- correlation de Spearman : `0,4319` ;
- nombre d'observations : `4340584`.

**Conclusion : H3 est partiellement confirmee.** La relation est positive et
moderee : les arrets desservis par plusieurs lignes ont generalement davantage
de departs, mais le nombre de lignes ne suffit pas a expliquer seul le niveau
d'offre. Cette relation ne prouve pas une causalite.

Visualisation presente : `reports/etape4_h3_correlation_lignes_departs.png`.

## 4. Controle du script

Le fichier `src/06_analyse_exploratoire.py` ne presente aucune erreur detectee
par le controle de code.

Le script evite de charger les 4 millions d'observations en memoire : les
agregations H1 et H2 sont effectuees dans SQLite et H3 est calculee a partir
d'un regroupement compact. Cette optimisation corrige le risque initial de
`disk I/O error` observe lors d'une lecture massive depuis OneDrive.

Les resultats CSV et PNG attendus sont presents dans `reports/`, ce qui confirme
qu'une execution reussie a deja ete realisee. Une nouvelle execution n'a pas
pu etre relancee par le terminal PowerShell de ce controle, celui-ci ne
resolvant pas correctement le chemin de l'environnement virtuel ; ce point est
un probleme d'environnement de terminal, pas une erreur detectee dans le code.

## 5. Controle du document Markdown

### Points conformes

- les trois hypotheses sont formulees et traitees ;
- les trois graphiques sont inseres avec des chemins relatifs corrects ;
- les resultats H2 et H3 sont interpretes ;
- les limites des donnees GTFS sont mentionnees ;
- la veille est liee au sujet des transports publics ;
- Airflow n'est pas presente comme une technologie utilisee dans le projet.

### Points a corriger

- `## 1. Objectifs` est vide ;
- `## 2. Donnees et methode` est vide ;
- `### Interprétation` de H1 est vide ;
- la veille ne contient pas de references ou de liens vers des sources ;
- le controle Markdown signale trois occurrences de lignes vides consecutives ;
- la phrase sur la demande potentielle le week-end doit rester presentee comme
  une interpretation, et non comme un fait mesure, car aucune frequentation
  reelle n'est disponible.

## 6. Controle de la veille

Le sujet choisi est pertinent : l'IA et le Big Data pour l'optimisation des
transports publics. Les trois axes sont coherents :

1. prevision de la demande ;
2. optimisation des itineraires et des horaires ;
3. exploitation des donnees temps reel.

La synthese distingue correctement les possibilites technologiques des limites
reelles du projet. En revanche, une veille autonome doit citer ses sources.
Il faut ajouter au minimum deux sources fiables, avec leur titre, organisme,
date de consultation et lien.

## 7. Plan d'action avant remise

1. Completer les objectifs et la methode dans le document principal.
2. Ajouter l'interpretation quantitative de H1.
3. Ajouter au moins deux sources de veille fiables.
4. Supprimer les lignes vides consecutives signalees par le controle Markdown.
5. Relancer le script depuis Git Bash pour confirmer la regeneration des trois
   CSV et des trois PNG.
6. Verifier l'aperçu Markdown avec `Ctrl + Shift + V`.

## 8. Conclusion

L'etape 4 est solide sur le plan analytique et repond deja a la majeure partie
du travail attendu : analyse statistique, correlations, tendances et
visualisations Python sont realisees.

Le statut recommande est **quasi validee**. Les corrections restantes sont
principalement documentaires et formelles. Elles sont necessaires pour rendre
le travail complet et presentable, mais elles ne remettent pas en cause les
resultats statistiques obtenus.
