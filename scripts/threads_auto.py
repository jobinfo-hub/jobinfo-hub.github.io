
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

    text = str(value).strip()

    # 날짜만 있는 값은 시간대 변환 없이 처리
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    try:
        dt = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
        if dt.tzinfo is None:
            return dt.date()
        return dt.astimezone(KST).date()
    except (ValueError, TypeError):
        return None


def hiring_count(job):
    # 검증된 모집인원만 사용
    value = job.get("verified_hiring_count")

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if re.fullmatch(r"\d+", cleaned):
            return int(cleaned)

    return None


def is_regular(job):
    emp = job.get("emp", [])

    if isinstance(emp, str):
        emp = [emp]

    if not isinstance(emp, list):
        return False

    return any(
        "정규직" in str(item) or "무기계약" in str(item)
        for item in emp
    )


def count_priority(count):
    if count is None:
        return 0
    if count >= 100:
        return 4
    if count >= 50:
        return 3
    if count >= 30:
        return 2
    return 1


def candidates(posts, history, today):
    posted = set(
        str(value) for value in history.get("posted_ids", [])
    )

    selected = []
    seen = set()

    for job in posts:
        if not isinstance(job, dict):
            continue

        job_id = str(job.get("id", "")).strip()
        due = parse_date(job.get("due"))

        if not job_id or not due:
            continue

        if job_id in posted or job_id in seen:
            continue

        remaining = (due - today).days

        if not MIN_DAYS <= remaining <= MAX_DAYS:
            continue

        if not job.get("title") or not job.get("org"):
            continue

        seen.add(job_id)

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
            "priority": count_priority(count),
            "region": job.get("region", ""),
            "edu": job.get("edu", []),
        })

    # 정규직 → 모집인원 등급 → 실제 인원 → 마감일
    selected.sort(key=lambda j: (
        -int(j["regular"]),
        -j["priority"],
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

    print("=== CareerPick Threads Preview ===")
    print("KST:", now.isoformat())
    print("Eligible jobs:", len(eligible))

    print("\n=== Selected Top 5 ===")

    for index, job in enumerate(eligible[:MAX_DAILY], 1):
        count_label = (
            str(job["count"]) + "명"
            if job["count"] is not None
            else "미확인"
        )

        print(
            f"{index}. [{job['org']}] "
            f"{job['title']} "
            f"| D-{job['days']} "
            f"| 정규직={job['regular']} "
            f"| 모집인원={count_label} "
            f"| 우선순위={job['priority']}"
        )

    print("\n=== Data Quality ===")
    print(
        "Verified hiring counts:",
        sum(j["count"] is not None for j in eligible)
    )
    print(
        "Missing hiring counts:",
        sum(j["count"] is None for j in eligible)
    )

    # 인증 완료 전 실제 게시 금지
    if os.getenv("THREADS_ENABLED") == "true":
        raise RuntimeError(
            "Threads publishing adapter is not installed. "
            "Keep THREADS_ENABLED disabled."
        )

    print("\nPreview completed. No posts published.")


if __name__ == "__main__":
    main()
