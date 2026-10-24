"""Private JSON subscriber registry: fail closed on missing or invalid input.

Never commit the registry. This loader intentionally does not fetch, enumerate,
or export OneSignal subscribers. IDs must come from explicit opt-in records.
"""
import json
from pathlib import Path


def load_registry(path):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("Private subscriber registry unavailable")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("Invalid subscriber registry version")
    subscribers = raw.get("subscriptions")
    if not isinstance(subscribers, list):
        raise ValueError("Invalid subscriber registry records")
    seen = set()
    output = []
    for item in subscribers:
        if not isinstance(item, dict):
            raise ValueError("Invalid subscriber record")
        sid = item.get("subscription_id")
        if not isinstance(sid, str) or not sid or any(c not in "0123456789abcdefABCDEF-" for c in sid):
            raise ValueError("Invalid subscription ID")
        if sid in seen:
            raise ValueError("Duplicate subscription ID")
        seen.add(sid)
        if item.get("opted_in") is not True:
            continue
        output.append(sid)
    return output
