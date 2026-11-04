"""Tests de l'étape 7 sur de petites données synthétiques (pas besoin du GTFS complet)."""
from importlib import import_module

import pandas as pd

etape7 = import_module("src.08_offre_fenetre_valide")


def test_periode_horaire_respecte_les_coupures_et_les_heures_apres_minuit() -> None:
    heures = pd.Series([0, 5, 6, 8, 9, 12, 14, 17, 20, 25])
    attendu = ["night", "night", "morning_peak", "morning_peak", "morning", "midday",
               "afternoon", "evening_peak", "night_service", "night_service"]
    assert list(etape7.periode_horaire(heures)) == attendu


def test_les_passages_sans_montee_ne_sont_pas_des_departs() -> None:
    stop_times = pd.DataFrame({
        "trip_id": ["T1", "T1", "T1"],
        "stop_id": ["A", "B", "C"],
        "departure_time": ["08:00:00", "08:10:00", "08:20:00"],
        "pickup_type": [0, 0, 1],
    })
    trips = pd.DataFrame({"trip_id": ["T1"], "service_id": ["S"]})
    res = etape7.departs_par_service(stop_times, trips)
    assert set(res["stop_id"]) == {"A", "B"}
    assert res["n"].sum() == 2


def test_la_grille_contient_les_creneaux_sans_depart() -> None:
    par_service = pd.DataFrame({"service_id": ["S"], "stop_id": ["A"],
                                "period": pd.Categorical(["morning_peak"], categories=etape7.PERIODES), "n": [3]})
    cal = pd.DataFrame({"service_id": ["S"], "date": [pd.Timestamp("2025-04-08")]})
    stops = pd.DataFrame({"stop_id": ["A"], "in_pdl": [True]})
    g = etape7.grille_complete(par_service, cal, stops)
    nb_jours = len(pd.date_range(etape7.FENETRE_DEBUT, etape7.FENETRE_FIN))
    assert len(g) == nb_jours * len(etape7.PERIODES)
    assert g["departures"].sum() == 3
    assert (g["departures"] == 0).sum() == len(g) - 1


def test_calendrier_traite_les_feries_comme_des_dimanches() -> None:
    df = pd.DataFrame({"date": pd.to_datetime(["2025-05-01", "2025-05-03", "2025-05-05", "2025-05-30"])})
    df = etape7.ajouter_calendrier(df)
    assert list(df["type_jour"]) == ["dimanche_ferie", "samedi", "ouvre", "ouvre"]
    assert list(df["pont"]) == [False, False, False, True]


def test_profil_offre_moyenne_par_jour_et_ignore_les_feries() -> None:
    dates = pd.to_datetime(["2025-05-05", "2025-05-06", "2025-05-10", "2025-05-11", "2025-05-08"])
    df = pd.DataFrame({"date": dates.repeat(len(etape7.PERIODES)),
                       "period": pd.Categorical(etape7.PERIODES * len(dates), categories=etape7.PERIODES)})
    df["departures"] = 0
    df.loc[df["period"] == "morning_peak", "departures"] = [10, 20, 4, 1, 99]  # le 8 mai (férié) est exclu
    df = etape7.ajouter_calendrier(df)
    synthese, table = etape7.profil_offre(df)
    assert synthese["jours_normaux"] == {"dimanche_ferie": 1, "ouvre": 2, "samedi": 1}
    assert synthese["departs_regionaux_par_jour"] == {"ouvre": 15, "samedi": 4, "dimanche_ferie": 1}
    assert table.loc["morning_peak", "ouvre"] == 15
    assert synthese["baisse_samedi_vs_ouvre"] == round(1 - 4 / 15, 3)
