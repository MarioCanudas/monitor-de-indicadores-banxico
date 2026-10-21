"""API para consultar e ingerir indicadores del SIE de Banxico."""

import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time as datetime_time, timedelta
from typing import Annotated, Any, Literal, cast

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .banxico_client import (
    SERIES_BY_ID,
    SERIES_METADATA,
    clean_observations,
    fetch_series,
    parse_observations,
)
from .analytics import build_snapshot_from_metrics, business_days_between
from .config import get_settings
from .exceptions import BackendError, BanxicoError, ConfigurationError, MongoDBError
from .llm_client import generate_executive_summary
from .mongodb_client import (
    aggregate_series_metrics,
    close_database,
    get_database,
    list_ingestion_logs,
    list_observations as query_observations,
    insert_observations,
    save_ingestion_log,
    seed_catalogo,
    update_catalogo_latest,
    get_latest_observation,
    get_earliest_observation,
    get_snapshot,
    list_snapshots,
    save_snapshot,
)
from .schemas import (
    GroupedStatistics,
    IngestResponse,
    IngestionLog,
    IngestionLogPage,
    KpiResponse,
    Observation,
    ObservationPage,
    Pagination,
    SeriesMetadata,
    StatisticsResponse,
    DatePeriod,
    Snapshot,
    SnapshotPage,
    ReportRequest,
    ReportResponse,
)
from .reports import render_report, send_report, validate_recipient
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

# El frontend puede servirse desde otro origen (Vite en desarrollo o un CDN en
# produccion). Sin CORS el navegador bloquearia las peticiones reales.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Type"],
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


