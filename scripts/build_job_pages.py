
"""Generate searchable static ALIO job pages for CareerPick.

Run from the repository root: python scripts/build_job_pages.py
"""

import json
import re
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'alio.json'
DETAIL = ROOT / 'alio-detail.json'
OUT = ROOT / 'jobs'
BASE = 'https://jobinfo-hub.github.io'

DETAIL_LABELS = {
    'recrutSeNm': '채용 구분',
    'recrutPblntTtl': '채용공고 제목',
    'aplyQlfcCn': '지원 자격',
    'recrutPrgsCn': '채용 절차',
}


def clean(value):
    if isinstance(value, list):
        return ', '.join(map(str, value))
    return str(value or '').strip()


def safe_url(value):
    value = clean(value)
    parsed = urlparse(value)
    return value if parsed.scheme == 'https' and parsed.netloc else ''


def parse_date(value, end_of_day=False):
    """Accept valid ISO dates/times and common ALIO formats.

    For a date-only deadline, use the end of that date
    in Korea time.
    """
    raw = clean(value)
    if not raw:
        return ''

    raw = raw.replace('년', '-').replace('월', '-').replace('일', ' ').strip()
    raw = re.sub(r'(?<=\d)[./](?=\d)', '-', raw)
    raw = re.sub(r'\s+', ' ', raw)

    if re.fullmatch(r'\d{8}', raw):
        raw = f'{raw[:4]}-{raw[4:6]}-{raw[6:8]}'

    if re.fullmatch(r'\d{4}-\d{1,2}-\d{1,2}', raw):
        y, m, d = map(int, raw.split('-'))
        try:
            parsed = date(y, m, d)
        except ValueError:
            return ''
        return (
            f'{parsed.isoformat()}T23:59:59+09:00'
            if end_of_day
            else parsed.isoformat()
        )

    normalized = (
        raw.replace(' ', 'T', 1)
        if 'T' not in raw and ' ' in raw
        else raw
    )

    if normalized.endswith('Z'):
        normalized = normalized[:-1] + '+00:00'

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return ''

    if parsed.tzinfo is None:
        return parsed.isoformat(timespec='seconds') + '+09:00'

    return parsed.isoformat(timespec='seconds')


def date_label(value):
    parsed = parse_date(value)
    if not parsed:
        return clean(value) or '공식 공고 확인'
    if 'T' not in parsed:
        return parsed
    return parsed[:16].replace('T', ' ')


def is_closed(due):
    parsed = parse_date(due, end_of_day=True)
    if not parsed:
        return False

    try:
        deadline = datetime.fromisoformat(parsed)
        if deadline.tzinfo is None:
            return False
        return (
            deadline.astimezone(timezone.utc)
            < datetime.now(timezone.utc)
        )
    except ValueError:
        return False


def render(post, detail):
    title = clean(post.get('title'))
    org = clean(post.get('org'))
    pid = clean(post.get('id'))

    canonical = f'{BASE}/jobs/{quote(pid, safe="")}.html'
    due = clean(post.get('due'))
    deadline = parse_date(due, end_of_day=True)
    closed = is_closed(due)

    official = (
        safe_url(post.get('src'))
        or safe_url(post.get('url'))
    )

    fields = [
        ('기관명', org),
        (
            '모집인원',
            clean(post.get('n')) + '명'
            if post.get('n')
            else '공고 확인'
        ),
        ('고용형태', clean(post.get('emp')) or '공고 확인'),
        ('학력조건', clean(post.get('edu')) or '공고 확인'),
        ('근무지역', clean(post.get('region')) or '공고 확인'),
        ('접수마감', date_label(due)),
    ]

    rows = '\n'.join(
        f'<dt>{escape(k)}</dt><dd>{escape(v)}</dd>'
        for k, v in fields
    )

    extra = ''
    if isinstance(detail, dict):
        for key, label in DETAIL_LABELS.items():
            val = detail.get(key)
            if isinstance(val, str) and val.strip():
                extra += (
                    f'<section><h2>{escape(label)}</h2>'
                    f'<p>{escape(val[:1500])}</p></section>'
                )

    schema = {
        '@context': 'https://schema.org',
        '@type': 'JobPosting',
        'title': title,
        'description': (
            clean(post.get('desc'))
            or (
                f'{org} 채용공고. 지원자격과 세부사항은 '
                '공식 공고에서 확인하세요.'
            )
        ),
        'hiringOrganization': {
            '@type': 'Organization',
            'name': org,
        },
        'url': canonical,
    }

    posted = parse_date(post.get('pub'))
    if posted:
        schema['datePosted'] = posted

    if deadline:
        schema['validThrough'] = deadline

    if post.get('region'):
        schema['jobLocation'] = {
            '@type': 'Place',
            'address': {
                '@type': 'PostalAddress',
                'addressCountry': 'KR',
                'addressRegion': clean(post['region']),
            },
        }

    if post.get('emp'):
        employment = clean(post['emp'])
        if '정규직' in employment:
            schema['employmentType'] = 'FULL_TIME'
        elif '계약직' in employment or '인턴' in employment:
            schema['employmentType'] = 'TEMPORARY'

    # 마감된 공고는 JobPosting 구조화 데이터를 제거합니다.
    # 안내용 HTML 페이지는 그대로 유지합니다.
    schema_json = '' if closed else (
        '<script type="application/ld+json">'
        + json.dumps(
            schema,
            ensure_ascii=False
        ).replace('<', '\\u003c')
        + '</script>'
    )

    notice = (
        '<p class="closed">'
        '접수 마감된 공고입니다. '
        '최신 모집 여부는 공식 공고를 확인하세요.'
        '</p>'
        if closed
        else ''
    )

    link = (
        f'<a class="apply" '
        f'href="{escape(official, quote=True)}" '
        f'rel="noopener noreferrer" target="_blank">'
        f'공식 채용공고 확인 ↗</a>'
        if official
        else '<p>공식 지원 링크를 확인 중입니다.</p>'
    )

    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} | {escape(org)} | 커리어픽</title>
