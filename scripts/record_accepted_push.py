"""Record a OneSignal API-accepted *single-device* request only after validation.

This module does not send notifications, fetch subscribers, or persist state.
API acceptance is not confirmation of device display.
"""
from scripts.onesignal_response_validation import api_accepted
from scripts.alert_delivery_ledger import mark_delivered

def record_accepted_target(state, job_id, subscription_id, status, payload, *, targeted_subscription_ids):
    """Return updated ledger for an unambiguously single-device accepted request.

    Refuse broadcasts, multi-recipient requests, mismatched targets, and errors.
    """
    if not isinstance(targeted_subscription_ids, (list, tuple)):
        raise ValueError("Explicit single-device targeting is required")
    if len(targeted_subscription_ids) != 1 or targeted_subscription_ids[0] != subscription_id:
        raise ValueError("Notification target must match exactly one subscription")
    if not isinstance(subscription_id, str) or not subscription_id.strip():
        raise ValueError("Invalid subscription ID")
    if not api_accepted(status, payload) or payload["recipients"] != 1:
        raise ValueError("OneSignal did not accept exactly one targeted recipient")
    return mark_delivered(state, job_id, subscription_id)
