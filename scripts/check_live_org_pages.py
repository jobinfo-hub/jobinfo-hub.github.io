"""Verify public GitHub Pages content after deployment, with bounded retries."""
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://jobinfo-hub.github.io/"
PATH = "org-대한적십자사.html"
URL = BASE + quote(PATH)
MARKERS = ("careerpick-alio-list:start", "data-alio-current=", "jobs/a")

def main():
    for attempt in range(1, 9):
        try:
            request = Request(URL, headers={"User-Agent": "CareerPick-deployment-smoke-test/1.0", "Cache-Control": "no-cache"})
            with urlopen(request, timeout=15) as response:
                html = response.read().decode("utf-8")
                if response.status == 200 and all(marker in html for marker in MARKERS):
                    print(f"Live Pages smoke test PASS: {URL}, attempt {attempt}")
                    return
                print(f"Attempt {attempt}: page available but expected institution ALIO list not yet visible")
        except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
            print(f"Attempt {attempt}: {exc}")
        if attempt < 8:
            time.sleep(15)
    sys.exit("Live Pages smoke test FAILED: deployed site did not show the ALIO list")

if __name__ == "__main__":
    main()
