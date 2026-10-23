"""Verify that the public Pages institution ALIO block matches this deployment."""
import sys
import re
import json
import time
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
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

class JobLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        if href.startswith("jobs/a") and href.endswith(".html"):
            self.links.append(href)

def verify_job_detail(block):
    parser = JobLinkParser()
    parser.feed(block)
    if not parser.links:
        raise RuntimeError("No static job links found in deployed institution listing")
    url = urljoin(BASE, parser.links[0])
    request = Request(url, headers={"User-Agent": "CareerPick-deployment-smoke-test/1.0", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=15) as response:
        html = response.read().decode("utf-8")
        if response.status != 200 or "<html" not in html.lower() or "</html>" not in html.lower():
            raise RuntimeError(f"Public job detail page missing or invalid: {url}")
    canonical = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
    if not canonical or canonical.group(1) != url:
        raise RuntimeError(f"Public job detail canonical mismatch: {url}")
    # Public JSON-LD must agree with the actual URL. Expired jobs can omit it.
    job_schemas = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise RuntimeError(f"Invalid public JSON-LD: {url}") from exc
        if isinstance(parsed, dict) and parsed.get("@type") == "JobPosting":
            job_schemas.append(parsed)
    if len(job_schemas) > 1:
        raise RuntimeError(f"Duplicate public JobPosting schema: {url}")
    if job_schemas and job_schemas[0].get("url") != url:
        raise RuntimeError(f"Public JobPosting URL mismatch: {url}")
    print(f"Live job detail PASS: {url}")

def verify_live_search_files(root=None):
    """Check deployed sitemap and robots against this exact checkout."""
    root = root or Path(__file__).resolve().parent.parent
    for name in ("sitemap.xml", "robots.txt"):
        local = (root / name).read_bytes()
        request = Request(urljoin(BASE, name), headers={
            "User-Agent": "CareerPick-deployment-smoke-test/1.0",
            "Cache-Control": "no-cache",
        })
        with urlopen(request, timeout=20) as response:
            remote = response.read()
            if response.status != 200 or remote != local:
                raise RuntimeError(f"Public {name} differs from deployment")
        print(f"Live {name} equality PASS")

def main():
    expected = expected_block()
    for attempt in range(1, 9):
        try:
            request = Request(URL, headers={"User-Agent": "CareerPick-deployment-smoke-test/1.0", "Cache-Control": "no-cache"})
            with urlopen(request, timeout=15) as response:
                html = response.read().decode("utf-8")
                if response.status == 200 and alio_block(html) == expected:
                    verify_job_detail(expected)
                    verify_live_search_files()
                    print(f"Live Pages content equality PASS: {URL}, attempt {attempt}")
                    return
                print(f"Attempt {attempt}: live institution ALIO block differs from this deployment")
        except (HTTPError, URLError, TimeoutError, UnicodeError, RuntimeError) as exc:
            print(f"Attempt {attempt}: {exc}")
        if attempt < 8:
            time.sleep(15)
    sys.exit("Live Pages smoke test FAILED: public ALIO list differs from deployed repository")

if __name__ == "__main__":
    main()
