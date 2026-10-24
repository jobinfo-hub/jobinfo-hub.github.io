"""Generate conservative, review-required Naver blog drafts from CareerPick ALIO data.
Usage: python scripts/generate_naver_drafts.py
No Naver login, publishing, or automatic factual claims.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "naver-drafts"
BASE = "https://jobinfo-hub.github.io"

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
        try:
            if due and datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(timezone.utc) < now:
                continue
        except ValueError:
            continue
        candidates.append(post)
    candidates.sort(key=lambda p: (plain(p.get("due")) or "9999", plain(p.get("id"))))
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    seen = set()
    for post in candidates:
        if len(manifest) >= 11:
            break
        if str(post["id"]) in seen:
            continue
        seen.add(str(post["id"]))
        pid = re.sub(r"[^a-zA-Z0-9_-]", "", str(post["id"]))
        if not pid:
            continue
        title = plain(post.get("title"))
        org = plain(post.get("org"))
        fields = [
            ("모집기관", org), ("채용분야", plain(post.get("desc"))),
            ("고용형태", plain(post.get("emp"))), ("학력", plain(post.get("edu"))),
            ("근무지역", plain(post.get("region"))), ("모집인원", plain(post.get("n"))),
            ("접수 마감", plain(post.get("due")))
        ]
        summary = "\n".join(f"- {k}: {v or '공고 원문 확인 필요'}" for k,v in fields)
        body = f"""# {title} | 지원자격·접수마감 정리

{org}의 채용공고입니다. 지원 전 접수 마감과 지원 자격을 먼저 확인하세요.
아래는 커리어픽에 수집된 공고 정보이며, 최종 조건은 공식 공고가 우선합니다.

## 채용 핵심 정보
{summary}

## 지원 전에 꼭 확인할 10가지 질문
1. 정확한 접수 마감 시각은 언제인가요?
2. 지원 가능한 학력과 경력은 무엇인가요?
3. 필수 자격증이 있나요?
4. 근무지는 어디인가요?
5. 고용기간과 근무시간은 어떻게 되나요?
6. 급여는 얼마인가요?
7. 서류·필기·면접 절차는 어떻게 되나요?
8. 우대사항과 가점은 무엇인가요?
9. 제출 서류는 무엇인가요?
10. 중복지원이나 결격사유가 있나요?

위 질문의 구체적인 답변은 원문 또는 첨부 모집요강을 확인한 뒤 보완해야 합니다.
확인되지 않은 사항을 추정해 작성하지 마세요.

## 커리어픽 확인 링크
- 공식 공고: {plain(post.get("url"))}
- 커리어픽 채용정보: {BASE}/jobs/{pid}.html
- 내게 맞는 채용공고 찾기: {BASE}/

작성: 커리어픽
검수 상태: 미검수 · 네이버 블로그 게시 전 원문 대조 필요
"""
        (OUT / f"{pid}.md").write_text(body, encoding="utf-8")
        manifest.append({"id": pid, "title": title, "file": f"{pid}.md", "status": "needs_review"})
    # Remove stale drafts from previous runs.
    current = {item["file"] for item in manifest}
    for old in OUT.glob("*.md"):
        if old.name not in current:
            old.unlink()
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(manifest)} review-only drafts in {OUT}")

if __name__ == "__main__":
    main()
