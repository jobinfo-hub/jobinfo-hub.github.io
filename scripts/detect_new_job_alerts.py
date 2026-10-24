#!/usr/bin/env python3
"""Prepare CareerPick new-job and deadline D-1 candidates. Dry run: no sending."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "alio.json"
STATE = ROOT / ".notification-state.json"
KST = ZoneInfo("Asia/Seoul")

def parse_due(value):
    if not value:
        return None
    try:
        due = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return due.replace(tzinfo=KST) if due.tzinfo is None else due.astimezone(KST)
    except (ValueError, TypeError):
        return None

def compact(p):
    return {key: p.get(key) for key in ("id", "org", "title", "url", "due", "region", "emp", "edu", "cat", "desc")}

def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    posts = payload.get("posts", [])
    current = {str(p["id"]): p for p in posts if isinstance(p, dict) and p.get("id") and p.get("type") == "j" and p.get("alio")}
    previous_state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    initial = not STATE.exists()
    previous_ids = set(map(str, previous_state.get("ids", [])))
    alerted_deadlines = set(previous_state.get("deadline_alerted", []))
    now = datetime.now(KST)
    tomorrow = (now + timedelta(days=1)).date()

    new_jobs = [compact(p) for key, p in current.items() if not initial and key not in previous_ids
                and (parse_due(p.get("due")) is None or parse_due(p.get("due")) > now)]
    deadline_jobs = []
    newly_alerted = set()
    for key, p in current.items():
        due = parse_due(p.get("due"))
        token = f"{key}:{tomorrow.isoformat()}"
        if due and due.date() == tomorrow and due > now and token not in alerted_deadlines:
            deadline_jobs.append(compact(p))
            newly_alerted.add(token)

    report = {"checked_at": now.isoformat(), "dry_run": True, "initial_run": initial,
              "new_count": len(new_jobs), "deadline_d1_count": len(deadline_jobs),
              "new_jobs": new_jobs, "deadline_d1_jobs": deadline_jobs,
              "note": "Candidate report only; device-specific saved-job targeting and OneSignal sending are NOT enabled."}
    Path(os.environ.get("CP_ALERT_REPORT", "/tmp/careerpick-new-jobs.json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("initial_run", "new_count", "deadline_d1_count")}, ensure_ascii=False))
    if os.environ.get("CP_UPDATE_ALERT_STATE") == "1":
        keep = {token for token in alerted_deadlines if token.split(":")[-1] >= now.date().isoformat()}
        state = {"ids": sorted(current), "deadline_alerted": sorted(keep | newly_alerted), "updated": now.isoformat()}
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
