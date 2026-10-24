"""Regression tests for the production OneSignal schema-4 preference tags."""
import json
import unittest

from scripts.alert_preference_matcher import matches
from scripts.plan_targeted_alerts import plan_notifications


def tags(**overrides):
    profile = {
        "v": 4,
        "region": ["서울"],
        "employment": [],
        "education": [],
        "category": [],
        "keywords": "전산",
    }
    profile.update(overrides)
    return {"cp_optin": "yes", "cp_profile": json.dumps(profile, ensure_ascii=False)}


class Schema4AlertTests(unittest.TestCase):
    def setUp(self):
        self.job = {"id": "alio-123", "title": "전산 담당자", "org": "공공기관",
                    "region": "서울", "emp": "정규직", "edu": "무관", "cat": "정보기술"}

    def test_matching_opted_in_subscriber(self):
        plan = plan_notifications([self.job], [
            {"subscription_id": "sub-a", "opted_in": True, "tags": tags()}
        ])
        self.assertEqual(len(plan), 1)
        self.assertFalse(plan[0]["sendable"])

    def test_opted_out_is_excluded(self):
        self.assertEqual(plan_notifications([self.job], [
            {"subscription_id": "sub-a", "opted_in": False, "tags": tags()}
        ]), [])

    def test_wrong_region_excluded(self):
        self.assertFalse(matches(self.job, tags(region=["부산"])))

    def test_wrong_keyword_excluded(self):
        self.assertFalse(matches(self.job, tags(keywords="간호")))

    def test_malformed_profile_does_not_fall_back(self):
        self.assertFalse(matches(self.job, {
            "cp_optin": "yes", "cp_profile": "{bad",
            "cp_preferences_set": "yes", "cp_schema": "2",
            "cp2_region_1": "서울",
        }))

    def test_empty_preferences_do_not_broadcast(self):
        self.assertFalse(matches(self.job, tags(region=[], keywords="")))

    def test_no_duplicate_candidate_for_same_subscription(self):
        subscribers = [{"subscription_id": "sub-a", "opted_in": True, "tags": tags()}]
        self.assertEqual(len(plan_notifications([self.job, self.job], subscribers)), 1)


if __name__ == "__main__":
    unittest.main()
