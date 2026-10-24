"""Offline subscriber matching never targets opted-out or malformed records."""
import unittest
from scripts.evaluate_subscriber_matches import match_counts

JOB = {"id": "job-1", "region": "서울", "title": "사무 채용"}
TAGS = {"cp_schema": "2", "cp_preferences_set": "yes", "cp2_region_1": "서울"}

class SubscriberMatchTests(unittest.TestCase):
    def test_only_opted_in_matching_unique_subscriptions(self):
        subscribers = [
            {"subscription_id": "device-a", "opted_in": True, "tags": TAGS},
            {"subscription_id": "device-a", "opted_in": True, "tags": TAGS},
            {"subscription_id": "device-b", "opted_in": False, "tags": TAGS},
            {"subscription_id": "device-c", "opted_in": True, "tags": {"cp_schema": "2", "cp_preferences_set": "yes", "cp2_region_1": "부산"}},
            {"subscription_id": "", "opted_in": True, "tags": TAGS},
        ]
        result = match_counts([JOB], subscribers)
        self.assertEqual(result[0]["matching_subscriptions"], 1)
        self.assertFalse(result[0]["sendable"])

if __name__ == "__main__":
    unittest.main()
