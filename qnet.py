"""큐넷(한국산업인력공단) 국가자격 시험일정을 가져와 qnet.json 과 certs.html 을 만드는 스크립트

- 공공데이터포털 '한국산업인력공단_국가자격 시험일정 조회 서비스' (data.go.kr 15074408, 자동 승인)
- 잡알리오와 같은 인증키(ALIO_KEY)를 씀 → 공공데이터포털에서 위 서비스 '활용신청'만 하면 됨
- 시험일정은 자주 바뀌지 않아서 하루에 한 번만 API를 부름 (나머지 실행은 건너뜀)
- 실패해도 기존 파일을 그대로 두므로 사이트에는 영향이 없음
"""
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "qnet.json"
KST = timezone(timedelta(hours=9))
ENDPOINTS = ["https://apis.data.go.kr/B490007/qualExamSchd/getQualExamSchdList"]
# 종목코드 없이 받기가 안 될 때 쓰는 대표 종목 (같은 등급은 시험일정이 같음)
FALLBACK = [("기사·산업기사", "1320"), ("기능사", "7780"), ("기사·산업기사", "9511")]
GRADE_ORDER = ["기술사", "기능장", "기사·산업기사", "기사", "산업기사", "기능사"]
FIELDS = {"wa1": "docRegStartDt", "wa2": "docRegEndDt", "w1": "docExamStartDt", "w2": "docExamEndDt",
          "wp": "docPassDt", "pa1": "pracRegStartDt", "pa2": "pracRegEndDt", "p1": "pracExamStartDt",
          "p2": "pracExamEndDt", "pp": "pracPassDt"}


