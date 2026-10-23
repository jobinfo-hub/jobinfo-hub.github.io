"""Offline regression checks for the public Pages smoke test.

No network access required: exercises the exact public-page verifier with
mocked HTTP responses and validates success, retry, and failure behavior.
"""
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError
import check_live_org_pages as checker

class Response:
    status = 200
    def __init__(self, body):
        self.body = body.encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.body

def run():
    good = Response('<html><!-- careerpick-alio-list:start --><details data-alio-current="true"><a href="jobs/a306139.html">job</a></details></html>')
    with patch.object(checker, "urlopen", return_value=good) as fetch:
        checker.main()
        assert fetch.call_count == 1
    with patch.object(checker, "urlopen", side_effect=[URLError("transient"), good]) as fetch, patch.object(checker.time, "sleep") as sleep:
        checker.main()
        assert fetch.call_count == 2 and sleep.call_count == 1
    with patch.object(checker, "urlopen", return_value=Response("<html>stale</html>")) as fetch, patch.object(checker.time, "sleep"):
        try:
            checker.main()
            raise AssertionError("Stale public page must fail")
        except SystemExit:
            pass
        assert fetch.call_count == 8
    print("Public Pages smoke test regression PASS: success, transient retry, stale-site failure")

if __name__ == "__main__":
    run()
