"""Conexión y operaciones con MongoDB para el monitor de indicadores Banxico."""

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import BulkWriteError, PyMongoError

from .banxico_client import SERIES_METADATA
from .config import get_settings
from .exceptions import ConfigurationError, MongoDBError
from .indexes import ensure_all_indexes


_client: MongoClient | None = None
_indexes_ready: set[str] = set()


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
        if settings.mongodb_database not in _indexes_ready:
            ensure_indexes(database)
            _indexes_ready.add(settings.mongodb_database)
        return database
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible conectar con MongoDB: {error}") from error


def close_database() -> None:
    """Cierra el cliente MongoDB reutilizado por la aplicacion."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
    _indexes_ready.clear()


def ensure_indexes(database: Any) -> None:
    """Crea los 8 indices basicos, 5 avanzados y 5 desde Python."""
    ensure_all_indexes(database)


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


def _extreme_movement(want_max: bool) -> dict[str, Any]:
    """Expresion ``$reduce`` que elige el mayor/menor cambio diario."""
    keep_current = (
        {"$lte": ["$$this.pct", "$$value.pct"]}
        if want_max
        else {"$gte": ["$$this.pct", "$$value.pct"]}
    )
    return {
        "$reduce": {
            "input": "$movimientos",
            "initialValue": None,
            "in": {
                "$cond": [
                    {
                        "$or": [
                            {"$eq": ["$$this.pct", None]},
                            {
                                "$and": [
                                    {"$ne": ["$$value", None]},
                                    keep_current,
                                ]
                            },
                        ]
                    },
                    "$$value",
                    "$$this",
                ]
            },
        }
    }


def _kpi_pipeline(
    start_date: datetime,
    end_date: datetime,
    business_days: int,
    series_id: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregation pipeline real ($match/$sort/$group/$project) para KPIs.

    El servidor colapsa fechas duplicadas, calcula extremos, cambios diarios,
    mediana, volatilidad y cobertura por serie. Python solo recibe un documento
    agregado por serie, no el historico completo.
    """
    match: dict[str, Any] = {
        "fecha": {"$gte": start_date, "$lte": end_date},
        "valor": {"$type": "number"},
    }
    if series_id:
        match["serie_id"] = series_id

    movimientos = {
        "$map": {
            "input": {"$range": [1, {"$size": "$valores"}]},
            "as": "i",
            "in": {
                "$let": {
                    "vars": {
                        "actual": {"$arrayElemAt": ["$valores", "$$i"]},
                        "anterior": {
                            "$arrayElemAt": ["$valores", {"$subtract": ["$$i", 1]}]
                        },
                        "punto": {"$arrayElemAt": ["$puntos", "$$i"]},
                    },
                    "in": {
                        "fecha": "$$punto.fecha",
                        "valor": "$$actual",
                        "delta": {"$subtract": ["$$actual", "$$anterior"]},
                        "pct": {
                            "$cond": [
                                {"$eq": ["$$anterior", 0]},
                                None,
                                {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                {"$subtract": ["$$actual", "$$anterior"]},
                                                "$$anterior",
                                            ]
                                        },
                                        100,
                                    ]
                                },
                            ]
                        },
                    },
                }
            },
        }
    }

    pendiente = {
        "$cond": [
            {"$gt": [{"$size": "$movimientos"}, 0]},
            {
                "$divide": [
                    {
                        "$sum": {
                            "$map": {
                                "input": "$movimientos",
                                "as": "movimiento",
                                "in": "$$movimiento.delta",
                            }
                        }
                    },
                    {"$size": "$movimientos"},
                ]
            },
            0.0,
        ]
    }

    return [
        {"$match": match},
        {"$sort": {"serie_id": ASCENDING, "fecha": ASCENDING, "_id": ASCENDING}},
        {
            "$group": {
                "_id": {"serie_id": "$serie_id", "fecha": "$fecha"},
                "valor": {"$last": "$valor"},
                "var_pct": {"$last": "$var_pct"},
            }
        },
        {"$sort": {"_id.serie_id": ASCENDING, "_id.fecha": ASCENDING}},
        {
            "$group": {
                "_id": "$_id.serie_id",
                "puntos": {
                    "$push": {
                        "fecha": "$_id.fecha",
                        "valor": "$valor",
                        "var_pct": "$var_pct",
                    }
                },
                "valores": {"$push": "$valor"},
                "valor_inicial": {"$first": "$valor"},
                "fecha_inicial": {"$first": "$_id.fecha"},
                "valor_final": {"$last": "$valor"},
                "fecha_final": {"$last": "$_id.fecha"},
                "ultimo_var_pct": {"$last": "$var_pct"},
                "min": {"$min": "$valor"},
                "max": {"$max": "$valor"},
                "promedio": {"$avg": "$valor"},
                "desviacion_estandar": {"$stdDevSamp": "$valor"},
                "observaciones_validas": {"$sum": 1},
            }
        },
        {
            "$project": {
                "serie_id": "$_id",
                "puntos": 1,
                "valores": 1,
                "movimientos": movimientos,
                "valor_inicial": 1,
                "fecha_inicial": 1,
                "valor_final": 1,
                "fecha_final": 1,
                "ultimo_var_pct": 1,
                "min": 1,
                "max": 1,
                "promedio": 1,
                "desviacion_estandar": 1,
                "observaciones_validas": 1,
            }
        },
        {
            "$project": {
                "serie_id": 1,
                "valor_inicial": 1,
                "fecha_inicial": 1,
                "valor_final": 1,
                "fecha_final": 1,
                "ultimo_var_pct": 1,
                "min": 1,
                "max": 1,
                "promedio": 1,
                "desviacion_estandar": 1,
                "observaciones_validas": 1,
                "movimientos": 1,
                "pendiente": pendiente,
                "dias_alza": {
                    "$size": {
                        "$filter": {
                            "input": "$movimientos",
                            "as": "movimiento",
                            "cond": {"$gt": ["$$movimiento.delta", 0]},
                        }
                    }
                },
                "dias_baja": {
                    "$size": {
                        "$filter": {
                            "input": "$movimientos",
                            "as": "movimiento",
                            "cond": {"$lt": ["$$movimiento.delta", 0]},
                        }
                    }
                },
                "dias_sin_cambio": {
                    "$size": {
                        "$filter": {
                            "input": "$movimientos",
                            "as": "movimiento",
                            "cond": {"$eq": ["$$movimiento.delta", 0]},
                        }
                    }
                },
                "volatilidad_diaria_pct": {
                    "$stdDevSamp": {
                        "$map": {
                            "input": "$movimientos",
                            "as": "movimiento",
                            "in": "$$movimiento.pct",
                        }
                    }
                },
                "mediana": {
                    "$round": [
                        {
                            "$let": {
                                "vars": {
                                    "ordenados": {
                                        "$sortArray": {"input": "$valores", "sortBy": 1}
                                    }
                                },
                                "in": {
                                    "$let": {
                                        "vars": {
                                            "n": {"$size": "$$ordenados"},
                                            "mitad": {
                                                "$floor": {
                                                    "$divide": [{"$size": "$$ordenados"}, 2]
                                                }
                                            },
                                        },
                                        "in": {
                                            "$cond": [
                                                {"$eq": [{"$mod": ["$$n", 2]}, 1]},
                                                {
                                                    "$arrayElemAt": [
                                                        "$$ordenados",
                                                        "$$mitad",
                                                    ]
                                                },
                                                {
                                                    "$divide": [
                                                        {
                                                            "$add": [
                                                                {
                                                                    "$arrayElemAt": [
                                                                        "$$ordenados",
                                                                        {
                                                                            "$subtract": [
                                                                                "$$mitad",
                                                                                1,
                                                                            ]
                                                                        },
                                                                    ]
                                                                },
                                                                {
                                                                    "$arrayElemAt": [
                                                                        "$$ordenados",
                                                                        "$$mitad",
                                                                    ]
                                                                },
                                                            ]
                                                        },
                                                        2,
                                                    ]
                                                },
                                            ]
                                        },
                                    }
                                },
                            }
                        },
                        6,
                    ]
                },
                "fecha_min": {
                    "$let": {
                        "vars": {
                            "punto": {
                                "$arrayElemAt": [
                                    {
                                        "$filter": {
                                            "input": "$puntos",
                                            "as": "punto",
                                            "cond": {"$eq": ["$$punto.valor", "$min"]},
                                        }
                                    },
                                    0,
                                ]
                            }
                        },
                        "in": "$$punto.fecha",
                    }
                },
                "fecha_max": {
                    "$let": {
                        "vars": {
                            "punto": {
                                "$arrayElemAt": [
                                    {
                                        "$filter": {
                                            "input": "$puntos",
                                            "as": "punto",
                                            "cond": {"$eq": ["$$punto.valor", "$max"]},
                                        }
                                    },
                                    0,
                                ]
                            }
                        },
                        "in": "$$punto.fecha",
                    }
                },
                "mayor_subida": _extreme_movement(True),
                "mayor_caida": _extreme_movement(False),
            }
        },
        {
            "$project": {
                "_id": 0,
                "serie_id": 1,
                "valor_inicial": {"$round": ["$valor_inicial", 6]},
                "fecha_inicial": 1,
                "valor_final": {"$round": ["$valor_final", 6]},
                "fecha_final": 1,
                "ultimo_var_pct": {"$ifNull": ["$ultimo_var_pct", 0.0]},
                "min": {"$round": ["$min", 6]},
                "fecha_min": 1,
                "max": {"$round": ["$max", 6]},
                "fecha_max": 1,
                "rango": {"$round": [{"$subtract": ["$max", "$min"]}, 6]},
                "promedio": {"$round": ["$promedio", 6]},
                "mediana": 1,
                "desviacion_estandar": {
                    "$ifNull": [{"$round": ["$desviacion_estandar", 6]}, 0.0]
                },
                "volatilidad_diaria_pct": {
                    "$ifNull": [{"$round": ["$volatilidad_diaria_pct", 6]}, 0.0]
                },
                "dias_alza": 1,
                "dias_baja": 1,
                "dias_sin_cambio": 1,
                "cambio_absoluto": {
                    "$round": [{"$subtract": ["$valor_final", "$valor_inicial"]}, 6]
                },
                "var_periodo_pct": {
                    "$cond": [
                        {"$eq": ["$valor_inicial", 0]},
                        None,
                        {
                            "$round": [
                                {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                {
                                                    "$subtract": [
                                                        "$valor_final",
                                                        "$valor_inicial",
                                                    ]
                                                },
                                                "$valor_inicial",
                                            ]
                                        },
                                        100,
                                    ]
                                },
                                6,
                            ]
                        },
                    ]
                },
                "var_ultimo_dia_pct": {
                    "$let": {
                        "vars": {
                            "ultimo": {"$arrayElemAt": ["$movimientos", -1]}
                        },
                        "in": {
                            "$ifNull": [{"$round": ["$$ultimo.pct", 6]}, 0.0]
                        },
                    }
                },
                "mayor_subida_pct": {
                    "$ifNull": [{"$round": ["$mayor_subida.pct", 6]}, 0.0]
                },
                "fecha_mayor_subida": "$mayor_subida.fecha",
                "mayor_caida_pct": {
                    "$ifNull": [{"$round": ["$mayor_caida.pct", 6]}, 0.0]
                },
                "fecha_mayor_caida": "$mayor_caida.fecha",
                "tendencia": {
                    "$cond": [
                        {
                            "$or": [
                                {"$eq": ["$promedio", 0]},
                                {"$eq": ["$promedio", None]},
                                {
                                    "$lte": [
                                        {"$abs": "$pendiente"},
                                        {
                                            "$multiply": [
                                                {"$abs": "$promedio"},
                                                0.0001,
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                        "estable",
                        {
                            "$cond": [
                                {"$gt": ["$pendiente", 0]},
                                "ascendente",
                                "descendente",
                            ]
                        },
                    ]
                },
                "observaciones_validas": 1,
                "dias_habiles_esperados": {"$literal": business_days},
                "cobertura_pct": {
                    "$round": [
                        {
                            "$min": [
                                100.0,
                                {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                "$observaciones_validas",
                                                {"$literal": business_days},
                                            ]
                                        },
                                        100,
                                    ]
                                },
                            ]
                        },
                        2,
                    ]
                },
                "distancia_promedio_pct": {
                    "$cond": [
                        {"$eq": ["$promedio", 0]},
                        0.0,
                        {
                            "$round": [
                                {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                {
                                                    "$subtract": [
                                                        "$valor_final",
                                                        "$promedio",
                                                    ]
                                                },
                                                "$promedio",
                                            ]
                                        },
                                        100,
                                    ]
                                },
                                6,
                            ]
                        },
                    ]
                },
                "cambio_puntos_porcentuales": {
                    "$cond": [
                        {"$eq": ["$serie_id", "SF60648"]},
                        {"$round": [{"$subtract": ["$valor_final", "$valor_inicial"]}, 6]},
                        None,
                    ]
                },
                "cambio_puntos_base": {
                    "$cond": [
                        {"$eq": ["$serie_id", "SF60648"]},
                        {
                            "$round": [
                                {
                                    "$multiply": [
                                        {"$subtract": ["$valor_final", "$valor_inicial"]},
                                        100,
                                    ]
                                },
                                4,
                            ]
                        },
                        None,
                    ]
                },
            }
        },
        {"$sort": {"serie_id": ASCENDING}},
    ]


def aggregate_series_metrics(
    database: Any,
    start_date: datetime,
    end_date: datetime,
    business_days: int,
    series_id: str | None = None,
) -> list[dict[str, Any]]:
    """Calcula KPIs por serie con un aggregation pipeline en MongoDB."""
    pipeline = _kpi_pipeline(start_date, end_date, business_days, series_id)
    try:
        return list(database.observaciones.aggregate(pipeline, allowDiskUse=True))
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible calcular los KPIs en MongoDB: {error}") from error


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
