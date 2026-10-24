"""Coordinate validated, individual alert sends without subscriber discovery.

The caller must supply freshly verified opted-in subscriber records in memory.
No subscriber exports are written to disk. Never mark dry-run attempts delivered.
"""
from scripts.alert_preference_matcher import matches
from scripts.alert_delivery_ledger import delivered, mark_delivered
from scripts.onesignal_guarded_transport import send


def deliver_verified(jobs, subscribers, ledger, *, live=False, sender=send):
    state = dict(ledger)
    results = {"eligible": 0, "accepted": 0, "skipped": 0}
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or not job.get("id") or not job.get("title"):
            continue
        for sub in subscribers:
            if not isinstance(sub, dict) or sub.get("opted_in") is not True:
                continue
            sid = sub.get("subscription_id")
            tags = sub.get("tags")
            if not isinstance(sid, str) or not sid or not isinstance(tags, dict):
                continue
            if not matches(job, tags):
                continue
            pair = (str(job["id"]), sid)
            if pair in seen or delivered(state, *pair):
                results["skipped"] += 1
                continue
            seen.add(pair)
            results["eligible"] += 1
            if not live:
                continue
            response = sender(job, sid, verified_opt_in=True, live=True)
            if response.get("sent") is True:
                state = mark_delivered(state, *pair)
                results["accepted"] += 1
    return state, results
