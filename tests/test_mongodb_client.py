import unittest
from datetime import datetime

from pymongo.errors import BulkWriteError

from backend.indexes import (
    ADVANCED_INDEXES,
    ALL_INDEXES,
    BASIC_INDEXES,
    PYTHON_INDEXES,
    summarize_explain,
)
from backend.mongodb_client import aggregate_series_metrics, ensure_indexes, insert_observations


class FakeCollection:
    def insert_many(self, documents, ordered):
        raise BulkWriteError({
            "writeErrors": [{"code": 11000}],
            "nInserted": 1,
        })


class FakeDatabase:
    observaciones = FakeCollection()


class IndexCollection:
    def __init__(self):
        self.indexes = []

    def create_index(self, keys, **options):
        self.indexes.append((keys, options))

    def index_information(self):
        information = {"_id_": {"key": [("_id", 1)]}}
        for index, (keys, options) in enumerate(self.indexes):
            information[options.get("name", f"index_{index}")] = {"key": keys}
        return information

    def drop_index(self, name):
        self.indexes = [
            item for item in self.indexes if item[1].get("name") != name
        ]


class IndexDatabase:
    def __init__(self):
        self.collections = {
            "observaciones": IndexCollection(),
            "ingesta_log": IndexCollection(),
            "snapshots": IndexCollection(),
            "series_catalogo": IndexCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


class AggregationCollection:
    def __init__(self, documents):
        self.documents = documents
        self.pipeline = None
        self.options = None

    def aggregate(self, pipeline, **options):
        self.pipeline = pipeline
        self.options = options
        return iter(self.documents)


class AggregationDatabase:
    def __init__(self, documents):
        self.observaciones = AggregationCollection(documents)


class MongoDBClientTests(unittest.TestCase):
    def test_insert_observations_counts_duplicate_keys(self):
        result = insert_observations(FakeDatabase(), [{"_id": "a"}, {"_id": "b"}])

        self.assertEqual(result, (1, 1))

    def test_ensure_indexes_creates_basic_advanced_and_python_indexes(self):
        database = IndexDatabase()

        ensure_indexes(database)

        self.assertEqual(len(BASIC_INDEXES), 8)
        self.assertEqual(len(ADVANCED_INDEXES), 5)
        self.assertEqual(len(PYTHON_INDEXES), 5)
        self.assertEqual(len(ALL_INDEXES), 18)
        created = [
            item
            for collection in database.collections.values()
            for item in collection.indexes
        ]
        self.assertEqual(len(created), 18)
        self.assertIn(
            ([("serie_id", 1), ("fecha", -1)], {"name": "obs_serie_fecha_unique", "unique": True}),
            database.collections["observaciones"].indexes,
        )

    def test_kpi_aggregation_uses_match_and_group_pipeline(self):
        documents = [{
            "serie_id": "SF43718",
            "valor_inicial": 10.0,
            "valor_final": 11.0,
            "var_periodo_pct": 10.0,
        }]
        database = AggregationDatabase(documents)

        result = aggregate_series_metrics(
            database,
            datetime(2026, 10, 1),
            datetime(2026, 10, 31),
            business_days=23,
        )

        self.assertEqual(result, documents)
        stages = [next(iter(stage)) for stage in database.observaciones.pipeline]
        self.assertIn("$match", stages)
        self.assertIn("$group", stages)
        self.assertIn("$project", stages)
        self.assertEqual(database.observaciones.options.get("allowDiskUse"), True)

    def test_explain_summary_extracts_index_and_examined_documents(self):
        explain = {
            "queryPlanner": {
                "winningPlan": {
                    "stage": "FETCH",
                    "inputStage": {
                        "stage": "IXSCAN",
                        "indexName": "obs_serie_fecha_unique",
                    },
                }
            },
            "executionStats": {
                "nReturned": 1,
                "totalDocsExamined": 1,
                "totalKeysExamined": 1,
                "executionTimeMillis": 0,
            },
        }

        summary = summarize_explain(explain)

        self.assertEqual(summary["index"], "obs_serie_fecha_unique")
        self.assertEqual(summary["docs_examined"], 1)
        self.assertEqual(summary["keys_examined"], 1)


if __name__ == "__main__":
    unittest.main()
