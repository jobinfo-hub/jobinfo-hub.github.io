#!/usr/bin/env python3
"""Read-only CareerPick repository regression audit.

Run: python scripts/audit_site.py
No network calls, publication, or production data modification.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
GENERATOR = ROOT / "scripts" / "build_job_pages.py"


def check():
    errors = []
    for file in (INDEX, GENERATOR):
        if not file.is_file():
            errors.append(f"Missing required file: {file.relative_to(ROOT)}")
    if errors:
        return errors

    html = INDEX.read_text(encoding="utf-8")
    script = GENERATOR.read_text(encoding="utf-8")
    checks = {
        "Korean document language": bool(re.search(r'<html[^>]*lang=["\']ko["\']', html)),
        "Responsive viewport": 'name="viewport"' in html,
        "Unique homepage canonical": len(re.findall(r'<link\s+rel="canonical"', html)) == 1,
        "Homepage description": 'name="description"' in html,
        "Accessible primary heading": bool(re.search(r'<h1(?:\s|>)', html)),
        "ALIO detail-page generator": "def render(" in script,
        "Job-page regression tests": "def self_test(" in script,
        "Safe official link validation": "def safe_url(" in script,
        "Job-page inventory": "available.js" in script,
        "Job quality reporting": "job-quality-report.json" in script,
    }
    for name, ok in checks.items():
        print(f'{"PASS" if ok else "FAIL"}: {name}')
        if not ok:
            errors.append(name)
    return errors


if __name__ == "__main__":
    failures = check()
    if failures:
        print(f"Audit failed: {len(failures)} issue(s)", file=sys.stderr)
        sys.exit(1)
    print("CareerPick read-only site audit: PASS")
