"""Calculos deterministas para snapshots, metricas y alertas.

La ruta principal de la API calcula los KPIs con un aggregation pipeline en
MongoDB (``$match``/``$sort``/``$group``/``$project``). Este modulo recibe esos
documentos ya agregados y solo se encarga de armar el snapshot y las alertas.
``build_snapshot`` conserva una implementacion equivalente en Python puro para
pruebas y para calcular sobre datos que aun no estan persistidos.
"""

import math
import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any

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
    if value is None:
        return 0.0
    numeric = float(value)
    return 0.0 if not math.isfinite(numeric) else numeric


def business_days_between(start_date: date, end_date: date) -> int:
    """Dias habiles (lunes a viernes) del periodo, minimo uno."""
    if end_date < start_date:
        return 1
    total = sum(
        1
        for offset in range((end_date - start_date).days + 1)
        if (start_date + timedelta(days=offset)).weekday() < 5
    )
    return max(1, total)


def _period_metrics(
    values: list[dict[str, Any]], start_date: date, end_date: date
) -> dict[str, Any]:
    """Calculo de respaldo en Python puro (sin pandas) para pruebas."""
    ordered = sorted(
        ((_date_value(item["fecha"]), float(item["valor"])) for item in values),
        key=lambda item: item[0],
    )
    deduplicated: dict[datetime, float] = {}
    for observation_date, value in ordered:
        deduplicated[observation_date] = value
    points = sorted(deduplicated.items())
    frame = [{"fecha": observation_date, "valor": value} for observation_date, value in points]
    numeric = [point["valor"] for point in frame]
    first = frame[0]
    last = frame[-1]

    movements = [
        {
            "fecha": frame[index]["fecha"],
            "delta": numeric[index] - numeric[index - 1],
            "pct": (
                None
                if numeric[index - 1] == 0
                else ((numeric[index] - numeric[index - 1]) / numeric[index - 1]) * 100
            ),
        }
        for index in range(1, len(frame))
    ]
    changes = [item["pct"] for item in movements if item["pct"] is not None]
    differences = [item["delta"] for item in movements]
    mean = statistics.fmean(numeric)
    slope = statistics.fmean(differences) if differences else 0.0
    expected_days = business_days_between(start_date, end_date)
    initial = float(first["valor"])
    final = float(last["valor"])
    absolute_change = final - initial
    period_change = None if initial == 0 else (absolute_change / initial) * 100
    max_change = max(movements, key=lambda item: item["pct"] if item["pct"] is not None else -math.inf) if changes else None
    min_change = min(movements, key=lambda item: item["pct"] if item["pct"] is not None else math.inf) if changes else None
    min_point = min(frame, key=lambda item: item["valor"])
    max_point = max(frame, key=lambda item: item["valor"])
    latest_change = changes[-1] if changes else 0.0
    tiie = str(values[0]["serie_id"]) == "SF60648"
    return {
        "valor_inicial": initial,
        "fecha_inicial": first["fecha"],
        "valor_final": final,
        "fecha_final": last["fecha"],
        "cambio_absoluto": round(absolute_change, 6),
        "var_periodo_pct": None if period_change is None else round(period_change, 6),
        "var_ultimo_dia_pct": round(latest_change, 6),
        "min": float(min_point["valor"]),
        "fecha_min": min_point["fecha"],
        "max": float(max_point["valor"]),
        "fecha_max": max_point["fecha"],
        "rango": round(float(max_point["valor"] - min_point["valor"]), 6),
        "promedio": round(mean, 6),
        "mediana": round(float(statistics.median(numeric)), 6),
        "desviacion_estandar": round(
            _finite_or_zero(statistics.stdev(numeric) if len(numeric) > 1 else 0.0), 6
        ),
        "volatilidad_diaria_pct": round(
            _finite_or_zero(statistics.stdev(changes) if len(changes) > 1 else 0.0), 6
        ),
        "dias_alza": sum(1 for value in differences if value > 0),
        "dias_baja": sum(1 for value in differences if value < 0),
        "dias_sin_cambio": sum(1 for value in differences if value == 0),
        "mayor_subida_pct": round(float(max_change["pct"]), 6) if max_change else 0.0,
        "fecha_mayor_subida": max_change["fecha"] if max_change else None,
        "mayor_caida_pct": round(float(min_change["pct"]), 6) if min_change else 0.0,
        "fecha_mayor_caida": min_change["fecha"] if min_change else None,
        "tendencia": _trend(slope, mean),
        "observaciones_validas": len(frame),
        "dias_habiles_esperados": expected_days,
        "cobertura_pct": round(min(100.0, len(frame) / expected_days * 100), 2),
        "distancia_promedio_pct": round(
            ((final - mean) / mean) * 100 if mean else 0.0, 6
        ),
        "cambio_puntos_porcentuales": round(absolute_change, 6) if tiie else None,
        "cambio_puntos_base": round(absolute_change * 100, 4) if tiie else None,
    }


def build_snapshot_from_metrics(
    metrics: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    settings: Settings,
) -> dict[str, Any]:
    """Arma el snapshot y las alertas a partir de KPIs ya agregados."""
    series: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    for metric in sorted(metrics, key=lambda item: str(item["serie_id"])):
        series_id = str(metric["serie_id"])
        summary = {
            **{key: value for key, value in metric.items() if key != "serie_id"},
            "serie_id": series_id,
            "ultimo_valor": float(metric["valor_final"]),
            "ultima_fecha": metric["fecha_final"],
            "var_pct": float(metric.get("ultimo_var_pct") or 0.0),
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


def build_snapshot(
    observations: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    settings: Settings,
) -> dict[str, Any]:
    """Respaldo en Python puro para pruebas o datos no persistidos."""
    by_series: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        by_series.setdefault(str(observation["serie_id"]), []).append(observation)

    metrics: list[dict[str, Any]] = []
    for series_id, values in sorted(by_series.items()):
        ordered = sorted(values, key=lambda item: _date_value(item["fecha"]))
        latest = ordered[-1]
        metrics.append({
            "serie_id": series_id,
            **_period_metrics(ordered, start_date, end_date),
            "ultimo_var_pct": float(latest.get("var_pct") or 0.0),
        })
    return build_snapshot_from_metrics(metrics, start_date, end_date, settings)
