"""Validate OneSignal notification creation responses without network requests.

An accepted API request is not proof that the device displayed the notification.
Only an accepted targeted notification may be recorded as API-accepted.
"""
def api_accepted(status, payload):
    if not isinstance(status, int) or not 200 <= status < 300:
        return False
    if not isinstance(payload, dict) or payload.get("errors"):
        return False
    notification_id = payload.get("id")
    recipients = payload.get("recipients")
    return isinstance(notification_id, str) and bool(notification_id.strip()) and isinstance(recipients, int) and recipients > 0
