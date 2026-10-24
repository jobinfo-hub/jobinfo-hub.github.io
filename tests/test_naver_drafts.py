"""Regression checks for conservative Naver draft generator."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scripts.generate_naver_drafts as generator

class DraftTests(unittest.TestCase):
    def test_exact_deadline_and_kst_boundaries(self):
        from datetime import datetime, timezone
        now = datetime.fromisoformat("2026-10-24T09:00:00+00:00")
        for due in ["2026-10-24T18:00:00+09:00", "2026-10-24T17:59:00+09:00", "2026-10-23"]:
            self.assertEqual(generator.eligibility({"due":due}, now), "expired")
        self.assertEqual(generator.eligibility({"due":"2026-10-24T18:01:00+09:00"}, now), "eligible")
        self.assertEqual(generator.eligibility({"due":"2026-10-25", "expired":True}, now), "expired")
        self.assertEqual(generator.eligibility({"due":"bad"}, now), "deadline_unknown")

    def test_plain(self):
        self.assertEqual(generator.plain(["사무", "기술"]), "사무, 기술")
        self.assertEqual(generator.plain(None), "")

    def test_deduplicates_and_cleans_stale_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "naver-drafts"
            out.mkdir()
            (out / "stale.md").write_text("old", encoding="utf-8")
            job = {"id":"a200","alio":True,"title":"중복 시험","org":"기관",
                   "url":"https://example.org/job","due":"2099-01-01T00:00:00+09:00"}
            (root / "alio.json").write_text(json.dumps({"posts":[job,job]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", out):
                generator.main()
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 1)
            self.assertFalse((out / "stale.md").exists())

    def test_faq_uses_only_source_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = {"id":"a500","alio":True,"title":"FAQ 테스트","org":"테스트기관",
                   "url":"https://example.org/job","due":"2099-01-01T00:00:00+09:00",
                   "region":"서울","n":"3명","edu":"학력무관"}
            (root / "alio.json").write_text(json.dumps({"posts":[job]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            article = (root / "naver-drafts" / "a500.md").read_text(encoding="utf-8")
            self.assertIn("수집된 근무지역: **서울**", article)
            self.assertIn("수집된 인원: **3명**", article)
            self.assertIn("현재 수집 정보만으로 확정할 수 없습니다", article)
            self.assertIn("발행 전 검수 체크리스트", article)

    def test_unverified_deadline_time_is_labeled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = {"id":"a400", "alio":True, "title":"시각 미확인", "org":"기관",
                   "url":"https://example.org/job", "due":"2099-01-01T23:59:00+09:00",
                   "dueHasTime":False}
            (root / "alio.json").write_text(json.dumps({"posts":[job]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            text = (root / "naver-drafts" / "a400.md").read_text(encoding="utf-8")
            self.assertIn("마감 시각은 원문 확인 필요", text)

    def test_unknown_deadline_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = {"id": "a300", "alio": True, "title": "미확인 마감", "org": "기관",
                   "url": "https://example.org/job"}
            (root / "alio.json").write_text(json.dumps({"posts": [job]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            result = json.loads((root / "naver-drafts" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result, [])
            self.assertFalse((root / "naver-drafts" / "a300.md").exists())

    def test_sanitized_ids_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = [
                {"id":"job/1","alio":True,"title":"공고A","url":"https://example.org/a","due":"2099-01-01"},
                {"id":"job1","alio":True,"title":"공고B","url":"https://example.org/b","due":"2099-01-01"},
            ]
            (root / "alio.json").write_text(json.dumps({"posts":jobs}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            result = json.loads((root / "naver-drafts" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], "job1")

    def test_generates_all_more_than_eleven(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = [
                {"id":f"all{i}","alio":True,"title":f"공고 {i}","org":"기관",
                 "url":f"https://example.org/{i}","due":"2099-01-01"}
                for i in range(25)
            ]
            (root / "alio.json").write_text(json.dumps({"posts":jobs}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            result = json.loads((root / "naver-drafts" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(result), 25)
            with (root / "naver-drafts" / "review-index.csv").open(encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.DictReader(fp))
            self.assertEqual(len(rows), 25)
            self.assertEqual(rows[0]["검수상태"], "needs_review")

    def test_today_unknown_time_is_held(self):
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = {"id":"today1","alio":True,"title":"오늘 마감","org":"기관",
                   "url":"https://example.org/today","due":today,"dueHasTime":False}
            (root / "alio.json").write_text(json.dumps({"posts":[job]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(generator, "ROOT", root), patch.object(generator, "OUT", root / "naver-drafts"):
                generator.main()
            result = json.loads((root / "naver-drafts" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result, [])

    def test_thumbnail_status_labels(self):
        from scripts.build_naver_review_packs import image_for
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            draft = "# 채용 테스트\n- 모집기관: 기관"
            expired = Path(tmp) / "expired.png"
            unknown = Path(tmp) / "unknown.png"
            image_for(draft, expired, expired=True)
            image_for(draft, unknown, deadline_known=False)
            with Image.open(expired) as img:
                self.assertEqual(img.size, (1080, 1080))
            with Image.open(unknown) as img:
                self.assertEqual(img.size, (1080, 1080))

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
            self.assertFalse((root/"naver-drafts"/"a101.md").exists())
            self.assertEqual(manifest[0]["status"],"needs_review")
            self.assertIn("공식 공고", (root/"naver-drafts"/"a100.md").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
