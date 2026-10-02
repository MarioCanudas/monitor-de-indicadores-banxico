"""Cliente para consultar la API REST del SIE de Banxico y limpieza de datos."""

import math
from datetime import date
from typing import Any

import pandas as pd
import requests

from .config import get_settings
from .exceptions import BanxicoError, ConfigurationError

SERIES_METADATA = [
    {"_id": "SF43718", "titulo": "Pesos por dólar, FIX", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF46410", "titulo": "Euro", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF46406", "titulo": "Yen japonés", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF46407", "titulo": "Libra esterlina", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF60632", "titulo": "Dólar canadiense", "unidad": "Pesos", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
    {"_id": "SF60648", "titulo": "TIIE a 28 días", "unidad": "Porcentaje", "frecuencia": "Diaria", "paquetes": ["mercados"], "activa": True},
]
SERIES_BY_ID = {series["_id"]: series for series in SERIES_METADATA}


def clean_observations(data: list[dict[str, Any]]) -> pd.DataFrame:
    """Normaliza observaciones y descarta fechas o valores no analizables."""
    observations = pd.DataFrame(data).reindex(columns=["fecha", "dato"])
    observations["fecha"] = pd.to_datetime(
        observations["fecha"], format="%d/%m/%Y", errors="coerce"
    )
    values = observations["dato"].astype("string").str.strip().str.replace(",", "", regex=False)
    missing_values = {"", "--", "N/E", "N/D", "ND", "S/D", "NA", "N/A", "NULL", "NONE", "NAN"}
    values = values.mask(values.str.upper().isin(missing_values))
    observations["valor"] = pd.to_numeric(values, errors="coerce")
    valid_values = observations["valor"].map(
        lambda value: pd.notna(value) and math.isfinite(float(value))
    )
    observations = observations.loc[observations["fecha"].notna() & valid_values]
    return (
        observations.sort_values("fecha", kind="stable")
        .drop_duplicates(subset=["fecha"], keep="last")
        .loc[:, ["fecha", "valor"]]
        .reset_index(drop=True)
    )


def parse_observations(
    series: dict[str, Any], run_id: str, previous_value: float | None = None
) -> list[dict[str, Any]]:
    """Convierte la respuesta de Banxico al esquema persistido en MongoDB."""
    documents = []
    try:
        previous_value = float(previous_value) if previous_value is not None else None
        if previous_value is not None and not math.isfinite(previous_value):
            previous_value = None
    except (TypeError, ValueError):
        previous_value = None

    observations = clean_observations(series.get("datos", []))
    for item in observations.itertuples(index=False):
        value = float(item.valor)
        observation_date = item.fecha.to_pydatetime()
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
    """Consulta la API REST del SIE de Banxico y devuelve las series limpias."""
    try:
        token = get_settings().require_banxico_api()
    except ConfigurationError as error:
        raise error
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
        payload = response.json()
        if not isinstance(payload, dict):
            raise BanxicoError("La respuesta de Banxico no tiene un formato valido.")
        bmx = payload.get("bmx", {})
        series = bmx.get("series", []) if isinstance(bmx, dict) else []
        if not isinstance(series, list):
            raise BanxicoError("La respuesta de Banxico no contiene series validas.")
        return series
    except BanxicoError:
        raise
    except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
        raise BanxicoError(f"Error al consultar Banxico: {error}") from error
