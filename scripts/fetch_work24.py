"""Fetch Work24 recruitment listings and common codes without exposing API keys.

Output is separate from ALIO and never changes existing Threads, jobs or sitemap.
"""
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work24.json"
CODES = ROOT / "work24-codes.json"
BASE = "https://www.work24.go.kr/cm/openApi/call/wk/"
LIST = BASE + "callOpenApiSvcInfo210L01.do"
COMMON = BASE + "callOpenApiSvcInfo21L01.do"


def request_xml(endpoint, params):
    url = endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(5_000_001)
    except Exception as exc:
        # Never print the URL: it contains the secret.
        raise RuntimeError("Work24 API request failed (credentials redacted)") from None
    if len(data) > 5_000_000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsafe or oversized XML response")
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise ValueError("Invalid Work24 XML response") from None


def field(element, name):
    return (element.findtext(name) or "").strip()


def safe_link(value):
    parsed = urlsplit(value)
    return value if parsed.scheme == "https" and parsed.hostname and (
        parsed.hostname == "work24.go.kr" or parsed.hostname.endswith(".work24.go.kr")
        or parsed.hostname == "work.go.kr" or parsed.hostname.endswith(".work.go.kr")
    ) else ""


def normalize(root):
    if root.tag != "wantedRoot":
        raise ValueError("Unexpected Work24 recruitment response")
    result = []
    for node in root.findall("wanted"):
        number = field(node, "wantedAuthNo")
        title = field(node, "title")
        company = field(node, "company")
        if not number or not title or not company:
            continue
        close = field(node, "closeDt")
        if re.fullmatch(r"\d{8}", close):
            close = f"{close[:4]}-{close[4:6]}-{close[6:]}"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", close) and close < date.today().isoformat():
            continue
        result.append({
            "id": number, "title": title, "company": company,
            "region": field(node, "region"), "occupation_code": field(node, "jobsCd"),
            "salary": field(node, "sal"), "career": field(node, "career"),
            "employment_code": field(node, "empTpCd"),
            "posted": field(node, "regDt"), "deadline": close,
            "url": safe_link(field(node, "wantedInfoUrl")),
            "source": "고용24",
        })
    return result


def main():
    key = os.environ.get("WORK24_RECRUITMENT_KEY", "").strip()
    if not key:
        raise SystemExit("WORK24_RECRUITMENT_KEY is not configured")
    pages = max(1, min(int(os.environ.get("WORK24_PAGES", "2")), 5))
    seen = {}
    for page in range(1, pages + 1):
        root = request_xml(LIST, {
            "authKey": key, "callTp": "L", "returnType": "XML",
            "startPage": page, "display": 100, "sortOrderBy": "DESC",
        })
        records = normalize(root)
        for record in records:
            seen[record["id"]] = record
        if not root.findall("wanted"):
            break
    if not seen:
        raise RuntimeError("No valid recruitment records; retaining previous output")
    output = {"source": "고용24", "updated_at": datetime.now(timezone.utc).isoformat(),
              "count": len(seen), "posts": list(seen.values())}
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Work24 recruitment records:", len(seen))

    code_key = os.environ.get("WORK24_COMMON_KEY", "").strip()
    if code_key:
        # Region and occupation code lookup. Keep raw XML-derived entries isolated.
        groups = {}
        for category in (1, 2):
            root = request_xml(COMMON, {
                "authKey": code_key, "returnType": "XML",
                "target": "CMCD", "dtlGb": category,
            })
            if root.tag != "cmcdInd":
                raise ValueError("Unexpected Work24 common-code response")
            groups[str(category)] = [
                {child.tag: (child.text or "").strip() for child in node}
                for node in root if node.tag not in ("total", "codeName")
                for child_node in [node]
                if len(child_node)
            ][:5000]
        CODES.write_text(json.dumps({"source": "고용24", "codes": groups}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Work24 common code categories:", len(groups))


if __name__ == "__main__":
    main()
