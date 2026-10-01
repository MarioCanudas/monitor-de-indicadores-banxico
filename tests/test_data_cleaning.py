import unittest

from backend.main import clean_observations, parse_observations


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


if __name__ == "__main__":
    unittest.main()