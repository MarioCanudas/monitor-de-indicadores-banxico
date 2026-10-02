import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from backend.main import clean_observations, create_ingestion, parse_observations
from backend.statistics import compute_grouped_statistics, compute_statistics


class ObservationCleaningTests(unittest.TestCase):
    def test_cleaning_normalizes_values_and_removes_invalid_and_duplicate_rows(self):
        observations = clean_observations([
            {"fecha": "02/01/2024", "dato": "1,234.50"},
            {"fecha": "01/01/2024", "dato": "N/E"},
            {"fecha": "fecha inválida", "dato": "12"},
            {"fecha": "02/01/2024", "dato": "1,235.00"},
            {"fecha": "03/01/2024", "dato": "inf"},
        ])

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations.iloc[0]["valor"], 1235.0)

    def test_ingestion_uses_previous_batch_value_for_first_variation(self):
        documents = parse_observations(
            {
                "idSerie": "SF43718",
                "datos": [
                    {"fecha": "02/01/2024", "dato": "125"},
                    {"fecha": "03/01/2024", "dato": "150"},
                ],
            },
            "run-1",
            previous_value=100,
        )

        self.assertEqual([document["var_pct"] for document in documents], [25.0, 20.0])

    def test_empty_statistics_keep_documented_metric_keys(self):
        statistics = compute_statistics(pd.DataFrame(columns=["fecha", "valor"]))

        self.assertEqual(
            set(statistics),
            {"count", "mean", "std", "min", "25%", "50%", "75%", "max"},
        )
        self.assertTrue(all(value is None for value in statistics.values()))

    def test_grouped_statistics_support_year_month_and_year_month(self):
        observations = pd.DataFrame({
            "fecha": pd.to_datetime(["2024-01-01", "2024-02-01", "2025-01-01"]),
            "valor": [10.0, 20.0, 30.0],
        })

        self.assertEqual(
            [item["grupo"] for item in compute_grouped_statistics(observations, "year")],
            ["2024", "2025"],
        )
        self.assertEqual(
            [item["grupo"] for item in compute_grouped_statistics(observations, "month")],
            ["01", "02"],
        )
        self.assertEqual(
            [item["grupo"] for item in compute_grouped_statistics(observations, "year_month")],
            ["2024-01", "2024-02", "2025-01"],
        )

    def test_ingestion_rejects_an_invalid_date_range_before_connecting(self):
        with patch("backend.main.get_database") as get_database:
            with self.assertRaises(HTTPException) as context:
                create_ingestion(date(2024, 2, 1), date(2024, 1, 1))

        self.assertEqual(context.exception.status_code, 422)
        get_database.assert_not_called()


if __name__ == "__main__":
    unittest.main()