#!/usr/bin/env python3
"""CareerPick ALIO new-job detector. No credentials or notification sends."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "alio.json"
STATE = ROOT / ".notification-state.json"

def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    posts = payload.get("posts", [])
    current = {str(p["id"]): p for p in posts if p.get("id") and p.get("type") == "j" and p.get("alio")}
    previous = set()
    if STATE.exists():
        previous = set(json.loads(STATE.read_text(encoding="utf-8")).get("ids", []))
    fresh = [p for key, p in current.items() if key not in previous]
    now = datetime.now(timezone.utc)
    fresh = [p for p in fresh if not p.get("due") or datetime.fromisoformat(p["due"].replace("Z", "+00:00")) > now]
    output = {"checked_at": now.isoformat(), "initial_run": not STATE.exists(), "new_count": 0 if not STATE.exists() else len(fresh),
              "new_jobs": [] if not STATE.exists() else [{"id": p["id"], "org": p.get("org"), "title": p.get("title"), "url": p.get("url"), "due": p.get("due")} for p in fresh]}
    Path(os.environ.get("CP_ALERT_REPORT", "/tmp/careerpick-new-jobs.json")).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"initial_run": output["initial_run"], "new_count": output["new_count"]}, ensure_ascii=False))
    if os.environ.get("CP_UPDATE_ALERT_STATE") == "1":
        STATE.write_text(json.dumps({"ids": sorted(current), "updated": now.isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
