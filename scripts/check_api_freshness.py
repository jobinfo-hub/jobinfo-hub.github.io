#!/usr/bin/env python3
"""Check published CareerPick API snapshots without exposing credentials.

Usage: python scripts/check_api_freshness.py
This check reads local JSON only; it never calls external APIs.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))


def check_snapshot(filename, timestamp_field, max_age_hours):
    path = ROOT / filename
    if not path.exists():
        return f"FAIL {filename}: missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return f"FAIL {filename}: invalid JSON object"
        rows = data.get("posts" if filename == "alio.json" else "rows")
        if not isinstance(rows, list) or not rows:
            return f"FAIL {filename}: empty or invalid records"
        stamp = data.get(timestamp_field)
        if not isinstance(stamp, str):
            return f"FAIL {filename}: missing {timestamp_field}"
        if timestamp_field == "fetched":
            recorded = datetime.fromisoformat(stamp).replace(tzinfo=KST)
        else:
            recorded = datetime.fromisoformat(stamp)
            if recorded.tzinfo is None:
                return f"FAIL {filename}: timezone missing"
        age = datetime.now(KST) - recorded
        if age < -timedelta(hours=2):
            return f"FAIL {filename}: future timestamp"
        if age > timedelta(hours=max_age_hours):
            return f"FAIL {filename}: stale ({age.days}d {age.seconds // 3600}h)"
        return f"PASS {filename}: {len(rows)} records; age {age.days}d {age.seconds // 3600}h"
    except (ValueError, OSError, TypeError) as exc:
        return f"FAIL {filename}: {type(exc).__name__}"


if __name__ == "__main__":
    results = [
        check_snapshot("alio.json", "updated", 48),
        check_snapshot("qnet.json", "fetched", 72),
    ]
    for result in results:
        print(result)
    sys.exit(1 if any(result.startswith("FAIL") for result in results) else 0)
