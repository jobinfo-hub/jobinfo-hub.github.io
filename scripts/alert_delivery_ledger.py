"""Separate candidate observation state from successful notification delivery.

Detection is not delivery. Never mark a notification sent from a dry run.
"""
import json
from pathlib import Path

def delivered(state, job_id, subscription_id, kind="new_job"):
    key = str(kind) + ":" + str(job_id) + ":" + str(subscription_id)
    return key in state.get("delivered", [])

def mark_delivered(state, job_id, subscription_id, kind="new_job"):
    if not job_id or not subscription_id:
        raise ValueError("job and subscriber are required")
    key = str(kind) + ":" + str(job_id) + ":" + str(subscription_id)
    return {"delivered": sorted(set(state.get("delivered", [])) | {key})}

def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"delivered": []}
