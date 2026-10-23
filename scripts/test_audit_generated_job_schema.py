"""Offline tests for generated job schema audit."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from audit_generated_job_schema import audit
from build_job_pages import render

def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "jobs").mkdir()
        posts = [
            {"id": "a123", "title": "채용 안내", "org": "시험기관", "due": "2099-10-28", "alio": True},
            {"id": "a124", "title": "마감 공고", "org": "시험기관", "due": "2020-01-01", "alio": True},
        ]
        (root / "alio.json").write_text(json.dumps({"posts": posts}, ensure_ascii=False), encoding="utf-8")
        for post in posts:
            (root / "jobs" / (post["id"] + ".html")).write_text(render(post, {}), encoding="utf-8")
        assert audit(root) == 2
        page = root / "jobs" / "a123.html"
        page.write_text(page.read_text(encoding="utf-8").replace('"name": "시험기관"', '"name": "다른기관"'), encoding="utf-8")
        try:
            audit(root)
        except SystemExit:
            pass
        else:
            raise AssertionError("Schema mismatch must fail audit")
    print("Generated JobPosting audit regression PASS")

if __name__ == "__main__":
    main()
