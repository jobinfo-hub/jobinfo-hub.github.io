
#!/usr/bin/env python3
"""CareerPick Threads job selector - safe preview mode."""

import json
import os
import re
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "alio.json"
HISTORY = ROOT / "threads_posted.json"
KST = ZoneInfo("Asia/Seoul")

MAX_DAILY = 5
MIN_DAYS = 5
MAX_DAYS = 20


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).astimezone(KST).date()
    except (ValueError, TypeError):
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None


def hiring_count(job):
    # 'n' 필드는 실제 모집인원인지 확인 전까지
    # 순위 산정에 사용하지 않습니다.
    for key in ("verified_hiring_count",):
        value = job.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(value, 0)
        if isinstance(value, str) and re.fullmatch(
            r"\d+", value.strip()
        ):
            return int(value.strip())
    return None


def is_regular(job):
    emp = job.get("emp", [])
    if isinstance(emp, str):
        emp = [emp]
    return any(
        "정규직" in str(item) or "무기계약" in str(item)
        for item in emp
    )


def candidates(posts, history, today):
    posted = set(history.get("posted_ids", []))
    selected = []

    for job in posts:
        if not isinstance(job, dict):
            continue

        job_id = str(job.get("id", "")).strip()
        due = parse_date(job.get("due"))

        if not job_id or not due or job_id in posted:
            continue

        remaining = (due - today).days
        if not MIN_DAYS <= remaining <= MAX_DAYS:
            continue

        if not job.get("title") or not job.get("org"):
            continue

        count = hiring_count(job)
        regular = is_regular(job)

        selected.append({
            "id": job_id,
            "org": job["org"],
            "title": job["title"],
            "url": job.get("url", ""),
            "due": str(due),
            "days": remaining,
            "regular": regular,
            "count": count,
            "region": job.get("region", ""),
            "edu": job.get("edu", []),
        })

    selected.sort(key=lambda j: (
        -int(j["regular"]),
        -int(j["count"] is not None and j["count"] >= 30),
        -(j["count"] if j["count"] is not None else -1),
        j["days"],
        j["id"],
    ))

    return selected


def main():
    now = datetime.now(KST)
    data = load_json(DATA, {"posts": []})
    history = load_json(HISTORY, {"posted_ids": []})

    posts = data.get("posts", [])
    if not isinstance(posts, list):
        raise ValueError("Invalid alio.json posts")

    eligible = candidates(posts, history, now.date())

    print("CareerPick Threads preview")
    print("KST:", now.isoformat())
    print("Eligible jobs:", len(eligible))

    for index, job in enumerate(eligible[:MAX_DAILY], 1):
        print(
            f"{index}. [{job['org']}] "
            f"{job['title']} | D-{job['days']} "
            f"| regular={job['regular']} "
            f"| count={job['count']}"
        )

    # 실제 게시 기능은 인증 후 추가합니다.
    # 인증 전에는 이력을 변경하지 않습니다.
    if os.getenv("THREADS_ENABLED") == "true":
        raise RuntimeError(
            "Publishing adapter not installed. "
            "Do not enable Threads yet."
        )

    print("Preview completed. No posts published.")


if __name__ == "__main__":
    main()
