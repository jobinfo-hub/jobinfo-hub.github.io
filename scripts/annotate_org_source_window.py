"""Add a transparent ALIO data-window note to institution pages.

The date shown is the latest date already stated by each page's own source
summary, not a claim of real-time refresh. Idempotent and reversible.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LEAD = re.compile(r'(<p class="lead">[^<]*최근 채용공고.*?\((\d{2}\.\d{1,2}\.\d{1,2}) ~ (\d{2}\.\d{1,2}\.\d{1,2}), 알리오 기준\).*?</p>)', re.DOTALL)
NOTE = '<p class="meta" data-alio-window="true">자료 범위: ALIO 공개 채용공고 {start} ~ {end}. 마지막 수록 공고일은 사이트 갱신 시각이 아닙니다. 채용 상태와 자격 요건은 지원 전 원문에서 확인하세요.</p>'

def main():
    pages = list(ROOT.glob("org-*.html"))
    added = 0
    skipped = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if 'data-alio-window="true"' in html:
            continue
        match = LEAD.search(html)
        if not match:
            skipped += 1
            continue
        note = NOTE.format(start=match.group(2), end=match.group(3))
        html = html[:match.end()] + '\n' + note + html[match.end():]
        page.write_text(html, encoding="utf-8")
        added += 1
    print(f"ALIO source window: {len(pages)} institution pages, {added} notices added, {skipped} no matching date range")

if __name__ == "__main__":
    main()
