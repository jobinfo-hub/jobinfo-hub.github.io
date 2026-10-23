"""Provide a complete, collapsible ALIO snapshot list on institution pages.

Preserve existing historical statistics and editorial sections. Regenerate the
marked block on each rebuild so it cannot accumulate stale entries.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
import json
import re

from audit_org_alio_coverage import normalized_org_name

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
BLOCK = re.compile(r'(?:<h2 data-careerpick-alio-heading="true">📢 ALIO 수록 모집 공고</h2>)?\n?<!-- careerpick-alio-list:start -->.*?<!-- careerpick-alio-list:end -->', re.S)
ANCHOR = re.compile(r'(<h2>📢 지금 모집 중</h2><div class="olist">.*?</div>)', re.S)

def main():
    data = json.loads((ROOT / "alio.json").read_text(encoding="utf-8"))
    now = datetime.now(KST)
    grouped = defaultdict(list)
    for post in data.get("posts", []):
        if not isinstance(post, dict) or not post.get("alio"):
            continue
        job_id = str(post.get("id", ""))
        org = str(post.get("org", "")).strip()
        if not re.fullmatch(r"a\d+", job_id) or not org:
            continue
        try:
            due = datetime.fromisoformat(str(post.get("due", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if due.tzinfo is None or due.astimezone(KST) < now:
            continue
        if not (ROOT / "jobs" / (job_id + ".html")).is_file():
            continue
        grouped[org].append((job_id, str(post.get("title", "")), due))
    # Only map an ALIO institution to a page when its normalized name is unique.
    pages = sorted(ROOT.glob("org-*.html"))
    page_aliases = defaultdict(list)
    for page in pages:
        page_aliases[normalized_org_name(page.stem.removeprefix("org-"))].append(page.stem.removeprefix("org-"))
    mapped = defaultdict(list)
    ambiguous = []
    for org, posts in grouped.items():
        candidates = page_aliases.get(normalized_org_name(org), [])
        if len(candidates) == 1:
            mapped[candidates[0]].extend(posts)
        elif len(candidates) > 1:
            ambiguous.append((org, candidates))
    for org, candidates in ambiguous:
        print(f"AMBIGUOUS ALIO ORG: {org}: {', '.join(candidates)}")
    updated_pages = 0
    listings = 0
    for page in pages:
        original = page.read_text(encoding="utf-8")
        html = BLOCK.sub("", original)
        org = page.stem.removeprefix("org-")
        posts = sorted(mapped.get(org, []), key=lambda item: (item[2], item[0]))
        if not posts:
            if html != original:
                page.write_text(html, encoding="utf-8")
                updated_pages += 1
            continue
        rows = []
        for job_id, title, due in posts:
            rows.append(
                f'<a href="jobs/{job_id}.html">{escape(title)}'
                f' <span class="meta">· 저장된 마감일 {due.astimezone(KST):%Y.%m.%d}</span></a>'
            )
        block = (
            '\n<!-- careerpick-alio-list:start -->\n'
            f'<details class="box" data-alio-current="true"><summary>ALIO 수록 모집 공고 전체 {len(posts)}건 펼쳐보기</summary>'
            f'<p class="meta">ALIO 데이터 기준 {escape(str(data.get("updated", "미상")))}. '
            '저장된 마감일이 지나지 않은 공고만 표시합니다. 실제 접수 상태는 공식 원문에서 확인하세요.</p>'
            '<div class="olist">\n' + '\n'.join(rows) + '\n</div></details>\n'
            '<!-- careerpick-alio-list:end -->'
        )
        anchor = ANCHOR.search(html)
        if anchor:
            html = html[:anchor.end()] + block + html[anchor.end():]
        else:
            # Pages without an existing active section still need their ALIO
            # snapshot represented, but never replace historical summaries.
            pos = html.find('<h2>📝 최근 공고의 지원 자격</h2>')
            if pos < 0:
                pos = html.find('</main>')
            if pos < 0:
                continue
            html = html[:pos] + '<h2 data-careerpick-alio-heading="true">📢 ALIO 수록 모집 공고</h2>' + block + html[pos:]
        if html != original:
            page.write_text(html, encoding="utf-8")
            updated_pages += 1
        listings += len(posts)
    print(f"Institution complete ALIO lists: {updated_pages} pages updated, {listings} current ALIO job links shown across {len(mapped)} matched institutions")

if __name__ == "__main__":
    main()
