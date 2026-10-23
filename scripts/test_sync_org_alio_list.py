"""Regression-test ALIO institution list generation without touching repository data."""
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sys

import sync_org_alio_list as generator

def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "jobs").mkdir()
        (root / "jobs" / "a123.html").write_text("<html>job</html>", encoding="utf-8")
        future = (datetime.now(generator.KST) + timedelta(days=10)).isoformat()
        (root / "alio.json").write_text(json.dumps({
            "updated": "2026-10-23T12:00:00+09:00",
            "posts": [{"alio": True, "id": "a123", "org": "시험기관", "title": "신입 모집", "due": future}]
        }, ensure_ascii=False), encoding="utf-8")
        page = root / "org-시험기관.html"
        original = "<html><main><h2>📝 최근 공고의 지원 자격</h2></main></html>"
        page.write_text(original, encoding="utf-8")
        with patch.object(generator, "ROOT", root):
            generator.main()
            first = page.read_text(encoding="utf-8")
            assert first.count('data-careerpick-alio-heading="true"') == 1
            assert first.count("jobs/a123.html") == 1
            generator.main()
            second = page.read_text(encoding="utf-8")
            assert second == first, "Daily rebuild must be idempotent"
            data = json.loads((root / "alio.json").read_text(encoding="utf-8"))
            data["posts"][0]["due"] = (datetime.now(generator.KST) - timedelta(days=2)).isoformat()
            (root / "alio.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            generator.main()
            third = page.read_text(encoding="utf-8")
            assert "jobs/a123.html" not in third
            assert 'data-careerpick-alio-heading="true"' not in third
            assert "📝 최근 공고의 지원 자격" in third
            legacy = '<h2>📢 ALIO 수록 모집 공고</h2>\n<!-- careerpick-alio-list:start --><div>old</div><!-- careerpick-alio-list:end -->'
            page.write_text(original.replace('<h2>📝', legacy + '<h2>📝'), encoding="utf-8")
            generator.main()
            migrated = page.read_text(encoding="utf-8")
            assert "📢 ALIO 수록 모집 공고" not in migrated
            assert "careerpick-alio-list:start" not in migrated
            # An ALIO legal suffix must map to the existing institution page.
            data["posts"][0]["org"] = "(주)시험기관"
            data["posts"][0]["due"] = future
            (root / "alio.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            generator.main()
            fourth = page.read_text(encoding="utf-8")
            assert fourth.count("jobs/a123.html") == 1
            generator.main()
            assert page.read_text(encoding="utf-8") == fourth
            # Avoid silently merging if more than one page normalizes to the same name.
            duplicate = root / "org-(주)시험기관.html"
            duplicate.write_text(original, encoding="utf-8")
            data["posts"][0]["org"] = "㈜시험기관"
            (root / "alio.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            generator.main()
            assert "jobs/a123.html" not in page.read_text(encoding="utf-8")
            assert "jobs/a123.html" not in duplicate.read_text(encoding="utf-8")
            # Exact ALIO name must still resolve when alias-normalized pages collide.
            data["posts"][0]["org"] = "시험기관"
            (root / "alio.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            generator.main()
            assert page.read_text(encoding="utf-8").count("jobs/a123.html") == 1
            assert "jobs/a123.html" not in duplicate.read_text(encoding="utf-8")
    print("Institution ALIO list regression PASS: idempotent rebuild, expired removal, heading cleanup")

if __name__ == "__main__":
    main()
