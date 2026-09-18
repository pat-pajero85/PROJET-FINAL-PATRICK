"""API locale de consultation et de gestion des donnees GTFS."""

from __future__ import annotations

import hmac
import os
import sqlite3
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Path as FastAPIPath, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parent.parent
DATABASE = Path(os.getenv("GTFS_DATABASE", ROOT / "data" / "database" / "gtfs_pays_loire.sqlite"))
API_KEY = os.getenv("GTFS_API_KEY")

TAGS_METADATA = [
    {"name": "system", "description": "Verification de disponibilite de l API."},
    {"name": "stops", "description": "Arrets GTFS et operations CRUD."},
    {"name": "catalogue", "description": "Referentiels GTFS en lecture seule."},
    {"name": "analytics", "description": "Indicateurs d offre issus des vues SQL."},
]

app = FastAPI(
    title="API GTFS Pays de la Loire",
    description=(
        "Acces HTTP aux donnees GTFS nettoyees et aux indicateurs d'offre. "
        "Les schemas JSON sont valides avec Pydantic."
    ),
    version="1.0.0",
    contact={"name": "Projet Data Analyst"},
    openapi_tags=TAGS_METADATA,
)


class StopPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_name: str = Field(min_length=1, max_length=255)
    stop_lat: float = Field(ge=-90, le=90)
    stop_lon: float = Field(ge=-180, le=180)
    location_type: int = Field(default=0, ge=0, le=4)
    wheelchair_boarding: int | None = Field(default=None, ge=0, le=2)
    coordinate_status: str = Field(pattern="^(within_pdl_bbox|outside_pdl_bbox|invalid_coordinate)$")


class StopCreate(StopPayload):
    stop_id: str = Field(min_length=1, max_length=100)


class StopUpdate(StopPayload):
    pass


class StopPatch(BaseModel):
    # Les champs restent optionnels pour permettre un PATCH partiel.
    model_config = ConfigDict(extra="forbid")

    stop_name: str | None = Field(default=None, min_length=1, max_length=255)
    stop_lat: float | None = Field(default=None, ge=-90, le=90)
    stop_lon: float | None = Field(default=None, ge=-180, le=180)
    location_type: int | None = Field(default=None, ge=0, le=4)
    wheelchair_boarding: int | None = Field(default=None, ge=0, le=2)
    coordinate_status: str | None = Field(
        default=None,
        pattern="^(within_pdl_bbox|outside_pdl_bbox|invalid_coordinate)$",
    )

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "StopPatch":
        # Une valeur absente signifie "ne pas modifier" ; null ne doit pas
        # être transmis aux colonnes SQLite qui sont obligatoires.
        if any(value is None for value in self.model_dump(exclude_unset=True).values()):
            raise ValueError("Les champs envoyes dans un PATCH ne peuvent pas etre nuls.")
        return self


class Stop(StopCreate):
    pass


