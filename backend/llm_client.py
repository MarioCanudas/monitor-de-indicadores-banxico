"""Generacion del resumen narrativo con Azure OpenAI."""

import json
from typing import Any

from openai import AzureOpenAI, OpenAI, OpenAIError
from pydantic import ValidationError

from .banxico_client import SERIES_BY_ID
from .config import Settings
from .exceptions import BackendError, ConfigurationError
from .schemas import ExecutiveSummary, NarrativeInput, NarrativeOutput


def _period_label(snapshot: dict[str, Any]) -> str:
    start = str(snapshot["desde"])[:10]
    end = str(snapshot["hasta"])[:10]
    return start if start == end else f"{start} a {end}"


def _narrative_input(snapshot: dict[str, Any]) -> NarrativeInput:
    alerts_by_series = {str(alert["serie_id"]) for alert in snapshot.get("alertas", [])}
    indicators = []
    for item in snapshot.get("series", []):
        series_id = str(item["serie_id"])
        name = str(SERIES_BY_ID.get(series_id, {}).get("titulo", series_id))
        change = float(item.get("var_periodo_pct", item.get("var_pct", 0)) or 0)
        if change > 0.05:
            balance = "al_alza"
        elif change < -0.05:
            balance = "a_la_baja"
        else:
            balance = "estable"
        indicators.append({
            "nombre": name,
            "unidad": str(SERIES_BY_ID.get(series_id, {}).get("unidad", "")),
            "tendencia": item.get("tendencia", "estable"),
            "balance": balance,
            "cobertura_pct": float(item.get("cobertura_pct", 0)),
            "tiene_alerta": series_id in alerts_by_series,
        })
    return NarrativeInput(
        periodo=_period_label(snapshot),
        es_un_dia=str(snapshot["desde"])[:10] == str(snapshot["hasta"])[:10],
        indicadores=indicators,
        alertas_totales=len(snapshot.get("alertas", [])),
    )


def _fallback(snapshot: dict[str, Any]) -> ExecutiveSummary:
    narrative = _narrative_input(snapshot)
    alerts = narrative.alertas_totales
    if not narrative.indicadores:
        text = f"No hay información válida disponible para {narrative.periodo}."
    elif alerts:
        text = (
            f"Durante {narrative.periodo} se observaron movimientos entre los indicadores "
            f"y se detectaron {alerts} alerta(s) que conviene revisar."
        )
    else:
        text = (
            f"Durante {narrative.periodo} los indicadores mostraron un comportamiento "
            "sin cambios fuera de los umbrales configurados."
        )
    return ExecutiveSummary(resumen=text)


def _client(settings: Settings) -> AzureOpenAI | OpenAI:
    api_key, endpoint = settings.require_azure_openai()
    if ".services.ai.azure.com/api/projects/" in endpoint:
        return OpenAI(
            api_key=api_key,
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
        )
    return AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=settings.azure_openai_api_version,
    )


def generate_executive_summary(
    snapshot: dict[str, Any], settings: Settings
) -> ExecutiveSummary:
    """Genera solo narrativa; las metricas y alertas se calculan fuera del LLM."""
    try:
        narrative_input = _narrative_input(snapshot)
        response = _client(settings).chat.completions.create(
            model=settings.azure_openai_deployment,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Escribe un resumen ejecutivo breve, claro y amigable para una "
                        "persona no tecnica. Devuelve exclusivamente JSON con la clave "
                        "'resumen'. Explica con palabras la situacion general y las "
                        "tendencias, sin repetir metricas, cifras, porcentajes, IDs, "
                        "nombres de series tecnicos ni inventar causas. No des consejos "
                        "financieros. Usa solo los nombres y estados recibidos."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        narrative_input.model_dump(), ensure_ascii=False
                    ),
                },
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise BackendError("Azure OpenAI devolvio una respuesta vacia.")
        output = NarrativeOutput.model_validate(json.loads(content))
        return ExecutiveSummary(resumen=output.resumen)
    except (ConfigurationError, BackendError, OpenAIError, ValidationError, ValueError, TypeError):
        return _fallback(snapshot)
