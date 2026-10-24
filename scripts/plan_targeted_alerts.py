"""Prepare privacy-safe per-device notification plans. Never sends messages."""
from scripts.alert_preference_matcher import matches

def plan_notifications(jobs, subscribers):
    """Return matching pairs for a local dry run; no network access."""
    result = []
    seen = set()
    subscribers = list(subscribers)
    if not isinstance(jobs, list):
        jobs = list(jobs)
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id") or "").strip()
        if not job_id or not str(job.get("title") or "").strip():
            continue
        for sub in subscribers:
            if not isinstance(sub, dict) or sub.get("opted_in") is not True:
                continue
            sub_id = sub.get("subscription_id")
            tags = sub.get("tags")
            if not isinstance(sub_id, str) or not sub_id.strip() or not isinstance(tags, dict):
                continue
            key = (job_id, sub_id)
            if key in seen or not matches(job, tags):
                continue
            seen.add(key)
            result.append({"job_id": job_id, "subscription_id": sub_id, "sendable": False})
    return result
