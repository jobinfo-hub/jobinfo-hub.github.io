"""Persist one explicitly targeted OneSignal API acceptance to a private ledger.

Does not send notifications or fetch subscribers. Caller must supply a private,
durable path. POSIX file locking serializes local writers only. Do not use a
public repository file or GitHub Actions cache as the authoritative ledger.
"""
from pathlib import Path
from contextlib import contextmanager
import fcntl
import os
from scripts.alert_delivery_ledger import load, save, delivered
from scripts.record_accepted_push import record_accepted_target

@contextmanager
def exclusive_ledger_lock(path):
    """Serialize read-modify-write across local processes on POSIX runners."""
    lock_path = Path(str(path) + ".lock")
    if lock_path.is_symlink():
        raise ValueError("Refusing a symlinked lock file")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "r+") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def record_and_save_accepted(path, job_id, subscription_id, status, payload, *, targeted_subscription_ids):
    ledger_path = Path(path)
    if not ledger_path.is_absolute():
        raise ValueError("Use an absolute private ledger path")
    if ledger_path.is_symlink():
        raise ValueError("Refusing a symlinked ledger path")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_ledger_lock(ledger_path):
        state = load(ledger_path)
        if delivered(state, job_id, subscription_id):
            return False
        updated = record_accepted_target(state, job_id, subscription_id, status, payload,
                                         targeted_subscription_ids=targeted_subscription_ids)
        save(ledger_path, updated)
        return True
