"""Conexión y operaciones con MongoDB para el monitor de indicadores Banxico."""

import os
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient
from pymongo.errors import BulkWriteError, PyMongoError

from .banxico_client import SERIES_METADATA
from .config import get_settings
from .exceptions import ConfigurationError, MongoDBError


_client: MongoClient | None = None


def get_database() -> Any:
    """Abre MongoDB solo cuando una ruta que lo necesita es llamada."""
    global _client
    settings = get_settings()
    try:
        mongo_uri = settings.require_mongodb_uri()
    except ConfigurationError as error:
        raise MongoDBError(str(error)) from error
    try:
        if _client is None:
            _client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
            )
        _client.admin.command("ping")
        database = _client[settings.mongodb_database]
        ensure_indexes(database)
        return database
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible conectar con MongoDB: {error}") from error


def close_database() -> None:
    """Cierra el cliente MongoDB reutilizado por la aplicacion."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def ensure_indexes(database: Any) -> None:
    """Crea los indices requeridos de forma repetible."""
    try:
        database.observaciones.create_index([("serie_id", 1), ("fecha", -1)])
        database.observaciones.create_index([("fecha", -1)])
        database.ingesta_log.create_index([("run_id", 1)], unique=True)
        database.ingesta_log.create_index([("creado_en", -1)])
        snapshots = getattr(database, "snapshots", None)
        if snapshots is not None:
            snapshots.create_index([("desde", -1), ("hasta", -1)])
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible crear indices en MongoDB: {error}") from error


def save_snapshot(database: Any, snapshot: dict[str, Any]) -> None:
    """Guarda o reemplaza un snapshot por su identificador determinista."""
    try:
        database.snapshots.replace_one(
            {"_id": snapshot["_id"]},
            snapshot,
            upsert=True,
        )
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible guardar el snapshot: {error}") from error


def get_snapshot(database: Any, snapshot_id: str) -> dict[str, Any] | None:
    try:
        return database.snapshots.find_one({"_id": snapshot_id})
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible consultar el snapshot: {error}") from error


def list_snapshots(
    database: Any,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    try:
        total = database.snapshots.count_documents({})
        snapshots = database.snapshots.find({}).sort(
            [("hasta", -1), ("_id", -1)]
        ).skip(skip).limit(limit)
        return list(snapshots), total
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible listar snapshots: {error}") from error


def seed_catalogo(database: Any) -> None:
    """Inserta las series del catálogo de forma idempotente."""
    for metadata in SERIES_METADATA:
        try:
            database.series_catalogo.update_one(
                {"_id": metadata["_id"]},
                {"$set": metadata},
                upsert=True,
            )
        except PyMongoError as error:
            raise MongoDBError(f"No fue posible actualizar el catalogo: {error}") from error


def insert_observations(database: Any, documents: list[dict[str, Any]]) -> tuple[int, int]:
    """Inserta observaciones en la colección 'observaciones', devolviendo (nuevos, duplicados)."""
    if not documents:
        return 0, 0
    try:
        result = database.observaciones.insert_many(documents, ordered=False)
        return len(result.inserted_ids), 0
    except BulkWriteError as error:
        details = error.details or {}
        write_errors = details.get("writeErrors", [])
        non_duplicate_errors = [item for item in write_errors if item.get("code") != 11000]
        if non_duplicate_errors:
            raise MongoDBError(f"Error al insertar observaciones: {error}") from error
        return details.get("nInserted", 0), len(write_errors)
    except Exception as error:
        raise MongoDBError(f"Error al insertar observaciones: {error}") from error


def update_catalogo_latest(database: Any, series_id: str, documents: list[dict[str, Any]]) -> None:
    """Actualiza la última fecha y marca activa en la colección 'series_catalogo'."""
    if not documents:
        return
    max_date = max(document["fecha"] for document in documents)
    try:
        database.series_catalogo.update_one(
            {"_id": series_id},
            {"$set": {"ultima_fecha": max_date, "activa": True}},
        )
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible actualizar el catalogo: {error}") from error


def save_ingestion_log(database: Any, run_id: str, resumen: dict[str, Any], series: list[dict[str, Any]]) -> None:
    """Guarda el registro de la ingesta en la colección 'ingesta_log'."""
    try:
        database.ingesta_log.insert_one({
            "run_id": run_id,
            "creado_en": datetime.now(UTC),
            "resumen": resumen,
            "series": series,
        })
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible guardar el registro de ingesta: {error}") from error


def get_latest_observation(database: Any, series_id: str) -> dict[str, Any] | None:
    """Obtiene la última observación de una serie, sin el _id."""
    try:
        return database.observaciones.find_one(
            {"serie_id": series_id},
            {"fecha": 1, "valor": 1, "_id": 0},
            sort=[("fecha", -1)],
        )
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible consultar observaciones: {error}") from error


def get_earliest_observation(database: Any, series_id: str) -> dict[str, Any] | None:
    """Obtiene la primera observacion persistida de una serie."""
    try:
        return database.observaciones.find_one(
            {"serie_id": series_id},
            {"fecha": 1, "valor": 1, "_id": 0},
            sort=[("fecha", 1)],
        )
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible consultar observaciones: {error}") from error


def list_observations(
    database: Any,
    series_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    """Consulta observaciones con filtros y paginacion por offset."""
    query: dict[str, Any] = {}
    if series_id:
        query["serie_id"] = series_id
    if start_date or end_date:
        query["fecha"] = {}
        if start_date:
            query["fecha"]["$gte"] = start_date
        if end_date:
            query["fecha"]["$lte"] = end_date
    try:
        total = database.observaciones.count_documents(query)
        observations = database.observaciones.find(query).sort(
            [("fecha", -1), ("_id", -1)]
        ).skip(skip).limit(limit)
        return list(observations), total
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible consultar observaciones: {error}") from error


def list_all_observations(
    database: Any,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Obtiene todas las observaciones del periodo para calculos internos."""
    query = {"fecha": {"$gte": start_date, "$lte": end_date}}
    try:
        return list(database.observaciones.find(query).sort(
            [("serie_id", 1), ("fecha", 1), ("_id", 1)]
        ))
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible consultar todas las observaciones: {error}") from error


def list_ingestion_logs(
    database: Any,
    run_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    """Consulta logs de ingesta con filtros y paginacion."""
    query: dict[str, Any] = {}
    if run_id:
        query["run_id"] = run_id
    if start_date or end_date:
        query["creado_en"] = {}
        if start_date:
            query["creado_en"]["$gte"] = start_date
        if end_date:
            query["creado_en"]["$lte"] = end_date
    try:
        total = database.ingesta_log.count_documents(query)
        logs = database.ingesta_log.find(query, {"_id": 0}).sort(
            [("creado_en", -1), ("run_id", -1)]
        ).skip(skip).limit(limit)
        return list(logs), total
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible consultar logs de ingesta: {error}") from error
