#!/usr/bin/env python3
"""CareerPick push candidate preview. No external calls or subscriber data access.

This first stage deliberately does NOT send notifications: client-side preference
tags require an audited server-side matching strategy before production sends.
"""
import argparse
import json
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="alio.json")
    ap.add_argument("--output", default="/tmp/careerpick-push-preview.json")
    args = ap.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    now = datetime.now(KST)
    found = candidates(data.get("posts", []), now)
    result = {
        "generated_at": now.isoformat(),
        "mode": "preview_only",
        "total_candidates": len(found),
        "candidates": found[:MAX_PREVIEW],
        "send_enabled": False,
        "reason": "Subscriber-side tag matching and deduplication must be validated before production."
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Push preview only: {len(found)} candidates, {min(len(found),MAX_PREVIEW)} shown. No notifications sent.")
    for kind in ("new", "deadline_d1"):
        print(f"  {kind}: {sum(x['kind'] == kind for x in found)}")

if __name__ == "__main__":
    main()
