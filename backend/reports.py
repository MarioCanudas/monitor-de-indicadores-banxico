"""Renderizado HTML y envio de reportes por Gmail."""

import html
import re
import smtplib
from email.message import EmailMessage
from typing import Any

from .banxico_client import INDICATOR_CONTEXT, SERIES_BY_ID
from .config import Settings
from .exceptions import ConfigurationError, BackendError
from .schemas import ExecutiveSummary


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_recipient(recipient: str) -> str:
    value = recipient.strip()
    if not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("El destinatario no tiene un formato de correo valido.")
    return value


def _date_label(value: Any) -> str:
    return "—" if value is None else str(value)[:10]


def _friendly_summary_point(point: str) -> str:
    """Reemplaza IDs de series por sus nombres sin alterar cifras ni texto restante."""
    result = point
    for series_id, metadata in SERIES_BY_ID.items():
        result = result.replace(series_id, str(metadata.get("titulo", series_id)))
    return result


def _number(value: Any, decimals: int = 4, signed: bool = False) -> str:
    if value is None:
        return "—"
    prefix = "+" if signed and float(value) > 0 else ""
    return f"{prefix}{float(value):,.{decimals}f}"


def _tone(value: Any) -> str:
    if value is None or float(value) == 0:
        return "#64748b"
    return "#16803c" if float(value) > 0 else "#c0392b"


def _metric_card(label: str, value: str, tone: str = "#17365d") -> str:
    return (
        '<div style="background:#f8fafc;border:1px solid #e7edf5;border-radius:10px;'
        'padding:12px;min-width:130px;flex:1">'
        f'<div style="font-size:11px;color:#718096;text-transform:uppercase;'
        f'letter-spacing:.04em">{html.escape(label)}</div>'
        f'<div style="font-size:18px;font-weight:700;color:{tone};margin-top:5px">'
        f"{html.escape(value)}</div></div>"
    )


def _deterministic_summary_points(snapshot: dict[str, Any]) -> list[str]:
    points = []
    for item in snapshot.get("series", []):
        series_id = str(item["serie_id"])
        name = SERIES_BY_ID.get(series_id, {}).get("titulo", series_id)
        variation = item.get("var_periodo_pct", item.get("var_pct", 0))
        points.append(
            f"{name}: {_number(item.get('valor_final', item.get('ultimo_valor')))} "
            f"({_number(variation, signed=True)}% en el periodo)"
        )
    return points


