#!/usr/bin/env python3
"""Offline API transport and secret redaction regression checks."""
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote_plus
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alio
import qnet


def main():
    for name, endpoints in (("ALIO", alio.ENDPOINTS), ("QNet", qnet.ENDPOINTS)):
        assert endpoints and all(url.startswith("https://") for url in endpoints), (
            f"{name}: API credentials must never be sent over plaintext HTTP"
        )

    key = "offline+secret/42"
    url = f"https://apis.data.go.kr/example?serviceKey={quote_plus(key)}"
    with patch.object(alio.urllib.request, "urlopen", side_effect=RuntimeError(url)):
        try:
            alio.call(key, 1)
        except RuntimeError as exc:
            message = str(exc)
            assert key not in message, "ALIO raw key leaked in error"
            assert quote_plus(key) not in message, "ALIO URL-encoded key leaked in error"
            assert "***" in message, "ALIO redaction marker missing"
        else:
            raise AssertionError("Mocked ALIO request should fail")
    print("API HTTPS and credential redaction: PASS")


if __name__ == "__main__":
    main()
