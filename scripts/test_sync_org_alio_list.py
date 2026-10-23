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
    print("Institution ALIO list regression PASS: idempotent rebuild, expired removal, heading cleanup")

if __name__ == "__main__":
    main()
