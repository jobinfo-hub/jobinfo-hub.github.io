"""Offline safety checks for guarded OneSignal transport."""
import os
import unittest
from unittest.mock import patch
from scripts.onesignal_guarded_transport import build_payload, send


JOB = {"id": "job-001", "title": "전산직", "org": "테스트기관"}


class GuardedTransportTests(unittest.TestCase):
    def test_payload_targets_only_one_subscription(self):
        payload = build_payload(JOB, "sub-001", "app-001")
        self.assertEqual(payload["include_subscription_ids"], ["sub-001"])
        self.assertEqual(payload["target_channel"], "push")
        self.assertNotIn("included_segments", payload)

    def test_no_consent_blocks_even_dry_run(self):
        with patch.dict(os.environ, {"CP_ONESIGNAL_APP_ID": "app-001"}):
            with self.assertRaises(ValueError):
                send(JOB, "sub-001", verified_opt_in=False)

    def test_default_mode_never_calls_network(self):
        with patch.dict(os.environ, {"CP_ONESIGNAL_APP_ID": "app-001",
                                     "CP_ENABLE_LIVE_PUSH": "0"}, clear=True):
            with patch("scripts.onesignal_guarded_transport.urlopen") as network:
                result = send(JOB, "sub-001", verified_opt_in=True)
                self.assertFalse(result["sent"])
                network.assert_not_called()

    def test_live_requires_both_flags_and_credentials(self):
        with patch.dict(os.environ, {"CP_ONESIGNAL_APP_ID": "app-001",
                                     "CP_ENABLE_LIVE_PUSH": "1"}, clear=True):
            with self.assertRaises(ValueError):
                send(JOB, "sub-001", verified_opt_in=True, live=True)

    def test_invalid_target_rejected(self):
        with self.assertRaises(ValueError):
            build_payload(JOB, "", "app-001")


if __name__ == "__main__":
    unittest.main()
