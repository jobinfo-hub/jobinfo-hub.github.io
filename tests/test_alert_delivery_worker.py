"""Regression checks for verified alert delivery coordination."""
import json
import unittest
from scripts.alert_delivery_worker import deliver_verified

JOB = {"id": "job-1", "title": "전산직", "region": "서울"}
TAGS = {"cp_optin": "yes", "cp_profile": json.dumps({
    "v": 4, "region": ["서울"], "employment": [], "education": [],
    "category": [], "keywords": "전산"}, ensure_ascii=False)}
SUB = {"subscription_id": "sub-1", "opted_in": True, "tags": TAGS}


class DeliveryWorkerTests(unittest.TestCase):
    def test_dry_run_never_calls_sender_or_marks_delivery(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("dry run attempted network send")
        state, stats = deliver_verified([JOB], [SUB], {"delivered": []}, sender=forbidden)
        self.assertEqual(stats["eligible"], 1)
        self.assertEqual(stats["accepted"], 0)
        self.assertEqual(state["delivered"], [])

    def test_success_is_recorded_and_duplicate_skipped(self):
        calls = []
        def accepted(job, sid, **kwargs):
            calls.append(sid)
            return {"sent": True}
        state, stats = deliver_verified([JOB, JOB], [SUB], {"delivered": []},
                                         live=True, sender=accepted)
        self.assertEqual(calls, ["sub-1"])
        self.assertEqual(stats["accepted"], 1)
        _, again = deliver_verified([JOB], [SUB], state, live=True, sender=accepted)
        self.assertEqual(again["accepted"], 0)
        self.assertEqual(calls, ["sub-1"])

    def test_rejected_response_does_not_mark_delivery(self):
        state, stats = deliver_verified([JOB], [SUB], {"delivered": []},
                                         live=True, sender=lambda *a, **kw: {"sent": False})
        self.assertEqual(state["delivered"], [])
        self.assertEqual(stats["accepted"], 0)

    def test_opted_out_is_not_contacted(self):
        state, stats = deliver_verified([JOB], [{**SUB, "opted_in": False}],
                                         {"delivered": []}, live=True,
                                         sender=lambda *a, **kw: self.fail("unexpected send"))
        self.assertEqual(stats["eligible"], 0)
        self.assertEqual(state["delivered"], [])


if __name__ == "__main__":
    unittest.main()
