#!/usr/bin/env python3
"""Offline regression tests for CareerPick snapshot freshness checks."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import check_api_freshness as checker


class SnapshotFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch.object(checker, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def save(self, filename, data):
        (self.root / filename).write_text(json.dumps(data), encoding="utf-8")

    def test_recent_alio_snapshot_passes(self):
        stamp = datetime.now(checker.KST).isoformat()
        self.save("alio.json", {"updated": stamp, "posts": [{"id": "a1"}]})
        self.assertTrue(checker.check_snapshot("alio.json", "updated", 48).startswith("PASS"))

    def test_old_alio_snapshot_fails(self):
        stamp = (datetime.now(checker.KST) - timedelta(hours=49)).isoformat()
        self.save("alio.json", {"updated": stamp, "posts": [{"id": "a1"}]})
        self.assertIn("stale", checker.check_snapshot("alio.json", "updated", 48))

    def test_qnet_date_snapshot_passes(self):
        stamp = datetime.now(checker.KST).date().isoformat()
        self.save("qnet.json", {"fetched": stamp, "rows": [{"kind": "T"}]})
        self.assertTrue(checker.check_snapshot("qnet.json", "fetched", 72).startswith("PASS"))

    def test_empty_records_fail(self):
        self.save("alio.json", {"updated": datetime.now(checker.KST).isoformat(), "posts": []})
        self.assertIn("empty", checker.check_snapshot("alio.json", "updated", 48))

    def test_missing_snapshot_fails(self):
        self.assertIn("missing", checker.check_snapshot("alio.json", "updated", 48))


if __name__ == "__main__":
    unittest.main()
