"""API para consultar e ingerir indicadores del SIE de Banxico."""

import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, PyMongoError

load_dotenv()

SERIES_METADATA = [
    {"_id": "SF43718", "titulo": "Pesos por dólar, FIX", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF46410", "titulo": "Euro", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF46406", "titulo": "Yen japonés", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF46407", "titulo": "Libra esterlina", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF60632", "titulo": "Dólar canadiense", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF60648", "titulo": "TIIE a 28 días", "unidad": "Porcentaje", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
]
SERIES_BY_ID = {series["_id"]: series for series in SERIES_METADATA}

app = FastAPI(
    title="Monitor de indicadores Banxico",
    description="API para consultar el catálogo e ingerir series del SIE de Banxico.",
    version="1.0.0",
)


class IngestResponse(BaseModel):
    run_id: str
    nuevos: int
    duplicados: int
    errores: int
    duracion_seg: float
    series: list[dict[str, Any]]


def get_database():
    """Abre MongoDB solo cuando una ruta que lo necesita es llamada."""
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise HTTPException(status_code=503, detail="MONGODB_URI no está configurada.")
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client["banxico_monitor"]
    except PyMongoError as error:
        raise HTTPException(status_code=503, detail=f"No fue posible conectar con MongoDB: {error}") from error


def parse_observations(
    series: dict[str, Any], run_id: str, previous_value: float | None = None
) -> list[dict[str, Any]]:
    """Convierte la respuesta de Banxico al esquema persistido en MongoDB."""
    documents = []
    previous_value = None
    for item in series.get("datos", []):
        try:
            value = float(item.get("dato", "").replace(",", "").strip())
            observation_date = datetime.strptime(item["fecha"], "%d/%m/%Y")
        except (AttributeError, KeyError, TypeError, ValueError):
            continue

        variation = 0.0 if previous_value in (None, 0) else round(
            ((value - previous_value) / previous_value) * 100, 4
        )
        previous_value = value
        date_key = observation_date.strftime("%Y-%m-%d")
        documents.append({
            "_id": f"{series.get('idSerie')}|{date_key}",
            "serie_id": series.get("idSerie"),
            "fecha": observation_date,
            "anio": observation_date.year,
            "mes": observation_date.month,
            "valor": value,
            "var_pct": variation,
            "run_id": run_id,
        })
    return documents


def fetch_series(
    series_ids: list[str], start_date: date, end_date: date
) -> list[dict[str, Any]]:
    token = os.getenv("BANXICO_API")
    if not token:
        raise HTTPException(status_code=503, detail="BANXICO_API no está configurada.")
    if start_date > end_date:
        return []

    requested_series = ",".join(series_ids)
    url = (
        "https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
        f"{requested_series}/datos/{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"
    )
    try:
        response = requests.get(url, headers={"Bmx-Token": token}, timeout=20)
        response.raise_for_status()
        return response.json().get("bmx", {}).get("series", [])
    except (requests.RequestException, ValueError) as error:
        raise HTTPException(status_code=502, detail=f"Error al consultar Banxico: {error}") from error


@app.get("/health", tags=["Sistema"])
def health() -> dict[str, str]:
    """Comprueba que el proceso de la API está disponible."""
    return {"status": "ok"}


@app.get("/series", tags=["Catálogo"])
def list_series() -> list[dict[str, Any]]:
    """Devuelve las series configuradas para el paquete mercados."""
    return SERIES_METADATA


@app.get("/series/{series_id}", tags=["Catálogo"])
def get_series(series_id: str) -> dict[str, Any]:
    """Devuelve los metadatos de una serie por su identificador Banxico."""
    series = SERIES_BY_ID.get(series_id)
    if series is None:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    return series


@app.get("/estadisticas/{series_id}", tags=["Datos"])
def get_series_statistics(
    series_id: str,
    start_date: date = Query(default=date(2024, 1, 1), description="Fecha inicial inclusiva."),
    end_date: date = Query(default_factory=date.today, description="Fecha final inclusiva."),
) -> dict[str, Any]:
    """Calcula estadísticas descriptivas con los datos consultados a Banxico."""
    metadata = SERIES_BY_ID.get(series_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")

    series_data = fetch_series([series_id], start_date, end_date)
    series = next((item for item in series_data if item.get("idSerie") == series_id), {})
    observations = pd.DataFrame(series.get("datos", []), columns=["fecha", "dato"])
    observations["fecha"] = pd.to_datetime(observations["fecha"], format="%d/%m/%Y", errors="coerce")
    values = observations["dato"].astype("string").str.replace(",", "", regex=False).str.strip()
    observations["valor"] = pd.to_numeric(values, errors="coerce")
    observations = observations.dropna(subset=["fecha", "valor"])

    description = observations["valor"].describe()
    statistics = {
        name: None if pd.isna(value) else round(float(value), 6)
        for name, value in description.items()
    }
    return {
        "serie": metadata,
        "periodo": {"desde": start_date.isoformat(), "hasta": end_date.isoformat()},
        "total_observaciones": len(observations),
        "estadisticas": statistics,
    }


@app.get("/observaciones", tags=["Datos"])
def list_observations(
    series_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    """Consulta observaciones persistidas, opcionalmente filtradas por serie."""
    if series_id and series_id not in SERIES_BY_ID:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    database = get_database()
    query = {"serie_id": series_id} if series_id else {}
    observations = database.observaciones.find(query, {"_id": 0}).sort("fecha", -1).limit(limit)
    return list(observations)


@app.post("/ingestas", response_model=IngestResponse, status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def create_ingestion(
    start_date: date = Query(default=date(2024, 1, 1), description="Fecha inicial inclusiva."),
    end_date: date = Query(default_factory=date.today, description="Fecha final inclusiva."),
) -> IngestResponse:
    """Descarga las series de Banxico y las inserta de forma idempotente en MongoDB."""
    started_at = time.time()
    run_id = datetime.now(timezone.utc).isoformat()
    database = get_database()
    for metadata in SERIES_METADATA:
        database.series_catalogo.update_one({"_id": metadata["_id"]}, {"$setOnInsert": metadata}, upsert=True)

    total_new = total_duplicates = total_errors = 0
    series_log = []
    for metadata in SERIES_METADATA:
        series_id = metadata["_id"]
        latest = database.observaciones.find_one(
            {"serie_id": series_id},
            {"fecha": 1, "valor": 1, "_id": 0},
            sort=[("fecha", -1)],
        )
        next_date = start_date
        if latest and isinstance(latest.get("fecha"), datetime):
            next_date = max(next_date, latest["fecha"].date() + timedelta(days=1))

        if next_date > end_date:
            series_log.append({
                "serie_id": series_id,
                "nuevos": 0,
                "duplicados": 0,
                "consultada": False,
                "motivo": "sin datos nuevos",
            })
            continue

        series_data = fetch_series([series_id], next_date, end_date)
        series = next((item for item in series_data if item.get("idSerie") == series_id), {})
        previous_value = latest.get("valor") if latest else None
        documents = parse_observations(series, run_id, previous_value)
        new_count = duplicate_count = 0
        if documents:
            try:
                result = database.observaciones.insert_many(documents, ordered=False)
                new_count = len(result.inserted_ids)
            except BulkWriteError as error:
                new_count = error.details.get("nInserted", 0)
                duplicate_count = len(error.details.get("writeErrors", []))
            except PyMongoError:
                total_errors += 1
            database.series_catalogo.update_one(
                {"_id": series_id},
                {"$set": {"ultima_fecha": max(document["fecha"] for document in documents), "activa": True}},
            )
        total_new += new_count
        total_duplicates += duplicate_count
        series_log.append({
            "serie_id": series_id,
            "nuevos": new_count,
            "duplicados": duplicate_count,
            "consultada": True,
            "desde": next_date.isoformat(),
            "hasta": end_date.isoformat(),
        })

    duration = round(time.time() - started_at, 2)
    database.ingesta_log.insert_one({
        "run_id": run_id,
        "resumen": {"nuevos": total_new, "duplicados": total_duplicates, "errores": total_errors, "duracion_seg": duration},
        "series": series_log,
    })
    return IngestResponse(run_id=run_id, nuevos=total_new, duplicados=total_duplicates, errores=total_errors, duracion_seg=duration, series=series_log)