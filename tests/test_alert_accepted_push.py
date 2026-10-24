"""Ensure only an accepted, exactly targeted push can update delivery history."""
import unittest
from scripts.record_accepted_push import record_accepted_target
from scripts.alert_delivery_ledger import delivered

class AcceptedPushLedgerTests(unittest.TestCase):
    def test_single_target_success(self):
        initial = {"delivered": []}
        result = record_accepted_target(initial, "job1", "sub1", 200,
                                        {"id": "notification-1", "recipients": 1},
                                        targeted_subscription_ids=["sub1"])
        self.assertTrue(delivered(result, "job1", "sub1"))
        self.assertFalse(delivered(initial, "job1", "sub1"))

    def test_blank_job_id_rejected(self):
        with self.assertRaises(ValueError):
            record_accepted_target({"delivered": []}, " ", "sub1", 200,
                                   {"id": "notification-1", "recipients": 1},
                                   targeted_subscription_ids=["sub1"])

    def test_unsafe_requests_never_record(self):
        cases = [
            (["sub1", "sub2"], 200, {"id": "x", "recipients": 2}),
            (["other"], 200, {"id": "x", "recipients": 1}),
            (["sub1"], 400, {"id": "x", "recipients": 1}),
            (["sub1"], 200, {"id": "x", "recipients": 0}),
            (["sub1"], 200, {"id": "x", "recipients": 1, "errors": ["failure"]}),
        ]
        for targets, status, payload in cases:
            initial = {"delivered": []}
            with self.subTest(targets=targets, status=status):
                with self.assertRaises(ValueError):
                    record_accepted_target(initial, "job1", "sub1", status, payload,
                                           targeted_subscription_ids=targets)
                self.assertEqual(initial, {"delivered": []})

if __name__ == "__main__":
    unittest.main()