def ask(key, year, gb, page=1, jm=None):
    q = {"serviceKey": key, "dataFormat": "json", "implYy": str(year), "qualgbCd": gb,
         "numOfRows": "50", "pageNo": str(page)}
    if jm:
        q["jmCd"] = jm
    last = None
    for base in ENDPOINTS:
        try:
            req = urllib.request.Request(f"{base}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "jobinfo-hub"})
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
            data = json.loads(text)
            head = data.get("header") or (data.get("response") or {}).get("header") or {}
            body = data.get("body") or (data.get("response") or {}).get("body") or {}
            code = str(head.get("resultCode", "00"))
            if code not in ("00", "0", "200"):
                raise RuntimeError(f"API 오류 {code}: {head.get('resultMsg')}")
            items = body.get("items") or []
            if isinstance(items, dict):
                items = items.get("item") or []
            if isinstance(items, dict):
                items = [items]
            return [x for x in items if isinstance(x, dict)], body.get("totalCount")
        except Exception as e:
            last = str(e).replace(key, "***")
    raise RuntimeError(last)


def d8(v):
    s = "".join(ch for ch in str(v or "") if ch.isdigit())[:8]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else ""


def grade_of(desc, fallback=""):
    d = str(desc or "")
    if "기술사" in d:
        return "기술사"
    if "기능장" in d:
        return "기능장"
    if "산업기사" in d or re.search(r"(?<!산업)기사", d):
        return "기사·산업기사"
    if "기능사" in d:
        return "기능사"
    return fallback or re.sub(r"\(.*?\)|\d{4}년도?|제?\s*\d+\s*회|국가(?:기술|전문)?자격", "", d).strip(" -·") or "기타"


class IncompleteQnetResponse(RuntimeError):
    """An API page limit would discard reported QNet schedule records."""



def collect(key, year, gb):
    rows, page, reported_total = [], 1, None
    while page <= 6:
        items, total = ask(key, year, gb, page)
        if total is not None and reported_total is None:
            reported_total = total
        rows += items
        try:
            if len(items) < 50 or (total and len(rows) >= int(total)):
                break
        except (TypeError, ValueError):
            break
        page += 1
    # Reject incomplete pagination rather than replacing a complete daily cache.
    try:
        expected = int(reported_total) if reported_total is not None else None
    except (TypeError, ValueError):
        expected = None
    if expected is not None and expected > len(rows):
        raise IncompleteQnetResponse(
            f"큐넷 {year} {gb} 수집 불완전: {len(rows)} / {expected}건"
        )
    if expected is None and page > 6 and len(items) == 50:
        raise IncompleteQnetResponse(
            f"큐넷 {year} {gb} 페이지 한도 도달: 수집 {len(rows)}건"
        )
    return rows


def to_row(it, year, kind, grade=""):
    desc = str(it.get("description") or it.get("jmfldnm") or "").strip()
    r = {"kind": kind, "g": grade_of(desc, grade) if kind == "T" else (grade or grade_of(desc)),
         "y": int(str(it.get("implYy") or year)[:4]), "r": str(it.get("implSeq") or "").strip(), "desc": desc}
    for k, f in FIELDS.items():
        r[k] = d8(it.get(f))
    return r


def merge(rows):
    """빠른접수·일반접수처럼 같은 회차가 여러 줄로 오면 하나로 합침"""
    box = {}
    for r in rows:
        if not (r["wa1"] or r["pa1"] or r["w1"] or r["p1"]):
            continue
        k = (r["kind"], r["g"], r["y"], r["r"])
        if k not in box:
            box[k] = dict(r)
            continue
        b = box[k]
        for f in ("wa1", "pa1"):
            if r[f] and (not b[f] or r[f] < b[f]):
                b[f] = r[f]
        for f in ("wa2", "pa2"):
            if r[f] and (not b[f] or r[f] > b[f]):
                b[f] = r[f]
        for f in FIELDS:
            if not b[f] and r[f]:
                b[f] = r[f]
    out = list(box.values())
    rank = {g: i for i, g in enumerate(GRADE_ORDER)}
    out.sort(key=lambda r: (r["kind"], rank.get(r["g"], 99), r["g"], r["y"], int(r["r"]) if r["r"].isdigit() else 99))
    return out


def fetch(key, now):
    rows = []
    for year in (now.year, now.year + 1):
        # 1) 국가기술자격: 종목코드 없이 등급별 일정 받기
        got = []
        try:
            got = collect(key, year, "T")
            if got and year == now.year:
                print("큐넷 응답 필드:", ", ".join(sorted(got[0].keys())))
                print("큐넷 일정 설명 예:", " | ".join(sorted({str(x.get("description", ""))[:30] for x in got})[:8]))
        except IncompleteQnetResponse:
            raise  # Never replace a complete snapshot with a truncated schedule.
        except Exception as e:
            print(f"큐넷 {year} 국가기술자격 요청 실패:", e)
        if got:
            rows += [to_row(it, year, "T") for it in got]
        else:
            # 2) 안 되면 대표 종목코드로 받기
            for grade, jm in FALLBACK:
                try:
                    items, _ = ask(key, year, "T", 1, jm)
                    rows += [to_row(it, year, "T", grade) for it in items]
                except Exception as e:
                    print(f"큐넷 {year} {grade}({jm}) 요청 실패:", e)
        # 3) 국가전문자격 (공인노무사 등) — 있으면 함께
        try:
            sp = collect(key, year, "S")
            if len(sp) <= 300:
                rows += [to_row(it, year, "S") for it in sp]
        except IncompleteQnetResponse:
            raise
        except Exception as e:
            print(f"큐넷 {year} 국가전문자격 요청 실패(무시):", e)
    return merge(rows)


def fmt(s):
    if not s:
        return "-"
    y, m, d = map(int, s.split("-"))
    return f"{m}.{d}({'월화수목금토일'[datetime(y, m, d).weekday()]})"


def span(a, b):
    if not a and not b:
        return "-"
    if a and b and a != b:
        return f"{fmt(a)} ~ {fmt(b)}"
    return fmt(a or b)


def certs_html(rows, now):
    import sitegen
    e = lambda s: html.escape(str(s or ""), quote=True)
    today = now.strftime("%Y-%m-%d")
    open_now = [r for r in rows if (r["wa1"] and r["wa1"] <= today <= r["wa2"]) or (r["pa1"] and r["pa1"] <= today <= r["pa2"])]
    body = [f"<h1>{now.year}년 국가자격 시험일정</h1>",
            f'<p class="lead">큐넷(한국산업인력공단) 공식 일정을 매일 자동으로 정리해요. 기사·산업기사, 기능사, 기술사 등 등급별 '
            f'원서접수·시험·합격발표 날짜를 한눈에 볼 수 있어요. ({now.month}월 {now.day}일 기준)</p>']
    if open_now:
        body.append('<div class="box">🔥 <b>지금 원서접수 중</b>: ' + ", ".join(
            f'{e(r["g"])} {r["y"]}년 제{e(r["r"])}회 {"필기" if r["wa1"] and r["wa1"] <= today <= r["wa2"] else "실기"}'
            f'(~{fmt(r["wa2"] if r["wa1"] and r["wa1"] <= today <= r["wa2"] else r["pa2"])})' for r in open_now)
            + ' · <a href="https://www.q-net.or.kr" target="_blank" rel="noopener">큐넷에서 접수 ↗</a></div>')
    groups = {}
    for r in rows:
        groups.setdefault((r["kind"], r["g"]), []).append(r)
    for (kind, g), rs in groups.items():
        body.append(f"<h2>{e(g)}{' (국가전문자격)' if kind == 'S' else ''}</h2>")
        body.append('<div style="overflow-x:auto"><table class="tbl"><thead><tr><th>회차</th><th>필기 접수</th><th>필기 시험</th>'
                    '<th>필기 발표</th><th>실기 접수</th><th>실기 시험</th><th>최종 발표</th></tr></thead><tbody>')
        for r in rs:
            past = (r["pp"] or r["p2"] or r["wp"] or "9999") < today
            body.append(f'<tr{" class=past" if past else ""}><td>{r["y"]}년 {e(r["r"])}회</td><td>{span(r["wa1"], r["wa2"])}</td>'
                        f'<td>{span(r["w1"], r["w2"])}</td><td>{fmt(r["wp"])}</td><td>{span(r["pa1"], r["pa2"])}</td>'
                        f'<td>{span(r["p1"], r["p2"])}</td><td>{fmt(r["pp"])}</td></tr>')
        body.append("</tbody></table></div>")
    if not rows:
        body.append("<p>시험일정을 불러오는 중이에요. 곧 자동으로 채워져요.</p>")
    body.append('<div class="box">⚠️ 종목에 따라 시행하지 않는 회차가 있고, 원서접수는 보통 마지막 날 18시에 마감돼요. '
                '정확한 일정과 종목별 시행 여부는 <a href="https://www.q-net.or.kr" target="_blank" rel="noopener">큐넷</a>에서 꼭 확인하세요.</div>')
    body.append('<p class="lead">자격증으로 지원할 수 있는 공공기관 공고는 <a href="./?tab=cert">커리어픽 자격증 탭</a>에서 확인하세요.</p>')
    body.append("<style>.tbl{width:100%;border-collapse:collapse;font-size:13.5px;min-width:620px}.tbl th,.tbl td{border-bottom:1px solid var(--line,#ddd);"
                "padding:8px 6px;text-align:left;white-space:nowrap}.tbl th{font-size:12.5px;color:var(--muted,#666)}.tbl tr.past td{color:#999}</style>")
    desc = f"{now.year}년 국가기술자격(기사·산업기사·기능사·기술사) 원서접수·시험·합격발표 일정을 큐넷 공식 자료로 매일 정리해요."
    return sitegen.page("certs.html", f"{now.year} 국가자격 시험일정 (기사·기능사)", desc, "\n".join(body))


def run(key):
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text("utf-8"))
        except ValueError:
            old = {}
    rows = old.get("rows") or []
    if key and old.get("fetched") != today:
        try:
            new = fetch(key, now)
            if new:
                rows = new
                OUT.write_text(json.dumps({"updated": now.isoformat(timespec="seconds"), "fetched": today, "rows": rows},
                                          ensure_ascii=False, indent=1), "utf-8")
                print(f"qnet.json 갱신: 시험 회차 {len(rows)}건")
            else:
                print("큐넷 시험일정을 받지 못해 기존 파일을 유지합니다. (공공데이터포털에서 15074408 활용신청 여부 확인)")
        except Exception as e:
            print("큐넷 시험일정 오류(무시하고 계속):", e)
    page = certs_html(rows, now)
    f = ROOT / "certs.html"
    if not f.exists() or f.read_text("utf-8") != page:
        f.write_text(page, "utf-8")


if __name__ == "__main__":
    import os
    run(os.environ.get("ALIO_KEY", "").strip())