def render_report(snapshot: dict[str, Any]) -> tuple[str, str]:
    summary = ExecutiveSummary.model_validate(snapshot.get("analisis") or {})
    start_label = _date_label(snapshot["desde"])
    end_label = _date_label(snapshot["hasta"])
    period_label = (
        f"{start_label}" if start_label == end_label else f"{start_label} a {end_label}"
    )
    subject = f"Monitor Banxico - {period_label}"
    indicator_sections = []
    for item in snapshot.get("series", []):
        series_id = str(item["serie_id"])
        metadata = SERIES_BY_ID.get(series_id, {})
        context = INDICATOR_CONTEXT.get(series_id, {
            "que_es": "Indicador económico publicado por Banxico.",
            "representa": "Una medida cuantitativa de la serie consultada.",
            "interpretacion": "La lectura debe analizarse junto con su unidad, fecha y variación.",
        })
        period_change = item.get("var_periodo_pct")
        change_absolute = item.get("cambio_absoluto")
        absolute_unit = "puntos porcentuales" if series_id == "SF60648" else str(metadata.get("unidad", "unidades"))
        direction = (
            "ascendente" if (period_change or 0) > 0
            else "descendente" if (period_change or 0) < 0
            else "estable"
        )
        movement_color = _tone(period_change)
        detail_metrics = "".join([
            _metric_card("Inicio", f"{_number(item.get('valor_inicial'))} {metadata.get('unidad', '')}"),
            _metric_card("Final", f"{_number(item.get('valor_final'))} {metadata.get('unidad', '')}"),
            _metric_card("Cambio del periodo", f"{_number(period_change, signed=True)}%", movement_color),
            _metric_card("Cambio absoluto", f"{_number(change_absolute, signed=True)} {absolute_unit}", movement_color),
            _metric_card("Mínimo", f"{_number(item.get('min'))} · {_date_label(item.get('fecha_min'))}"),
            _metric_card("Máximo", f"{_number(item.get('max'))} · {_date_label(item.get('fecha_max'))}"),
            _metric_card("Rango", _number(item.get("rango"))),
            _metric_card("Promedio", _number(item.get("promedio"))),
            _metric_card("Mediana", _number(item.get("mediana"))),
            _metric_card("Desv. estándar", _number(item.get("desviacion_estandar"))),
            _metric_card("Volatilidad diaria", f"{_number(item.get('volatilidad_diaria_pct'), signed=False)}%"),
            _metric_card("Cobertura", f"{_number(item.get('cobertura_pct'), 2)}%"),
            _metric_card("Datos válidos", (
                f"{item.get('observaciones_validas', 0)} de "
                f"{item.get('dias_habiles_esperados', 0)}"
            )),
            _metric_card("Distancia del promedio", (
                f"{_number(item.get('distancia_promedio_pct'), signed=True)}%"
            ), _tone(item.get("distancia_promedio_pct"))),
            _metric_card("Último día", (
                f"{_number(item.get('var_ultimo_dia_pct'), signed=True)}%"
            ), _tone(item.get("var_ultimo_dia_pct"))),
        ])
        daily_movement = (
            f"Mayor subida: <strong>{_number(item.get('mayor_subida_pct'), signed=True)}%</strong> "
            f"({_date_label(item.get('fecha_mayor_subida'))}) · "
            f"Mayor caída: <strong>{_number(item.get('mayor_caida_pct'), signed=True)}%</strong> "
            f"({_date_label(item.get('fecha_mayor_caida'))})"
        )
        direction_detail = (
            f"{item.get('dias_alza', 0)} días al alza · "
            f"{item.get('dias_baja', 0)} días a la baja · "
            f"{item.get('dias_sin_cambio', 0)} sin cambio"
        )
        tiie_detail = ""
        if series_id == "SF60648":
            tiie_detail = (
                f'<p style="margin:8px 0;color:#52657e"><strong>Lectura financiera:</strong> '
                f'{_number(item.get("cambio_puntos_base"), 2, True)} puntos base en el periodo.</p>'
            )
        indicator_sections.append(
            f"""<article style="border:1px solid #e6ebf2;border-radius:12px;padding:18px;margin:12px 0">
<div style="display:flex;justify-content:space-between;gap:16px;align-items:baseline">
<h3 style="margin:0;color:#17365d">{html.escape(str(metadata.get("titulo", series_id)))}</h3>
<span style="font-size:12px;color:#8090a5">{html.escape(series_id)}</span></div>
<p style="margin:12px 0 6px"><strong>Qué es:</strong> {html.escape(context["que_es"])}</p>
<p style="margin:6px 0"><strong>Qué representa:</strong> {html.escape(context["representa"])}</p>
<p style="margin:6px 0;color:#52657e"><strong>Cómo leerlo:</strong> {html.escape(context["interpretacion"])}</p>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:16px">{detail_metrics}</div>
<p style="margin:14px 0 4px;color:{movement_color}"><strong>Tendencia {direction}</strong> · {direction_detail}</p>
<p style="margin:6px 0;color:#52657e">{daily_movement}</p>
{tiie_detail}
</article>"""
        )
    indicators = "".join(indicator_sections) or (
        '<p style="color:#61738d">No hay indicadores disponibles para este periodo.</p>'
    )
    bullets = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in _deterministic_summary_points(snapshot)
    )
    executive_summary = _friendly_summary_point(summary.resumen)
    snapshot_alerts = [
        _friendly_summary_point(str(alert["mensaje"]))
        for alert in snapshot.get("alertas", [])
    ]
    alerts = "".join(
        f"<li>{html.escape(item)}</li>" for item in snapshot_alerts
    )
    body = f"""<!doctype html>
<html><body style="margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#24344d">
<main style="max-width:760px;margin:24px auto;background:#fff;border-radius:16px;
padding:32px;box-shadow:0 8px 28px #17365d1f">
<div style="border-bottom:3px solid #2f80ed;padding-bottom:16px">
<h1 style="margin:0;color:#17365d">Monitor de indicadores Banxico</h1>
<p style="color:#61738d">Resumen {"diario" if start_label == end_label else "del periodo"} · {html.escape(period_label)}</p></div>
<h2>Resumen ejecutivo</h2><p>{html.escape(executive_summary)}</p>
<h2>Resumen</h2><ul>{bullets or '<li>Sin puntos destacados.</li>'}</ul>
<div style="background:#eef6ff;border-left:4px solid #2f80ed;border-radius:8px;padding:14px;margin:18px 0">
<strong>Cómo leer este reporte</strong>
<p style="margin:6px 0 0;color:#52657e">El cambio del periodo compara el primer y el último dato disponible. La volatilidad resume cuánto variaron los valores entre días; la cobertura indica qué proporción de días hábiles tuvo información válida.</p>
</div>
<h2>Indicadores</h2>
<p style="color:#61738d;font-size:14px">Una guía breve para entender qué mide cada indicador y cómo interpretar su valor.</p>
{indicators}
<h2>Alertas</h2><ul>{alerts or '<li>No se detectaron alertas.</li>'}</ul>
</main></body></html>"""
    return subject, body


def send_report(
    recipient: str,
    subject: str,
    body: str,
    settings: Settings,
    dry_run: bool = True,
) -> None:
    recipient = validate_recipient(recipient)
    if dry_run:
        return
    try:
        sender, password = settings.require_gmail()
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient
        message.set_content("Este reporte requiere un cliente con HTML habilitado.")
        message.add_alternative(body, subtype="html")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(message)
    except ConfigurationError:
        raise
    except (OSError, smtplib.SMTPException) as error:
        raise BackendError(f"No fue posible enviar el reporte: {error}") from error
