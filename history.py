"""공공기관 지난 채용공고를 모아 '공고 예정 달력'(calendar.html, forecast.json)을 만드는 스크립트

- alio.py 가 실행될 때 함께 호출됨 (같은 ALIO_KEY 사용)
- 처음 며칠은 지난 공고(마감된 공고)를 조금씩 모으고, 다 모은 뒤에는 추가 호출 없이
  매시간 모집 중 공고를 기록에 더하기만 함 → 하루 호출 한도(1,000회) 안에서 동작
- 예상 일정은 '작년·재작년 같은 시기에 공고를 냈는지'로 계산한 추정치
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
STORE = ROOT / "history.json"       # 지난 공고 기록 (사이트에서는 쓰지 않음)
FORECAST = ROOT / "forecast.json"   # 예상 일정 결과
KST = timezone(timedelta(hours=9))
PAGES_PER_RUN = 15                  # 1시간에 지난 공고 15페이지(1,500건)씩 수집
KEEP_YEARS = 3
WINDOW_DAYS = 60                    # 앞으로 60일 안의 예상 공고
ALREADY_DAYS = 75                   # 최근 75일 안에 이미 공고했으면 '이미 공고'로 제외
WD = "월화수목금토일"


def ymd(s):
    s = "".join(ch for ch in str(s or "") if ch.isdigit())[:8]
    try:
        return datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=KST) if len(s) == 8 else None
    except ValueError:
        return None


def short_hire(h):
    h = str(h or "")
    if "무기" in h:
        return "무기계약직"
    if "인턴" in h:
        return "인턴"
    if "정규" in h.replace("비정규", ""):
        return "정규직"
    return "비정규직"


def nope_of(it):
    s = "".join(ch for ch in str(it.get("recrutNope") or "") if ch.isdigit())
    return int(s) if s else 0


def record(it):
    """API 항목 → 짧은 기록 [기관, 시작일, 마감일, 인원, 고용형태, 제목, 채용구분]"""
    org = str(it.get("instNm") or "").strip()
    bgn = "".join(ch for ch in str(it.get("pbancBgngYmd") or "") if ch.isdigit())[:8]
    if not org or len(bgn) != 8:
        return None
    end = "".join(ch for ch in str(it.get("pbancEndYmd") or "") if ch.isdigit())[:8]
    return [org, bgn, end, nope_of(it), short_hire(it.get("hireTypeNmLst")),
            str(it.get("recrutPbancTtl") or "").strip()[:60], str(it.get("recrutSeNm") or "").strip()]


def is_major(r):
    """달력에 쓸 '큰 채용': 정규직·무기계약직 3명 이상, 또는 인턴 5명 이상"""
    _, _, _, n, hire, title, _ = r
    if hire in ("정규직", "무기계약직") and n >= 3:
        return True
    if hire == "인턴" and n >= 5:
        return True
    return ("공채" in title or "신입사원" in title) and hire != "비정규직"


def load():
    if STORE.exists():
        try:
            return json.loads(STORE.read_text("utf-8"))
        except ValueError:
            pass
    return {"items": {}, "next_page": 1, "done": False, "total": None}


def save(st):
    STORE.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":"), sort_keys=True), "utf-8")


def backfill(st, call, key, now):
    """마감된 지난 공고를 조금씩 수집"""
    oldest = (now - timedelta(days=365 * KEEP_YEARS)).strftime("%Y%m%d")
    for _ in range(PAGES_PER_RUN):
        page = st["next_page"]
        try:
            data = call(key, page, ongoing="N")
        except Exception as e:
            print("지난 공고 수집 실패:", e)
            return
        rows = data.get("result") or []
        if isinstance(rows, dict):
            rows = [rows]
        if st.get("total") is None:
            st["total"] = data.get("totalCount")
        for it in rows:
            if not isinstance(it, dict):
                continue
            r = record(it)
            if r and r[1] >= oldest:
                st["items"][str(it.get("recrutPblntSn"))] = r
        st["next_page"] = page + 1
        if len(rows) < 100:
            st["done"] = True
            print(f"지난 공고 수집 완료: {len(st['items'])}건")
            return
    print(f"지난 공고 수집 중: {st['next_page'] - 1}페이지 / 기록 {len(st['items'])}건 (API 전체 {st.get('total')})")


def forecast(st, open_items, now):
    today = now.date()
    by_org = {}
    for sn, r in st["items"].items():
        by_org.setdefault(r[0], []).append(r)
    open_orgs = {}
    for it in open_items:
        r = record(it)
        if r and is_major(r):
            open_orgs.setdefault(r[0], r)

    rows, skipped = [], []
    for org, recs in by_org.items():
        major = [r for r in recs if is_major(r)]
        if not major:
            continue
        # 이미 이번 시기에 공고했는지
        recent = [r for r in major if timedelta(0) <= (today - ymd(r[1]).date()) <= timedelta(days=ALREADY_DAYS)]
        if org in open_orgs or recent:
            last = open_orgs.get(org) or max(recent, key=lambda r: r[1])
            skipped.append({"org": org, "date": last[1], "title": last[5]})
            continue
        best = None
        basis = []
        for back in (1, 2):
            lo = today.replace(year=today.year - back) if not (today.month == 2 and today.day == 29) else today.replace(year=today.year - back, day=28)
            hi = lo + timedelta(days=WINDOW_DAYS)
            hits = sorted([r for r in major if lo <= ymd(r[1]).date() <= hi], key=lambda r: r[1])
            if hits:
                h = hits[0]
                basis.append({"date": h[1], "n": h[3], "hire": h[4], "title": h[5]})
                d = ymd(h[1]).date()
                try:
                    exp = d.replace(year=d.year + back)
                except ValueError:
                    exp = d.replace(year=d.year + back, day=28)
                if best is None:
                    best = exp
        if best and best >= today:
            rows.append({"org": org, "expect": best.isoformat(), "conf": "매년" if len(basis) == 2 else "작년",
                         "basis": basis})
    rows.sort(key=lambda x: (x["expect"], x["org"]))
    skipped.sort(key=lambda x: x["date"], reverse=True)
    return rows, skipped


def week_label(d):
    first = d.replace(day=1)
    wk = (d.day + first.weekday()) // 7 + 1
    names = ["첫째", "둘째", "셋째", "넷째", "다섯째", "여섯째"]
    return f"{d.month}월 {names[min(wk, 6) - 1]} 주"


def calendar_html(rows, skipped, st, now):
    import html
    import sitegen
    e = lambda s: html.escape(str(s or ""), quote=True)
    fmt = lambda s: f"{int(s[4:6])}.{int(s[6:8])}"
    yfmt = lambda s: f"{s[2:4]}.{int(s[4:6])}.{int(s[6:8])}"
    body = ["<h1>공공기관 채용 공고 예정 달력</h1>",
            f'<p class="lead">{now.year}년 {now.month}월 {now.day}일 기준, 앞으로 {WINDOW_DAYS}일 안에 공고가 예상되는 공공기관 '
            f'<b>{len(rows)}곳</b>이에요. 작년·재작년 같은 시기에 낸 채용공고(정규직·무기계약직 3명 이상, 인턴 5명 이상)를 바탕으로 계산했어요.</p>',
            '<div class="box">⚠️ <b>예상 일정이에요.</b> 기관 사정에 따라 공고가 늦어지거나 열리지 않을 수 있어요. '
            '이미 이번 시기에 공고를 낸 기관은 목록에서 자동으로 빠져요.</div>']
    if not st.get("done"):
        total = st.get("total")
        pct = ""
        try:
            pct = f" ({min(99, int((st['next_page'] - 1) * 100 * 100 / int(total)))}%)" if total else ""
        except (TypeError, ValueError, ZeroDivisionError):
            pct = ""
        body.append(f'<div class="box">📥 지난 공고 데이터를 모으는 중이에요{pct}. 며칠 안에 예상 기관이 더 늘어나요.</div>')
    if rows:
        cur = None
        for r in rows:
            d = datetime.fromisoformat(r["expect"]).date()
            wl = week_label(d)
            if wl != cur:
                if cur is not None:
                    body.append("</ul>")
                body.append(f"<h2>{wl}</h2><ul class=\"list\">")
                cur = wl
            basis = " · ".join(f'{yfmt(b["date"])} {e(b["hire"])}{(" " + str(b["n"]) + "명") if b["n"] else ""}' for b in r["basis"])
            title = r["basis"][0]["title"]
            body.append(
                f'<li class="item"><a href="https://search.naver.com/search.naver?query={e(r["org"])}+채용" target="_blank" rel="noopener">'
                f'<span class="dd{" hot" if r["conf"] == "매년" else ""}">{d.month}.{d.day}<br><small>경</small></span>'
                f'<span class="bd"><span class="org">{e(r["org"])} · {"매년 이 시기" if r["conf"] == "매년" else "작년 이 시기"}</span>'
                f'<span class="tt">{e(title)}</span><span class="meta">지난 공고: {basis}</span></span></a></li>')
        body.append("</ul>")
    else:
        body.append("<p>아직 예상 기관이 없어요. 지난 공고 데이터가 모이면 자동으로 채워져요.</p>")
    if skipped:
        body.append(f'<details class="box"><summary>이미 이번 시기에 공고한 기관 {len(skipped)}곳 (목록에서 제외)</summary><p class="meta">'
                    + ", ".join(f'{e(s["org"])}({fmt(s["date"])})' for s in skipped[:80]) + "</p></details>")
    body.append('<p class="lead">지금 모집 중인 공고는 <a href="./">마감순 전체 공고</a>에서 확인하세요.</p>')
    desc = f"앞으로 {WINDOW_DAYS}일 안에 채용공고가 예상되는 공공기관 {len(rows)}곳을 지난 공고 일정으로 정리했어요."
    return sitegen.page("calendar.html", "공공기관 채용 공고 예정 달력", desc, "\n".join(body))


def run(key, call, open_items):
    now = datetime.now(KST)
    st = load()
    # 모집 중 공고도 기록에 더해 두면, 마감된 뒤에도 '지난 공고'로 남음
    for it in open_items:
        r = record(it)
        if r:
            st["items"][str(it.get("recrutPblntSn"))] = r
    if not st.get("done"):
        backfill(st, call, key, now)
    oldest = (now - timedelta(days=365 * KEEP_YEARS)).strftime("%Y%m%d")
    st["items"] = {k: v for k, v in st["items"].items() if v[1] >= oldest}
    save(st)
    rows, skipped = forecast(st, open_items, now)
    out = json.dumps({"updated": now.isoformat(timespec="seconds"), "done": st.get("done"),
                      "rows": rows, "skipped": skipped}, ensure_ascii=False, indent=1)
    if not FORECAST.exists() or json.loads(FORECAST.read_text("utf-8")).get("rows") != rows:
        FORECAST.write_text(out, "utf-8")
    page = calendar_html(rows, skipped, st, now)
    cal = ROOT / "calendar.html"
    if not cal.exists() or cal.read_text("utf-8") != page:
        cal.write_text(page, "utf-8")
    print(f"공고 예정 달력: 예상 {len(rows)}곳 · 이미 공고 {len(skipped)}곳 제외")
