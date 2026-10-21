import unittest
from datetime import date, datetime

from backend.analytics import build_snapshot, build_snapshot_from_metrics
from backend.config import Settings


class AnalyticsTests(unittest.TestCase):
    def test_snapshot_calculates_period_metrics_and_tiie_basis_points(self):
        settings = Settings(
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
            azure_openai_deployment="test",
            azure_openai_api_version="test",
            gmail_user=None,
            gmail_key=None,
        )
        observations = [
            {"serie_id": "SF60648", "fecha": datetime(2026, 10, 1), "valor": 10.0, "var_pct": 0},
            {"serie_id": "SF60648", "fecha": datetime(2026, 10, 2), "valor": 10.2, "var_pct": 2},
            {"serie_id": "SF60648", "fecha": datetime(2026, 10, 5), "valor": 10.1, "var_pct": -0.98},
        ]

        snapshot = build_snapshot(
            observations, date(2026, 10, 1), date(2026, 10, 5), settings
        )
        metrics = snapshot["series"][0]

        self.assertEqual(metrics["valor_inicial"], 10.0)
        self.assertEqual(metrics["valor_final"], 10.1)
        self.assertEqual(metrics["var_periodo_pct"], 1.0)
        self.assertEqual(metrics["cambio_puntos_base"], 10.0)
        self.assertEqual(metrics["dias_alza"], 1)
        self.assertEqual(metrics["dias_baja"], 1)
        self.assertEqual(metrics["observaciones_validas"], 3)
        self.assertGreater(metrics["cobertura_pct"], 0)

    def test_snapshot_from_aggregated_metrics_keeps_kpis_and_builds_alerts(self):
        settings = Settings(
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
            azure_openai_deployment="test",
            azure_openai_api_version="test",
            gmail_user=None,
            gmail_key=None,
        )
        metrics = [{
            "serie_id": "SF43718",
            "valor_inicial": 10.0,
            "fecha_inicial": datetime(2026, 10, 1),
            "valor_final": 10.8,
            "fecha_final": datetime(2026, 10, 5),
            "ultimo_var_pct": 0.5,
            "var_periodo_pct": 8.0,
            "promedio": 10.4,
            "cobertura_pct": 60.0,
        }]

        snapshot = build_snapshot_from_metrics(
            metrics, date(2026, 10, 1), date(2026, 10, 5), settings
        )

        metric = snapshot["series"][0]
        self.assertEqual(metric["serie_id"], "SF43718")
        self.assertEqual(metric["ultimo_valor"], 10.8)
        self.assertEqual(metric["ultima_fecha"], datetime(2026, 10, 5))
        self.assertEqual(metric["var_pct"], 0.5)
        self.assertEqual(metric["promedio"], 10.4)
        self.assertEqual(snapshot["estado"], "con_alertas")
        self.assertEqual(snapshot["alertas"][0]["severidad"], "alta")


if __name__ == "__main__":
    unittest.main()
