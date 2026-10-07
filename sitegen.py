"""검색엔진·애드센스용 정적 페이지 생성기 (update.py가 실행할 때마다 호출)

만드는 것
- index.html 안의 공고 목록(검색 로봇이 바로 읽을 수 있게 미리 써 넣음)
- deadline-week.html  이번 주 마감 채용공고 총정리
- intern.html         모집 중인 인턴 채용 모음
- highschool.html     고졸·학력무관 지원 가능 채용 모음
- sitemap.xml
"""
import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SITE = "https://jobinfo-hub.github.io/"
KST = timezone(timedelta(hours=9))
WD = "월화수목금토일"
STATIC_PAGES = ["about.html", "privacy.html", "contact.html"]

e = lambda s: html.escape(str(s or ""), quote=True)


def dt(s):
    return datetime.fromisoformat(s) if s else None


def due_text(p):
    d = dt(p["due"]).astimezone(KST)
    t = f"{d.month}.{d.day}({WD[d.weekday()]})"
    return t + (f" {d:%H:%M}" if p.get("dueHasTime") else "")


def clean_title(t):
    s = re.sub(r"\s*D-(?:DAY|\d{1,3})", "", t, flags=re.I)
    s = re.sub(r"\s*\d{1,2}[./]\d{1,2}\.?\s*(?:\([^)]*\))?\s*(?:(?:오전|오후|낮)\s*)?(?:\d{1,2}(?::\d{2}|시))?\s*마감(?:\s*전)?", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s*([,—–])\s*(?=[,—–]|$)", "", s).strip(" ,—–")
    return s if len(s) >= 6 else t


def open_jobs(posts, now):
    jobs = [p for p in posts if p["type"] == "j" and p.get("due") and dt(p["due"]) > now]
    return sorted(jobs, key=lambda p: p["due"])


def job_item(p, now):
    days = (dt(p["due"]).astimezone(KST).date() - now.date()).days
    dd = "D-DAY" if days == 0 else f"D-{days}"
    tags = []
    if p.get("n"):
        tags.append(f"{e(p['n'])}명")
    tags += [e(x) for x in (p.get("emp") or []) + (p.get("edu") or [])]
    if p.get("region"):
        tags.append(e(p["region"]))
    org = f'<span class="org">{e(p["org"])}</span>' if p.get("org") else ""
    return (f'<li class="item"><a href="{e(p["url"])}" target="_blank" rel="noopener">'
            f'<span class="dd{" hot" if days <= 3 else ""}">{dd}</span>'
            f'<span class="bd">{org}<span class="tt">{e(clean_title(p["title"]))}</span>'
            f'<span class="meta">접수 마감 {due_text(p)}{" · " + " · ".join(tags) if tags else ""}</span></span></a></li>')


# ── 1) index.html 안에 정적 목록 써 넣기 ──
def prerender_index(posts, now):
    path = ROOT / "index.html"
    if not path.exists():
        return False
    src = path.read_text("utf-8")
    start, end = "<!--STATIC-LIST-->", "<!--/STATIC-LIST-->"
    if start not in src:
        return False
    jobs = open_jobs(posts, now)[:40]
    others = [p for p in posts if p["type"] != "j"][:10]
    items = []
    for p in jobs:
        org = f'{e(p["org"])} · ' if p.get("org") and not p["title"].startswith(p["org"]) else ""
        items.append(f'<li class="card mini"><a class="main" href="{e(p["url"])}"><div class="kind">'
                     f'<span class="pill p">마감 {due_text(p)}</span></div>'
                     f'<div class="t">{org}{e(clean_title(p["title"]))}</div></a></li>')
    for p in others:
        label = "정책" if p["type"] == "m" else "취업준비"
        items.append(f'<li class="card mini"><a class="main" href="{e(p["url"])}"><div class="kind">'
                     f'<span class="pill {p["type"]}">{label}</span></div><div class="t">{e(p["title"])}</div></a></li>')
    block = start + "\n" + "\n".join(items) + "\n" + end
    new = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: block, src, flags=re.S)
    if new != src:
        path.write_text(new, "utf-8")
        return True
    return False


