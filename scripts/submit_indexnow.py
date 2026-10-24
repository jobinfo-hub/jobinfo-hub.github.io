"""Notify Bing IndexNow about newly added or changed CareerPick job pages.

Usage: python scripts/submit_indexnow.py [--dry-run]
Only changed jobs/a<digits>.html files from the latest commit are submitted.
IndexNow submission does not guarantee indexing.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "jobinfo-hub.github.io"
KEY = "07c8a6cf68fabf06a287d28a3166a8ff"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"


def changed_job_urls():
    try:
        names = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=AM", "HEAD^", "HEAD"],
            cwd=ROOT, text=True, timeout=20,
        ).splitlines()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return sorted({
        f"https://{HOST}/{name}"
        for name in names
        if re.fullmatch(r"jobs/a[0-9]+\.html", name)
        and (ROOT / name).is_file()
    })


def main():
    key_file = ROOT / (KEY + ".txt")
    if not key_file.is_file() or key_file.read_text(encoding="utf-8").strip() != KEY:
        raise SystemExit("IndexNow ownership key file missing or invalid")
    urls = changed_job_urls()
    print(f"IndexNow changed job URLs: {len(urls)}")
    if not urls:
        return
    payload = {"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION, "urlList": urls}
    if "--dry-run" in sys.argv:
        print(json.dumps(payload, ensure_ascii=False))
        return
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        print("IndexNow response:", response.status)
        if response.status not in (200, 202):
            raise RuntimeError("IndexNow request not accepted")


if __name__ == "__main__":
    main()
