"""No API requests: verify accepted notification persistence and safe failures."""
import tempfile
import unittest
from pathlib import Path
from scripts.persist_accepted_push import record_and_save_accepted
from scripts.alert_delivery_ledger import load, delivered

class PersistAcceptedPushTests(unittest.TestCase):
    def test_persist_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            kwargs = {"targeted_subscription_ids": ["sub1"]}
            self.assertTrue(record_and_save_accepted(path, "job1", "sub1", 200,
                            {"id": "notification-1", "recipients": 1}, **kwargs))
            self.assertTrue(delivered(load(path), "job1", "sub1"))
            self.assertFalse(record_and_save_accepted(path, "job1", "sub1", 200,
                             {"id": "notification-1", "recipients": 1}, **kwargs))

    def test_duplicate_with_invalid_response_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            record_and_save_accepted(path, "job1", "sub1", 200,
                                     {"id": "ok", "recipients": 1},
                                     targeted_subscription_ids=["sub1"])
            with self.assertRaises(ValueError):
                record_and_save_accepted(path, "job1", "sub1", 400,
                                         {"errors": ["invalid"]},
                                         targeted_subscription_ids=["sub1"])

    def test_rejection_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            with self.assertRaises(ValueError):
                record_and_save_accepted(path, "job1", "sub1", 400, {"errors": ["bad"]},
                                         targeted_subscription_ids=["sub1"])
            self.assertFalse(path.exists())

    def test_lock_file_created_with_private_permissions(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            record_and_save_accepted(path, "job1", "sub1", 200,
                                     {"id": "x", "recipients": 1},
                                     targeted_subscription_ids=["sub1"])
            lock = Path(str(path) + ".lock")
            self.assertTrue(lock.exists())
            self.assertEqual(stat.S_IMODE(os.stat(lock).st_mode), 0o600)

    def test_parallel_writers_do_not_lose_updates(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            def record(index):
                sub = "sub-" + str(index)
                return record_and_save_accepted(
                    path, "job1", sub, 200,
                    {"id": "accepted-" + str(index), "recipients": 1},
                    targeted_subscription_ids=[sub])
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(record, range(20)))
            self.assertTrue(all(results))
            state = load(path)
            self.assertEqual(len(state["delivered"]), 20)
            for index in range(20):
                self.assertTrue(delivered(state, "job1", "sub-" + str(index)))

    def test_relative_path_rejected(self):
        with self.assertRaises(ValueError):
            record_and_save_accepted("ledger.json", "job1", "sub1", 200,
                                     {"id": "x", "recipients": 1},
                                     targeted_subscription_ids=["sub1"])

if __name__ == "__main__":
    unittest.main()
