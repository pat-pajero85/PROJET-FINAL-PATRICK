"""La variable GTFS_DB_PATH permet de placer la base SQLite hors du projet (ex. hors de OneDrive)."""
import importlib
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["src.05_analyse_offre", "src.07_modelisation_risques"])
def test_gtfs_db_path_est_prioritaire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, module: str) -> None:
    cible = tmp_path / "gtfs_pays_loire.sqlite"
    monkeypatch.setenv("GTFS_DB_PATH", str(cible))
    mod = importlib.reload(importlib.import_module(module))
    assert mod.DATABASE == cible


def test_chemin_par_defaut_dans_le_projet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GTFS_DB_PATH", raising=False)
    monkeypatch.delenv("GTFS_DATABASE", raising=False)
    mod = importlib.reload(importlib.import_module("src.05_analyse_offre"))
    assert mod.DATABASE.parts[-3:] == ("data", "database", "gtfs_pays_loire.sqlite")
