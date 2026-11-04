"""Étape 7 : révision méthodologique de l'analyse et de la prévision de l'offre.

Pourquoi cette étape ? L'audit des étapes 5 et 6 a montré trois problèmes :

1. **Fenêtre de validité du feed.** ``calendar_dates.txt`` va jusqu'en avril 2027, mais l'offre réelle
   n'est planifiée que du 2 avril au 30 juin 2025 (≈ 330 000 départs par jour ouvré), puis s'effondre
   (quelques départs par jour à partir de 2026). Un découpage 80/20 sur toutes les dates plaçait le test
   dans la partie quasi vide : 588 observations, toutes égales à 1.
2. **Créneaux sans service invisibles.** La vue ``v_departures_by_stop_period`` ne contient que les
   créneaux avec au moins un départ : la « plus faible offre » trouvée valait toujours 1. On reconstruit
   ici une grille complète arrêt x date x période, avec 0 quand rien ne passe.
3. **Périmètre et définition d'un départ.** 4 374 gares SNCF hors Pays de la Loire (24 % des départs)
   étaient mêlées à l'offre régionale, et les passages sans montée possible (``pickup_type = 1``,
   406 377 lignes) étaient comptés comme des départs.

Le script lit directement les fichiers GTFS (pas besoin de la base SQLite) et écrit ses résultats dans
``reports/etape7_*``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parent.parent
GTFS = ROOT / "data" / "raw" / "gtfs"
REPORTS = ROOT / "reports"

PERIODES = ["night", "morning_peak", "morning", "midday", "afternoon", "evening_peak", "night_service"]
BORNES_HEURES = [-1, 5, 8, 11, 13, 16, 19, 99]  # mêmes coupures que la vue SQL (6h, 9h, 12h, 14h, 17h, 20h)

# Emprise indicative des Pays de la Loire (identique en esprit au statut "within_pdl_bbox")
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 46.25, 48.6, -2.7, 0.95

FENETRE_DEBUT, FENETRE_FIN = "2025-04-07", "2025-06-29"  # 12 semaines complètes dans la période valide
DEBUT_TEST = "2025-05-26"  # 7 semaines d'entraînement, 5 semaines de test
DEBUT_RECENT = "2025-05-12"  # semaines de référence pour la baseline « calendrier récent »

JOURS_FERIES = pd.to_datetime(["2025-04-21", "2025-05-01", "2025-05-08", "2025-05-29", "2025-06-09"])
PONTS = pd.to_datetime(["2025-05-02", "2025-05-09", "2025-05-30"])
VACANCES_ZONE_B = (pd.Timestamp("2025-04-05"), pd.Timestamp("2025-04-21"))  # printemps 2025, académie de Nantes


# --------------------------------------------------------------------------------------------------
# Construction des données
# --------------------------------------------------------------------------------------------------
def periode_horaire(heures: pd.Series) -> pd.Categorical:
    """Associe une heure GTFS (pouvant dépasser 24) à une période horaire."""
    return pd.cut(heures, bins=BORNES_HEURES, labels=PERIODES)


def departs_par_service(stop_times: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    """Nombre de départs avec montée possible par service x arrêt x période."""
    st = stop_times[stop_times["pickup_type"].fillna(0) != 1].copy()
    st["period"] = periode_horaire(st["departure_time"].str.split(":", n=1).str[0].astype(int))
    par_trip = st.groupby(["trip_id", "stop_id", "period"], observed=True).size().rename("n").reset_index()
    par_trip = par_trip.merge(trips[["trip_id", "service_id"]], on="trip_id", validate="many_to_one")
    return par_trip.groupby(["service_id", "stop_id", "period"], observed=True)["n"].sum().reset_index()


def dates_actives(calendar_dates: pd.DataFrame) -> pd.DataFrame:
    """Dates de circulation de chaque service (exception_type = 1 : service ajouté)."""
    cal = calendar_dates[calendar_dates["exception_type"] == 1][["service_id", "date"]].copy()
    cal["date"] = pd.to_datetime(cal["date"].astype(str), format="%Y%m%d")
    return cal


def departs_par_jour(par_service: pd.DataFrame, cal: pd.DataFrame) -> pd.Series:
    """Total des départs planifiés par date, sur toute la durée du feed."""
    total = par_service.groupby("service_id")["n"].sum().reset_index()
    return total.merge(cal, on="service_id").groupby("date")["n"].sum()


def grille_complete(par_service: pd.DataFrame, cal: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
    """Grille arrêt x date x période sur la fenêtre valide, avec 0 quand aucun départ n'est prévu."""
    debut, fin = pd.Timestamp(FENETRE_DEBUT), pd.Timestamp(FENETRE_FIN)
    cw = cal[(cal["date"] >= debut) & (cal["date"] <= fin)]
    offre = (par_service.merge(cw, on="service_id")
             .groupby(["stop_id", "date", "period"], observed=True)["n"].sum())
    actifs = offre.index.get_level_values("stop_id").unique()
    regionaux = stops.loc[stops["in_pdl"] & stops["stop_id"].isin(actifs), "stop_id"].unique()
    index = pd.MultiIndex.from_product([regionaux, pd.date_range(debut, fin), PERIODES],
                                       names=["stop_id", "date", "period"])
    offre.index = offre.index.set_levels(offre.index.levels[2].astype(str), level=2)
    grille = offre.reindex(index, fill_value=0).rename("departures").reset_index()
    grille["stop_id"] = grille["stop_id"].astype("category")
    grille["period"] = pd.Categorical(grille["period"], categories=PERIODES)
    return ajouter_calendrier(grille)


