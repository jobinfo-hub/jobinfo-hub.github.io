"""네이버 블로그 RSS를 읽어 posts.json을 갱신하는 스크립트 (GitHub Actions에서 1시간마다 실행)"""
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

BLOG_ID = "hid4989-3"
RSS_URL = f"https://rss.blog.naver.com/{BLOG_ID}.xml"
OUT = Path(__file__).parent / "posts.json"
KST = timezone(timedelta(hours=9))
MAX_POSTS = 300  # 목록에 보관할 최대 글 수

MONEY_CATS = {"국가지원금·세금·재테크"}
MONEY_WORDS = ["대출", "금리", "연말정산", "연금", "펀드", "청약", "육아휴직", "지원금", "재테크", "통장", "ISA", "세금", "환급"]
PREP_CATS = {"자소서·NCS·필기·면접", "자격증/시험", "전형별 준비"}
PREP_WORDS = ["자소서", "자기소개서", "면접", "합격선", "공부법", "인적성", "skct", "작성법", "독학", " vs "]

TIME = r"(?:(?P<ap>오전|오후|낮|밤|저녁)\s*)?(?P<h>\d{1,2})(?::(?P<mi>\d{2})|시(?:\s*(?P<mi2>\d{1,2})분)?(?:\s*\d{1,2}초)?)"
DATES = [
    r"(?:20\d\d년\s*)?(?P<m>\d{1,2})월\s*(?P<d>\d{1,2})일(?:\s*\([^)]{1,3}\))?",
    r"(?:20\d\d\.\s*)?(?P<m>\d{1,2})\.\s*(?P<d>\d{1,2})\.?(?:\s*\([^)]{1,3}\))?",
]
PATTERNS = []
for D in DATES:
    PATTERNS.append(re.compile(D + r"\s*(?:" + TIME + r")?\s*(?:도착분\s*)?(?:까지|마감)"))
    PATTERNS.append(re.compile(r"마감(?:은|일은|일시는|일)?\s*" + D + r"\s*(?:" + TIME + r")?"))


def clean(text):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def find_deadline(text, pub):
    best = None
    for pat in PATTERNS:
        for m in pat.finditer(text):
            month, day = int(m["m"]), int(m["d"])
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            year = pub.year + (1 if month < pub.month - 6 else 0)
            has_time = m["h"] is not None
            hour, minute = 23, 59
            if has_time:
                hour = int(m["h"])
                minute = int(m["mi"] or m["mi2"] or 0)
                if m["ap"] in ("오후", "밤", "저녁") and hour < 12:
                    hour += 12
                if hour > 23 or minute > 59:
                    continue
            try:
                due = datetime(year, month, day, hour, minute, tzinfo=KST)
            except ValueError:
                continue
            if due < pub - timedelta(days=1):
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), due, has_time)
            break
    return (best[1], best[2]) if best else (None, False)


def deadline_for(title, desc, pub):
    due, has_time = find_deadline(desc, pub)
    if not due:
        due, has_time = find_deadline(title, pub)
    if not due:
        m = re.search(r"D-(\d{1,3})", title)
        if m:
            d = pub.date() + timedelta(days=int(m[1]))
            due, has_time = datetime(d.year, d.month, d.day, 23, 59, tzinfo=KST), False
    return due, has_time


def classify(cat, title, due):
    is_job = "채용" in title or "공채" in title
    if cat in MONEY_CATS or (not is_job and any(w in title for w in MONEY_WORDS)):
        return "m"
    if not is_job and any(w in title.lower() for w in PREP_WORDS):
        return "p"
    if cat in PREP_CATS and not due:
        return "p"
    return "j" if (is_job or due) else "p"


def summarize(text):
    text = re.sub(r"^.{0,100}?(?:제작|출처[^)]*|기준[^)]*|재구성)\)\s*", "", text)
    for s in re.split(r"(?<=[다요])\.\s+", text):
        s = s.strip()
        if len(s) < 15 or any(x in s for x in ("이 글은", "출처", "제작")):
            continue
        s = re.sub(r"^(?:3줄 요약|결론부터|한 줄로 먼저)[^?]{0,30}\?\s*", "", s)
        s = re.sub(r"^(?:3줄 요약|결론부터)[:：\s]*", "", s)
        return s if len(s) <= 70 else s[:68].rstrip() + "…"
    return ""


def fetch():
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": "Mozilla/5.0 (posts updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def main():
    old = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"posts": []}
    posts = {p["id"]: p for p in old["posts"]}
    before = json.dumps(sorted(posts.values(), key=lambda p: p["id"]), ensure_ascii=False)

    for item in fetch().iter("item"):
        guid = (item.findtext("guid") or "").strip()
        pid = guid.rstrip("/").split("/")[-1]
        if not pid.isdigit():
            continue
        title = clean(item.findtext("title"))
        cat = clean(item.findtext("category"))
        desc_text = clean(item.findtext("description"))
        pub = parsedate_to_datetime(item.findtext("pubDate")).astimezone(KST)

        if pid in posts:  # 이미 있는 글은 제목·카테고리만 갱신 (마감일·요약을 직접 고친 경우 유지)
            posts[pid]["title"], posts[pid]["cat"] = title, cat
            continue
        due, has_time = deadline_for(title, desc_text, pub)
        posts[pid] = {
            "id": pid,
            "type": classify(cat, title, due),
            "cat": cat,
            "title": title,
            "desc": summarize(desc_text),
            "url": f"https://m.blog.naver.com/{BLOG_ID}/{pid}",
            "pub": pub.isoformat(),
            "due": due.isoformat() if due else None,
            "dueHasTime": has_time,
        }

    ordered = sorted(posts.values(), key=lambda p: p["pub"], reverse=True)[:MAX_POSTS]
    after = json.dumps(sorted(ordered, key=lambda p: p["id"]), ensure_ascii=False)
    if after == before:
        print("변경 없음")
        return
    data = {"updated": datetime.now(KST).isoformat(timespec="seconds"), "posts": ordered}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    print(f"posts.json 갱신: 글 {len(ordered)}개")


if __name__ == "__main__":
    main()