class Route(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: str
    agency_id: str
    route_short_name: str | None
    route_long_name: str
    route_type: int


class Agency(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agency_id: str
    agency_name: str
    agency_timezone: str


class Departure(BaseModel):
    service_date: str
    stop_id: str
    stop_name: str
    planned_departures: int
    route_count: int
    first_departure_seconds: int | None
    last_departure_seconds: int | None


def get_connection() -> Generator[sqlite3.Connection, None, None]:
    if not DATABASE.exists():
        raise HTTPException(status_code=503, detail="La base SQLite est introuvable.")
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    # SQLite désactive les clés étrangères par connexion : on les réactive ici.
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def require_write_access(x_api_key: str | None = Header(default=None)) -> None:
    """Protège les mutations si une cle API est configuree dans l'environnement."""
    if API_KEY is not None and (
        x_api_key is None or not hmac.compare_digest(x_api_key, API_KEY)
    ):
        raise HTTPException(status_code=401, detail="Cle API absente ou invalide.")


def row_as_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def handle_integrity_error(error: sqlite3.IntegrityError) -> None:
    message = str(error).lower()
    if "unique" in message or "primary key" in message:
        raise HTTPException(status_code=409, detail="Cette ressource existe deja.") from error
    if "foreign key" in message:
        raise HTTPException(
            status_code=409,
            detail="La ressource est encore referencee ou une reference est inconnue.",
        ) from error
    raise HTTPException(status_code=422, detail="La base a refuse les donnees transmises.") from error


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Retourne le point d entree et le lien vers la documentation interactive."""
    return {
        "message": "API GTFS Pays de la Loire",
        "documentation": "/docs",
    }


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Verifie que l API repond et que SQLite est disponible."""
    if not DATABASE.exists():
        raise HTTPException(status_code=503, detail="La base SQLite est introuvable.")
    try:
        # Un SELECT 1 distingue une base réellement accessible d'un simple fichier présent.
        with sqlite3.connect(DATABASE, timeout=2) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail="La base SQLite est indisponible.") from error
    return {"status": "ok", "database": DATABASE.name}


@app.get("/api/v1/stops", response_model=list[Stop], tags=["stops"])
def list_stops(
    name: str | None = Query(default=None, min_length=1, description="Recherche dans le nom."),
    coordinate_status: str | None = Query(default=None, description="Statut geographique."),
    limit: int = Query(default=100, ge=1, le=1000, description="Nombre maximal de resultats."),
    offset: int = Query(default=0, ge=0, description="Nombre de resultats a ignorer."),
    connection: sqlite3.Connection = Depends(get_connection),
) -> list[dict[str, Any]]:
    # Les valeurs utilisateur restent dans parameters pour éviter l'injection SQL.
    clauses: list[str] = []
    parameters: list[Any] = []
    if name:
        clauses.append("stop_name LIKE ? ESCAPE '\\'")
        parameters.append(f"%{name.replace('%', r'%').replace('_', r'_')}%")
    if coordinate_status:
        clauses.append("coordinate_status = ?")
        parameters.append(coordinate_status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, "
        f"wheelchair_boarding, coordinate_status FROM stop {where} "
        "ORDER BY stop_id LIMIT ? OFFSET ?",
        [*parameters, limit, offset],
    ).fetchall()
    return [row_as_dict(row) for row in rows]


@app.get("/api/v1/stops/{stop_id}", response_model=Stop, tags=["stops"])
def get_stop(
    stop_id: str = FastAPIPath(..., min_length=1, description="Identifiant GTFS de l arret."),
    connection: sqlite3.Connection = Depends(get_connection),
) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM stop WHERE stop_id = ?", (stop_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Arret introuvable.")
    return row_as_dict(row)