def ajouter_calendrier(df: pd.DataFrame) -> pd.DataFrame:
    """Variables de calendrier : jour de semaine, férié, pont, vacances scolaires, type de jour."""
    df["dow"] = df["date"].dt.dayofweek
    df["ferie"] = df["date"].isin(JOURS_FERIES)
    df["pont"] = df["date"].isin(PONTS)
    df["vacances"] = df["date"].between(*VACANCES_ZONE_B)
    df["type_jour"] = np.select([df["ferie"] | (df["dow"] == 6), df["dow"] == 5],
                                ["dimanche_ferie", "samedi"], "ouvre")
    return df


# --------------------------------------------------------------------------------------------------
# Prévision : baselines et modèle
# --------------------------------------------------------------------------------------------------
def moyenne(train: pd.DataFrame, cles: list[str], nom: str) -> pd.Series:
    """Moyenne des départs par combinaison de clés sur un jeu d'entraînement."""
    return train.groupby(cles, observed=True)["departures"].mean().rename(nom)


def stats_recentes(src: pd.DataFrame) -> list[pd.Series]:
    """Profils de référence calculés sur une période donnée (jours normaux, samedis, dimanches)."""
    normal = src[~src["ferie"] & ~src["pont"] & ~src["vacances"]]
    return [
        moyenne(normal, ["stop_id", "type_jour", "period"], "r_type"),
        moyenne(normal, ["stop_id", "dow", "period"], "r_dow"),
        moyenne(src[src["type_jour"] == "dimanche_ferie"], ["stop_id", "period"], "r_dim"),
    ]


def joindre(df: pd.DataFrame, series: list[pd.Series]) -> pd.DataFrame:
    """Ajoute des profils de référence comme colonnes (0 si l'arrêt n'avait aucun départ)."""
    for s in series:
        df = df.join(s, on=list(s.index.names))
        df[s.name] = df[s.name].fillna(0)
    return df


def evaluer(y: pd.Series, pred: np.ndarray, masque_ferie: np.ndarray) -> dict:
    """MAE et RMSE globales, sur les jours fériés / ponts et sur les jours normaux."""
    pred = np.asarray(pred)
    return {
        "mae": round(mean_absolute_error(y, pred), 3),
        "rmse": round(mean_squared_error(y, pred) ** 0.5, 3),
        "mae_feries_ponts": round(mean_absolute_error(y[masque_ferie], pred[masque_ferie]), 3),
        "mae_jours_normaux": round(mean_absolute_error(y[~masque_ferie], pred[~masque_ferie]), 3),
    }


