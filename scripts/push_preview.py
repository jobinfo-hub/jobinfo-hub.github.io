#!/usr/bin/env python3
"""CareerPick push candidate preview. No external calls or subscriber data access.

This first stage deliberately does NOT send notifications: client-side preference
tags require an audited server-side matching strategy before production sends.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
BASE = "https://jobinfo-hub.github.io"
MAX_PREVIEW = 30

def parse_date(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=KST)
    except ValueError:
        return None

def candidates(posts, now):
    found = []
    for p in posts:
        if not isinstance(p, dict) or not p.get("alio"):
            continue
        job_id = str(p.get("id", ""))
        if not (job_id.startswith("a") and job_id[1:].isdigit()):
            continue
        due = parse_date(p.get("due"))
        if not due or due < now:
            continue
        pub = parse_date(p.get("pub"))
        title = str(p.get("title", "")).strip()
        if not title:
            continue
        entry = {
            "id": job_id,
            "title": title[:100],
            "org": str(p.get("org", ""))[:80],
            "region": str(p.get("region", ""))[:40],
            "emp": p.get("emp", []),
            "edu": p.get("edu", []),
            "cat": str(p.get("cat", ""))[:80],
            "due": due.isoformat(),
            "url": f"{BASE}/jobs/{job_id}.html",
        }
        if pub and now - timedelta(hours=26) <= pub <= now:
            found.append(dict(entry, kind="new", event_id=f"new:{job_id}"))
        if due.astimezone(KST).date() == (now.astimezone(KST) + timedelta(days=1)).date():
            found.append(dict(entry, kind="deadline_d1", event_id=f"d1:{job_id}:{due.date()}"))
    return found

def matched_job_tags(job):
    """Return a conservative OneSignal tag filter for a job.

    Users select multiple values encoded with '|', which cannot be matched
    safely using exact equality. Therefore this function does not pretend
    that OneSignal's equals filter supports multi-select matching.
    """
    return None


def event_deduplicate(events, sent_ids):
    """Remove previously processed events, without mutating the ledger."""
    seen = set(sent_ids)
    result = []
    for item in events:
        event_id = item["event_id"]
        if event_id not in seen:
            result.append(item)
            seen.add(event_id)
    return result


def load_ledger(path):
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sent_event_ids", []), list):
        raise ValueError("Invalid push ledger format")
    return set(str(x) for x in data["sent_event_ids"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="alio.json")
    ap.add_argument("--output", default="/tmp/careerpick-push-preview.json")
    ap.add_argument("--ledger", default="push_sent.json")
    args = ap.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    now = datetime.now(KST)
    found = event_deduplicate(candidates(data.get("posts", []), now), load_ledger(Path(args.ledger)))
    result = {
        "generated_at": now.isoformat(),
        "mode": "preview_only",
        "total_candidates": len(found),
        "candidates": found[:MAX_PREVIEW],
        "send_enabled": False,
        "targeting_verified": False,
        "deduplication": "preview-only: excludes event IDs in the read-only ledger",
        "reason": "Client-side multi-select tags are pipe-delimited and cannot safely be targeted using OneSignal equals filters. No notifications sent."
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Push preview only: {len(found)} candidates, {min(len(found),MAX_PREVIEW)} shown. No notifications sent.")
    for kind in ("new", "deadline_d1"):
        print(f"  {kind}: {sum(x['kind'] == kind for x in found)}")

if __name__ == "__main__":
    main()
