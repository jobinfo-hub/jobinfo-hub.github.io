"""Offline checks for exact public Pages content verification."""
from unittest.mock import patch
from urllib.error import URLError
import check_live_org_pages as checker

BLOCK = '<!-- careerpick-alio-list:start --><details data-alio-current="true"><a href="jobs/a306139.html">job</a></details><!-- careerpick-alio-list:end -->'

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
    assert checker.alio_block("<html>" + BLOCK + "</html>") == BLOCK
    assert checker.alio_block("<html>no marker</html>") is None
    good = Response("<html>" + BLOCK + "</html>")
    with patch.object(checker, "expected_block", return_value=BLOCK), patch.object(checker, "verify_job_detail") as detail:
        with patch.object(checker, "urlopen", return_value=good) as fetch:
            checker.main()
            assert fetch.call_count == 1 and detail.call_count == 1
        with patch.object(checker, "urlopen", side_effect=[URLError("transient"), good]) as fetch, patch.object(checker.time, "sleep") as sleep:
            checker.main()
            assert fetch.call_count == 2 and sleep.call_count == 1
        old = Response("<html>" + BLOCK.replace("jobs/a306139.html", "jobs/a111111.html") + "</html>")
        with patch.object(checker, "urlopen", return_value=old) as fetch, patch.object(checker.time, "sleep"):
            try:
                checker.main()
                raise AssertionError("Outdated public list must fail")
            except SystemExit:
                pass
            assert fetch.call_count == 8
    with patch.object(checker, "urlopen", return_value=Response("<html><title>Job</title></html>")) as fetch:
        checker.verify_job_detail(BLOCK)
        assert fetch.call_count == 1
    assert checker.JobLinkParser is not None
    print("Public Pages content equality regression PASS: match, retry, outdated list rejection, job detail")

if __name__ == "__main__":
    run()
