import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_openapi_contains_ingestion_history_grouping_and_kpis(self):
        schema = app.openapi()

        self.assertIn("/ingestas/historial", schema["paths"])
        self.assertIn("/kpis/{series_id}", schema["paths"])
        parameters = schema["paths"]["/estadisticas/{series_id}"]["get"]["parameters"]
        self.assertIn("agrupacion", {parameter["name"] for parameter in parameters})

    def test_cors_allows_the_frontend_origin(self):
        response = self.client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:8080",
        )
        self.assertIn("GET", response.headers.get("access-control-allow-methods", ""))

    def test_statistics_endpoint_returns_grouped_contract(self):
        payload = [{
            "idSerie": "SF43718",
            "datos": [
                {"fecha": "01/01/2024", "dato": "10"},
                {"fecha": "01/02/2024", "dato": "20"},
            ],
        }]
        with patch("backend.main.fetch_series", return_value=payload):
            response = self.client.get(
                "/estadisticas/SF43718",
                params={
                    "start_date": date(2024, 1, 1).isoformat(),
                    "end_date": date(2024, 2, 1).isoformat(),
                    "agrupacion": "year_month",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["grupo"] for item in response.json()["grupos"]], ["2024-01", "2024-02"])

    def test_invalid_statistics_group_is_rejected(self):
        response = self.client.get("/estadisticas/SF43718", params={"agrupacion": "week"})

        self.assertEqual(response.status_code, 422)

    def test_kpis_endpoint_returns_the_aggregation_result(self):
        kpi = {
            "serie_id": "SF43718",
            "valor_inicial": 10.0,
            "valor_final": 11.0,
            "var_periodo_pct": 10.0,
        }
        with (
            patch("backend.main.get_database", return_value=object()),
            patch("backend.main.aggregate_series_metrics", return_value=[kpi]) as aggregate,
        ):
            response = self.client.get(
                "/kpis/SF43718",
                params={
                    "start_date": date(2026, 10, 1).isoformat(),
                    "end_date": date(2026, 10, 31).isoformat(),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kpi"], kpi)
        self.assertEqual(aggregate.call_args.kwargs["series_id"], "SF43718")

    def test_kpis_endpoint_rejects_unknown_series(self):
        response = self.client.get("/kpis/NO_EXISTE")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()