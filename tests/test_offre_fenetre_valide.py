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
