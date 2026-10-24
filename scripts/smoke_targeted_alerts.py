"""Run an entirely synthetic end-to-end targeted-alert smoke check.

No credentials, no subscriber export, no API requests, and no sending.
"""
from scripts.plan_targeted_alerts import plan_notifications
from scripts.alert_delivery_ledger import delivered, mark_delivered, delivery_key

def main():
    jobs = [{"id": "synthetic-001", "title": "행정직", "region": "서울"}]
    tags = {"cp_preferences_set": "yes", "cp_schema": "2", "cp2_region_1": "서울"}
    subscribers = [
        {"subscription_id": "synthetic-opted-in", "opted_in": True, "tags": tags},
        {"subscription_id": "synthetic-opted-out", "opted_in": False, "tags": tags},
    ]
    plan = plan_notifications(jobs, subscribers)
    assert len(plan) == 1, "Expected exactly one opted-in match"
    item = plan[0]
    assert item["sendable"] is False
    state = {"delivered": []}
    assert not delivered(state, item["job_id"], item["subscription_id"])
    state = mark_delivered(state, item["job_id"], item["subscription_id"])
    assert delivered(state, item["job_id"], item["subscription_id"])
    assert state["delivered"] == [delivery_key(item["job_id"], item["subscription_id"])]
    assert "synthetic-opted-in" not in str(state)
    print("Synthetic targeted alert smoke check: PASS (sent=0)")

if __name__ == "__main__":
    main()
