"""API para consultar e ingerir indicadores del SIE de Banxico."""

import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time as datetime_time, timedelta
from typing import Annotated, Any, Literal, cast

from fastapi import FastAPI, HTTPException, Query, status

from .banxico_client import (
    SERIES_BY_ID,
    SERIES_METADATA,
    clean_observations,
    fetch_series,
    parse_observations,
)
from .config import get_settings
from .exceptions import BanxicoError, ConfigurationError, MongoDBError
from .mongodb_client import (
    close_database,
    get_database,
    list_ingestion_logs,
    list_observations as query_observations,
    insert_observations,
    save_ingestion_log,
    seed_catalogo,
    update_catalogo_latest,
    get_latest_observation,
)
from .schemas import (
    GroupedStatistics,
    IngestResponse,
    IngestionLog,
    IngestionLogPage,
    Observation,
    ObservationPage,
    Pagination,
    SeriesMetadata,
    StatisticsResponse,
    DatePeriod,
)
from .statistics import compute_grouped_statistics, compute_statistics


settings = get_settings()
DEFAULT_END_DATE = settings.today


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    close_database()


app = FastAPI(
    title="Monitor de indicadores Banxico",
    description="API para consultar el catálogo e ingerir series del SIE de Banxico.",
    version="1.0.0",
    lifespan=lifespan,
)


def _service_error(error: Exception) -> HTTPException:
    if isinstance(error, BanxicoError):
        return HTTPException(status_code=502, detail=str(error))
    if isinstance(error, (ConfigurationError, MongoDBError)):
        return HTTPException(status_code=503, detail=str(error))
    return HTTPException(status_code=500, detail="Error interno del servicio.")


def _date_bounds(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    return (
        datetime.combine(start_date, datetime_time.min) if start_date else None,
        datetime.combine(end_date, datetime_time.max) if end_date else None,
    )


@app.get("/health", tags=["Sistema"])
def health() -> dict[str, str]:
    """Comprueba que el proceso de la API está disponible."""
    return {"status": "ok"}


@app.get("/series", response_model=list[SeriesMetadata], tags=["Catálogo"])
def list_series() -> list[SeriesMetadata]:
    """Devuelve las series configuradas para el paquete mercados."""
    return [SeriesMetadata.model_validate(series) for series in SERIES_METADATA]


@app.get("/series/{series_id}", response_model=SeriesMetadata, tags=["Catálogo"])
def get_series(series_id: str) -> SeriesMetadata:
    """Devuelve los metadatos de una serie por su identificador Banxico."""
    series = SERIES_BY_ID.get(series_id)
    if series is None:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    return SeriesMetadata.model_validate(series)


@app.get("/estadisticas/{series_id}", response_model=StatisticsResponse, tags=["Datos"])
def get_series_statistics(
    series_id: str,
    start_date: Annotated[date, Query(description="Fecha inicial inclusiva.")] = settings.default_start_date,
    end_date: Annotated[date, Query(description="Fecha final inclusiva.")] = DEFAULT_END_DATE,
    agrupacion: Annotated[Literal["none", "year", "month", "year_month"], Query()] = "none",
) -> StatisticsResponse:
    """Calcula estadísticas descriptivas con los datos consultados a Banxico."""
    metadata = SERIES_BY_ID.get(series_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")

    try:
        series_data = fetch_series([series_id], start_date, end_date)
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error
    series = cast(
        dict[str, Any],
        next((item for item in series_data if item.get("idSerie") == series_id), {}),
    )
    observations = clean_observations(series.get("datos", []))

    statistics = compute_statistics(observations)
    return StatisticsResponse(
        serie=SeriesMetadata.model_validate(metadata),
        periodo=DatePeriod(desde=start_date, hasta=end_date),
        total_observaciones=len(observations),
        estadisticas=statistics,
        agrupacion=None if agrupacion == "none" else agrupacion,
        grupos=[] if agrupacion == "none" else [
            GroupedStatistics.model_validate(item)
            for item in compute_grouped_statistics(observations, agrupacion)
        ],
    )


@app.get("/observaciones", response_model=ObservationPage, tags=["Datos"])
def list_observations(
    series_id: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = 100,
) -> ObservationPage:
    """Consulta observaciones persistidas, opcionalmente filtradas por serie."""
    if series_id and series_id not in SERIES_BY_ID:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")
    try:
        database = get_database()
        start_datetime, end_datetime = _date_bounds(start_date, end_date)
        observations, total = query_observations(
            database, series_id, start_datetime, end_datetime, skip, limit
        )
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error
    return ObservationPage(
        items=[Observation.model_validate(observation) for observation in observations],
        pagination=Pagination(total=total, skip=skip, limit=limit, has_more=skip + len(observations) < total),
    )


@app.get("/ingestas/historial", response_model=IngestionLogPage, tags=["Ingesta"])
def list_ingestion_history(
    run_id: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = 100,
) -> IngestionLogPage:
    """Consulta ejecuciones de ingesta almacenadas en MongoDB."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")
    try:
        database = get_database()
        start_datetime, end_datetime = _date_bounds(start_date, end_date)
        logs, total = list_ingestion_logs(
            database, run_id, start_datetime, end_datetime, skip, limit
        )
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error
    return IngestionLogPage(
        items=[IngestionLog.model_validate(log) for log in logs],
        pagination=Pagination(total=total, skip=skip, limit=limit, has_more=skip + len(logs) < total),
    )


@app.post("/ingestas", response_model=IngestResponse, status_code=status.HTTP_201_CREATED, tags=["Ingesta"])
def create_ingestion(
    start_date: Annotated[date, Query(description="Fecha inicial inclusiva.")] = settings.default_start_date,
    end_date: Annotated[date, Query(description="Fecha final inclusiva.")] = DEFAULT_END_DATE,
) -> IngestResponse:
    """Descarga las series de Banxico y las inserta de forma idempotente en MongoDB."""
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")

    started_at = time.time()
    run_id = datetime.now(UTC).isoformat()
    try:
        database = get_database()
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error

    try:
        seed_catalogo(database)
    except MongoDBError as error:
        raise _service_error(error) from error

    total_new = total_duplicates = total_errors = 0
    series_log: list[dict[str, Any]] = []
    for metadata in SERIES_METADATA:
        series_id = str(metadata["_id"])
        try:
            latest = get_latest_observation(database, series_id)
        except MongoDBError as error:
            raise _service_error(error) from error
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

        try:
            series_data = fetch_series([series_id], next_date, end_date)
        except ConfigurationError as error:
            raise _service_error(error) from error
        except BanxicoError as error:
            total_errors += 1
            series_log.append({
                "serie_id": series_id,
                "nuevos": 0,
                "duplicados": 0,
                "consultada": True,
                "error": str(error),
            })
            continue
        series = cast(
            dict[str, Any],
            next((item for item in series_data if item.get("idSerie") == series_id), {}),
        )
        previous_value = latest.get("valor") if latest else None
        documents = parse_observations(series, run_id, previous_value)
        new_count = duplicate_count = 0
        if documents:
            try:
                new_count, duplicate_count = insert_observations(database, documents)
                update_catalogo_latest(database, series_id, documents)
            except MongoDBError as error:
                raise _service_error(error) from error
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
    try:
        save_ingestion_log(database, run_id, {
            "nuevos": total_new,
            "duplicados": total_duplicates,
            "errores": total_errors,
            "duracion_seg": duration,
        }, series_log)
    except MongoDBError as error:
        raise _service_error(error) from error
    return IngestResponse(run_id=run_id, nuevos=total_new, duplicados=total_duplicates, errores=total_errors, duracion_seg=duration, series=series_log)