"""Offline end-to-end smoke test using CareerPick's current OneSignal schema v4.

No API credentials, subscriber exports, network calls, or live notifications.
"""
import json
from scripts.alert_delivery_worker import deliver_verified

def main():
    job = {"id": "synthetic-v4-001", "title": "전산직 채용", "org": "테스트기관",
           "region": "서울", "emp": "정규직", "edu": "무관", "cat": "정보기술"}
    profile = {"v": 4, "region": ["서울"], "employment": [],
               "education": [], "category": [], "keywords": "전산"}
    tags = {"cp_optin": "yes", "cp_profile": json.dumps(profile, ensure_ascii=False)}
    subscribers = [
        {"subscription_id": "synthetic-opt-in", "opted_in": True, "tags": tags},
        {"subscription_id": "synthetic-opt-out", "opted_in": False, "tags": tags},
    ]
    def never_send(*args, **kwargs):
        raise AssertionError("Dry run attempted to send a notification")
    state, stats = deliver_verified([job], subscribers, {"delivered": []},
                                     live=False, sender=never_send)
    assert stats == {"eligible": 1, "accepted": 0, "skipped": 0}, stats
    assert state == {"delivered": []}
    print("Schema-v4 alert delivery smoke test: PASS (accepted=0, network=0)")

if __name__ == "__main__":
    main()
