"""Calculos deterministas para snapshots, metricas y alertas."""

import math
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from .banxico_client import SERIES_BY_ID
from .config import Settings


def _date_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())


def _trend(slope: float, scale: float) -> str:
    if scale == 0 or abs(slope) <= abs(scale) * 0.0001:
        return "estable"
    return "ascendente" if slope > 0 else "descendente"


def _finite_or_zero(value: Any) -> float:
    numeric = float(value)
    return 0.0 if not math.isfinite(numeric) else numeric


def _period_metrics(values: list[dict[str, Any]], start_date: date, end_date: date) -> dict[str, Any]:
    frame = pd.DataFrame([
        {"fecha": _date_value(item["fecha"]), "valor": float(item["valor"])}
        for item in values
    ]).sort_values("fecha", kind="stable")
    frame = frame.drop_duplicates("fecha", keep="last").reset_index(drop=True)
    first = frame.iloc[0]
    last = frame.iloc[-1]
    numeric = frame["valor"]
    changes = numeric.pct_change().dropna().mul(100)
    differences = numeric.diff().dropna()
    min_index = numeric.idxmin()
    max_index = numeric.idxmax()
    expected_days = max(
        1,
        len(pd.bdate_range(start=start_date, end=end_date)),
    )
    slope = 0.0
    if len(frame) > 1:
        slope = float(pd.Series(numeric).reset_index(drop=True).diff().dropna().mean())
    initial = float(first["valor"])
    final = float(last["valor"])
    absolute_change = final - initial
    period_change = None if initial == 0 else (absolute_change / initial) * 100
    latest_change = float(changes.iloc[-1]) if not changes.empty else 0.0
    tiie = SERIES_BY_ID.get(str(values[0]["serie_id"]), {}).get("_id") == "SF60648"
    return {
        "valor_inicial": initial,
        "fecha_inicial": first["fecha"],
        "valor_final": final,
        "fecha_final": last["fecha"],
        "cambio_absoluto": round(absolute_change, 6),
        "var_periodo_pct": None if period_change is None else round(period_change, 6),
        "var_ultimo_dia_pct": round(latest_change, 6),
        "min": float(numeric.min()),
        "fecha_min": frame.loc[min_index, "fecha"],
        "max": float(numeric.max()),
        "fecha_max": frame.loc[max_index, "fecha"],
        "rango": round(float(numeric.max() - numeric.min()), 6),
        "promedio": round(float(numeric.mean()), 6),
        "mediana": round(float(numeric.median()), 6),
        "desviacion_estandar": round(_finite_or_zero(numeric.std(ddof=1)), 6),
        "volatilidad_diaria_pct": round(_finite_or_zero(changes.std(ddof=1)), 6),
        "dias_alza": int((differences > 0).sum()),
        "dias_baja": int((differences < 0).sum()),
        "dias_sin_cambio": int((differences == 0).sum()),
        "mayor_subida_pct": round(float(changes.max()), 6) if not changes.empty else 0.0,
        "fecha_mayor_subida": frame.loc[changes.idxmax(), "fecha"] if not changes.empty else None,
        "mayor_caida_pct": round(float(changes.min()), 6) if not changes.empty else 0.0,
        "fecha_mayor_caida": frame.loc[changes.idxmin(), "fecha"] if not changes.empty else None,
        "tendencia": _trend(slope, float(numeric.mean())),
        "observaciones_validas": int(len(frame)),
        "dias_habiles_esperados": expected_days,
        "cobertura_pct": round(min(100.0, len(frame) / expected_days * 100), 2),
        "distancia_promedio_pct": round(
            ((final - float(numeric.mean())) / float(numeric.mean())) * 100, 6
            if numeric.mean() else 0.0,
        ),
        "cambio_puntos_porcentuales": round(absolute_change, 6) if tiie else None,
        "cambio_puntos_base": round(absolute_change * 100, 4) if tiie else None,
    }


def build_snapshot(
    observations: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    settings: Settings,
) -> dict[str, Any]:
    by_series: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        by_series.setdefault(str(observation["serie_id"]), []).append(observation)

    series = []
    alerts = []
    for series_id, values in sorted(by_series.items()):
        latest = max(values, key=lambda item: item["fecha"])
        metrics = _period_metrics(values, start_date, end_date)
        summary = {
            "serie_id": series_id,
            **metrics,
            "ultimo_valor": float(latest["valor"]),
            "ultima_fecha": latest["fecha"],
            "var_pct": float(latest.get("var_pct", 0.0)),
        }
        series.append(summary)
        variation = abs(summary["var_periodo_pct"] or 0.0)
        if variation >= settings.alert_high_threshold_pct:
            severity = "alta"
        elif variation >= settings.alert_medium_threshold_pct:
            severity = "media"
        else:
            continue
        alerts.append({
            "tipo": "variacion_porcentual",
            "severidad": severity,
            "serie_id": series_id,
            "mensaje": (
                f"La serie {series_id} registró una variación de "
                f"{summary['var_pct']:.4f}%."
            ),
            "valor": summary["ultimo_valor"],
            "var_pct": summary["var_pct"],
        })

    snapshot_id = f"{start_date.isoformat()}|{end_date.isoformat()}"
    return {
        "_id": snapshot_id,
        "creado_en": datetime.now(UTC),
        "desde": datetime.combine(start_date, datetime.min.time()),
        "hasta": datetime.combine(end_date, datetime.min.time()),
        "series": series,
        "alertas": alerts,
        "estado": "con_alertas" if alerts else "ok",
        "analisis": None,
    }
