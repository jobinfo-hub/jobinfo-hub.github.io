"""Read one known OneSignal subscription with a private API key.

Never enumerates users or writes personal data. Not wired to scheduled sending.
"""
import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen
from scripts.onesignal_subscriber_validation import verified_subscriber


def lookup(subscription_id, *, opener=urlopen, timeout=12):
    if not isinstance(subscription_id, str) or not subscription_id:
        raise ValueError("Subscription id required")
    if not all(char in "0123456789abcdefABCDEF-" for char in subscription_id):
        raise ValueError("Invalid subscription id")
    app_id = os.environ.get("CP_ONESIGNAL_APP_ID", "")
    api_key = os.environ.get("CP_ONESIGNAL_REST_API_KEY", "")
    if not app_id or not api_key:
        raise ValueError("Missing OneSignal credentials")
    path = "/apps/" + quote(app_id, safe="") + "/users/by/onesignal_subscription_id/" + quote(subscription_id, safe="")
    request = Request("https://api.onesignal.com" + path,
                      headers={"Authorization": "Key " + api_key,
                               "Accept": "application/json"}, method="GET")
    with opener(request, timeout=timeout) as response:
        result = json.loads(response.read(262144).decode("utf-8"))
    return verified_subscriber(result, subscription_id)
