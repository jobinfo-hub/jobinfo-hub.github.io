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
    # Verify the minimum crawlability and publisher trust signals without network calls.
    robots = ROOT / "robots.txt"
    sitemap = ROOT / "sitemap.xml"
    ads = ROOT / "ads.txt"
    checks.update({
        "Robots file present": robots.is_file(),
        "Sitemap present": sitemap.is_file(),
        "About page present": (ROOT / "about.html").is_file(),
        "Privacy policy present": (ROOT / "privacy.html").is_file(),
        "Contact page present": (ROOT / "contact.html").is_file(),
        "Ads publisher declaration present": ads.is_file(),
    })
    if robots.is_file():
        robots_text = robots.read_text(encoding="utf-8")
        checks["Robots sitemap declaration"] = "https://jobinfo-hub.github.io/sitemap.xml" in robots_text
    if sitemap.is_file():
        import xml.etree.ElementTree as ET
        try:
            root = ET.parse(sitemap).getroot()
            checks["Sitemap valid XML"] = root.tag.endswith("urlset")
        except ET.ParseError:
            checks["Sitemap valid XML"] = False
    if sitemap.is_file():
        from urllib.parse import urlsplit, unquote
        try:
            sitemap_root = ET.parse(sitemap).getroot()
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            entries = sitemap_root.findall("sm:url", ns)
            locs = [e.findtext("sm:loc", default="", namespaces=ns).strip() for e in entries]
            checks["Sitemap has URLs"] = bool(locs)
            checks["Sitemap URLs unique"] = len(locs) == len(set(locs))
            checks["Sitemap URLs use site HTTPS origin"] = all(
                urlsplit(loc).scheme == "https"
                and urlsplit(loc).netloc == "jobinfo-hub.github.io"
                and not urlsplit(loc).query and not urlsplit(loc).fragment
                for loc in locs
            )
            checks["Sitemap paths exist locally"] = all(
                (ROOT / unquote(urlsplit(loc).path).lstrip("/")).is_file()
                if urlsplit(loc).path not in ("", "/") else INDEX.is_file()
                for loc in locs
            )
        except (ET.ParseError, ValueError):
            checks["Sitemap URLs unique"] = False
            checks["Sitemap paths exist locally"] = False
    if ads.is_file():
        publishers = set(re.findall(r"ca-pub-(\d+)", html))
        ads_text = ads.read_text(encoding="utf-8")
        checks["Ads publisher ID consistent"] = (
            len(publishers) == 1
            and f"google.com, pub-{next(iter(publishers))}, DIRECT" in ads_text
        )
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
