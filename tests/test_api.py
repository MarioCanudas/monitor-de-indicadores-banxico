import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_openapi_contains_ingestion_history_and_grouping(self):
        schema = app.openapi()

        self.assertIn("/ingestas/historial", schema["paths"])
        parameters = schema["paths"]["/estadisticas/{series_id}"]["get"]["parameters"]
        self.assertIn("agrupacion", {parameter["name"] for parameter in parameters})

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


if __name__ == "__main__":
    unittest.main()