@app.get("/kpis/{series_id}", response_model=KpiResponse, tags=["Datos"])
def get_series_kpis(
    series_id: str,
    start_date: Annotated[date, Query(description="Fecha inicial inclusiva.")] = settings.default_start_date,
    end_date: Annotated[date, Query(description="Fecha final inclusiva.")] = DEFAULT_END_DATE,
) -> KpiResponse:
    """Calcula los KPIs de una serie con un aggregation pipeline en MongoDB."""
    metadata = SERIES_BY_ID.get(series_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Serie no encontrada: {series_id}")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")
    try:
        database = get_database()
        start_datetime, end_datetime = _date_bounds(start_date, end_date)
        metrics = aggregate_series_metrics(
            database,
            start_datetime,
            end_datetime,
            business_days_between(start_date, end_date),
            series_id=series_id,
        )
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error
    return KpiResponse(
        serie=SeriesMetadata.model_validate(metadata),
        periodo=DatePeriod(desde=start_date, hasta=end_date),
        kpi=metrics[0] if metrics else None,
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
            earliest = get_earliest_observation(database, series_id)
        except MongoDBError as error:
            raise _service_error(error) from error

        earliest_date: date | None = None
        latest_date: date | None = None
        if earliest and isinstance(earliest.get("fecha"), datetime):
            earliest_date = earliest["fecha"].date()
        if latest and isinstance(latest.get("fecha"), datetime):
            latest_date = latest["fecha"].date()

        gaps: list[tuple[date, date]] = []
        if earliest_date is None or latest_date is None:
            gaps.append((start_date, end_date))
        else:
            if start_date < earliest_date:
                gaps.append((start_date, min(end_date, earliest_date - timedelta(days=1))))
            if latest_date < end_date:
                forward_start = max(start_date, latest_date + timedelta(days=1))
                if forward_start <= end_date:
                    gaps.append((forward_start, end_date))

        if not gaps:
            series_log.append({
                "serie_id": series_id,
                "nuevos": 0,
                "duplicados": 0,
                "consultada": False,
                "motivo": "sin datos nuevos",
            })
            continue

        stored_forward_value: float | None = None
        if latest and isinstance(latest.get("valor"), (int, float)):
            stored_forward_value = float(latest["valor"])

        all_documents: list[dict[str, Any]] = []
        new_count = duplicate_count = 0
        gap_error: str | None = None
        prev_backfill: float | None = None
        prev_forward: float | None = stored_forward_value
        for gap_start, gap_end in gaps:
            is_forward = (
                earliest_date is not None
                and latest_date is not None
                and gap_start > latest_date
            )
            base_value = prev_forward if is_forward else prev_backfill
            # Sin histórico, el primer hueco encadena sobre lo ya descargado
            # en esta misma ejecución.
            if earliest_date is None or latest_date is None:
                base_value = (
                    float(all_documents[-1]["valor"]) if all_documents else None
                )
            try:
                series_data = fetch_series([series_id], gap_start, gap_end)
            except ConfigurationError as error:
                raise _service_error(error) from error
            except BanxicoError as error:
                total_errors += 1
                gap_error = str(error)
                break
            series = cast(
                dict[str, Any],
                next((item for item in series_data if item.get("idSerie") == series_id), {}),
            )
            documents = parse_observations(series, run_id, base_value)
            if is_forward:
                prev_forward = (
                    float(documents[-1]["valor"]) if documents else prev_forward
                )
            else:
                prev_backfill = (
                    float(documents[-1]["valor"]) if documents else prev_backfill
                )
            if documents:
                try:
                    inserted, duplicates = insert_observations(database, documents)
                    new_count += inserted
                    duplicate_count += duplicates
                    all_documents.extend(documents)
                except MongoDBError as error:
                    raise _service_error(error) from error
        if all_documents:
            try:
                update_catalogo_latest(database, series_id, all_documents)
            except MongoDBError as error:
                raise _service_error(error) from error
        total_new += new_count
        total_duplicates += duplicate_count
        entry: dict[str, Any] = {
            "serie_id": series_id,
            "nuevos": new_count,
            "duplicados": duplicate_count,
            "consultada": True,
            "desde": gaps[0][0].isoformat(),
            "hasta": gaps[-1][1].isoformat(),
        }
        if gap_error is not None:
            entry["error"] = gap_error
        series_log.append(entry)

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


@app.post("/snapshots", response_model=Snapshot, status_code=status.HTTP_201_CREATED, tags=["Snapshots"])
def create_snapshot(
    start_date: Annotated[date, Query()] = settings.default_start_date,
    end_date: Annotated[date, Query()] = DEFAULT_END_DATE,
) -> Snapshot:
    """Calcula y persiste un snapshot a partir de observaciones almacenadas."""
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")
    try:
        database = get_database()
        start_datetime, end_datetime = _date_bounds(start_date, end_date)
        metrics = aggregate_series_metrics(
            database,
            start_datetime,
            end_datetime,
            business_days_between(start_date, end_date),
        )
        snapshot = build_snapshot_from_metrics(metrics, start_date, end_date, settings)
        snapshot["analisis"] = generate_executive_summary(snapshot, settings).model_dump()
        save_snapshot(database, snapshot)
        return Snapshot.model_validate(snapshot)
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error


@app.post(
        "/snapshots/diario",
        response_model=Snapshot,
        status_code=status.HTTP_201_CREATED,
        tags=["Snapshots"],
)
def create_daily_snapshot(
    start_date: Annotated[date, Query(description="Fecha inicial inclusiva.")],
    end_date: Annotated[date, Query(description="Fecha final inclusiva.")],
) -> Snapshot:
    """Genera un snapshot para un día o periodo indicado."""
    return create_snapshot(start_date, end_date)


@app.post(
    "/tareas/diaria",
    response_model=Snapshot,
    status_code=status.HTTP_201_CREATED,
    tags=["Sistema"],
)
def run_daily_task(
    start_date: Annotated[date, Query(description="Fecha inicial inclusiva.")],
    end_date: Annotated[date, Query(description="Fecha final inclusiva.")],
) -> Snapshot:
    """Ejecuta la ingesta y genera el snapshot del periodo indicado."""
    _ = create_ingestion(start_date, end_date)
    return create_daily_snapshot(start_date, end_date)


@app.get("/snapshots", response_model=SnapshotPage, tags=["Snapshots"])
def get_snapshots(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = 100,
) -> SnapshotPage:
    """Lista snapshots calculados, del más reciente al más antiguo."""
    try:
        database = get_database()
        snapshots, total = list_snapshots(database, skip, limit)
        return SnapshotPage(
            items=[Snapshot.model_validate(item) for item in snapshots],
            pagination=Pagination(
                total=total,
                skip=skip,
                limit=limit,
                has_more=skip + len(snapshots) < total,
            ),
        )
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error


@app.get("/snapshots/{snapshot_id}", response_model=Snapshot, tags=["Snapshots"])
def read_snapshot(snapshot_id: str) -> Snapshot:
    """Devuelve un snapshot por su periodo determinista."""
    try:
        snapshot = get_snapshot(get_database(), snapshot_id)
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Snapshot no encontrado: {snapshot_id}")
    return Snapshot.model_validate(snapshot)


@app.post("/reportes/preview", response_model=ReportResponse, tags=["Reportes"])
def preview_report(request: ReportRequest) -> ReportResponse:
    """Genera el HTML del reporte del periodo sin realizar ningún envío."""
    try:
        if request.start_date > request.end_date:
            raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")
        recipient = validate_recipient(request.destinatario)
        database = get_database()
        snapshot = get_snapshot(
            database, f"{request.start_date.isoformat()}|{request.end_date.isoformat()}"
        )
        if snapshot is None:
            raise HTTPException(status_code=404, detail="No existe snapshot para el periodo solicitado.")
        subject, body = render_report(snapshot)
        return ReportResponse(
            destinatario=recipient,
            dry_run=True,
            asunto=subject,
            html=body,
            snapshot_id=snapshot["_id"],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (BanxicoError, ConfigurationError, MongoDBError) as error:
        raise _service_error(error) from error


@app.post("/reportes/enviar", response_model=ReportResponse, tags=["Reportes"])
def send_email_report(request: ReportRequest) -> ReportResponse:
    """Genera el reporte del periodo y lo envía solo cuando dry_run es falso."""
    try:
        if request.start_date > request.end_date:
            raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior o igual a la fecha final.")
        recipient = validate_recipient(request.destinatario)
        database = get_database()
        snapshot = get_snapshot(
            database, f"{request.start_date.isoformat()}|{request.end_date.isoformat()}"
        )
        if snapshot is None:
            raise HTTPException(status_code=404, detail="No existe snapshot para el periodo solicitado.")
        subject, body = render_report(snapshot)
        send_report(recipient, subject, body, settings, request.dry_run)
        return ReportResponse(
            destinatario=recipient,
            dry_run=request.dry_run,
            asunto=subject,
            html=body,
            snapshot_id=snapshot["_id"],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (BanxicoError, ConfigurationError, MongoDBError, BackendError) as error:
        raise _service_error(error) from error