def comparer_modeles(g: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Compare 3 baselines et un modèle de gradient boosting sur les 5 semaines de test."""
    split = pd.Timestamp(DEBUT_TEST)
    train, test = g[g["date"] < split], g[g["date"] >= split].copy()
    masque = (test["ferie"] | test["pont"]).to_numpy()
    y = test["departures"]

    # V1 du projet : moyenne par arrêt et période, sans calendrier
    test = joindre(test, [moyenne(train, ["stop_id", "period"], "b_v1")])
    # Calendrier : par type de jour, sur toutes les semaines d'entraînement hors vacances
    test = joindre(test, [moyenne(train[~train["vacances"]], ["stop_id", "type_jour", "period"], "b_cal")])
    # Calendrier récent : mêmes profils, mais calculés sur les 2 dernières semaines d'entraînement
    recent = train[train["date"] >= pd.Timestamp(DEBUT_RECENT)]
    test = joindre(test, stats_recentes(recent))
    test["b_cal_recent"] = np.where(test["type_jour"] == "dimanche_ferie", test["r_dim"], test["r_type"])

    # Ajustement des ponts : rapport offre d'un pont / jour ouvré normal, appris par période sur les ponts
    # de l'entraînement (2 et 9 mai), puis appliqué aux ponts du test (30 mai)
    normal = train[(train["type_jour"] == "ouvre") & ~train["pont"] & ~train["vacances"]]
    ratio = (train[train["pont"]].groupby("period", observed=True)["departures"].mean()
             / normal.groupby("period", observed=True)["departures"].mean()).rename("ratio_pont")
    test = test.join(ratio, on="period")
    test["b_cal_recent_ponts"] = np.where(test["pont"], test["b_cal_recent"] * test["ratio_pont"], test["b_cal_recent"])

    # Modèle : HistGradientBoosting (perte de Poisson, adaptée aux comptages) sur les profils récents
    def jeu(cible_debut: str, cible_fin: str, ref_debut: str, ref_fin: str) -> pd.DataFrame:
        cible = g[g["date"].between(pd.Timestamp(cible_debut), pd.Timestamp(cible_fin))].copy()
        ref = g[g["date"].between(pd.Timestamp(ref_debut), pd.Timestamp(ref_fin))]
        return joindre(cible, stats_recentes(ref))

    fit = pd.concat([jeu("2025-04-28", "2025-05-11", "2025-04-07", "2025-04-27"),
                     jeu("2025-05-12", "2025-05-25", "2025-04-22", "2025-05-11")])
    features = ["r_type", "r_dow", "r_dim", "dow", "ferie", "pont"]
    for d in (fit, test):
        d["per"] = d["period"].cat.codes
    features.append("per")
    modele = HistGradientBoostingRegressor(loss="poisson", max_iter=300, max_leaf_nodes=31, random_state=42)
    modele.fit(fit[features].astype(float), fit["departures"])
    test["hgb"] = modele.predict(test[features].astype(float))

    resultats = {
        "fenetre": [FENETRE_DEBUT, FENETRE_FIN],
        "entrainement": [FENETRE_DEBUT, str((split - pd.Timedelta(days=1)).date())],
        "test": [DEBUT_TEST, FENETRE_FIN],
        "observations_test": int(len(test)),
        "part_creneaux_sans_depart_test": round(float((y == 0).mean()), 3),
        "modeles": {
            "baseline_v1_arret_periode": evaluer(y, test["b_v1"], masque),
            "baseline_calendrier": evaluer(y, test["b_cal"], masque),
            "baseline_calendrier_recent": evaluer(y, test["b_cal_recent"], masque),
            "baseline_calendrier_recent_ponts": evaluer(y, test["b_cal_recent_ponts"], masque),
            "hist_gradient_boosting": evaluer(y, test["hgb"], masque),
        },
    }
    resultats["modele_retenu"] = min(resultats["modeles"], key=lambda k: resultats["modeles"][k]["mae"])
    return resultats, test


# --------------------------------------------------------------------------------------------------
# Analyses descriptives et figures
# --------------------------------------------------------------------------------------------------
def faible_desserte(g: pd.DataFrame, stops: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Offre d'un jour ouvré normal (semaines récentes) par arrêt, réseau et période."""
    ref = g[(g["date"] >= pd.Timestamp(DEBUT_RECENT)) & (g["date"] < pd.Timestamp(DEBUT_TEST))
            & (g["type_jour"] == "ouvre") & ~g["ferie"] & ~g["pont"]]
    jours = ref["date"].nunique()
    par_arret = (ref.groupby("stop_id", observed=True)["departures"].sum() / jours).rename("departs_jour").reset_index()
    par_arret["reseau"] = par_arret["stop_id"].astype(str).str.split(":").str[0]
    par_arret = par_arret.merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id")
    pointe = (ref[ref["period"] == "morning_peak"].groupby("stop_id", observed=True)["departures"].sum() / jours)
    par_arret["departs_pointe_matin"] = par_arret["stop_id"].map(pointe).fillna(0)

    par_reseau = par_arret.groupby("reseau").agg(
        arrets=("stop_id", "size"),
        departs_jour_median=("departs_jour", "median"),
        part_moins_de_5_departs=("departs_jour", lambda s: round(float((s < 5).mean()), 3)),
        part_sans_pointe_matin=("departs_pointe_matin", lambda s: round(float((s == 0).mean()), 3)),
    ).sort_values("arrets", ascending=False)

    synthese = {
        "jours_ouvres_de_reference": int(jours),
        "arrets_regionaux_actifs": int(len(par_arret)),
        "departs_jour_median": float(par_arret["departs_jour"].median()),
        "part_arrets_moins_de_5_departs_jour": round(float((par_arret["departs_jour"] < 5).mean()), 3),
        "part_arrets_sans_depart_pointe_matin": round(float((par_arret["departs_pointe_matin"] == 0).mean()), 3),
        "par_reseau": par_reseau.reset_index().to_dict(orient="records"),
    }
    return synthese, par_arret


def figures(par_jour: pd.Series, par_arret: pd.DataFrame, resultats: dict, test: pd.DataFrame) -> None:
    """Quatre figures : horizon du feed, carte de l'offre, comparaison des modèles, prévision vs réalité."""
    fig, ax = plt.subplots(figsize=(10, 3.2))
    par_jour.resample("W").mean().clip(lower=1).plot(ax=ax, color="#4C72B0", label="départs planifiés")
    ax.axvspan(pd.Timestamp(FENETRE_DEBUT), pd.Timestamp(FENETRE_FIN), color="#55A868", alpha=0.15,
               label="fenêtre retenue")
    ax.set(title="Départs planifiés par jour (moyenne hebdomadaire) sur toute la durée du feed",
           ylabel="départs / jour", xlabel="")
    ax.set_yscale("log"); ax.set_ylim(bottom=1); ax.legend()
    fig.tight_layout(); fig.savefig(REPORTS / "etape7_horizon_feed.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6.5))
    d = par_arret.sort_values("departs_jour")
    sc = ax.scatter(d["stop_lon"], d["stop_lat"], c=np.log10(d["departs_jour"] + 1), s=3, cmap="viridis")
    cb = fig.colorbar(sc, ax=ax, shrink=0.8)
    cb.set_ticks(np.log10(np.array([1, 5, 20, 100, 500]) + 1)); cb.set_ticklabels(["1", "5", "20", "100", "500"])
    cb.set_label("départs par jour ouvré")
    ax.set(title="Offre par arrêt un jour ouvré (Pays de la Loire)", xlabel="longitude", ylabel="latitude")
    ax.set_aspect(1.45)
    fig.tight_layout(); fig.savefig(REPORTS / "etape7_carte_offre.png", dpi=120); plt.close(fig)

    noms = {"baseline_v1_arret_periode": "Baseline V1\n(arrêt × période)", "baseline_calendrier": "Calendrier",
            "baseline_calendrier_recent": "Calendrier\nrécent", "baseline_calendrier_recent_ponts": "Calendrier récent\n+ ponts",
            "hist_gradient_boosting": "Gradient\nboosting"}
    m = pd.DataFrame(resultats["modeles"]).T.rename(index=noms)
    fig, ax = plt.subplots(figsize=(9, 3.5))
    m[["mae_jours_normaux", "mae_feries_ponts"]].plot.bar(ax=ax, rot=0, color=["#4C72B0", "#C44E52"])
    ax.set(title="Erreur absolue moyenne sur 5 semaines de test (départs par arrêt et période)", ylabel="MAE")
    ax.legend(["jours normaux", "fériés et ponts"])
    fig.tight_layout(); fig.savefig(REPORTS / "etape7_comparaison_modeles.png", dpi=120); plt.close(fig)

    jour = test.groupby("date")[["departures", "b_v1", "b_cal_recent_ponts"]].sum()
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(jour.index, jour["departures"], "k-", lw=2, label="offre planifiée réelle")
    ax.plot(jour.index, jour["b_cal_recent_ponts"], "--", color="#55A868", label="calendrier récent + ponts")
    ax.plot(jour.index, jour["b_v1"], ":", color="#C44E52", label="baseline V1")
    ax.set(title="Total régional prévu vs réel par jour (période de test)", ylabel="départs / jour")
    ax.legend(fontsize=8); fig.autofmt_xdate()
    fig.tight_layout(); fig.savefig(REPORTS / "etape7_prevision_vs_reel.png", dpi=120); plt.close(fig)


def main() -> None:
    stop_times = pd.read_csv(GTFS / "stop_times.txt", usecols=["trip_id", "departure_time", "stop_id", "pickup_type"],
                             dtype={"trip_id": "string", "stop_id": "string", "departure_time": "string"})
    trips = pd.read_csv(GTFS / "trips.txt", usecols=["trip_id", "service_id"], dtype=str)
    cal = dates_actives(pd.read_csv(GTFS / "calendar_dates.txt", dtype={"service_id": str}))
    stops = pd.read_csv(GTFS / "stops.txt", dtype={"stop_id": str})
    stops["in_pdl"] = stops["stop_lat"].between(LAT_MIN, LAT_MAX) & stops["stop_lon"].between(LON_MIN, LON_MAX)

    par_service = departs_par_service(stop_times, trips)
    par_jour = departs_par_jour(par_service, cal)
    g = grille_complete(par_service, cal, stops)

    actifs = stops[stops["stop_id"].isin(par_service["stop_id"].unique())]
    hors = actifs[~actifs["in_pdl"]]
    perimetre = {
        "passages_total": int(len(stop_times)),
        "passages_sans_montee_exclus": int((stop_times["pickup_type"].fillna(0) == 1).sum()),
        "arrets_actifs": int(len(actifs)),
        "arrets_hors_pays_de_la_loire": int(len(hors)),
        "dont_sncf": int(hors["stop_id"].str.startswith("SNCF").sum()),
        "arrets_coordonnees_nulles": int((actifs["stop_lat"] == 0).sum()),
        "grille_observations": int(len(g)),
        "part_creneaux_sans_depart": round(float((g["departures"] == 0).mean()), 3),
    }
    fenetre_valide = par_jour[par_jour > 0.25 * par_jour.max()]
    horizon = {
        "date_min_calendar": str(par_jour.index.min().date()),
        "date_max_calendar": str(par_jour.index.max().date()),
        "premiere_date_offre_complete": str(fenetre_valide.index.min().date()),
        "derniere_date_offre_complete": str(fenetre_valide.index.max().date()),
        "departs_jour_ouvre_median_avril_juin_2025": int(par_jour["2025-04-07":"2025-06-27"][
            par_jour["2025-04-07":"2025-06-27"].index.dayofweek < 5].median()),
        "departs_jour_median_2026": int(par_jour["2026"].median()) if "2026" in par_jour.index.year.astype(str) else 0,
    }
    resultats, test = comparer_modeles(g)
    desserte, par_arret = faible_desserte(g, stops)
    figures(par_jour, par_arret, resultats, test)

    sortie = {"perimetre": perimetre, "horizon_feed": horizon, "prevision": resultats, "faible_desserte": desserte}
    (REPORTS / "etape7_offre_fenetre_valide.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=2),
                                                             encoding="utf-8")
    par_arret.sort_values("departs_jour").to_csv(REPORTS / "etape7_offre_par_arret.csv", index=False)
    print(json.dumps({k: sortie[k] for k in ["perimetre", "horizon_feed"]}, ensure_ascii=False, indent=1))
    print(json.dumps(resultats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
