from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verified_sandbox.storage import JsonlStore, RunStore


class StorageTests(unittest.TestCase):
    def test_jsonl_store_round_trips_and_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonlStore(Path(directory) / "events.jsonl")
            store.append({"timestamp": 1, "run_id": "r1", "event": "start", "previous_hash": "0" * 64, "hash": "1" * 64, "kind": "test"})
            store.append({"timestamp": 2, "run_id": "r1", "event": "done", "previous_hash": "1" * 64, "hash": "2" * 64, "kind": "test"})
            self.assertEqual(len(store.query(run_id="r1")), 2)
            self.assertEqual(store.all()[1]["event"], "done")

    def test_chain_verification_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = JsonlStore(path)
            store.append({"timestamp": 1, "run_id": "r1", "event": "start", "previous_hash": "0" * 64, "hash": "1" * 64})
            self.assertFalse(store.verify_chain()["valid"])

    def test_run_store_isolated_by_id(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(Path(directory) / "events.jsonl")
            store.put("one", {"value": 1})
            store.put("two", {"value": 2})
            self.assertEqual(store.get("one")["value"], 1)
            self.assertEqual(len(store.values()), 2)


if __name__ == "__main__":
    unittest.main()
