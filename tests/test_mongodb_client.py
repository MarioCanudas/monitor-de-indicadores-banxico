import unittest

from pymongo.errors import BulkWriteError

from backend.mongodb_client import ensure_indexes, insert_observations


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


class IndexDatabase:
    def __init__(self):
        self.observaciones = IndexCollection()
        self.ingesta_log = IndexCollection()


class MongoDBClientTests(unittest.TestCase):
    def test_insert_observations_counts_duplicate_keys(self):
        result = insert_observations(FakeDatabase(), [{"_id": "a"}, {"_id": "b"}])

        self.assertEqual(result, (1, 1))

    def test_ensure_indexes_creates_query_indexes(self):
        database = IndexDatabase()

        ensure_indexes(database)

        self.assertEqual(len(database.observaciones.indexes), 2)
        self.assertEqual(len(database.ingesta_log.indexes), 2)
        self.assertIn(([("serie_id", 1), ("fecha", -1)], {}), database.observaciones.indexes)
        self.assertIn(([("run_id", 1)], {"unique": True}), database.ingesta_log.indexes)


if __name__ == "__main__":
    unittest.main()