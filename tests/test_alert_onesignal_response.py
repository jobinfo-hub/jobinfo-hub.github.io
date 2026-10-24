"""Reject failed or ambiguous OneSignal notification responses."""
import unittest
from scripts.onesignal_response_validation import api_accepted

class OneSignalResponseTests(unittest.TestCase):
    def test_confirmed_acceptance(self):
        self.assertTrue(api_accepted(200, {"id": "notification-1", "recipients": 1}))

    def test_rejects_failed_or_ambiguous_responses(self):
        samples = [
            (401, {"id": "x", "recipients": 1}),
            (200, {"id": "x", "recipients": 0}),
            (200, {"id": "x"}),
            (200, {"recipients": 1}),
            (200, {"id": "x", "recipients": 1, "errors": ["invalid"]}),
            (200, {"id": "x", "recipients": "1"}),
            (200, None),
        ]
        for status, payload in samples:
            with self.subTest(status=status, payload=payload):
                self.assertFalse(api_accepted(status, payload))

if __name__ == "__main__":
    unittest.main()
