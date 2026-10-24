#!/usr/bin/env python3
"""Validate an explicit OneSignal subscriber export against ALIO jobs.

This tool NEVER queries OneSignal, stores API keys, or sends notifications.
Input is a local JSON file: {"subscribers":[{"subscription_id":"...",
"opted_in":true,"tags":{"cp_schema":"2",...}}]}.
Never commit real subscriber exports: subscription identifiers and preferences
are private. Output includes counts only, never identifiers or tag contents.
"""
import json
import os
from pathlib import Path
from scripts.alert_preference_matcher import matches

def match_counts(jobs, subscribers):
    output = []
    for job in jobs:
        seen = set()
        for subscriber in subscribers:
            sid = subscriber.get("subscription_id")
            if (not isinstance(sid, str) or not sid or sid in seen
                    or subscriber.get("opted_in") is not True):
                continue
            tags = subscriber.get("tags")
            if isinstance(tags, dict) and matches(job, tags):
                seen.add(sid)
        output.append({"job_id": str(job.get("id", "")), "matching_subscriptions": len(seen),
                       "sendable": False})
    return output

def main():
    source = os.environ.get("CP_PRIVATE_SUBSCRIBER_EXPORT")
    if not source:
        print("No private subscriber export configured; no matching performed.")
        return
    raw = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("subscribers"), list):
        raise ValueError("Private subscriber export must contain a subscribers array")
    report = json.loads(Path(os.environ.get("CP_ALERT_REPORT", "careerpick-new-jobs.json")).read_text(encoding="utf-8"))
    rows = match_counts(report.get("new_jobs", []), raw.get("subscribers", []))
    print(json.dumps({"evaluated_jobs": len(rows), "total_job_subscription_matches":
                      sum(x["matching_subscriptions"] for x in rows), "sent": 0}))
    # Do not upload/store subscription IDs or preferences as workflow artifacts.

if __name__ == "__main__":
    main()