<meta name="description" content="{escape((org+' '+title+' 모집정보, 지원자격 및 접수마감 확인')[:155], quote=True)}">
<link rel="canonical" href="{escape(canonical, quote=True)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:url" content="{escape(canonical, quote=True)}">
{schema_json}
<style>
body{{margin:0;background:#f5f7fb;color:#14213d;font:16px/1.7 system-ui,'Malgun Gothic',sans-serif}}
main{{max-width:720px;margin:35px auto;padding:24px;background:white;border-radius:18px}}
h1{{font-size:1.6rem;line-height:1.4}}
dt{{font-weight:700;color:#475569}}
dd{{margin:0 0 14px}}
.apply{{display:inline-block;background:#1f3fbf;color:white;padding:12px 20px;border-radius:9px;text-decoration:none}}
a{{color:#1f3fbf}}
.muted{{color:#64748b}}
.closed{{padding:12px;background:#fff1f2;color:#9f1239;border-radius:8px;font-weight:700}}
@media(max-width:760px){{main{{margin:0;border-radius:0;padding:20px}}}}
</style>
</head>
<body>
<main>
<nav><a href="/">← 커리어픽 전체 채용공고</a></nav>
<p class="muted">공공기관 채용정보</p>
<h1>{escape(title)}</h1>
<p>{escape(org)}</p>
{notice}
<h2>모집 요약</h2>
<dl>{rows}</dl>
{link}
{extra}
<hr>
<p class="muted">
본 페이지는 공공 채용정보를 요약한 안내 페이지입니다.
지원 전 반드시 공식 공고의 자격조건, 마감시각,
변경사항을 확인하세요.
</p>
<section aria-label="지원 전 확인 사항">
<h2>지원 전 체크리스트</h2>
<p>채용공고의 필수 자격과 우대사항을 구분하고, 공식 원문에서 전형별 일정·증빙서류·접수 마감시각을 다시 확인하세요.</p>
<p><a href="/guides/application-checklist.html">공공기관 채용 지원 전 확인할 7가지 →</a></p>
</section>
<a href="/">다른 채용공고 찾아보기</a>
</main>
</body>
</html>'''


def main():
    if not DATA.exists():
        raise SystemExit('alio.json 파일이 없습니다.')

    raw = json.loads(DATA.read_text(encoding='utf-8'))
    posts = (
        raw.get('posts', [])
        if isinstance(raw, dict)
        else []
    )

    details = (
        json.loads(DETAIL.read_text(encoding='utf-8'))
        if DETAIL.exists()
        else {}
    )

    if not isinstance(details, dict):
        details = {}

    if not posts:
        raise SystemExit(
            '공고 데이터가 비어 있어 기존 페이지를 보존합니다.'
        )

    OUT.mkdir(exist_ok=True)
    created = 0

    # 1. 잡알리오 채용공고 상세페이지 생성
    for post in posts:
        if not isinstance(post, dict) or not post.get('alio'):
            continue

        pid = clean(post.get('id'))
        if not re.fullmatch(r'a[0-9]+', pid):
            continue

        target = OUT / f'{pid}.html'
        html = render(post, details.get(pid, {}))

        if (
            not target.exists()
            or target.read_text(encoding='utf-8') != html
        ):
            target.write_text(html, encoding='utf-8')
            created += 1

    # 2. 실제 존재하는 상세페이지 목록 생성
    # 홈페이지에서 없는 파일로 연결하지 않도록 사용
    available = sorted(
        p.stem
        for p in OUT.glob('a[0-9]*.html')
        if re.fullmatch(r'a[0-9]+', p.stem)
    )

    # 3. 홈페이지에서 읽을 JavaScript 목록 생성
    available_js = (
        'window.CAREERPICK_JOB_IDS = new Set('
        + json.dumps(available, ensure_ascii=False)
        + ');\n'
    )

    inventory = OUT / 'available.js'

    # 내용이 바뀌었을 때만 파일 갱신
    if (
        not inventory.exists()
        or inventory.read_text(encoding='utf-8') != available_js
    ):
        inventory.write_text(
            available_js,
            encoding='utf-8'
        )

    print(f'채용 상세페이지 생성/변경: {created}개')
    print(f'연결 가능한 상세페이지: {len(available)}개')
    print('상세페이지 연결 목록: jobs/available.js')


if __name__ == '__main__':
    main()
