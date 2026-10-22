
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

# 자동 발행 선정 조건
MAX_DAILY = 5
MIN_DAYS = 5
MAX_DAYS = 20


def load_json(path, default):
    if not path.exists():
        return default

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def parse_date(value):
    if not value:
        return None

    text = str(value).strip()

    # ISO 날짜/시간의 시간대를 우선 처리
    try:
        dt = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

        if dt.tzinfo is not None:
            return dt.astimezone(KST).date()

        return dt.date()

    except (ValueError, TypeError):
        pass

    try:
        return date.fromisoformat(text[:10])

    except (ValueError, TypeError):
        return None


def parse_count(value):
    """숫자로 확인 가능한 모집인원만 반환."""

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")

        if re.fullmatch(r"\d+", cleaned):
            return int(cleaned)

    return None


def hiring_count(job):
    """
    모집인원 확인 순서

    1. verified_hiring_count
    2. alio.json의 n 필드

    주의:
    n 필드가 실제 모집인원이라는 점은
    ALIO 수집 코드에서 최종 확인 필요.
    """

    for key in (
        "verified_hiring_count",
        "n",
    ):
        count = parse_count(job.get(key))

        if count is not None:
            return count

    return None


def is_regular(job):
    """정규직 또는 무기계약직 여부."""

    emp = job.get("emp", [])

    if isinstance(emp, str):
        emp = [emp]

    if not isinstance(emp, list):
        return False

    return any(
        "정규직" in str(item)
        or "무기계약" in str(item)
        for item in emp
    )


def count_priority(count):
    """모집인원별 우선순위."""

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
    """조건에 맞는 채용공고 선정."""

    posted = set(
        str(value)
        for value in history.get("posted_ids", [])
    )

    selected = []
    seen = set()

    for job in posts:

        if not isinstance(job, dict):
            continue

        job_id = str(
            job.get("id", "")
        ).strip()

        due = parse_date(
            job.get("due")
        )

        if not job_id or not due:
            continue

        # 이미 게시한 공고 제외
        if job_id in posted:
            continue

        # 동일 실행 내 중복 제외
        if job_id in seen:
            continue

        remaining = (
            due - today
        ).days

        # 마감일 D-5 ~ D-20
        if not MIN_DAYS <= remaining <= MAX_DAYS:
            continue

        if not job.get("title"):
            continue

        if not job.get("org"):
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

    # 자동 선정 우선순위
    #
    # 1. 정규직 우선
    # 2. 모집인원 100명 이상
    # 3. 모집인원 50~99명
    # 4. 모집인원 30~49명
    # 5. 모집인원 1~29명
    # 6. 모집인원 미확인
    #
    # 동일 조건에서는 실제 모집인원,
    # 마감일 순으로 정렬

    selected.sort(
        key=lambda j: (
            -int(j["regular"]),
            -j["priority"],
            -(
                j["count"]
                if j["count"] is not None
                else -1
            ),
            j["days"],
            j["id"],
        )
    )

    return selected


def main():

    now = datetime.now(KST)

    data = load_json(
        DATA,
        {"posts": []}
    )

    history = load_json(
        HISTORY,
        {"posted_ids": []}
    )

    posts = data.get("posts", [])

    if not isinstance(posts, list):
        raise ValueError(
            "Invalid alio.json posts"
        )

    eligible = candidates(
        posts,
        history,
        now.date()
    )

    print(
        "=== CareerPick Threads Preview ==="
    )

    print(
        "KST:",
        now.isoformat()
    )

    print(
        "Total source jobs:",
        len(posts)
    )

    print(
        "Eligible jobs:",
        len(eligible)
    )

    print(
        "\n=== Selected Top 5 ==="
    )

    for index, job in enumerate(
        eligible[:MAX_DAILY],
        1
    ):

        count_label = (
            f"{job['count']}명"
            if job["count"] is not None
            else "미확인"
        )

        regular_label = (
            "정규직 우선"
            if job["regular"]
            else "일반"
        )

        print(
            f"{index}. [{job['org']}] "
            f"{job['title']}"
        )

        print(
            f"   마감: D-{job['days']}"
        )

        print(
            f"   고용형태: {regular_label}"
        )

        print(
            f"   모집인원: {count_label}"
        )

        print(
            f"   우선순위: {job['priority']}"
        )

        print(
            f"   링크: {job['url']}"
        )

    print(
        "\n=== Data Quality ==="
    )

    verified = sum(
        j["count"] is not None
        for j in eligible
    )

    missing = sum(
        j["count"] is None
        for j in eligible
    )

    print(
        "Available hiring counts:",
        verified
    )

    print(
        "Missing hiring counts:",
        missing
    )

    print(
        "Regular jobs:",
        sum(
            j["regular"]
            for j in eligible
        )
    )

    print(
        "\n=== Publishing Status ==="
    )

    # 실제 Threads 게시 기능은 아직 미설치
    # 인증 전 게시 및 이력 변경 금지

    if os.getenv(
        "THREADS_ENABLED", ""
    ).lower() == "true":

        raise RuntimeError(
            "Threads publishing adapter "
            "is not installed. "
            "Keep THREADS_ENABLED disabled."
        )

    print(
        "Preview completed."
    )

    print(
        "No posts published."
    )

    print(
        "Posting history unchanged."
    )


if __name__ == "__main__":
    main()
