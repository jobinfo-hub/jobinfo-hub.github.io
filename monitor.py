#!/usr/bin/env python3
"""CareerPick official recruitment monitor (standard library only)."""
import hashlib
import html
import json
import re
import sys
import ssl
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))
CONFIG = ROOT / 'org_sources.json'
OUT = ROOT / 'monitor.json'
UA = 'Mozilla/5.0 (compatible; CareerPickMonitor/2.0; +https://jobinfo-hub.github.io/)'


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(str(s or ''))).strip()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.active = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag.lower() == 'a':
            if self.active is not None:
                self._finish()
            self.active = {'href': d.get('href', ''), 'onclick': d.get('onclick', ''), 'text': []}
            self.depth = 1
        elif self.active is not None:
            self.depth += 1

    def handle_data(self, data):
        if self.active is not None:
            self.active['text'].append(data)

    def handle_endtag(self, tag):
        if self.active is not None:
            if tag.lower() == 'a':
                self._finish()
            elif self.depth > 1:
                self.depth -= 1

    def _finish(self):
        if self.active:
            self.links.append((self.active['href'], clean(' '.join(self.active['text'])), self.active['onclick']))
        self.active = None
        self.depth = 0


def fetch(url):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*', 'Accept-Language': 'ko-KR,ko;q=0.9', 'Referer': url})
    with urlopen(req, timeout=30, context=ssl.create_default_context()) as res:
        raw = res.read(5_000_000)
        enc = res.headers.get_content_charset()
    if not enc:
        m = re.search(br'charset\s*=\s*["\']?([\w-]+)', raw[:6000], re.I)
        enc = m.group(1).decode('ascii', 'ignore') if m else 'utf-8'
    try:
        return raw.decode(enc)
    except (LookupError, UnicodeDecodeError):
        return raw.decode('utf-8', 'replace')


def target_url(base, href, onclick, cfg):
    href = html.unescape((href or '').strip())
    if href and not href.lower().startswith(('javascript:', 'mailto:', '#')):
        url = urldefrag(urljoin(base, href))[0]
        if urlparse(url).scheme in ('http', 'https'):
            return url
    # Institution-specific onclick patterns can be configured after reviewing logs.
    # Do not invent a destination from an arbitrary numeric JavaScript argument.
    return ''


def deadline(text):
    for keyword in ('접수기간', '원서접수', '지원기간'):
        p = text.find(keyword)
        if p >= 0:
            matches = re.findall(r'20\d{2}[./-]\s*\d{1,2}[./-]\s*\d{1,2}', text[p:p+300])
            if len(matches) >= 2:
                try:
                    parts = list(map(int, re.split(r'[./-]', matches[1])))
                    return datetime(*parts, 23, 59, tzinfo=KST).isoformat()
                except ValueError:
                    pass
    return None


def main():
    if not CONFIG.exists():
        print('[ERROR] org_sources.json 없음', file=sys.stderr)
        return 1
    configs = json.loads(CONFIG.read_text(encoding='utf-8'))
    try:
        previous = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    except (ValueError, OSError):
        previous = {}
    existing = {p['id']: p for p in previous.get('posts', []) if isinstance(p, dict) and p.get('id')}
    now = datetime.now(KST)
    for cfg in configs:
        if not cfg.get('enabled', True):
            continue
        name, base = cfg.get('name', ''), cfg.get('url', '')
        print(f'[START] {name} {base}', flush=True)
        try:
            source = fetch(base)
        except Exception as e:
            print(f'[ERROR] {name} 페이지 접근 실패: {type(e).__name__}: {e}', flush=True)
            continue
        parser = Links()
        parser.feed(source)
        print(f'[INFO] HTML {len(source)}자 / 링크 {len(parser.links)}개', flush=True)
        keys = cfg.get('link_keywords') or ['채용', '모집']
        excludes = cfg.get('exclude_keywords') or []
        matches = 0
        seen = set()
        js_candidates = []
        for href, title, onclick in parser.links:
            if not title or not any(k.lower() in title.lower() for k in keys):
                continue
            if any(k.lower() in title.lower() for k in excludes):
                continue
            if title.strip() in ('채용', '채용정보', '채용공고', '인재채용'):
                continue
            url = target_url(base, href, onclick, cfg)
            if not url:
                js_candidates.append((title[:75], (onclick or href)[:120]))
                continue
            if cfg.get('same_domain_only', True) and urlparse(url).netloc != urlparse(base).netloc:
                continue
            if url in seen:
                continue
            seen.add(url)
            matches += 1
            if matches > int(cfg.get('max_items', 30)):
                break
            detail = title
            try:
                detail += ' ' + clean(re.sub(r'<[^>]+>', ' ', fetch(url)))
            except Exception as e:
                print(f'[WARN] 상세 페이지 접근 실패: {type(e).__name__}', flush=True)
            pid = 'm' + hashlib.sha1(f'{name}|{url}|{title}'.encode()).hexdigest()[:16]
            if pid not in existing:
                existing[pid] = {'id': pid, 'type': 'j', 'monitor': True, 'cat': '기관 공식 채용공고', 'title': title,
                                 'org': name, 'desc': '기관 공식 홈페이지 자동 수집', 'url': url, 'src': url,
                                 'pub': now.isoformat(), 'due': deadline(detail), 'dueHasTime': False,
                                 'emp': [], 'edu': [], 'region': '', 'text': f'{name} {title}'}
                print(f'[NEW] {name}: {title}', flush=True)
        print(f'[RESULT] {name}: 공고 링크 {matches}개 / JS 또는 링크 없음 {len(js_candidates)}개', flush=True)
        for title, code in js_candidates[:5]:
            print(f'[DEBUG] 링크 미해결: {title} / {code}', flush=True)
        if matches == 0:
            print('[HINT] 공고가 0건이면 목록 HTML 구조/onclick 상세링크에 맞춘 기관별 파서가 필요합니다.', flush=True)
    posts = list(existing.values())
    posts.sort(key=lambda p: (p.get('due') is None, p.get('due') or '9999', p.get('pub') or ''))
    OUT.write_text(json.dumps({'updated': now.isoformat(), 'posts': posts}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'완료: monitor.json {len(posts)}건', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
