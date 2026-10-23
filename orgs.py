"""기관별 정보 페이지 생성기 (history.py 가 매시간 호출)

만드는 것
- orgs.html            기관 목록 (검색 가능)
- org-<기관명>.html     기관별 페이지: 채용 이력, 다음 공고 예상, 지금 모집 중, 최근 공고 지원 자격, 월별 공고 수
- orgs.json            sitegen 이 사이트맵에 넣을 기관 페이지 목록
"""
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import sitegen

ROOT = Path(__file__).parent
e = lambda s: html.escape(str(s or ""), quote=True)
WD = "월화수목금토일"


def slug(org):
    s = re.sub(r"\((주|재|사)\)", "", org)
    return re.sub(r"[\s\\/:*?\"<>|().,·'\[\]]", "", s)


def fname(org):
    return f"org-{slug(org)}.html"


def ymd_label(s, year=True):
    s = str(s)
    if len(s) < 8:
        return ""
    return (f"{s[2:4]}." if year else "") + f"{int(s[4:6])}.{int(s[6:8])}"


def clip(t, n=1200):
    t = re.sub(r"<br\s*/?>", "\n", str(t or ""), flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace("\r", "")
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t if len(t) <= n else t[:n].rstrip() + " …(원문에서 계속)"


def write_if_changed(name, text):
    p = ROOT / name
    if p.exists() and p.read_text("utf-8") == text:
        return False
    p.write_text(text, "utf-8")
    return True


EXTRA_CSS = """<style>
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:12px 0}
.kv div{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.kv b{display:block;font-size:20px;color:var(--brand);line-height:1.2}
.kv span{font-size:12.5px;color:var(--muted)}
.bars{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;align-items:end;height:120px;margin:8px 0 4px}
.bars div{background:var(--tile);border-radius:6px 6px 0 0;position:relative;min-height:2px}
.bars div.pk{background:var(--brand)}
.bars-l{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;font-size:11.5px;color:var(--muted);text-align:center}
.sec{white-space:pre-line;font-size:14.5px;line-height:1.75;word-break:keep-all;margin:4px 0 0}
table.hist{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--surface);border-radius:12px;overflow:hidden}
table.hist th,table.hist td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
table.hist th{font-size:12.5px;color:var(--muted);font-weight:600}
table.hist td.d{white-space:nowrap;color:var(--muted)}
.pill{display:inline-block;font-size:11.5px;font-weight:700;border-radius:5px;padding:0 6px;line-height:19px;background:var(--tile);color:var(--tile-ink);margin-right:4px}
.pill.hot{background:var(--hot-soft);color:var(--hot)}
.olist a{display:block;padding:10px 12px;background:var(--surface);border:1px solid var(--line);border-radius:12px;color:inherit;text-decoration:none;margin-bottom:6px}
.olist a:hover{border-color:var(--brand)}
#q{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);font:inherit;margin:4px 0 10px}
</style>"""


def org_page(org, recs, fc, sk, open_now, blog_now, det, now):
    recs = sorted(recs, key=lambda r: r[1], reverse=True)
    n_all = len(recs)
    hires = Counter(r[4] for r in recs)
    months = Counter(int(r[1][4:6]) for r in recs)
    peak = [m for m, _ in months.most_common(2) if months[m] > 0]
    big = [r for r in recs if (r[4] in ("정규직", "무기계약직") and r[3] >= 3) or (r[4] == "인턴" and r[3] >= 5)]
    first, last = (recs[-1][1], recs[0][1]) if recs else ("", "")
    b = [f"<h1>{e(org)} 채용 정보 · 공고 일정 · 지원 자격</h1>"]
    lead = f"{e(org)}의 최근 채용공고 {n_all}건을 정리했어요"
    if first:
        lead += f" ({ymd_label(first)} ~ {ymd_label(last)}, 알리오 기준)"
    lead += "."
    if peak:
        lead += f" 공고는 주로 <b>{'·'.join(str(m) + '월' for m in sorted(peak))}</b>에 많았어요."
    b.append(f'<p class="lead">{lead}</p>')
    b.append('<div class="kv">' + "".join(
        f"<div><b>{v}</b><span>{k}</span></div>" for k, v in [
            ("전체 공고", f"{n_all}건"), ("정규직", f"{hires.get('정규직', 0)}건"),
            ("무기계약직", f"{hires.get('무기계약직', 0)}건"), ("인턴", f"{hires.get('인턴', 0)}건"),
            ("비정규직", f"{hires.get('비정규직', 0)}건")]) + "</div>")

    # 다음 공고 예상
    b.append("<h2>🗓 다음 공고 예상</h2>")
    if open_now:
        b.append(f'<div class="box">지금 모집 중인 공고가 <b>{len(open_now)}건</b> 있어요. 아래 목록에서 확인하세요.</div>')
    elif sk:
        b.append(f'<div class="box">이번 시기에는 이미 <b>{ymd_label(sk["date"])}</b>에 공고를 냈어요. ({e(sk["title"])})</div>')
    elif fc:
        d = datetime.fromisoformat(fc["expect"]).date()
        basis = " · ".join(f'{ymd_label(x["date"])} {e(x["hire"])}{(" " + str(x["n"]) + "명") if x["n"] else ""}' for x in fc["basis"])
        b.append(f'<div class="box"><b>{d.month}월 {d.day}일경</b> 공고가 예상돼요 ({"매년 이 시기" if fc["conf"] == "매년" else "작년 이 시기"} 공고). '
                 f'근거: {basis}<br><span class="meta">지난 일정으로 계산한 예상이라 실제와 다를 수 있어요.</span></div>')
    elif peak:
        b.append(f'<div class="box">앞으로 60일 안에 예상되는 공고는 없어요. 지난 기록으로는 보통 '
                 f'<b>{"·".join(str(m) + "월" for m in sorted(peak))}</b>에 공고가 많았어요.</div>')
    else:
        b.append('<div class="box">예상 일정을 계산할 만큼 기록이 충분하지 않아요.</div>')

    # 지금 모집 중
    if open_now or blog_now:
        b.append("<h2>📢 지금 모집 중</h2><div class=\"olist\">")
        for p in blog_now:
            b.append(f'<a href="{e(p["url"])}" target="_blank" rel="noopener"><span class="pill hot">해설</span>'
                     f'{e(sitegen.clean_title(p["title"]))}<br><span class="meta">접수 마감 {sitegen.due_text(p)}</span></a>')
        for p in open_now[:8]:
            due = f"접수 마감 {sitegen.due_text(p)}" if p.get("due") else "상시 모집"
            meta = " · ".join(x for x in [f'{p["n"]}명' if p.get("n") else "", " ".join(p.get("emp") or []), due] if x)
            b.append(f'<a href="./jobs/{e(p["id"])}.html"><span class="pill">공식</span>{e(p["title"])}<br><span class="meta">{e(meta)}</span></a>')
        if len(open_now) > 8:
            b.append(f'<a href="./?q={e(org)}">외 {len(open_now) - 8}건 더 보기 →</a>')
        b.append("</div>")

    # 최근 공고 지원 자격
    if det:
        b.append(f'<h2>📝 최근 공고의 지원 자격</h2><p class="meta">{ymd_label(det["date"])} 공고 「{e(det["title"])}」 기준이에요. '
                 '공고마다 자격이 다르니 지원 전 해당 공고 원문을 꼭 확인하세요.</p>')
        for k, label in (("aply", "지원 자격"), ("pref", "우대 조건"), ("proc", "전형 절차·방법")):
            if det.get(k):
                b.append(f'<div class="box"><b>{label}</b><p class="sec">{e(clip(det[k]))}</p></div>')

    # 월별 공고 수
    if n_all:
        mx = max(months.values()) or 1
        b.append("<h2>📊 월별 공고 수</h2>")
        b.append('<div class="bars">' + "".join(
            f'<div class="{"pk" if m in peak else ""}" style="height:{max(2, int(months.get(m, 0) * 100 / mx))}%" '
            f'title="{m}월 {months.get(m, 0)}건"></div>' for m in range(1, 13)) + "</div>")
        b.append('<div class="bars-l">' + "".join(f"<span>{m}</span>" for m in range(1, 13)) + "</div>")
        b.append(f'<p class="meta">최근 기록 기준 월별 공고 수예요. 진한 막대가 공고가 가장 많았던 달이에요.</p>')

    # 채용 이력
    if recs:
        use_big = len(big) >= 5
        show = big[:25] if use_big else recs[:25]
        b.append(f'<h2>📜 채용 이력</h2><p class="meta">{"정규직·무기계약직 3명 이상, 인턴 5명 이상 공고" if use_big else "최근 공고"} 최대 25건이에요.</p>')
        b.append('<table class="hist"><tr><th>공고일</th><th>공고</th><th>형태·인원</th></tr>' + "".join(
            f'<tr><td class="d">{ymd_label(r[1])}</td><td>{e(r[5])}</td><td class="d">{e(r[4])}{(" " + str(r[3]) + "명") if r[3] else ""}</td></tr>'
            for r in show) + "</table>")

    b.append(f'<p class="lead" style="margin-top:18px"><a href="orgs.html">← 기관 목록</a> · <a href="calendar.html">공고 예정 달력</a> · '
             f'<a href="https://search.naver.com/search.naver?query={e(org)}+채용" target="_blank" rel="noopener">{e(org)} 채용 검색</a></p>')
    desc = f"{org} 채용공고 일정과 다음 공고 예상 시기, 최근 공고 지원 자격, 월별 공고 수를 정리했어요."
    page = sitegen.page(fname(org), f"{org} 채용 정보", desc, "\n".join(b))
    return page.replace("</head>", EXTRA_CSS + "\n</head>", 1)


def index_page(rows, now):
    b = ["<h1>기관별 채용 정보</h1>",
         f'<p class="lead">공공기관 <b>{len(rows)}곳</b>의 채용 이력, 다음 공고 예상 시기, 최근 지원 자격을 기관별로 모았어요.</p>',
         '<input id="q" type="search" placeholder="기관명 검색 (예: 수자원, 도로공사, 병원)" aria-label="기관 검색">',
         '<div class="olist" id="ol">']
    for r in rows:
        tag = ""
        if r["open"]:
            tag = f'<span class="pill hot">모집 중 {r["open"]}</span>'
        elif r["expect"]:
            tag = f'<span class="pill">{r["expect"]}경 예상</span>'
        b.append(f'<a href="{e(r["file"])}" data-n="{e(r["org"])}">{tag}<b>{e(r["org"])}</b><br>'
                 f'<span class="meta">최근 공고 {r["n"]}건{(" · 주로 " + r["peak"]) if r["peak"] else ""}</span></a>')
    b.append("</div>")
    b.append("""<script>
document.getElementById("q").addEventListener("input", ev => {
  const q = ev.target.value.replace(/\\s/g, "");
  document.querySelectorAll("#ol a").forEach(a => { a.style.display = !q || a.dataset.n.replace(/\\s/g, "").includes(q) ? "" : "none"; });
});
</script>""")
    desc = f"공공기관 {len(rows)}곳의 채용 이력과 다음 공고 예상 시기, 지원 자격을 기관별로 정리했어요."
    page = sitegen.page("orgs.html", "기관별 채용 정보", desc, "\n".join(b))
    return page.replace("</head>", EXTRA_CSS + "\n</head>", 1)


def generate(st, open_items, fc_rows, skipped, now):
    by_org = {}
    for r in st["items"].values():
        by_org.setdefault(r[0], []).append(r)
    fc = {r["org"]: r for r in fc_rows}
    sk = {s["org"]: s for s in skipped}
    try:
        alio_posts = json.loads((ROOT / "alio.json").read_text("utf-8")).get("posts", [])
    except Exception:
        alio_posts = []
    try:
        blog = json.loads((ROOT / "posts.json").read_text("utf-8")).get("posts", [])
    except Exception:
        blog = []
    open_by = {}
    for p in alio_posts:
        open_by.setdefault(p.get("org"), []).append(p)
    norm = lambda s: re.sub(r"\(주\)|주식회사|\s|[()·.,]", "", str(s or ""))
    details = st.get("details", {})
    rows, changed = [], 0
    for org, recs in by_org.items():
        if len(recs) < 2 and org not in open_by:
            continue
        on = norm(org)
        blog_now = [p for p in blog if p.get("type") == "j" and p.get("due") and p.get("org") and len(norm(p["org"])) > 1
                    and (norm(p["org"]) in on or on in norm(p["org"])) and datetime.fromisoformat(p["due"]) > now]
        text = org_page(org, recs, fc.get(org), sk.get(org), open_by.get(org, []), blog_now, details.get(org), now)
        if write_if_changed(fname(org), text):
            changed += 1
        months = Counter(int(r[1][4:6]) for r in recs)
        peak = "·".join(f"{m}월" for m, _ in sorted(months.most_common(2))) if months else ""
        exp = ""
        if org in fc:
            d = datetime.fromisoformat(fc[org]["expect"]).date()
            exp = f"{d.month}.{d.day}"
        rows.append({"org": org, "file": fname(org), "n": len(recs), "open": len(open_by.get(org, [])),
                     "expect": exp, "peak": peak})
    rows.sort(key=lambda r: r["org"])
    write_if_changed("orgs.html", index_page(rows, now))
    write_if_changed("orgs.json", json.dumps([r["file"] for r in rows], ensure_ascii=False))
    print(f"기관 페이지: {len(rows)}곳 (변경 {changed}곳)")
