"""Regression checks for conservative Naver draft generator."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scripts.generate_naver_drafts as generator

class DraftTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(generator.plain(["사무", "기술"]), "사무, 기술")
        self.assertEqual(generator.plain(None), "")

    def test_generation_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alio.json").write_text(json.dumps({"posts":[
                {"id":"a100","alio":True,"title":"테스트 채용","org":"테스트 기관","url":"https://example.org/job","due":"2099-01-01T00:00:00+09:00"},
                {"id":"a101","alio":True,"title":"만료","org":"기관","url":"https://example.org/old","due":"2020-01-01T00:00:00+09:00"}
            ]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            manifest = json.loads((root/"naver-drafts"/"manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest),1)
            self.assertEqual(manifest[0]["status"],"needs_review")
            self.assertIn("공식 공고", (root/"naver-drafts"/"a100.md").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
