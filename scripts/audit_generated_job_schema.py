"""Audit generated ALIO job pages against source data and structured-data rules."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
import json
import re

from build_job_pages import BASE, parse_date, is_closed

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

def audit(root=ROOT):
    data = json.loads((root / "alio.json").read_text(encoding="utf-8"))
    checked = 0
    active = 0
    closed = 0
    errors = []
    for post in data.get("posts", []):
        if not isinstance(post, dict) or not post.get("alio"):
            continue
        pid = str(post.get("id", ""))
        if not re.fullmatch(r"a[0-9]+", pid):
            continue
        path = root / "jobs" / (pid + ".html")
        if not path.is_file():
            errors.append(f"{pid}: generated HTML missing")
            continue
        checked += 1
        html = path.read_text(encoding="utf-8")
        schemas = []
        for raw in SCHEMA.findall(html):
            try:
                parsed = json.loads(raw)
            except ValueError:
                errors.append(f"{pid}: invalid JSON-LD")
                continue
            if isinstance(parsed, dict) and parsed.get("@type") == "JobPosting":
                schemas.append(parsed)
        if is_closed(post.get("due")):
            closed += 1
            if schemas:
                errors.append(f"{pid}: closed job retains JobPosting")
            continue
        active += 1
        if len(schemas) != 1:
            errors.append(f"{pid}: active job has {len(schemas)} JobPosting schemas")
            continue
        schema = schemas[0]
        expected_url = BASE + "/jobs/" + quote(pid, safe="") + ".html"
        if schema.get("url") != expected_url:
            errors.append(f"{pid}: incorrect canonical schema URL")
        if schema.get("title") != str(post.get("title") or "").strip():
            errors.append(f"{pid}: schema title differs from ALIO")
        org = schema.get("hiringOrganization")
        if not isinstance(org, dict) or org.get("name") != str(post.get("org") or "").strip():
            errors.append(f"{pid}: schema hiring organization differs from ALIO")
        expected_deadline = parse_date(post.get("due"), end_of_day=True)
        if expected_deadline and schema.get("validThrough") != expected_deadline:
            errors.append(f"{pid}: schema deadline differs from ALIO")
        if f'<link rel="canonical" href="{expected_url}"' not in html:
            errors.append(f"{pid}: canonical HTML link missing or incorrect")
    print(f"ALIO generated job schema audit: {checked} checked; {active} active; {closed} closed; {len(errors)} errors")
    for error in errors[:30]:
        print("SCHEMA AUDIT ERROR:", error)
    if errors:
        raise SystemExit(f"Job schema integrity failed: {len(errors)} errors")
    return checked

if __name__ == "__main__":
    audit()
