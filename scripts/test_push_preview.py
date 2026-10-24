import unittest
from datetime import datetime, timedelta, timezone
from scripts.push_preview import candidates, event_deduplicate, matched_job_tags

KST = timezone(timedelta(hours=9))

class PushPreviewTests(unittest.TestCase):
    def test_no_unsafe_tag_matching(self):
        self.assertIsNone(matched_job_tags({"region": "서울"}))

    def test_deduplication(self):
        events = [{"event_id": "new:a1"}, {"event_id": "new:a1"}, {"event_id": "d1:a1:2026-10-25"}]
        self.assertEqual([x["event_id"] for x in event_deduplicate(events, {"new:a1"})], ["d1:a1:2026-10-25"])

    def test_expired_job_excluded(self):
        now = datetime(2026, 10, 25, 12, tzinfo=KST)
        p = {"alio": True, "id": "a1", "title": "Test", "due": (now-timedelta(days=1)).isoformat()}
        self.assertEqual(candidates([p], now), [])

    def test_d1(self):
        now = datetime(2026, 10, 25, 12, tzinfo=KST)
        p = {"alio": True, "id": "a1", "title": "Test", "due": (now+timedelta(days=1)).isoformat()}
        self.assertEqual([x["kind"] for x in candidates([p], now)], ["deadline_d1"])

if __name__ == "__main__":
    unittest.main()
