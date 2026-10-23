#!/usr/bin/env python3
"""Offline tests for organization page ALIO link auditing."""
import tempfile
from pathlib import Path
from audit_org_links import check_page


def run_case(html, existing=()):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        page = root / "org-example.html"
        page.write_text(html, encoding="utf-8")
        for name in existing:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ok", encoding="utf-8")
        return check_page(page, root)


def main():
    assert not run_case('<a href="jobs/a123.html">공고</a>', ("jobs/a123.html",))
    assert len(run_case('<a href="jobs/a123.html">공고</a>')) == 1
    assert len(run_case('<a href="./#job=a123">공고</a>')) == 1
    assert len(run_case('<a href="./#job=a%31%32%33">공고</a>')) == 1
    assert not run_case('<a href="https://job.alio.go.kr/post">공식 링크</a>')
    assert not run_case('<a href="jobs/a123.html?from=org">공고</a>', ("jobs/a123.html",))
    assert len(run_case('<a href="./#%6aob=a123">공고</a>')) == 1
    assert len(run_case('<a href="./jobs/a123.html">공고</a>')) == 1
    assert not run_case('<a href="./jobs/a123.html">공고</a>', ("jobs/a123.html",))
    print("Organization link audit offline tests: PASS")


if __name__ == "__main__":
    main()
