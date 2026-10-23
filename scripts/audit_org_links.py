#!/usr/bin/env python3
"""Read-only check of ALIO job links in generated organization pages."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
JOB_ID = re.compile(r"a[0-9]+")
HREF = re.compile(r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\']', re.I)


def check_page(page, root=ROOT):
    errors = []
    for href in HREF.findall(page.read_text(encoding="utf-8")):
        link = urlsplit(href)
        if link.scheme or link.netloc:
            continue
        fragment = unquote(link.fragment)
        if fragment.startswith("job="):
            job_id = fragment[4:]
            if JOB_ID.fullmatch(job_id):
                errors.append(f"{page.name}: ALIO job {job_id} uses homepage hash instead of static detail page")
        path = unquote(link.path)
        normalized = path.removeprefix("./")
        if normalized.startswith("jobs/") and JOB_ID.fullmatch(Path(normalized).stem) and normalized.endswith(".html"):
            if not (root / normalized).is_file():
                errors.append(f"{page.name}: missing static job detail {path}")
    return errors


def main():
    pages = sorted(ROOT.glob("org-*.html"))
    if not pages:
        print("FAIL: no organization pages found")
        return 1
    errors = []
    for page in pages:
        errors.extend(check_page(page))
    for issue in errors[:30]:
        print("FAIL:", issue)
    print(f"Organization link audit: {len(pages)} pages, {len(errors)} issue(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
