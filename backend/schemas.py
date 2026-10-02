"""Modelos publicos de entrada y salida de la API."""

from datetime import date, datetime
from typing import Any

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
