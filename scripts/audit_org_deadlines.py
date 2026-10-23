"""Audit institution 'currently recruiting' links against job detail deadlines.

Read-only: do not infer official live status from static ALIO snapshots.
"""
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
ACTIVE = re.compile(r'<h2>📢 지금 모집 중</h2>(.*?)(?=<h2>|</div>\s*<h2>)', re.S)
LINK = re.compile(r'href="jobs/(a[0-9]+)\.html"')
JSONLD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

def main():
    pages = 0
    links = 0
    expired = []
    unknown = []
    future = 0
    for page in sorted(ROOT.glob("org-*.html")):
        pages += 1
        html = page.read_text(encoding="utf-8")
        match = ACTIVE.search(html)
        if not match:
            continue
        for job_id in LINK.findall(match.group(1)):
            links += 1
            target = ROOT / "jobs" / (job_id + ".html")
            if not target.is_file():
                unknown.append((page.name, job_id, "missing page"))
                continue
            detail = target.read_text(encoding="utf-8")
            found = JSONLD.search(detail)
            if not found:
                unknown.append((page.name, job_id, "no JSON-LD"))
                continue
            try:
                record = json.loads(unescape(found.group(1)))
                end = record.get("validThrough")
                if not end:
                    unknown.append((page.name, job_id, "no validThrough"))
                    continue
                deadline = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if deadline.tzinfo is None:
                    unknown.append((page.name, job_id, "timezone missing"))
                elif deadline.astimezone(KST) < NOW:
                    expired.append((page.name, job_id, end))
                else:
                    future += 1
            except (ValueError, TypeError, json.JSONDecodeError):
                unknown.append((page.name, job_id, "invalid deadline"))
    print(f"Institution deadline audit (KST {NOW.date()}): {pages} pages, {links} active-section links, {future} future deadlines, {len(expired)} past deadlines, {len(unknown)} unknown")
    for item in expired[:15]:
        print("PAST DEADLINE:", *item)
    for item in unknown[:10]:
        print("UNKNOWN DEADLINE:", *item)
    # Report, rather than fail, because institution HTML is a separate
    # snapshot and deadlines may be extended by the hiring organization.

if __name__ == "__main__":
    main()
