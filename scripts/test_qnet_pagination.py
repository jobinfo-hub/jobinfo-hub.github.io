#!/usr/bin/env python3
"""Offline regression for incomplete QNet pagination."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qnet


def test_complete():
    with patch.object(qnet, "ask", return_value=([{"implSeq": "1"}], 1)):
        assert len(qnet.collect("offline-key", 2026, "T")) == 1


def test_truncated():
    calls = []

    def fake_ask(key, year, gb, page):
        calls.append(page)
        return ([{"implSeq": str(page)}] * 50, 400)

    with patch.object(qnet, "ask", side_effect=fake_ask):
        try:
            qnet.collect("offline-key", 2026, "T")
        except qnet.IncompleteQnetResponse:
            pass
        else:
            raise AssertionError("Truncated QNet results must be rejected")
    assert calls == [1, 2, 3, 4, 5, 6]


def test_first_page_total_is_retained():
    def fake_ask(key, year, gb, page):
        if page == 1:
            return ([{"implSeq": "1"}] * 50, 80)
        return ([{"implSeq": "2"}], None)

    with patch.object(qnet, "ask", side_effect=fake_ask):
        try:
            qnet.collect("offline-key", 2026, "T")
        except qnet.IncompleteQnetResponse:
            pass
        else:
            raise AssertionError("First page totalCount must remain authoritative")


def test_fetch_does_not_silently_fallback():
    with patch.object(qnet, "collect", side_effect=qnet.IncompleteQnetResponse("partial")):
        try:
            qnet.fetch("offline-key", datetime(2026, 10, 24, tzinfo=timezone.utc))
        except qnet.IncompleteQnetResponse:
            pass
        else:
            raise AssertionError("Truncated QNet schedule must not replace the cache")


if __name__ == "__main__":
    test_complete()
    test_truncated()
    test_first_page_total_is_retained()
    test_fetch_does_not_silently_fallback()
    print("QNet pagination protection: PASS")
