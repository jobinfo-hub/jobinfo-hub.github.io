"""Replace institution homepage hash links with existing static job detail links.

Only rewrite href values when the corresponding jobs/aNNN.html file exists.
Safe to rerun; leaves unmatched links untouched.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r'href="\./#job=(a[0-9]+)"')


DIRECT = re.compile(r'href="jobs/(a[0-9]+)\.html"')


def main():
    changed_pages = 0
    replaced_links = 0
    unmatched = set()
    total_pages = 0
    direct_links = 0
    remaining_hash_links = 0
    broken_direct_links = set()
    for page in sorted(ROOT.glob("org-*.html")):
        total_pages += 1
        source = page.read_text(encoding="utf-8")
        count = [0]

        def replace(match):
            job_id = match.group(1)
            if not (ROOT / "jobs" / (job_id + ".html")).is_file():
                unmatched.add(job_id)
                return match.group(0)
            count[0] += 1
            return 'href="jobs/' + job_id + '.html"'

        updated = PATTERN.sub(replace, source)
        if updated != source:
            page.write_text(updated, encoding="utf-8")
            changed_pages += 1
            replaced_links += count[0]
        direct_links += len(DIRECT.findall(updated))
        remaining_hash_links += len(PATTERN.findall(updated))
        for job_id in DIRECT.findall(updated):
            if not (ROOT / "jobs" / (job_id + ".html")).is_file():
                broken_direct_links.add(job_id)
    print(f"Institution link audit: {total_pages} pages; {changed_pages} changed; {replaced_links} links repaired; {direct_links} direct job links; {remaining_hash_links} remaining hash links; {len(unmatched)} missing job pages; {len(broken_direct_links)} broken direct links")
    if broken_direct_links:
        raise SystemExit(f"Broken institution direct links: {sorted(broken_direct_links)[:10]}")


if __name__ == "__main__":
    main()
