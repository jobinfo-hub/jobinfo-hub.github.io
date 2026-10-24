"""Targeted notification planning is opt-in, deduplicated, and never sendable."""
import unittest
from scripts.plan_targeted_alerts import plan_notifications

JOB = {"id": "a100", "title": "행정직", "region": "서울"}
TAGS = {"cp_schema": "2", "cp_preferences_set": "yes", "cp2_region_1": "서울"}

class TargetedPlanTests(unittest.TestCase):
    def test_opt_in_and_dedup(self):
        subs = [
            {"subscription_id": "a", "opted_in": True, "tags": TAGS},
            {"subscription_id": "a", "opted_in": True, "tags": TAGS},
            {"subscription_id": "b", "opted_in": False, "tags": TAGS},
            {"subscription_id": "c", "opted_in": True, "tags": {"cp_schema": "2", "cp_preferences_set": "yes", "cp2_region_1": "부산"}},
        ]
        rows = plan_notifications([JOB, JOB], subs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["job_id"], "a100")
        self.assertFalse(rows[0]["sendable"])

    def test_generator_subscribers_work_for_multiple_jobs(self):
        subs = ({"subscription_id": "a", "opted_in": True, "tags": TAGS} for _ in range(1))
        rows = plan_notifications([JOB, {"id": "a101", "title": "행정직 2", "region": "서울"}], subs)
        self.assertEqual(len(rows), 2)

    def test_malformed_job_is_skipped(self):
        self.assertEqual(plan_notifications([None, "bad"], []), [])

    def test_missing_ids_are_skipped(self):
        self.assertEqual(plan_notifications([{"title": "no id"}],
                          [{"subscription_id": "a", "opted_in": True, "tags": TAGS}]), [])

if __name__ == "__main__":
    unittest.main()
