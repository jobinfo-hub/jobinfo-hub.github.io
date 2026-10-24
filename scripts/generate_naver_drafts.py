"""Generate conservative, review-required Naver blog drafts from CareerPick ALIO data.
Usage: python scripts/generate_naver_drafts.py
No Naver login, publishing, or automatic factual claims.
"""
import csv
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "naver-drafts"
BASE = "https://jobinfo-hub.github.io"
KST = timezone(timedelta(hours=9))

def plain(value):
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    return str(value or "").strip()

def main():
    data = json.loads((ROOT / "alio.json").read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    now = datetime.now(timezone.utc)
    candidates = []
    for post in posts:
        if not post.get("alio") or not post.get("id") or not post.get("url"):
            continue
        due = plain(post.get("due"))
        # Archive all ALIO listings, including expired or undated ones.
        # Publication is always a separate manual decision.
        candidates.append(post)
    candidates.sort(key=lambda p: (plain(p.get("due")) or "9999", plain(p.get("id"))))
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    seen = set()
    for post in candidates:
        pid = re.sub(r"[^a-zA-Z0-9_-]", "", str(post["id"]))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        title = plain(post.get("title"))
        org = plain(post.get("org"))
        fields = [
            ("모집기관", org), ("채용분야", plain(post.get("desc"))),
            ("고용형태", plain(post.get("emp"))), ("학력", plain(post.get("edu"))),
            ("근무지역", plain(post.get("region"))), ("모집인원", plain(post.get("n"))),
            ("접수 마감", plain(post.get("due")))
        ]
        summary = "\n".join(f"- {k}: {v or '공고 원문 확인 필요'}" for k,v in fields)
        # Respect source metadata: dueHasTime=false means the hour is not authoritative.
        deadline_note = (
            "마감 시각은 원문 확인 필요(수집 데이터에 표시된 시간은 확정 시각이 아닐 수 있음)."
            if post.get("dueHasTime") is False
            else "마감 시각과 변경 공지를 공식 원문에서 최종 확인하세요."
        )
        # Publishable claims are restricted to ALIO fields; unanswered details remain review tasks.
        verified = [(k, v) for k, v in fields if v]
        missing = [k for k, v in fields if not v]
        highlights = " / ".join(f"{k} {v}" for k, v in verified if k in ("고용형태", "근무지역", "모집인원"))
        if not highlights:
            highlights = "채용 분야와 지원 요건은 공식 공고에서 확인해야 합니다"
        review_items = [
            ("접수 마감 시각", "dueHasTime"),
            ("지원 자격·경력·자격증", None),
            ("전형 절차 및 일정", None),
            ("급여·복리후생", None),
            ("제출 서류·우대조건", None),
        ]
        checks = "\n".join(
            f"- [ ] {label}: 공식 모집요강·첨부파일 대조"
            for label, _ in review_items
        )
        due = plain(post.get("due"))
        try:
            deadline = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else None
            if deadline is not None and deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=KST)
            # A date-only or unverified deadline time must not be treated as an exact cutoff.
            # Mark expired only after the entire displayed calendar day ends in KST.
            if deadline is not None and (len(due) == 10 or post.get("dueHasTime") is False):
                expired = deadline.astimezone(KST).date() < now.astimezone(KST).date()
            else:
                expired = deadline is not None and deadline.astimezone(timezone.utc) < now
        except ValueError:
            deadline = None
            expired = False
        posting_note = (
            "⚠️ 접수 마감된 공고입니다. 기록·참고용이며 현재 지원 가능한 공고로 안내하지 마세요."
            if expired else (
                "⚠️ 접수 마감일을 확인할 수 없습니다. 발행 전에 현재 모집 여부를 확인하세요."
                if deadline is None else "접수 진행 여부는 공식 공고에서 최종 확인하세요."
            )
        )
        body = f"""# {title} | 지원자격·접수마감 정리

{posting_note}\n\n**핵심부터:** {org} 채용공고입니다. {highlights}.
지원 전 공식 모집요강에서 지원 자격과 접수 마감 조건을 확인하세요.

## 1. 모집 요약
{summary}

{deadline_note}

## 2. 지원 전에 확인할 사항
- 지원 자격: 학력·경력·자격증 등 필수 조건을 공식 모집요강에서 확인하세요.
- 전형 일정: 서류·필기·면접 단계와 발표일은 공고 첨부파일에서 확인하세요.
- 근무 조건: 급여, 근무시간, 계약기간은 공고 원문에서 확인하세요.
- 우대·가점: 적용 대상, 증빙서류, 중복 인정 여부를 확인하세요.

## 3. 지원자 FAQ
**Q. 어디서 지원하나요?**
공식 채용공고 링크에서 지원 방법과 접수처를 확인하세요.

**Q. 마감일은 언제인가요?**
수집된 마감 정보는 **{plain(post.get("due"))}**입니다. {deadline_note}

**Q. 학력이나 경력 제한이 있나요?**
수집된 학력 정보: **{plain(post.get("edu")) or "확인 필요"}**. 경력·자격증 제한은 원문 확인이 필요합니다.

**Q. 근무지는 어디인가요?**
수집된 근무지역: **{plain(post.get("region")) or "확인 필요"}**. 세부 배치지는 원문 확인이 필요합니다.

**Q. 몇 명을 모집하나요?**
수집된 인원: **{plain(post.get("n")) or "확인 필요"}**. 직무별 인원은 공고 원문을 확인하세요.

**Q. 급여와 전형은 어떻게 되나요?**
현재 수집 정보만으로 확정할 수 없습니다. 공식 모집요강을 확인하세요.

## 4. 발행 전 검수 체크리스트
{checks}

**자료 출처:** 커리어픽 ALIO 수집 정보. 본문에 없는 조건은 확인되지 않았으며, 공식 공고와 첨부파일이 우선합니다.

## 5. 공고 바로 확인하기
- 공식 채용공고: {plain(post.get("url"))}
- 커리어픽 상세정보: {BASE}/jobs/{pid}.html
- 다른 채용공고 찾아보기: {BASE}/

작성: 커리어픽
검수 상태: 미검수 · 네이버 블로그 게시 전 원문 및 첨부파일 대조 필요
"""
        (OUT / f"{pid}.md").write_text(body, encoding="utf-8")
        manifest.append({"id": pid, "title": title, "file": f"{pid}.md", "status": "needs_review", "expired": expired, "deadline_known": deadline is not None})
    # Remove stale drafts from previous runs.
    current = {item["file"] for item in manifest}
    for old in OUT.glob("*.md"):
        if old.name not in current:
            old.unlink()
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # Spreadsheet-friendly index for selecting which draft to publish manually.
    with (OUT / "review-index.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["ID", "제목", "검수상태", "마감여부", "마감일확인", "Markdown", "Word", "썸네일"])
        for item in manifest:
            pid = item["id"]
            writer.writerow([
                pid, item["title"], item["status"],
                "마감" if item["expired"] else "확인필요" if not item["deadline_known"] else "원문확인",
                "확인" if item["deadline_known"] else "미확인",
                f"{pid}.md", f"{pid}.docx", f"{pid}-thumbnail.png",
            ])
    print(f"Generated all {len(manifest)} ALIO review-only drafts in {OUT}")

if __name__ == "__main__":
    main()
