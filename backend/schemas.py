"""Modelos publicos de entrada y salida de la API."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SeriesMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    titulo: str
    unidad: str
    frecuencia: str
    paquetes: list[str]
    activa: bool
    ultima_fecha: datetime | None = None


class Observation(BaseModel):
    id: str = Field(alias="_id")
    serie_id: str
    fecha: datetime
    anio: int
    mes: int
    valor: float
    var_pct: float
    run_id: str

    model_config = ConfigDict(populate_by_name=True)


class Pagination(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


class ObservationPage(BaseModel):
    items: list[Observation]
    pagination: Pagination


class DatePeriod(BaseModel):
    desde: date
    hasta: date


class GroupedStatistics(BaseModel):
    grupo: str
    estadisticas: dict[str, float | None]
    total_observaciones: int


class StatisticsResponse(BaseModel):
    serie: SeriesMetadata
    periodo: DatePeriod
    total_observaciones: int
    estadisticas: dict[str, float | None]
    agrupacion: str | None = None
    grupos: list[GroupedStatistics] = Field(default_factory=list)


class IngestionSeriesResult(BaseModel):
    serie_id: str
    nuevos: int
    duplicados: int
    consultada: bool
    desde: date | None = None
    hasta: date | None = None
    motivo: str | None = None
    error: str | None = None


class IngestResponse(BaseModel):
    run_id: str
    nuevos: int
    duplicados: int
    errores: int
    duracion_seg: float
    series: list[IngestionSeriesResult]


class IngestionLog(BaseModel):
    run_id: str
    creado_en: datetime | None = None
    resumen: dict[str, Any]
    series: list[IngestionSeriesResult]


class IngestionLogPage(BaseModel):
    items: list[IngestionLog]
    pagination: Pagination


class ExecutiveSummary(BaseModel):
    resumen: str
    puntos_clave: list[str] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)
    limitaciones: list[str] = Field(default_factory=list)


class NarrativeIndicator(BaseModel):
    nombre: str
    unidad: str
    tendencia: Literal["ascendente", "descendente", "estable"]
    balance: Literal["al_alza", "a_la_baja", "mixto", "estable"]
    cobertura_pct: float
    tiene_alerta: bool


class NarrativeInput(BaseModel):
    periodo: str
    es_un_dia: bool
    indicadores: list[NarrativeIndicator]
    alertas_totales: int


class NarrativeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resumen: str = Field(min_length=20, max_length=1200)


class Alert(BaseModel):
    tipo: str
    severidad: Literal["media", "alta"]
    serie_id: str
    mensaje: str
    valor: float
    var_pct: float


class Snapshot(BaseModel):
    id: str = Field(alias="_id")
    creado_en: datetime
    desde: date
    hasta: date
    series: list[dict[str, Any]]
    alertas: list[Alert]
    estado: Literal["ok", "con_alertas"]
    analisis: "ExecutiveSummary | None" = None

    model_config = ConfigDict(populate_by_name=True)


class SnapshotPage(BaseModel):
    items: list[Snapshot]
    pagination: Pagination


class ReportRequest(BaseModel):
    destinatario: str
    start_date: date
    end_date: date
    dry_run: bool = True


class ReportResponse(BaseModel):
    destinatario: str
    dry_run: bool
    asunto: str
    html: str
    snapshot_id: str
