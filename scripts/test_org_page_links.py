#!/usr/bin/env python3
"""Offline regression: organization cards must link to static ALIO detail pages."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orgs


def main():
    now = datetime(2026, 10, 24, tzinfo=timezone(timedelta(hours=9)))
    post = {
        "id": "a123456",
        "title": "채용 <script>alert(1)</script>",
        "n": 3,
        "emp": ["정규직"],
        "due": "2099-12-31T23:59:00+09:00",
    }
    page = orgs.org_page("테스트기관", [], None, None, [post], [], None, now)
    assert 'href="./jobs/a123456.html"' in page, "static detail link missing"
    assert './#job=a123456' not in page, "legacy dynamic link remains"
    assert "<script>alert(1)</script>" not in page, "unescaped job title"
    assert "&lt;script&gt;" in page, "job title should remain visible as escaped text"
    print("Organization static detail link regression: PASS")


if __name__ == "__main__":
    main()
