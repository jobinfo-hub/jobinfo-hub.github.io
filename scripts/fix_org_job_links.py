"""Replace institution homepage hash links with existing static job detail links.

Only rewrite href values when the corresponding jobs/aNNN.html file exists.
Safe to rerun; leaves unmatched links untouched.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r'href="\./#job=(a[0-9]+)"')


def main():
    changed_pages = 0
    replaced_links = 0
    unmatched = set()
    for page in sorted(ROOT.glob("org-*.html")):
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
    print(f"Institution links: {changed_pages} pages updated, {replaced_links} links fixed, {len(unmatched)} missing job pages left unchanged")


if __name__ == "__main__":
    main()
