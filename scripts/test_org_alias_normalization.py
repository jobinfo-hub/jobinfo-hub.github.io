"""Check ALIO organization alias suggestions without conflating distinct names."""
from audit_org_alio_coverage import normalized_org_name, main
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO
import json

def main():
    examples = {
        " (재)우체국물류지원단 ": "우체국물류지원단",
        "한전KPS(주)": "한전KPS",
        "(주)강원랜드": "강원랜드",
        "㈜코레일테크": "코레일테크",
        "한국남부발전(주)": "한국남부발전",
        "국민건강보험공단 일산병원": "국민건강보험공단일산병원",
    }
    for name, expected in examples.items():
        actual = normalized_org_name(name)
        assert actual == expected, (name, actual, expected)
    assert normalized_org_name("한국수력원자력") != normalized_org_name("한국남부발전")
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "jobs").mkdir()
        for org in ("시험기관", "(주)시험기관"):
            (root / ("org-" + org + ".html")).write_text("<main></main>", encoding="utf-8")
        (root / "jobs" / "a123.html").write_text("<html></html>", encoding="utf-8")
        (root / "jobs" / "a124.html").write_text("<html></html>", encoding="utf-8")
        (root / "alio.json").write_text(json.dumps({"posts": [
            {"alio": True, "id": "a123", "org": "시험기관", "due": "2099-10-28T23:59:00+09:00"},
            {"alio": True, "id": "a124", "org": "㈜시험기관", "due": "2099-10-28T23:59:00+09:00"},
        ]}, ensure_ascii=False), encoding="utf-8")
        output = StringIO()
        with patch("audit_org_alio_coverage.ROOT", root), redirect_stdout(output):
            main()
        assert "1 ambiguous (1 jobs)" in output.getvalue(), output.getvalue()
        assert "1 active jobs in ALIO snapshot" in output.getvalue(), output.getvalue()
    print("ALIO institution name normalization and resolution PASS")

if __name__ == "__main__":
    main()
