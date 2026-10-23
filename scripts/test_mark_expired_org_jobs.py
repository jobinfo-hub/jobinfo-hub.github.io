"""Offline regression test for expired institution listing labels."""
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import mark_expired_org_jobs as module

def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "jobs").mkdir()
        html = ('<h2>🗓 다음 공고 예상</h2>'
                '<div class="box">지금 모집 중인 공고가 <b>2건</b> 있어요.</div>'
                '<h2>📢 지금 모집 중</h2><div class="olist">'
                '<a href="jobs/a100.html"><span class="pill">공식</span>마감 공고</a>'
                '<a href="jobs/a200.html"><span class="pill">공식</span>진행 공고</a>'
                '</div><h2>📝 최근 공고의 지원 자격</h2>')
        page = root / "org-test.html"
        page.write_text(html, encoding="utf-8")
        for job_id, deadline in [("a100", "2020-01-01T00:00:00+09:00"), ("a200", "2099-01-01T00:00:00+09:00")]:
            (root / "jobs" / (job_id + ".html")).write_text(
                '<script type="application/ld+json">' +
                json.dumps({"@type": "JobPosting", "validThrough": deadline}) +
                '</script>', encoding="utf-8")
        with patch.object(module, "ROOT", root):
            module.main()
            first = page.read_text(encoding="utf-8")
            assert 'href="jobs/a100.html" data-deadline-expired="true"' in first
            assert first.count('마감일 경과 · 원문 확인') == 1
            assert 'href="jobs/a200.html" data-deadline-expired=' not in first
            module.main()
            second = page.read_text(encoding="utf-8")
            assert first == second, "Running twice must not modify the page again"
        print("Institution expired-label regression PASS: expired marked, future retained, idempotent")

if __name__ == "__main__":
    main()