# ── 2) 정리 페이지 공통 틀 ──
CSS = """
:root{--bg:#F5F7FB;--surface:#fff;--ink:#14213D;--muted:#5B6475;--line:#DFE4EE;--brand:#1F3FBF;--hot:#D92D2A;--hot-soft:#FDE8E7;--tile:#EEF1F6;--tile-ink:#3A4560;box-sizing:border-box}
@media (prefers-color-scheme:dark){:root{--bg:#0F1524;--surface:#172036;--ink:#E8ECF5;--muted:#9AA6BD;--line:#2A3550;--brand:#7C95FF;--hot:#FF6B66;--hot-soft:#3A1F27;--tile:#1E2840;--tile-ink:#C3CBDD}}
*,*::before,*::after{box-sizing:inherit}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;font-size:15px;line-height:1.6;padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0)}
.wrap{max-width:720px;margin:0 auto;padding:12px 16px 40px}
.top{display:flex;align-items:center;gap:10px;text-decoration:none;color:inherit;margin-bottom:6px}
.logo{width:34px;height:34px;border-radius:9px;background:#1F3FBF;color:#fff;display:grid;place-items:center;font-weight:800;font-size:11px;line-height:1.05;text-align:center}
.top b{font-size:17px}
nav.links{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px}
nav.links a{font-size:13px;padding:5px 10px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}
nav.links a[aria-current]{background:var(--brand);border-color:var(--brand);color:#fff}
h1{font-size:22px;line-height:1.35;margin:6px 0 8px}
h2{font-size:17px;margin:22px 0 8px}
p.lead{color:var(--muted);margin:0 0 10px}
.box{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:12px 0}
ul.list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.item a{display:flex;gap:12px;align-items:flex-start;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:11px 12px;color:inherit;text-decoration:none}
.dd{flex:none;min-width:54px;text-align:center;font-weight:800;font-size:14px;border-radius:8px;padding:6px 4px;background:var(--tile);color:var(--tile-ink)}
.dd.hot{background:var(--hot-soft);color:var(--hot)}
.bd{display:flex;flex-direction:column;min-width:0}
.org{font-size:12.5px;font-weight:700;color:var(--brand)}
.tt{font-weight:700;line-height:1.4;word-break:keep-all}
.meta{font-size:12.5px;color:var(--muted);margin-top:2px}
footer{margin-top:28px;font-size:12.5px;color:var(--muted)}
footer a{color:inherit;margin-right:10px}
"""
NAV = [("index.html", "전체 공고"), ("deadline-week.html", "이번 주 마감"), ("intern.html", "인턴 모음"), ("highschool.html", "고졸 가능")]


def page(fname, title, desc, body):
    nav = "".join(f'<a href="{href}"{" aria-current=\"page\"" if href == fname else ""}>{label}</a>' for href, label in NAV)
    url = SITE + ("" if fname == "index.html" else fname)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)} | 취업/정책 지원소</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}og.png"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="icon-192.png" type="image/png"><link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#1F3FBF">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4206368432511517"
     crossorigin="anonymous"></script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<a class="top" href="./"><span class="logo">취업<br>정책</span><b>취업/정책 지원소</b></a>
