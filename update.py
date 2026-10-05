"""네이버 블로그 RSS를 읽어 posts.json을 갱신하는 스크립트 (GitHub Actions에서 1시간마다 실행)

posts.json에서 글 하나에 "lock": true 를 넣으면 그 글은 자동 수정하지 않습니다.
(마감일·기관명 등을 직접 고쳤을 때 사용)
"""
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
MAX_POSTS = 300
SCHEMA = 3  # 분류 규칙을 바꾸면 숫자를 올려 기존 글도 다시 분류

# ── 분류 기준 ─────────────────────────────────────────────
JOB_RE = re.compile(r"채용|공채|재공고|모집|선발|인턴")
MONEY_CATS = {"국가지원금·세금·재테크", "정부지원금"}
MONEY_WORDS = ["대출", "금리", "연말정산", "연금", "펀드", "청약", "육아휴직", "지원금", "재테크",
               "통장", "ISA", "세금", "환급", "적금", "이용권", "바우처", "수당", "장려금"]
PREP_CATS = {"자소서·NCS·필기·면접", "자격증/시험", "자격증·시험", "전형별 준비", "필기, NCS", "취업준비"}
PREP_WORDS = ["자소서", "자기소개서", "면접", "합격선", "공부", "계획표", "인적성", "skct", "작성법",
              "독학", " vs ", "기출", "자격증", "준비법", "보건증", "직업"]
EXAMS = [  # 취업준비 글에 붙일 '대비 시험' 표시
    (r"NCS", "NCS"), (r"PSAT", "PSAT"), (r"SKCT", "SKCT"), (r"GSAT", "GSAT"), (r"인적성", "인적성"),
    (r"한국사", "한국사"), (r"토익|TOEIC", "토익"), (r"컴퓨터활용능력|컴활", "컴활"),
    (r"유통관리사", "유통관리사"), (r"산업안전기사", "산업안전기사"), (r"소방안전관리자", "소방안전관리자"),
    (r"지게차", "지게차"), (r"정보처리기사", "정보처리기사"), (r"빅데이터분석기사|ADsP", "데이터 자격증"),
    (r"교육공무직", "교육공무직"), (r"검찰직", "검찰직"), (r"공무원", "공무원"),
    (r"자소서|자기소개서", "자소서"), (r"면접", "면접"), (r"자격증", "자격증"),
]
REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남",
           "전북", "전남", "경북", "경남", "제주", "나주", "완주", "오송", "원주", "진주", "김천", "전국"]
EMP = [(r"정규직", "정규직"), (r"무기계약", "무기계약직"), (r"공무직", "공무직"),
       (r"기간제|계약직", "계약직"), (r"인턴", "인턴"), (r"경력", "경력")]

