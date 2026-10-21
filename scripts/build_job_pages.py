"""Generate searchable static ALIO job pages for CareerPick.

Run from the repository root: python scripts/build_job_pages.py
"""
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'alio.json'
DETAIL = ROOT / 'alio-detail.json'
OUT = ROOT / 'jobs'
BASE = 'https://jobinfo-hub.github.io'


def clean(value):
    if isinstance(value, list):
        return ', '.join(map(str, value))
    return str(value or '').strip()


def safe_url(value):
    value = clean(value)
    parsed = urlparse(value)
    return value if parsed.scheme == 'https' and parsed.netloc else ''


def date_label(value):
    value = clean(value)
    return value[:16].replace('T', ' ') if value else '상시 모집'


def render(post, detail):
    title = clean(post.get('title'))
    org = clean(post.get('org'))
    pid = clean(post.get('id'))
    canonical = f'{BASE}/jobs/{quote(pid, safe="")}.html'
    due = clean(post.get('due'))
    official = safe_url(post.get('src')) or safe_url(post.get('url'))
    fields = [
        ('기관명', org),
        ('모집인원', clean(post.get('n')) + '명' if post.get('n') else '공고 확인'),
        ('고용형태', clean(post.get('emp')) or '공고 확인'),
        ('학력조건', clean(post.get('edu')) or '공고 확인'),
        ('근무지역', clean(post.get('region')) or '공고 확인'),
        ('접수마감', date_label(due)),
    ]
    rows = '\n'.join(f'<dt>{escape(k)}</dt><dd>{escape(v)}</dd>' for k, v in fields)
    extra = ''
    if isinstance(detail, dict):
        # Display a small set of verified API-provided text fields only.
        for key in ('recrutSeNm', 'recrutPblntTtl', 'aplyQlfcCn', 'recrutPrgsCn'):
            val = detail.get(key)
            if isinstance(val, str) and val.strip():
                extra += f'<section><h2>{escape(key)}</h2><p>{escape(val[:1500])}</p></section>'
    schema = {
        '@context': 'https://schema.org',
        '@type': 'JobPosting',
        'title': title,
        'description': clean(post.get('desc')) or f'{org} 채용공고. 지원자격과 세부사항은 공식 공고에서 확인하세요.',
        'datePosted': clean(post.get('pub'))[:10],
        'hiringOrganization': {'@type': 'Organization', 'name': org},
        'url': canonical,
    }
    if due:
        schema['validThrough'] = due
    if post.get('region'):
        schema['jobLocation'] = {'@type': 'Place', 'address': {'@type': 'PostalAddress', 'addressCountry': 'KR', 'addressRegion': clean(post['region'])}}
    if post.get('emp'):
        employment = clean(post['emp'])
        if '정규직' in employment:
            schema['employmentType'] = 'FULL_TIME'
        elif '계약직' in employment or '인턴' in employment:
            schema['employmentType'] = 'TEMPORARY'
    schema_json = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c')
    link = f'<a class="apply" href="{escape(official, quote=True)}" rel="noopener noreferrer" target="_blank">공식 채용공고 확인 ↗</a>' if official else '<p>공식 지원 링크를 확인 중입니다.</p>'
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} | {escape(org)} | 커리어픽</title>
<meta name="description" content="{escape((org+' '+title+' 모집정보, 지원자격 및 접수마감 확인')[:155], quote=True)}">
<link rel="canonical" href="{escape(canonical, quote=True)}">
<meta property="og:type" content="article"><meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:url" content="{escape(canonical, quote=True)}">
<script type="application/ld+json">{schema_json}</script>
<style>body{{margin:0;background:#f5f7fb;color:#14213d;font:16px/1.7 system-ui,'Malgun Gothic',sans-serif}}main{{max-width:720px;margin:35px auto;padding:24px;background:white;border-radius:18px}}h1{{font-size:1.6rem;line-height:1.4}}dt{{font-weight:700;color:#475569}}dd{{margin:0 0 14px}}.apply{{display:inline-block;background:#1f3fbf;color:white;padding:12px 20px;border-radius:9px;text-decoration:none}}a{{color:#1f3fbf}}.muted{{color:#64748b}}@media(max-width:760px){{main{{margin:0;border-radius:0;padding:20px}}}}</style>
</head><body><main><nav><a href="/">← 커리어픽 전체 채용공고</a></nav>
<p class="muted">공공기관 채용정보</p><h1>{escape(title)}</h1><p>{escape(org)}</p>
<h2>모집 요약</h2><dl>{rows}</dl>{link}
{extra}<hr><p class="muted">본 페이지는 공공 채용정보를 요약한 안내 페이지입니다. 지원 전 반드시 공식 공고의 자격조건, 마감시각, 변경사항을 확인하세요.</p>
<a href="/">다른 채용공고 찾아보기</a></main></body></html>'''


def main():
    if not DATA.exists():
        raise SystemExit('alio.json 파일이 없습니다.')
    raw = json.loads(DATA.read_text(encoding='utf-8'))
    posts = raw.get('posts', []) if isinstance(raw, dict) else []
    details = json.loads(DETAIL.read_text(encoding='utf-8')) if DETAIL.exists() else {}
    if not isinstance(details, dict):
        details = {}
    if not posts:
        raise SystemExit('공고 데이터가 비어 있어 기존 페이지를 보존합니다.')
    OUT.mkdir(exist_ok=True)
    created = 0
    for post in posts:
        if not isinstance(post, dict) or not post.get('alio'):
            continue
        pid = clean(post.get('id'))
        if not re.fullmatch(r'a[0-9]+', pid):
            continue
        target = OUT / f'{pid}.html'
        html = render(post, details.get(pid, {}))
        if not target.exists() or target.read_text(encoding='utf-8') != html:
            target.write_text(html, encoding='utf-8')
            created += 1
    print(f'채용 상세페이지 생성/변경: {created}개')


if __name__ == '__main__':
    main()
