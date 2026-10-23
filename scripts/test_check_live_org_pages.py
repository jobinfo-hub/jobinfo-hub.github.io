"""Offline checks for exact public Pages content verification."""
from unittest.mock import patch
from urllib.error import URLError
from pathlib import Path
from tempfile import TemporaryDirectory
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
    with patch.object(checker, "expected_block", return_value=BLOCK), patch.object(checker, "verify_job_detail") as detail, patch.object(checker, "verify_live_search_files"):
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
    with patch.object(checker, "urlopen", return_value=Response("<html><head><link rel=\"canonical\" href=\"https://jobinfo-hub.github.io/jobs/a306139.html\"></head><body>Job</body></html>")) as fetch:
        checker.verify_job_detail(BLOCK)
        assert fetch.call_count == 1
    with patch.object(checker, "urlopen", return_value=Response("<html><title>Wrong page</title></html>")):
        try:
            checker.verify_job_detail(BLOCK)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Wrong canonical must fail")
    canonical = '<link rel="canonical" href="https://jobinfo-hub.github.io/jobs/a306139.html">'
    valid_schema = '<script type="application/ld+json">{"@type":"JobPosting","url":"https://jobinfo-hub.github.io/jobs/a306139.html"}</script>'
    with patch.object(checker, "urlopen", return_value=Response("<html>" + canonical + valid_schema + "</html>")):
        checker.verify_job_detail(BLOCK)
    wrong_schema = valid_schema.replace("jobs/a306139.html", "jobs/a999.html")
    with patch.object(checker, "urlopen", return_value=Response("<html>" + canonical + wrong_schema + "</html>")):
        try:
            checker.verify_job_detail(BLOCK)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Wrong live JobPosting URL must fail")
    with patch.object(checker, "urlopen", return_value=Response("<html>" + canonical + valid_schema * 2 + "</html>")):
        try:
            checker.verify_job_detail(BLOCK)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Duplicate live JobPosting must fail")
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sitemap.xml").write_bytes(b"<urlset></urlset>")
        (root / "robots.txt").write_bytes(b"User-agent: *\nAllow: /\n")
        with patch.object(checker, "urlopen", side_effect=[
            Response("<urlset></urlset>"), Response("User-agent: *\nAllow: /\n")
        ]) as fetch:
            checker.verify_live_search_files(root)
            assert fetch.call_count == 2
        with patch.object(checker, "urlopen", side_effect=[
            Response("<urlset>stale</urlset>"), Response("User-agent: *\nAllow: /\n")
        ]):
            try:
                checker.verify_live_search_files(root)
            except RuntimeError:
                pass
            else:
                raise AssertionError("Stale public sitemap must fail")
    assert checker.JobLinkParser is not None
    print("Public Pages content equality regression PASS: match, retry, outdated list rejection, job detail")

if __name__ == "__main__":
    run()