# ── 마감일 인식 ───────────────────────────────────────────
TIME = r"(?:(?P<ap>오전|오후|낮|밤|저녁)\s*)?(?P<h>\d{1,2})(?::(?P<mi>\d{2})|시(?:\s*(?P<mi2>\d{1,2})분)?(?:\s*\d{1,2}초)?)"
DATES = [
    r"(?:20\d\d년\s*)?(?P<m>\d{1,2})월\s*(?P<d>\d{1,2})일(?:\s*\([^)]{1,3}\))?",
    r"(?:20\d\d\.\s*)?(?P<m>\d{1,2})[./]\s*(?P<d>\d{1,2})\.?(?:\s*\([^)]{1,3}\))?",
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


def deadline_for(title, text, pub):
    """(마감일시, 시간표시 여부, 출처) — 출처: text(본문) / title(제목 날짜) / dn(제목 D-n 추정)"""
    due, has_time = find_deadline(text, pub)
    if due:
        return due, has_time, "text"
    due, has_time = find_deadline(title, pub)
    if due:
        return due, has_time, "title"
    if JOB_RE.search(title):  # 제목의 D-n은 채용 글일 때만 마감으로 인정
        m = re.search(r"D-(\d{1,3})", title)
        if m:
            d = pub.date() + timedelta(days=int(m[1]))
            hour, minute, has_time = 23, 59, False
            t = re.search(r"(오전|오후|낮)?\s*(\d{1,2})시\s*마감", title)
            if t:
                hour = int(t[2]) + (12 if t[1] == "오후" and int(t[2]) < 12 else 0)
                minute, has_time = 0, True
            return datetime(d.year, d.month, d.day, hour, minute, tzinfo=KST), has_time, "dn"
    return None, False, ""


def classify(cat, title, has_due):
    is_job = bool(JOB_RE.search(title))
    low = title.lower()
    if cat in MONEY_CATS or (not is_job and any(w in title for w in MONEY_WORDS)):
        return "m"
    if not is_job and (cat in PREP_CATS or any(w.lower() in low for w in PREP_WORDS)):
        return "p"
    if is_job or has_due:
        return "j"
    return "p"


# ── 채용공고 정보 추출 ─────────────────────────────────────
ORG_STOP = re.compile(r"\s*(?:\(|20\d\d|상반기|하반기|신입|경력|정규직|공무직|재공고|채용|공채|모집|"
                      r"\d[\d,]*\s*명|제?\d+차|청년인턴|체험형|인턴|직원|D-\d|—|,)")


def extract_org(title):
    t = re.sub(r"^\s*20\d\d(?:년)?\s*(?:상반기|하반기)?\s*", "", title)
    m = ORG_STOP.search(t)
    if not m or m.start() == 0:
        return ""
    org = t[:m.start()].strip(" ,—-·")
    while True:  # '서울대치과병원 간호직', '순천병원 산업위생사 4급' → 기관명만
        nxt = re.sub(r"\s+\S*(?:직|급|사|과|의|위원|장|연구직)$", "", org)
        if nxt == org or not nxt:
            break
        org = nxt
    return org if 1 < len(org) <= 20 else ""


def extract_info(title, text, org):
    info = {}
    # 인원은 확실한 표현만: 제목의 N명 → 본문의 '총 N명' → 'N명(…)을 채용·뽑·모집·선발'
    # (각 N명, 중 N명, 'A 1명과 B 1명'처럼 나뉜 경우는 틀릴 수 있어 표시하지 않음)
    m = re.search(r"(\d[\d,]*)\s*명", title) or re.search(r"(?:총|모두|합계)\s*(\d[\d,]*)\s*명", text)
    if not m:
        for c in re.finditer(r"(\d[\d,]*)\s*명(?:\s*\([^)]{0,60}\))?(?:을|를)\s*[^.명]{0,22}?(?:채용|뽑|모집|선발)", text):
            before = text[max(0, c.start() - 40):c.start()]
            if re.search(r"[각중]\s*$", before) or re.search(r"명\s*(?:과|와|,|·)", before):
                continue
            m = c
            break
    if m:
        info["n"] = m[1].replace(",", "")
    head = (title + " " + text[:450])
    info["emp"] = [label for pat, label in EMP if re.search(pat, head)][:3]
    edu = []
    if re.search(r"학력[^.]{0,20}(?:제한(?:이|은)?\s*(?:없|무관)|무관)|학력무관", text):
        edu.append("학력무관")
    if "고졸" in head:
        edu.append("고졸 가능")
    info["edu"] = edu
    body = text.replace(org, " ") if org else text
    region = ""
    for w in re.finditer(r"(?:근무지|근무 ?지역|근무하|본원|본사)[^.]{0,40}", body):
        hit = next((r for r in REGIONS if r in w.group(0)), "")
        if hit:
            region = hit
            break
    info["region"] = region
    src = re.search(r"\b((?:[a-z0-9-]+\.)+(?:co\.kr|or\.kr|go\.kr|re\.kr|ac\.kr|kr|com|net))\b", text)
    if src and not re.search(r"naver|pstatic|blog", src[1]):
        info["src"] = "https://" + src[1]
    return info


def extract_exam(title, text):
    head = title + " " + text[:200]
    found = []
    for pat, label in EXAMS:
        if re.search(pat, head, re.I) and label not in found:
            found.append(label)
    return found[:2]


def summarize(text):
    text = re.sub(r"^.{0,100}?(?:제작|출처[^)]*|기준[^)]*|재구성)\)\s*", "", text)
    for s in re.split(r"(?<=[다요])\.\s+", text):
        s = s.strip(" .")
        if len(s) < 15 or any(x in s for x in ("이 글은", "출처", "제작")):
            continue
        s = re.sub(r"^(?:3줄 요약|결론부터|한 줄로 먼저)[^?]{0,30}\?\s*", "", s)
        s = re.sub(r"^(?:3줄 요약|결론부터)[:：\s]*", "", s)
        return s if len(s) <= 70 else s[:68].rstrip() + "…"
    return ""


def build(pid, title, cat, text, pub, old=None):
    due, has_time, how = deadline_for(title, text, pub)
    typ = classify(cat, title, due is not None)
    if old and old.get("due") and typ != "p" and how != "text":  # 본문에서 못 찾으면 예전 마감일 유지
        due, has_time = datetime.fromisoformat(old["due"]), old.get("dueHasTime", False)
    if typ == "p":
        due, has_time = None, False
    post = {
        "id": pid, "type": typ, "cat": cat, "title": title,
        "desc": summarize(text) or (old or {}).get("desc", ""),
        "url": f"https://m.blog.naver.com/{BLOG_ID}/{pid}",
        "pub": pub.isoformat(),
        "due": due.isoformat() if due else None, "dueHasTime": has_time,
        "text": text[:700], "v": SCHEMA,
    }
    if typ == "j":
        post["org"] = extract_org(title)
        post.update(extract_info(title, text, post["org"]))
        # 본문이 짧아 인원을 못 찾은 옛 글은 이전 값 유지 (단, 오인식이 잦던 '1명'은 버림)
        if "n" not in post and old and str(old.get("n", "")).isdigit() and int(old["n"]) > 1:
            post["n"] = old["n"]
        for k in ("region", "src"):
            if not post.get(k) and old and old.get(k):
                post[k] = old[k]
    elif typ == "p":
        post["exam"] = extract_exam(title, text)
    return post


def fetch():
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": "Mozilla/5.0 (posts updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def main():
    old = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"posts": []}
    posts = {p["id"]: p for p in old["posts"]}
    before = json.dumps(sorted(posts.values(), key=lambda p: p["id"]), ensure_ascii=False)

    feed = {}
    for item in fetch().iter("item"):
        pid = (item.findtext("guid") or "").strip().rstrip("/").split("/")[-1]
        if pid.isdigit():
            feed[pid] = (clean(item.findtext("title")), clean(item.findtext("category")),
                         clean(item.findtext("description")),
                         parsedate_to_datetime(item.findtext("pubDate")).astimezone(KST))

    for pid, (title, cat, text, pub) in feed.items():
        cur = posts.get(pid)
        if cur and cur.get("lock"):
            continue
        if cur and cur.get("v") == SCHEMA:  # 이미 처리한 글은 제목·카테고리만 갱신
            cur["title"], cur["cat"] = title, cat
            continue
        posts[pid] = build(pid, title, cat, text, pub, cur)

    for pid, cur in list(posts.items()):  # RSS에서 빠진 옛 글도 새 규칙으로 한 번 다시 분류
        if pid in feed or cur.get("lock") or cur.get("v") == SCHEMA:
            continue
        text = cur.get("text") or cur.get("desc", "")
        posts[pid] = build(pid, cur["title"], cur["cat"], text, datetime.fromisoformat(cur["pub"]), cur)

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
