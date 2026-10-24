"""Delivery ledger must not confuse detection with delivery."""
import unittest
from scripts.alert_delivery_ledger import delivered, mark_delivered, delivery_key

class DeliveryLedgerTests(unittest.TestCase):
    def test_only_explicit_delivery_is_recorded(self):
        initial = {"delivered": []}
        self.assertFalse(delivered(initial, "job1", "sub1"))
        updated = mark_delivered(initial, "job1", "sub1")
        self.assertFalse(delivered(initial, "job1", "sub1"))
        self.assertTrue(delivered(updated, "job1", "sub1"))
        self.assertFalse(delivered(updated, "job1", "sub2"))
        self.assertEqual(updated, mark_delivered(updated, "job1", "sub1"))

    def test_delivery_key_does_not_expose_subscription(self):
        key = delivery_key("job1", "private-device-id")
        self.assertEqual(len(key), 64)
        self.assertNotIn("private-device-id", key)
        self.assertNotEqual(key, delivery_key("job1", "another-device"))

    def test_missing_identity_rejected(self):
        with self.assertRaises(ValueError):
            mark_delivered({}, "", "sub1")

if __name__ == "__main__":
    unittest.main()
