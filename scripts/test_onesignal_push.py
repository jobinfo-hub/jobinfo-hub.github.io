#!/usr/bin/env python3
"""OneSignal test sender: explicitly targeted subscription only, never broadcasts.

Required secrets: CP_ONESIGNAL_REST_API_KEY, CP_TEST_SUBSCRIPTION_ID.
Run only with CP_SEND_TEST_PUSH=1. No production automation is enabled here.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

APP_ID = "31443bc9-bef0-4519-9817-2f916a548b6a"
API_URL = "https://api.onesignal.com/notifications"

def main():
    if os.environ.get("CP_SEND_TEST_PUSH") != "1":
        print("SAFE MODE: test sending disabled.")
        return
    key = os.environ.get("CP_ONESIGNAL_REST_API_KEY", "").strip()
    subscription = os.environ.get("CP_TEST_SUBSCRIPTION_ID", "").strip()
    if not key or not subscription:
        sys.exit("Missing CP_ONESIGNAL_REST_API_KEY or CP_TEST_SUBSCRIPTION_ID.")
    if not subscription.count("-") == 4 or len(subscription) != 36:\n        sys.exit("Test subscription must be a UUID; refusing ambiguous targeting.")\n    if len(subscription) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in subscription):
        sys.exit("Invalid test subscription ID.")
    payload = {
        "app_id": APP_ID,
        "include_subscription_ids": [subscription],
        "target_channel": "push",
        "headings": {"en": "CareerPick test", "ko": "커리어픽 테스트 알림"},
        "contents": {"en": "Push setup test only.", "ko": "웹푸시 연결 테스트입니다. 실제 채용 알림이 아닙니다."},
        "url": "https://jobinfo-hub.github.io/"
    }
    req = Request(API_URL, data=json.dumps(payload).encode("utf-8"),
                  headers={"Authorization": "Key " + key, "Content-Type": "application/json"},
                  method="POST")
    try:
        with urlopen(req, timeout=20) as response:
            result = json.load(response)
            print(json.dumps({"status": response.status, "notification_id": result.get("id"),
                              "recipients": result.get("recipients"), "errors": result.get("errors")}, ensure_ascii=False))
            if not result.get("id") or result.get("errors"):
                sys.exit("OneSignal did not confirm successful creation.")
    except (HTTPError, URLError) as error:
        sys.exit("OneSignal request failed: " + str(getattr(error, "code", type(error).__name__)))

if __name__ == "__main__":
    main()
