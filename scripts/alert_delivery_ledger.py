"""Separate candidate observation state from successful notification delivery.

Detection is not delivery. Never mark a notification sent from a dry run.
"""
import json
import hashlib
from pathlib import Path

def delivery_key(job_id, subscription_id, kind="new_job"):
    """Avoid storing raw subscription identifiers in persisted delivery records."""
    raw = json.dumps([str(kind), str(job_id), str(subscription_id)], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def delivered(state, job_id, subscription_id, kind="new_job"):
    key = delivery_key(job_id, subscription_id, kind)
    return key in state.get("delivered", [])

def mark_delivered(state, job_id, subscription_id, kind="new_job"):
    if not job_id or not subscription_id:
        raise ValueError("job and subscriber are required")
    key = str(kind) + ":" + str(job_id) + ":" + str(subscription_id)
    return {"delivered": sorted(set(state.get("delivered", [])) | {key})}

def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"delivered": []}