<nav class="links">{nav}</nav>
{body}
<footer>
<p>각 공고는 기관 공식 채용공고 원문을 확인해 정리한 블로그 글을 바탕으로 합니다. 지원 전 반드시 공식 공고(잡알리오·나라일터·기관 홈페이지)를 확인하세요.</p>
<a href="about.html">사이트 소개</a><a href="privacy.html">개인정보처리방침</a><a href="contact.html">문의</a>
</footer>
</div>
<script type="text/javascript" src="https://wcs.pstatic.net/wcslog.js"></script>
<script type="text/javascript">if(!wcs_add) var wcs_add = {{}}; wcs_add["wa"] = "1c5b542575a2270"; if(window.wcs) {{ wcs_do(); }}</script>
</body>
</html>
"""


def write_if_changed(fname, text):
    path = ROOT / fname
    if path.exists() and path.read_text("utf-8") == text:
        return False
    path.write_text(text, "utf-8")
    return True


def date_label(now):
    return f"{now.year}년 {now.month}월 {now.day}일"


def gen_week(posts, now):
    end = now + timedelta(days=7)
    jobs = [p for p in open_jobs(posts, now) if dt(p["due"]) <= end]
    groups = {}
    for p in jobs:
        d = dt(p["due"]).astimezone(KST)
        groups.setdefault(d.date(), []).append(p)
    total = sum(int(p["n"]) for p in jobs if str(p.get("n", "")).isdigit())
    body = [f"<h1>이번 주 마감 채용공고 총정리 ({now.month}/{now.day}~{end.month}/{end.day})</h1>",
            f'<p class="lead">{date_label(now)} 기준, 앞으로 7일 안에 접수가 끝나는 공기업·공공기관·공무직 채용공고 '
            f'<b>{len(jobs)}건</b>을 마감일 순서로 정리했습니다.'
            + (f" 인원이 공개된 공고만 합쳐도 <b>{total:,}명</b>을 뽑습니다." if total else "") + "</p>",
            '<div class="box">마감 시각이 오전 10시·오후 2시처럼 자정이 아닌 공고가 많습니다. '
            '마감일 당일에는 접수 사이트가 몰려 느려지니, 하루 전까지 제출하는 것을 권합니다.</div>']
    if not jobs:
        body.append("<p>이번 주에 마감되는 공고가 아직 없습니다.</p>")
    for day, items in groups.items():
        body.append(f"<h2>{day.month}월 {day.day}일({WD[day.weekday()]}) 마감 · {len(items)}건</h2>")
        body.append('<ul class="list">' + "".join(job_item(p, now) for p in items) + "</ul>")
    desc = f"{date_label(now)} 기준 7일 안에 마감되는 채용공고 {len(jobs)}건을 마감일별로 정리했습니다."
    return page("deadline-week.html", "이번 주 마감 채용공고 총정리", desc, "\n".join(body))


def gen_filtered(posts, now, fname, title, lead, tip, pred):
    jobs = [p for p in open_jobs(posts, now) if pred(p)]
    body = [f"<h1>{title}</h1>",
            f'<p class="lead">{date_label(now)} 기준 모집 중인 공고 <b>{len(jobs)}건</b>. {lead}</p>',
            f'<div class="box">{tip}</div>',
            '<ul class="list">' + "".join(job_item(p, now) for p in jobs) + "</ul>"
            if jobs else "<p>지금 모집 중인 공고가 없습니다. 새 공고가 올라오면 자동으로 추가됩니다.</p>"]
    desc = f"{date_label(now)} 기준 모집 중인 {title.replace(' 모음', '')} {len(jobs)}건을 마감순으로 정리했습니다."
    return page(fname, title, desc, "\n".join(body))


def is_intern(p):
    return "인턴" in (p.get("emp") or []) or "인턴" in p["title"]


def is_highschool(p):
    edu = p.get("edu") or []
    return "고졸 가능" in edu or "학력무관" in edu or "고졸" in p["title"]


def gen_sitemap(now):
    pages = ["", "deadline-week.html", "intern.html", "highschool.html"] + STATIC_PAGES
    urls = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{now:%Y-%m-%d}</lastmod></url>\n" for p in pages)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")


def generate(posts):
    now = datetime.now(KST)
    changed = []
    if prerender_index(posts, now):
        changed.append("index.html")
    outs = {
        "deadline-week.html": gen_week(posts, now),
        "intern.html": gen_filtered(
            posts, now, "intern.html", "모집 중인 인턴 채용 모음",
            "체험형·채용형 청년인턴 공고를 마감이 빠른 순서로 모았습니다.",
            "<b>체험형</b>은 기간이 끝나면 종료되고, <b>채용형</b>은 평가를 거쳐 정규직으로 전환됩니다. "
            "공고문에서 '채용형'인지 먼저 확인하세요. 체험형도 공공기관 경력으로 자소서에 활용할 수 있습니다.", is_intern),
        "highschool.html": gen_filtered(
            posts, now, "highschool.html", "고졸 지원 가능 채용 모음",
            "고졸 전형이 있거나 학력 제한이 없는 공고를 모았습니다.",
            "'학력무관'이어도 직렬에 따라 자격증이나 경력이 필수인 경우가 있습니다. "
            "고졸 전형은 졸업예정자 기준일을 꼭 확인하세요.", is_highschool),
    }
    for fname, text in outs.items():
        if write_if_changed(fname, text):
            changed.append(fname)
    sm = gen_sitemap(now)
    old = (ROOT / "sitemap.xml").read_text("utf-8") if (ROOT / "sitemap.xml").exists() else ""
    if re.sub(r"<lastmod>.*?</lastmod>", "", old) != re.sub(r"<lastmod>.*?</lastmod>", "", sm) or changed:
        (ROOT / "sitemap.xml").write_text(sm, "utf-8")
        changed.append("sitemap.xml")
    print("정적 페이지 갱신:", ", ".join(changed) if changed else "변경 없음")
