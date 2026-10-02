"""Análisis estadístico de las series de indicadores Banxico."""

from typing import Any

import pandas as pd


STATISTIC_NAMES = ("count", "mean", "std", "min", "25%", "50%", "75%", "max")


def compute_statistics(observations: pd.DataFrame) -> dict[str, Any]:
    """Calcula estadísticas descriptivas de un DataFrame de observaciones limpias."""
    if observations.empty:
        return {name: None for name in STATISTIC_NAMES}
    description = observations["valor"].describe()
    statistics = {
        name: None if pd.isna(value) else round(float(value), 6)
        for name, value in description.items()
    }
    return statistics


def compute_grouped_statistics(
    observations: pd.DataFrame,
    grouping: str,
) -> list[dict[str, Any]]:
    """Calcula estadisticas por anio, mes o combinacion anio-mes."""
    if grouping not in {"year", "month", "year_month"}:
        raise ValueError(f"Agrupacion no soportada: {grouping}")
    if observations.empty:
        return []

    grouped = observations.copy()
    grouped["fecha"] = pd.to_datetime(grouped["fecha"], errors="coerce")
    grouped = grouped.loc[grouped["fecha"].notna()]
    if grouping == "year":
        grouped["grupo"] = grouped["fecha"].dt.year.astype(str)
    elif grouping == "month":
        grouped["grupo"] = grouped["fecha"].dt.month.astype(str).str.zfill(2)
    else:
        grouped["grupo"] = grouped["fecha"].dt.strftime("%Y-%m")

    results = []
    for group_name, group in grouped.groupby("grupo", sort=True):
        results.append({
            "grupo": str(group_name),
            "estadisticas": compute_statistics(group),
            "total_observaciones": int(len(group)),
        })
    return results
