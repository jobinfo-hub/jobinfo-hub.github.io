#!/usr/bin/env python3
"""Build opt-in OneSignal notification previews from CareerPick detection reports.

No network calls. No broadcast targeting. Saved-job D-1 requires a server-side
per-subscriber mapping and therefore remains disabled.
"""
import json
import os
from pathlib import Path

REPORT = Path(os.environ.get("CP_ALERT_REPORT", "careerpick-new-jobs.json"))
OUT = Path(os.environ.get("CP_PUSH_PREVIEW", "careerpick-push-preview.json"))

def prepare(report):
    notifications = []
    for job in report.get("new_jobs", []):
        if not job.get("id") or not job.get("title"):
            continue
        notifications.append({
            "kind": "new_job",
            "job_id": str(job["id"]),
            "title": "커리어픽 신규 채용공고",
            "body": (str(job.get("org") or "공공기관") + " · " + str(job["title"]))[:160],
            "url": "https://jobinfo-hub.github.io/",
            "targeting": "NOT_CONFIGURED",
            "sendable": False,
            "reason": "Subscriber preferences are not yet matched server-side."
        })
    return {
        "dry_run": True,
        "new_job_previews": notifications,
        "deadline_d1_previews": [],
        "deadline_note": "Saved jobs are stored locally per device; never send global D-1 notifications.",
        "safe_to_send": False
    }

def main():
    result = prepare(json.loads(REPORT.read_text(encoding="utf-8")))
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"new_job_previews": len(result["new_job_previews"]),
                      "deadline_d1_previews": 0, "sent": 0}, ensure_ascii=False))

if __name__ == "__main__":
    main()
