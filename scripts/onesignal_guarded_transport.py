"""Guarded OneSignal transport for an already validated per-subscriber plan.

This module never discovers subscribers or matches preferences. Callers must
supply an opted-in, server-verified subscription and a validated job.
Sending is disabled unless CP_ENABLE_LIVE_PUSH=1 and credentials exist.
"""
import json
import os
from urllib.request import Request, urlopen

API_URL = "https://api.onesignal.com/notifications"


def build_payload(job, subscription_id, app_id):
    if not isinstance(job, dict) or not str(job.get("id") or "").strip():
        raise ValueError("Job id is required")
    if not str(job.get("title") or "").strip():
        raise ValueError("Job title is required")
    if not isinstance(subscription_id, str) or not subscription_id.strip():
        raise ValueError("Subscription id is required")
    if not isinstance(app_id, str) or not app_id.strip():
        raise ValueError("OneSignal app id is required")
    return {
        "app_id": app_id,
        "target_channel": "push",
        "include_subscription_ids": [subscription_id],
        "headings": {"ko": "커리어픽 신규 채용공고"},
        "contents": {"ko": (str(job.get("org") or "공공기관") + " · " + str(job["title"]))[:160]},
        "url": "https://jobinfo-hub.github.io/",
    }


def send(job, subscription_id, *, verified_opt_in=False, live=False, timeout=15):
    """Send only after the caller verified current consent and matching tags.

    Returns a non-sensitive response; never logs API keys or subscription ids.
    Does not write the delivery ledger: caller must record only confirmed sends.
    """
    if verified_opt_in is not True:
        raise ValueError("Verified current opt-in is required")
    app_id = os.environ.get("CP_ONESIGNAL_APP_ID", "")
    payload = build_payload(job, subscription_id, app_id)
    if not live or os.environ.get("CP_ENABLE_LIVE_PUSH") != "1":
        return {"sent": False, "reason": "live sending disabled"}
    key = os.environ.get("CP_ONESIGNAL_REST_API_KEY", "")
    if not key:
        raise ValueError("Missing private OneSignal REST API key")
    request = Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Key " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read(65536).decode("utf-8"))
    # An accepted notification is not proof that the device displayed it.
    return {"sent": bool(result.get("id")) and not result.get("errors"),
            "notification_id": result.get("id") if not result.get("errors") else None}


if __name__ == "__main__":
    raise SystemExit("Use from a validated alert worker; no standalone broadcasting.")
