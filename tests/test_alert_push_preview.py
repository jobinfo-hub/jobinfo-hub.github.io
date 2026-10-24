"""Alert preview must never contain a sendable or broad-targeting notification."""
import unittest
from scripts.prepare_push_preview import prepare

class PushPreviewTests(unittest.TestCase):
    def test_no_broadcast_even_with_deadlines(self):
        report = {"new_jobs": [{"id": "a123", "title": "사무 채용", "org": "기관"}],
                  "deadline_d1_jobs": [{"id": "a999", "title": "내일 마감"}]}
        result = prepare(report)
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["safe_to_send"])
        self.assertEqual(len(result["new_job_previews"]), 1)
        self.assertEqual(result["deadline_d1_previews"], [])
        self.assertFalse(result["new_job_previews"][0]["sendable"])
        self.assertEqual(result["new_job_previews"][0]["targeting"], "NOT_CONFIGURED")

    def test_incomplete_job_skipped(self):
        self.assertEqual(prepare({"new_jobs": [{"title": "no id"}, {"id": "1"}]})
                         ["new_job_previews"], [])

if __name__ == "__main__":
    unittest.main()
