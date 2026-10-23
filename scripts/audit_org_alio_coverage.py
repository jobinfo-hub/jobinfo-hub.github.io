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
    """Suggest likely page aliases without automatically equating institutions."""
    value = re.sub(r"\s+", "", name)
    value = re.sub(r"^(?:\(재\)|\(주\)|㈜)", "", value)
    value = re.sub(r"(?:\(주\)|㈜)$", "", value)
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
    normalized_pages = defaultdict(list)
    for existing in available_orgs:
        normalized_pages[normalized_org_name(existing)].append(existing)
    # Match exactly first; use a normalized alias only when it is unambiguous.
    resolved = defaultdict(set)
    aliased = []
    ambiguous = []
    unresolved = []
    for org, ids in latest.items():
        if org in available_orgs:
            resolved[org].update(ids)
            continue
        candidates = sorted(normalized_pages.get(normalized_org_name(org), []))
        if len(candidates) == 1:
            resolved[candidates[0]].update(ids)
            aliased.append((org, candidates[0], len(ids)))
        elif len(candidates) > 1:
            ambiguous.append((org, len(ids), candidates))
        else:
            unresolved.append((org, len(ids)))
    print(f"ALIO institution resolution: {len(aliased)} safe aliases ({sum(x[2] for x in aliased)} jobs); {len(ambiguous)} ambiguous ({sum(x[1] for x in ambiguous)} jobs); {len(unresolved)} without pages ({sum(x[1] for x in unresolved)} jobs)")
    for org, page, count in sorted(aliased, key=lambda item: (-item[2], item[0]))[:30]:
        print(f"SAFE ALIO PAGE ALIAS: {org} -> {page}: {count} active jobs")
    for org, count, pages in sorted(ambiguous, key=lambda item: (-item[1], item[0]))[:30]:
        print(f"AMBIGUOUS ALIO INSTITUTION: {org}: {count} active jobs; candidate pages: {', '.join(pages)}")
    for org, count in sorted(unresolved, key=lambda item: (-item[1], item[0]))[:30]:
        print(f"ALIO INSTITUTION WITHOUT PAGE: {org}: {count} active jobs")
    matched = 0
    missing = []
    total = 0
    for page in sorted(ROOT.glob("org-*.html")):
        org = page.stem[4:]
        expected = resolved.get(org, set())
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
