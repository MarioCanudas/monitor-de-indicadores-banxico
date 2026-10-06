import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from backend.config import Settings
from backend.llm_client import _narrative_input, generate_executive_summary
from backend.reports import render_report, send_report, validate_recipient


def settings_without_external_services() -> Settings:
    return Settings(
        banxico_api=None,
        mongodb_uri=None,
        mongodb_database="test",
        mongodb_timeout_ms=5000,
        default_start_date=date(2024, 1, 1),
        max_page_size=1000,
        alert_medium_threshold_pct=2,
        alert_high_threshold_pct=5,
        azure_openai_api_key=None,
        azure_openai_endpoint=None,
        azure_openai_deployment="gpt-4.1-mini-ejercicio-openai",
        azure_openai_api_version="2024-10-21",
        gmail_user=None,
        gmail_key=None,
    )


def snapshot() -> dict:
    return {
        "_id": "2026-10-05|2026-10-05",
        "creado_en": datetime.now(timezone.utc),
        "desde": date(2026, 10, 5),
        "hasta": date(2026, 10, 5),
        "series": [{
            "serie_id": "SF43718",
            "ultimo_valor": 18.25,
            "var_pct": 5.2,
            "min": 17.0,
            "max": 18.25,
            "promedio": 17.6,
        }],
        "alertas": [{
            "tipo": "variacion_porcentual",
            "severidad": "alta",
            "serie_id": "SF43718",
            "mensaje": "SF43718 superó el umbral.",
            "valor": 18.25,
            "var_pct": 5.2,
        }],
        "estado": "con_alertas",
        "analisis": {
            "resumen": "El dólar tuvo un movimiento relevante.",
            "puntos_clave": ["SF43718: 18.2500 (5.2000%)"],
            "alertas": ["La serie SF43718 registró una variación de 5.2000%."],
            "limitaciones": [],
        },
    }


class ReportTests(unittest.TestCase):
    def test_invalid_recipient_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_recipient("not-an-email")

    def test_rendered_report_is_html(self):
        subject, body = render_report(snapshot())

        self.assertIn("2026-10-05", subject)
        self.assertIn("<!doctype html>", body)
        self.assertIn("SF43718", body)
        self.assertIn("El dólar tuvo", body)
        self.assertIn("Tipo de cambio FIX", body)
        self.assertIn("Cuántos pesos se necesitan", body)
        self.assertIn("Resumen diario · 2026-10-05", body)
        self.assertIn("<h2>Resumen</h2>", body)
        self.assertIn("Pesos por dólar, FIX: 18.2500 (+5.2000% en el periodo)", body)
        self.assertNotIn("<li>SF43718:", body)

    def test_executive_summary_replaces_series_ids_with_indicator_names(self):
        data = snapshot()
        data["analisis"]["resumen"] = "SF43718 tuvo un movimiento relevante."
        data["analisis"]["alertas"] = ["SF43718 superó el umbral."]

        _, body = render_report(data)

        self.assertIn("Pesos por dólar, FIX tuvo un movimiento relevante.", body)
        self.assertIn("Pesos por dólar, FIX superó el umbral.", body)
        self.assertNotIn("SF43718 tuvo", body)

    def test_dry_run_does_not_connect_to_smtp(self):
        with patch("backend.reports.smtplib.SMTP_SSL") as smtp:
            send_report(
                "destino@example.com",
                "Asunto",
                "<p>Reporte</p>",
                settings_without_external_services(),
                dry_run=True,
            )
        smtp.assert_not_called()

    def test_missing_llm_configuration_uses_deterministic_fallback(self):
        result = generate_executive_summary(snapshot(), settings_without_external_services())

        self.assertIn("indicadores", result.resumen)
        self.assertEqual(result.puntos_clave, [])
        self.assertEqual(result.alertas, [])

    def test_llm_input_is_qualitative_and_validated(self):
        narrative = _narrative_input(snapshot())

        self.assertEqual(narrative.indicadores[0].nombre, "Pesos por dólar, FIX")
        self.assertEqual(narrative.indicadores[0].balance, "al_alza")
        self.assertNotIn("18.25", narrative.model_dump_json())

    def test_llm_output_is_structured_and_only_fills_narrative(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"resumen":"El comportamiento fue mixto y conviene observar su evolución."}'
                    )
                )
            ]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda *args, **kwargs: response
                )
            )
        )
        with patch("backend.llm_client._client", return_value=client):
            result = generate_executive_summary(snapshot(), settings_without_external_services())

        self.assertEqual(
            result.resumen,
            "El comportamiento fue mixto y conviene observar su evolución.",
        )
        self.assertEqual(result.puntos_clave, [])
        self.assertEqual(result.alertas, [])


if __name__ == "__main__":
    unittest.main()
