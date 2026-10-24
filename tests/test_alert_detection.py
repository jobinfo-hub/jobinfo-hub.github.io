"""Regression tests for ALIO alert detection, using isolated temporary fixtures."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "detect_new_job_alerts.py"
KST = ZoneInfo("Asia/Seoul")

class AlertDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "scripts").mkdir()
        (root / "scripts" / SOURCE.name).write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
        self.root = root
        self.report = root / "report.json"

    def run_detector(self, posts):
        (self.root / "alio.json").write_text(json.dumps({"posts": posts}), encoding="utf-8")
        env = dict(os.environ, CP_UPDATE_ALERT_STATE="1", CP_ALERT_REPORT=str(self.report))
        subprocess.run([sys.executable, str(self.root / "scripts" / SOURCE.name)], env=env, check=True, capture_output=True)
        return json.loads(self.report.read_text(encoding="utf-8"))

    def job(self, job_id, due):
        return {"id": job_id, "type": "j", "alio": True, "org": "테스트 기관",
                "title": "테스트 채용", "due": due.isoformat(), "region": "서울"}

    def test_first_run_does_not_mass_alert_existing_jobs(self):
        due = datetime.now(KST) + timedelta(days=5)
        result = self.run_detector([self.job("1", due)])
        self.assertTrue(result["initial_run"])
        self.assertEqual(result["new_count"], 0)

    def test_only_new_jobs_alert_once(self):
        due = datetime.now(KST) + timedelta(days=5)
        a, b = self.job("1", due), self.job("2", due)
        self.run_detector([a])
        self.assertEqual(self.run_detector([a, b])["new_count"], 1)
        self.assertEqual(self.run_detector([a, b])["new_count"], 0)

    def test_deadline_d1_alert_only_once(self):
        tomorrow = datetime.now(KST).date() + timedelta(days=1)
        due = datetime.combine(tomorrow, datetime.min.time(), tzinfo=KST) + timedelta(hours=23)
        a = self.job("1", due)
        self.assertEqual(self.run_detector([a])["deadline_d1_count"], 1)
        self.assertEqual(self.run_detector([a])["deadline_d1_count"], 0)

if __name__ == "__main__":
    unittest.main()
