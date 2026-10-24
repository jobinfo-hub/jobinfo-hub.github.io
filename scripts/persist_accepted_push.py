"""Persist one explicitly targeted OneSignal API acceptance to a private ledger.

Does not send notifications or fetch subscribers. Caller must supply a private,
durable path and must serialize concurrent writers externally. Do not use a
public repository file or GitHub Actions cache as the authoritative ledger.
"""
from pathlib import Path
from scripts.alert_delivery_ledger import load, save, delivered
from scripts.record_accepted_push import record_accepted_target

def record_and_save_accepted(path, job_id, subscription_id, status, payload, *, targeted_subscription_ids):
    ledger_path = Path(path)
    if not ledger_path.is_absolute():
        raise ValueError("Use an absolute private ledger path")
    if ledger_path.is_symlink():
        raise ValueError("Refusing a symlinked ledger path")
    state = load(ledger_path)
    if delivered(state, job_id, subscription_id):
        return False
    updated = record_accepted_target(state, job_id, subscription_id, status, payload,
                                     targeted_subscription_ids=targeted_subscription_ids)
    save(ledger_path, updated)
    return True
