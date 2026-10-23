"""Regression-test source-link classification for suspected duplicate jobs."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import build_job_pages as builder

def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        posts = [
            {"id": "a111", "title": "채용", "org": "기관", "due": "2099-10-28", "alio": True, "src": "https://example.org/a"},
            {"id": "a112", "title": "채용", "org": "기관", "due": "2099-10-28", "alio": True, "src": "https://example.org/b"},
            {"id": "a113", "title": "다른 채용", "org": "기관", "due": "2099-10-28", "alio": True, "src": "https://example.org/c"},
        ]
        (root / "alio.json").write_text(json.dumps({"posts": posts}, ensure_ascii=False), encoding="utf-8")
        with patch.object(builder, "ROOT", root), patch.object(builder, "DATA", root / "alio.json"), patch.object(builder, "DETAIL", root / "missing.json"), patch.object(builder, "OUT", root / "jobs"):
            builder.main()
        report = json.loads((root / "job-quality-report.json").read_text(encoding="utf-8"))
        groups = report["suspected_duplicates"]
        assert len(groups) == 1, groups
        assert groups[0]["ids"] == ["a111", "a112"]
        assert groups[0]["distinct_official_link_count"] == 2
        assert groups[0]["source_link_comparison"] == "different_official_links_review_separately"
        assert report["summary"]["duplicate_groups_with_distinct_official_links"] == 1
    print("Suspected duplicate official-link classification PASS")

if __name__ == "__main__":
    main()
