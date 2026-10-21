"""Estrategia de indices de MongoDB y diagnostico con ``explain()``.

El proyecto agrupa los indices en tres bloques explicitos:

* ``BASIC_INDEXES`` (8): filtros y ordenamientos de un solo campo.
* ``ADVANCED_INDEXES`` (5): compuestos, unicos y de cobertura.
* ``PYTHON_INDEXES`` (5): indices adicionales que crea la aplicacion desde
  Python para las agregaciones y consultas del monitor.

Todos los indices son idempotentes: ``create_index`` no falla si ya existen.
El modulo tambien puede ejecutarse como herramienta::

    uv run python -m backend.indexes --explain --drop

``--drop`` elimina unicamente los indices administrados por este modulo para
poder comparar el plan de ejecucion antes y despues de crearlos. ``--explain``
imprime ``totalDocsExamined``, ``totalKeysExamined`` y el indice usado por las
cinco consultas representativas del proyecto. Nunca elimina el indice ``_id_``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from .config import get_settings
from .exceptions import ConfigurationError, MongoDBError


@dataclass(frozen=True)
class IndexSpec:
    """Definicion declarativa de un indice administrado por la aplicacion."""

    collection: str
    keys: list[tuple[str, int]]
    options: dict[str, Any] = field(default_factory=dict)
    group: str = "basic"

    @property
    def name(self) -> str:
        return str(self.options.get("name", ""))


BASIC_INDEXES: list[IndexSpec] = [
    IndexSpec("observaciones", [("serie_id", ASCENDING)], {"name": "obs_serie_id"}),
    IndexSpec("observaciones", [("fecha", DESCENDING)], {"name": "obs_fecha_desc"}),
    IndexSpec("observaciones", [("anio", ASCENDING)], {"name": "obs_anio"}),
    IndexSpec("observaciones", [("mes", ASCENDING)], {"name": "obs_mes"}),
    IndexSpec("snapshots", [("creado_en", DESCENDING)], {"name": "snap_creado_en"}),
    IndexSpec("snapshots", [("estado", ASCENDING)], {"name": "snap_estado"}),
    IndexSpec("ingesta_log", [("creado_en", DESCENDING)], {"name": "ing_creado_en"}),
    IndexSpec("series_catalogo", [("activa", ASCENDING)], {"name": "cat_activa"}),
]

ADVANCED_INDEXES: list[IndexSpec] = [
    # Idempotencia de la ingesta y consulta "ultima observacion por serie".
    IndexSpec(
        "observaciones",
        [("serie_id", ASCENDING), ("fecha", DESCENDING)],
        {"name": "obs_serie_fecha_unique", "unique": True},
        group="advanced",
    ),
    # Estadisticas por serie y periodo sin traer documentos a Python.
    IndexSpec(
        "observaciones",
        [("serie_id", ASCENDING), ("anio", DESCENDING), ("mes", DESCENDING)],
        {"name": "obs_serie_periodo"},
        group="advanced",
    ),
    # Indice de cobertura para KPIs del periodo (fecha + serie + valor).
    IndexSpec(
        "observaciones",
        [("fecha", DESCENDING), ("serie_id", ASCENDING), ("valor", ASCENDING)],
        {"name": "obs_fecha_serie_valor_cover"},
        group="advanced",
    ),
    # Un run_id por ejecucion de ingesta.
    IndexSpec(
        "ingesta_log",
        [("run_id", ASCENDING)],
        {"name": "ing_run_id_unique", "unique": True},
        group="advanced",
    ),
    # Listado de snapshots con alertas, del mas reciente al mas antiguo.
    IndexSpec(
        "snapshots",
        [("estado", ASCENDING), ("hasta", DESCENDING)],
        {"name": "snap_estado_hasta"},
        group="advanced",
    ),
]

PYTHON_INDEXES: list[IndexSpec] = [
    # Agrupaciones por anio/mes/serie para estadisticas descriptivas.
    IndexSpec(
        "observaciones",
        [("anio", ASCENDING), ("mes", ASCENDING), ("serie_id", ASCENDING), ("valor", ASCENDING)],
        {"name": "obs_periodo_serie_valor"},
        group="python",
    ),
    # Alertas: solo se indexan variaciones positivas, un subconjunto pequeno.
    IndexSpec(
        "observaciones",
        [("var_pct", DESCENDING)],
        {
            "name": "obs_var_pct_positiva",
            "partialFilterExpression": {"var_pct": {"$gt": 0}},
        },
        group="python",
    ),
    # Busqueda de un snapshot por periodo determinista.
    IndexSpec(
        "snapshots",
        [("hasta", DESCENDING), ("_id", DESCENDING)],
        {"name": "snap_hasta_id"},
        group="python",
    ),
    # Historial de ingestas ordenado y filtrable por run_id.
    IndexSpec(
        "ingesta_log",
        [("creado_en", DESCENDING), ("run_id", DESCENDING)],
        {"name": "ing_creado_run"},
        group="python",
    ),
    # Catalogo por paquete y estado activo.
    IndexSpec(
        "series_catalogo",
        [("paquetes", ASCENDING), ("activa", ASCENDING)],
        {"name": "cat_paquete_activa"},
        group="python",
    ),
]

ALL_INDEXES: list[IndexSpec] = BASIC_INDEXES + ADVANCED_INDEXES + PYTHON_INDEXES

# Indices de versiones anteriores que ya no forman parte de la estrategia.
LEGACY_INDEX_KEYS: dict[str, list[list[tuple[str, int]]]] = {
    "snapshots": [[("desde", DESCENDING), ("hasta", DESCENDING)]],
}


def _drop_legacy_indexes(database: Any) -> None:
    for collection_name, key_patterns in LEGACY_INDEX_KEYS.items():
        collection = database[collection_name]
        for name, info in collection.index_information().items():
            if name == "_id_":
                continue
            if list(info.get("key", [])) in key_patterns:
                collection.drop_index(name)


def _replace_legacy_index(database: Any, spec: IndexSpec) -> None:
    """Elimina indices con las mismas llaves pero nombre distinto.

    MongoDB no falla si el mismo patron de llaves ya existe con otro nombre:
    simplemente conserva el indice anterior. Para que el inventario sea
    predecible, migramos esos indices legacy al nombre administrado.
    """
    collection = database[spec.collection]
    existing = collection.index_information()
    for name, info in existing.items():
        if name == "_id_" or name == spec.name:
            continue
        if list(info.get("key", [])) == list(spec.keys):
            collection.drop_index(name)


def _migrate_conflicting_index(
    database: Any, spec: IndexSpec, error: OperationFailure
) -> bool:
    """Reintenta despues de resolver un conflicto de nombre u opciones."""
    if error.code not in (85, 86):
        return False
    collection = database[spec.collection]
    existing = collection.index_information()
    if spec.name in existing or any(
        list(info.get("key", [])) == list(spec.keys)
        for info in existing.values()
    ):
        _replace_legacy_index(database, spec)
        if spec.name in collection.index_information():
            collection.drop_index(spec.name)
        collection.create_index(spec.keys, **spec.options)
        return True
    return False


def ensure_all_indexes(database: Any) -> int:
    """Crea los 18 indices administrados y devuelve cuantos se declararon."""
    try:
        _drop_legacy_indexes(database)
        for spec in ALL_INDEXES:
            _replace_legacy_index(database, spec)
            if spec.name in database[spec.collection].index_information():
                continue
            try:
                database[spec.collection].create_index(spec.keys, **spec.options)
            except OperationFailure as error:
                if not _migrate_conflicting_index(database, spec, error):
                    raise
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible crear indices en MongoDB: {error}") from error
    return len(ALL_INDEXES)


def drop_managed_indexes(database: Any) -> list[str]:
    """Elimina solo los indices declarados aqui (nunca ``_id_``)."""
    dropped: list[str] = []
    try:
        _drop_legacy_indexes(database)
        for spec in ALL_INDEXES:
            collection = database[spec.collection]
            existing = collection.index_information()
            for name, info in existing.items():
                if name == "_id_":
                    continue
                if name == spec.name or list(info.get("key", [])) == list(spec.keys):
                    collection.drop_index(name)
                    dropped.append(name)
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible eliminar los indices: {error}") from error
    return dropped


def index_inventory(database: Any) -> dict[str, list[dict[str, Any]]]:
    """Devuelve los indices realmente existentes agrupados por coleccion."""
    inventory: dict[str, list[dict[str, Any]]] = {}
    collections = sorted({spec.collection for spec in ALL_INDEXES})
    try:
        for collection in collections:
            inventory[collection] = [
                {"name": name, "keys": list(info.get("key", []))}
                for name, info in database[collection].index_information().items()
            ]
    except PyMongoError as error:
        raise MongoDBError(f"No fue posible leer los indices: {error}") from error
    return inventory


@dataclass(frozen=True)
class ExplainQuery:
    """Consulta representativa que se diagnostica con ``explain()``."""

    name: str
    collection: str
    description: str
    query: dict[str, Any] | None = None
    sort: list[tuple[str, int]] | None = None
    limit: int | None = None
    pipeline: list[dict[str, Any]] | None = None


def _iso_days_ago(days: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)


def explain_queries() -> list[ExplainQuery]:
    """Las cinco consultas criticas del monitor (una por operacion)."""
    start = _iso_days_ago(30)
    end = datetime.now(UTC).replace(tzinfo=None)
    return [
        ExplainQuery(
            "ultima_observacion_por_serie",
            "observaciones",
            "Ultimo dato de una serie (ingesta incremental y resumen).",
            query={"serie_id": "SF43718"},
            sort=[("fecha", DESCENDING)],
            limit=1,
        ),
        ExplainQuery(
            "observaciones_por_periodo",
            "observaciones",
            "Historico paginado de una serie en un rango de fechas.",
            query={"serie_id": "SF43718", "fecha": {"$gte": start, "$lte": end}},
            sort=[("fecha", DESCENDING)],
        ),
        ExplainQuery(
            "kpis_por_serie",
            "observaciones",
            "Aggregation pipeline que calcula los KPIs del snapshot.",
            pipeline=[
                {"$match": {"fecha": {"$gte": start, "$lte": end}}},
                {"$group": {"_id": "$serie_id", "promedio": {"$avg": "$valor"}}},
                {"$sort": {"_id": ASCENDING}},
            ],
        ),
        ExplainQuery(
            "snapshots_recientes",
            "snapshots",
            "Listado de snapshots del mas reciente al mas antiguo.",
            query={},
            sort=[("hasta", DESCENDING), ("_id", DESCENDING)],
        ),
        ExplainQuery(
            "historial_ingestas",
            "ingesta_log",
            "Historial de ejecuciones por fecha de creacion.",
            query={"creado_en": {"$gte": start, "$lte": end}},
            sort=[("creado_en", DESCENDING), ("run_id", DESCENDING)],
        ),
    ]


def _iter_plan_stages(plan: Any) -> Iterable[dict[str, Any]]:
    if isinstance(plan, dict):
        if "stage" in plan:
            yield plan
        for value in plan.values():
            yield from _iter_plan_stages(value)
    elif isinstance(plan, list):
        for item in plan:
            yield from _iter_plan_stages(item)


def _find_winning_plans(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        plan = payload.get("winningPlan")
        if isinstance(plan, dict):
            yield plan
        for key, value in payload.items():
            if key in {"executionStats", "allPlansExecution"}:
                continue
            yield from _find_winning_plans(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _find_winning_plans(item)


def _find_execution_stats(explain: Any) -> dict[str, Any]:
    if isinstance(explain, dict):
        stats = explain.get("executionStats")
        if isinstance(stats, dict) and "totalDocsExamined" in stats:
            return stats
        for value in explain.values():
            found = _find_execution_stats(value)
            if found:
                return found
    elif isinstance(explain, list):
        for item in explain:
            found = _find_execution_stats(item)
            if found:
                return found
    return {}


def summarize_explain(explain: dict[str, Any]) -> dict[str, Any]:
    """Extrae las metricas utiles de un ``explain(executionStats)``."""
    stats = _find_execution_stats(explain)
    winning_plans = list(_find_winning_plans(explain))
    stages = [
        stage
        for plan in winning_plans
        for stage in _iter_plan_stages(plan)
    ]
    if not stages:
        stages = list(_iter_plan_stages(explain))
    index_names = sorted({
        str(stage.get("indexName"))
        for stage in stages
        if stage.get("indexName")
    })
    stage_names = [str(stage.get("stage")) for stage in stages if stage.get("stage")]
    return {
        "stage": stage_names[0] if stage_names else None,
        "index": ", ".join(index_names) if index_names else "COLLSCAN",
        "n_returned": stats.get("nReturned"),
        "docs_examined": stats.get("totalDocsExamined"),
        "keys_examined": stats.get("totalKeysExamined"),
        "execution_ms": stats.get("executionTimeMillis"),
    }


def run_explain(database: Any, queries: list[ExplainQuery] | None = None) -> list[dict[str, Any]]:
    """Ejecuta ``explain('executionStats')`` sobre las consultas indicadas."""
    results: list[dict[str, Any]] = []
    for item in queries or explain_queries():
        try:
            collection = database[item.collection]
            if item.pipeline is not None:
                raw = database.command(
                    "explain",
                    {"aggregate": item.collection, "pipeline": item.pipeline, "cursor": {}},
                    verbosity="executionStats",
                )
            else:
                cursor = collection.find(item.query or {})
                if item.sort:
                    cursor = cursor.sort(item.sort)
                if item.limit:
                    cursor = cursor.limit(item.limit)
                raw = cursor.explain()
        except PyMongoError as error:
            results.append({"name": item.name, "error": str(error)})
            continue
        results.append({"name": item.name, "description": item.description, **summarize_explain(raw)})
    return results


def _format_report(rows: list[dict[str, Any]]) -> str:
    header = f"{'consulta':32} {'etapa':16} {'indice':34} {'docs':>8} {'keys':>8} {'ms':>7}"
    lines = [header, "-" * len(header)]
    for row in rows:
        if row.get("error"):
            lines.append(f"{row['name']:32} ERROR: {row['error']}")
            continue
        lines.append(
            f"{row['name']:32} {str(row.get('stage')):16} {str(row.get('index')):34} "
            f"{str(row.get('docs_examined')):>8} {str(row.get('keys_examined')):>8} "
            f"{str(row.get('execution_ms')):>7}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: crea indices y compara ``explain()`` antes/despues."""
    parser = argparse.ArgumentParser(description="Indices y explain() del monitor Banxico.")
    parser.add_argument("--drop", action="store_true", help="Elimina los indices administrados antes de medir.")
    parser.add_argument("--explain", action="store_true", help="Ejecuta explain() antes y despues.")
    parser.add_argument("--json", action="store_true", help="Imprime el resultado en JSON.")
    parser.add_argument("--inventory", action="store_true", help="Muestra solo el inventario de indices.")
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        uri = settings.require_mongodb_uri()
    except ConfigurationError as error:
        print(f"Error: {error}")
        return 2

    client = MongoClient(uri, serverSelectionTimeoutMS=settings.mongodb_timeout_ms)
    try:
        client.admin.command("ping")
        database = client[settings.mongodb_database]

        if args.inventory:
            payload = index_inventory(database)
            print(json.dumps(payload, indent=2, default=str) if args.json else payload)
            return 0

        before = None
        if args.drop:
            dropped = drop_managed_indexes(database)
            if not args.json:
                print(f"Indices eliminados: {len(dropped)}")
        if args.explain:
            before = run_explain(database)

        declared = ensure_all_indexes(database)

        after = run_explain(database) if args.explain else []
        if args.json:
            print(json.dumps({"declared": declared, "before": before, "after": after}, indent=2, default=str))
        else:
            print(f"Indices declarados: {declared}")
            if before is not None:
                print("\nANTES")
                print(_format_report(before))
            if after:
                print("\nDESPUES")
                print(_format_report(after))
            print("\nInventario:")
            for collection, indexes in index_inventory(database).items():
                print(f"  {collection}: {len(indexes)} indices")
        return 0
    except PyMongoError as error:
        print(f"No fue posible conectar con MongoDB: {error}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