@app.post(
    "/api/v1/stops",
    response_model=Stop,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
    tags=["stops"],
)
def create_stop(payload: StopCreate, connection: sqlite3.Connection = Depends(get_connection)) -> dict[str, Any]:
    try:
        connection.execute(
            "INSERT INTO stop (stop_id, stop_name, stop_lat, stop_lon, location_type, "
            "wheelchair_boarding, coordinate_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                payload.stop_id,
                payload.stop_name,
                payload.stop_lat,
                payload.stop_lon,
                payload.location_type,
                payload.wheelchair_boarding,
                payload.coordinate_status,
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        handle_integrity_error(error)
    return get_stop(payload.stop_id, connection)


@app.put(
    "/api/v1/stops/{stop_id}",
    response_model=Stop,
    dependencies=[Depends(require_write_access)],
    tags=["stops"],
)
def replace_stop(
    payload: StopUpdate,
    stop_id: str = FastAPIPath(..., min_length=1, description="Identifiant GTFS de l arret."),
    connection: sqlite3.Connection = Depends(get_connection),
) -> dict[str, Any]:
    if connection.execute("SELECT 1 FROM stop WHERE stop_id = ?", (stop_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Arret introuvable.")
    values = payload.model_dump()
    # PUT remplace l'ensemble des attributs modifiables, contrairement au PATCH.
    connection.execute(
        "UPDATE stop SET stop_name = ?, stop_lat = ?, stop_lon = ?, location_type = ?, "
        "wheelchair_boarding = ?, coordinate_status = ? WHERE stop_id = ?",
        (*values.values(), stop_id),
    )
    connection.commit()
    return get_stop(stop_id, connection)


@app.patch(
    "/api/v1/stops/{stop_id}",
    response_model=Stop,
    dependencies=[Depends(require_write_access)],
    tags=["stops"],
)
def patch_stop(
    payload: StopPatch,
    stop_id: str = FastAPIPath(..., min_length=1, description="Identifiant GTFS de l arret."),
    connection: sqlite3.Connection = Depends(get_connection),
) -> dict[str, Any]:
    if connection.execute("SELECT 1 FROM stop WHERE stop_id = ?", (stop_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Arret introuvable.")
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="Aucun champ a modifier.")
    assignments = ", ".join(f"{field} = ?" for field in values)
    # Les noms de colonnes viennent du modèle Pydantic ; seules les valeurs sont paramétrées.
    connection.execute(
        f"UPDATE stop SET {assignments} WHERE stop_id = ?",
        (*values.values(), stop_id),
    )
    connection.commit()
    return get_stop(stop_id, connection)


@app.delete(
    "/api/v1/stops/{stop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_write_access)],
    tags=["stops"],
)
def delete_stop(
    stop_id: str = FastAPIPath(..., min_length=1, description="Identifiant GTFS de l arret."),
    connection: sqlite3.Connection = Depends(get_connection),
) -> Response:
    try:
        cursor = connection.execute("DELETE FROM stop WHERE stop_id = ?", (stop_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Arret introuvable.")
        connection.commit()
    except sqlite3.IntegrityError as error:
        handle_integrity_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/routes", response_model=list[Route], tags=["catalogue"])
def list_routes(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    connection: sqlite3.Connection = Depends(get_connection),
) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT route_id, agency_id, route_short_name, route_long_name, route_type "
        "FROM route ORDER BY route_id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [row_as_dict(row) for row in rows]


@app.get("/api/v1/agencies", response_model=list[Agency], tags=["catalogue"])
def list_agencies(connection: sqlite3.Connection = Depends(get_connection)) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT agency_id, agency_name, agency_timezone FROM agency ORDER BY agency_id"
    ).fetchall()
    return [row_as_dict(row) for row in rows]


@app.get(
    "/api/v1/analytics/departures-by-stop-day",
    response_model=list[Departure],
    tags=["analytics"],
)
def departures_by_stop_day(
    service_date: str | None = Query(default=None, pattern=r"^\d{8}$"),
    stop_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    connection: sqlite3.Connection = Depends(get_connection),
) -> list[dict[str, Any]]:
    # Une requête sans filtre déclencherait l'agrégation de plusieurs millions de passages.
    if service_date is None and stop_id is None:
        raise HTTPException(
            status_code=422,
            detail="Fournir service_date ou stop_id pour limiter la requete analytics.",
        )
    if service_date:
        try:
            datetime.strptime(service_date, "%Y%m%d")
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Date de service invalide.") from error
    clauses: list[str] = []
    parameters: list[Any] = []
    if service_date:
        clauses.append("sd.service_date = ?")
        parameters.append(service_date)
    if stop_id:
        clauses.append("st.stop_id = ?")
        parameters.append(stop_id)
    rows = connection.execute(
        # Les filtres sont appliqués avant GROUP BY pour limiter le coût de l'agrégation.
        "SELECT sd.service_date, st.stop_id, s.stop_name, COUNT(*) AS planned_departures, "
        "COUNT(DISTINCT t.route_id) AS route_count, MIN(st.departure_seconds) "
        "AS first_departure_seconds, MAX(st.departure_seconds) AS last_departure_seconds "
        "FROM service_date AS sd "
        "JOIN trip AS t ON t.service_id = sd.service_id "
        "JOIN stop_time AS st ON st.trip_id = t.trip_id "
        "JOIN stop AS s ON s.stop_id = st.stop_id "
        "WHERE sd.exception_type = 1 "
        + ("AND " + " AND ".join(clauses) if clauses else "")
        + " GROUP BY sd.service_date, st.stop_id, s.stop_name "
        "ORDER BY sd.service_date, st.stop_id LIMIT ? OFFSET ?",
        [*parameters, limit, offset],
    ).fetchall()
    return [row_as_dict(row) for row in rows]
