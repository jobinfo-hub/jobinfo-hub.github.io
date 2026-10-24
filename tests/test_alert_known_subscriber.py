"""Network-isolated tests for OneSignal known-subscription lookup."""
import io
import json
import os
import unittest
from unittest.mock import patch
from scripts.onesignal_known_subscriber import lookup


class Response:
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, limit):
        return self.stream.read(limit)


class KnownSubscriberTests(unittest.TestCase):
    def test_authorized_single_lookup(self):
        response = {"subscriptions": [{"id": "abc-123", "enabled": True,
                                       "type": "ChromePush"}],
                    "properties": {"tags": {"cp_optin": "yes"}}}
        requests = []
        def opener(request, timeout):
            requests.append(request)
            return Response(response)
        with patch.dict(os.environ, {"CP_ONESIGNAL_APP_ID": "app-123",
                                     "CP_ONESIGNAL_REST_API_KEY": "fake-test-key"}):
            subscriber = lookup("abc-123", opener=opener)
        self.assertEqual(subscriber["subscription_id"], "abc-123")
        self.assertEqual(len(requests), 1)
        self.assertIn("/users/by/onesignal_subscription_id/abc-123",
                      requests[0].full_url)
        self.assertEqual(requests[0].get_method(), "GET")

    def test_missing_credentials_prevents_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                lookup("abc-123", opener=lambda *a, **kw: self.fail("network used"))

    def test_bad_id_prevents_network(self):
        with self.assertRaises(ValueError):
            lookup("../users", opener=lambda *a, **kw: self.fail("network used"))


if __name__ == "__main__":
    unittest.main()
