#!/usr/bin/env python3
"""
커리어픽 기관 채용공고 자동 모니터링
- org_sources.json에 등록한 기관의 공개 채용 게시판을 확인
- 신규 공고를 monitor.json에 누적
- 기존 alio.py / posts.json은 건드리지 않음
- 외부 라이브러리 없이 표준 라이브러리만 사용
"""

import hashlib
import html
import json
import re
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "org_sources.json"
OUT = ROOT / "monitor.json"
KST = timezone(timedelta(hours=9))
USER_AGENT = "CareerPick-JobMonitor/1.0 (+https://jobinfo-hub.github.io/)"
TIMEOUT = 25

# 기관 사이트가 TLS 체인 문제를 일으키는 경우에도 Actions에서 읽을 수 있도록
# 기본 검증 컨텍스트를 사용한다. HTTP가 아닌 HTTPS를 우선한다.
SSL_CONTEXT = ssl.create_default_context()


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self._href = None
        self._text = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            self._href = attrs.get("href")
            self._text = []
            self._depth = 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_starttag_nested(self, tag):
        pass

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            text = clean_text(" ".join(self._text))
            self.items.append((self._href, text))
            self._href = None
            self._text = []


def clean_text(s):
    s = html.unescape(str(s or ""))
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def fetch(url):
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml"
    })
    with urlopen(req, timeout=TIMEOUT, context=SSL_CONTEXT) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "replace")


def parse_anchors(source):
    p = AnchorParser()
    p.feed(source)
    return p.items


def visible_text(source):
    # 스크립트/스타일 제거 후 날짜 문맥을 얻기 위한 간단한 텍스트화
    s = re.sub(r"(?is)<script.*?</script>", " ", source)
    s = re.sub(r"(?is)<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return clean_text(s)


def same_domain(base, target):
    return urlparse(base).netloc == urlparse(target).netloc


def normalize_url(base, href):
    if not href:
        return ""
    href = href.strip()
    if href.startswith(("javascript:", "mailto:", "#")):
        return ""
    url = urldefrag(urljoin(base, href))[0]
    return url


def is_recruitment_title(title, cfg):
    t = title.lower()
    include = cfg.get("link_keywords") or ["채용", "모집", "인재"]
    exclude = cfg.get("exclude_keywords") or []
    if not any(k.lower() in t for k in include):
        return False
    if any(k.lower() in t for k in exclude):
        return False
    # 일반 메뉴/검색/채용정보 목록 자체는 공고로 저장하지 않는다.
    menu_only = {"채용정보", "채용공고", "채용", "인재채용", "채용정보 게시판"}
    if t.strip() in {x.lower() for x in menu_only}:
        return False
    return True


def parse_date(s):
    if not s:
        return None
    s = s.replace("년", ".").replace("월", ".").replace("일", "")
    m = re.search(r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})", s)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 23, 59, tzinfo=KST)
    except ValueError:
        return None


def parse_deadline(text):
    # 1) "접수기간/원서접수/지원기간" 주변에서 날짜쌍을 우선 탐색
    keywords = ["접수기간", "원서접수", "지원기간", "접수 기간", "지원 기간"]
    for kw in keywords:
        pos = text.find(kw)
        if pos >= 0:
            window = text[pos:pos + 500]
            dates = re.findall(
                r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})",
                window
            )
            if len(dates) >= 2:
                y, m, d = map(int, dates[-1])
                try:
                    return datetime(y, m, d, 23, 59, tzinfo=KST)
                except ValueError:
                    pass

    # 2) 제목/본문에 "~ 11.02" 또는 "~11/02"가 있는 경우
    m = re.search(r"~\s*(\d{1,2})\s*[./-]\s*(\d{1,2})", text)
    if m:
        now = datetime.now(KST)
        y = now.year
        try:
            return datetime(y, int(m.group(1)), int(m.group(2)), 23, 59, tzinfo=KST)
        except ValueError:
            pass

    return None


def make_id(org, url, title):
    raw = f"{org}|{url}|{title}".encode("utf-8")
    return "m" + hashlib.sha1(raw).hexdigest()[:16]


def load_existing():
    if not OUT.exists():
        return {"updated": None, "posts": []}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        if not isinstance(data.get("posts"), list):
            data["posts"] = []
        return data
    except Exception:
        return {"updated": None, "posts": []}


def main():
    if not CONFIG.exists():
        print("org_sources.json이 없습니다.", file=sys.stderr)
        return 1

    cfgs = json.loads(CONFIG.read_text(encoding="utf-8"))
    old = load_existing()
    posts = {str(p.get("id")): p for p in old.get("posts", []) if p.get("id")}

    now = datetime.now(KST)

    for cfg in cfgs:
        if not cfg.get("enabled", True):
            continue

        name = cfg.get("name", "").strip()
        page_url = cfg.get("url", "").strip()
        if not name or not page_url:
            continue

        try:
            page = fetch(page_url)
            anchors = parse_anchors(page)
        except Exception as e:
            print(f"[WARN] {name}: 목록 페이지 실패: {e}", file=sys.stderr)
            continue

        found = 0
        seen_urls = set()

        for href, title in anchors:
            title = clean_text(title)
            url = normalize_url(page_url, href)

            if not url or not title or url in seen_urls:
                continue
            seen_urls.add(url)

            if cfg.get("same_domain_only", True) and not same_domain(page_url, url):
                continue
            if not is_recruitment_title(title, cfg):
                continue

            found += 1
            if found > int(cfg.get("max_items", 30)):
                break

            detail_text = title
            try:
                detail = fetch(url)
                detail_text += " " + visible_text(detail)
            except Exception:
                pass

            due = parse_deadline(detail_text)
            item_id = make_id(name, url, title)

            # 이미 있는 공고는 URL/제목이 바뀌지 않는 한 건드리지 않는다.
            if item_id in posts:
                continue

            post = {
                "id": item_id,
                "type": "j",
                "monitor": True,
                "cat": "기관 공식 채용공고",
                "title": title,
                "org": name,
                "desc": "기관 공식 홈페이지 자동 수집",
                "url": url,
                "src": url,
                "pub": now.isoformat(),
                "due": due.isoformat() if due else None,
                "dueHasTime": False,
                "emp": [],
                "edu": [],
                "region": "",
                "text": f"{name} {title} 기관 공식 채용공고",
            }
            posts[item_id] = post
            print(f"[NEW] {name}: {title}")

    # 최근/마감순 표시를 위해 새 데이터가 위로 오도록 정렬.
    result_posts = list(posts.values())
    result_posts.sort(
        key=lambda p: (
            p.get("due") is None,
            p.get("due") or "9999-12-31T23:59:59+09:00",
            p.get("pub") or ""
        )
    )

    out = {
        "updated": now.isoformat(),
        "posts": result_posts
    }
    OUT.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"완료: monitor.json {len(result_posts)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
