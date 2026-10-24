"""Private registry format and safety tests."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.private_subscriber_registry import load_registry


class PrivateRegistryTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_registry(path)

    def test_only_opted_in_records(self):
        data = {"version": 1, "subscriptions": [
            {"subscription_id": "abc-123", "opted_in": True},
            {"subscription_id": "def-456", "opted_in": False}]}
        self.assertEqual(self.load(data), ["abc-123"])

    def test_duplicate_rejected(self):
        data = {"version": 1, "subscriptions": [
            {"subscription_id": "abc-123", "opted_in": True},
            {"subscription_id": "abc-123", "opted_in": True}]}
        with self.assertRaises(ValueError):
            self.load(data)

    def test_malformed_id_rejected(self):
        with self.assertRaises(ValueError):
            self.load({"version": 1, "subscriptions": [
                {"subscription_id": "../unsafe", "opted_in": True}]})

    def test_missing_file_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            load_registry("/not-present-careerpick-subscribers.json")


if __name__ == "__main__":
    unittest.main()
