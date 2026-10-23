"""Verify that the public Pages institution ALIO block matches this deployment."""
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://jobinfo-hub.github.io/"
PATH = "org-대한적십자사.html"
URL = BASE + quote(PATH)
START = "<!-- careerpick-alio-list:start -->"
END = "<!-- careerpick-alio-list:end -->"

def alio_block(html):
    start = html.find(START)
    if start < 0:
        return None
    end = html.find(END, start + len(START))
    if end < 0:
        return None
    return html[start:end + len(END)].strip()

def expected_block():
    local = Path(__file__).resolve().parent.parent / PATH
    block = alio_block(local.read_text(encoding="utf-8"))
    if not block or 'data-alio-current="true"' not in block or "jobs/a" not in block:
        raise RuntimeError(f"Missing expected ALIO block in {local}")
    return block

def main():
    expected = expected_block()
    for attempt in range(1, 9):
        try:
            request = Request(URL, headers={"User-Agent": "CareerPick-deployment-smoke-test/1.0", "Cache-Control": "no-cache"})
            with urlopen(request, timeout=15) as response:
                html = response.read().decode("utf-8")
                if response.status == 200 and alio_block(html) == expected:
                    print(f"Live Pages content equality PASS: {URL}, attempt {attempt}")
                    return
                print(f"Attempt {attempt}: live institution ALIO block differs from this deployment")
        except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
            print(f"Attempt {attempt}: {exc}")
        if attempt < 8:
            time.sleep(15)
    sys.exit("Live Pages smoke test FAILED: public ALIO list differs from deployed repository")

if __name__ == "__main__":
    main()
