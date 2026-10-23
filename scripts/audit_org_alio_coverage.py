"""Audit whether institution active listings reflect current ALIO data.

Read-only coverage check. An ALIO snapshot and institution HTML can be generated separately;
report coverage rather than silently editing institution statistics.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
ACTIVE = re.compile(r'<h2>📢 지금 모집 중</h2><div class="olist">(.*?)</div>', re.S)
LINK = re.compile(r'href="jobs/(a[0-9]+)\.html"')

FULL = re.compile(r'<!-- careerpick-alio-list:start -->(.*?)<!-- careerpick-alio-list:end -->', re.S)

def normalized_org_name(name):
    """For audit suggestions only; never automatically merge different entities."""
    value = re.sub(r"\\s+", "", name)
    value = re.sub(r"^\\(재\\)|^\\(주\\)|^㈜", "", value)
    value = re.sub(r"\\(주\\)$|㈜$", "", value)
    return value

def main():
    data = json.loads((ROOT / "alio.json").read_text(encoding="utf-8"))
    latest = defaultdict(set)
    for post in data.get("posts", []):
        if not isinstance(post, dict) or not post.get("alio"):
            continue
        job_id = str(post.get("id", ""))
        org = str(post.get("org", "")).strip()
        due = str(post.get("due", ""))
        try:
            deadline = datetime.fromisoformat(due.replace("Z", "+00:00"))
        except ValueError:
            continue
        if job_id.startswith("a") and org and deadline.tzinfo and deadline.astimezone(KST) >= NOW:
            if (ROOT / "jobs" / (job_id + ".html")).is_file():
                latest[org].add(job_id)
    available_orgs = {page.stem[4:] for page in ROOT.glob("org-*.html")}
    unmatched = [(org, len(ids)) for org, ids in latest.items() if org not in available_orgs]
    print(f"ALIO institutions without matching HTML page: {len(unmatched)}; active job records: {sum(count for _, count in unmatched)}")
    normalized_pages = defaultdict(list)
    for existing in available_orgs:
        normalized_pages[normalized_org_name(existing)].append(existing)
    for org, count in sorted(unmatched, key=lambda item: (-item[1], item[0]))[:30]:
        suggestions = sorted(normalized_pages.get(normalized_org_name(org), []))
        suffix = f"; possible existing page(s): {', '.join(suggestions)}" if suggestions else "; no normalized page match"
        print(f"UNMATCHED ALIO INSTITUTION: {org}: {count} active jobs{suffix}")
    matched = 0
    missing = []
    total = 0
    for page in sorted(ROOT.glob("org-*.html")):
        org = page.stem[4:]
        expected = latest.get(org, set())
        if not expected:
            continue
        matched += 1
        html = page.read_text(encoding="utf-8")
        section = ACTIVE.search(html)
        shown = set(LINK.findall(section.group(1))) if section else set()
        complete = FULL.search(html)
        if complete:
            shown.update(LINK.findall(complete.group(1)))
        absent = expected - shown
        total += len(expected)
        if absent:
            missing.append((org, len(absent), sorted(absent)[:5]))
    print(f"Institution ALIO coverage (KST {NOW.date()}): {matched} institutions with active ALIO jobs; {total} active jobs in ALIO snapshot; {sum(item[1] for item in missing)} not listed in institution active or complete ALIO sections; {len(missing)} institutions affected")
    for org, count, ids in sorted(missing, key=lambda item: -item[1])[:15]:
        print(f"ORG COVERAGE GAP: {org}: {count} missing, sample {','.join(ids)}")
    print(f"ALIO snapshot updated: {data.get('updated', 'unknown')}")
    # Informational: org pages have a separate generation pipeline.

if __name__ == "__main__":
    main()
