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

    def test_rejection_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            with self.assertRaises(ValueError):
                record_and_save_accepted(path, "job1", "sub1", 400, {"errors": ["bad"]},
                                         targeted_subscription_ids=["sub1"])
            self.assertFalse(path.exists())

    def test_relative_path_rejected(self):
        with self.assertRaises(ValueError):
            record_and_save_accepted("ledger.json", "job1", "sub1", 200,
                                     {"id": "x", "recipients": 1},
                                     targeted_subscription_ids=["sub1"])

if __name__ == "__main__":
    unittest.main()
