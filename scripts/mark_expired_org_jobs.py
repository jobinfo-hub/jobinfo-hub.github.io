"""Mark expired institution listings based on static JobPosting deadlines.

This is a snapshot-based label, not a real-time verification of official status.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
JOB_LINK = re.compile(r'<a href="jobs/(a[0-9]+)\.html"([^>]*)>')
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ACTIVE = re.compile(r'(<h2>📢 지금 모집 중</h2><div class="olist">)(.*?)(</div>)', re.S)
COUNT = re.compile(r'지금 모집 중인 공고가 <b>\d+건</b> 있어요')

def expired(job_id, now):
    path = ROOT / "jobs" / (job_id + ".html")
    if not path.is_file():
        return False
    match = LD.search(path.read_text(encoding="utf-8"))
    if not match:
        return False
    try:
        end = json.loads(match.group(1)).get("validThrough")
        dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return dt.tzinfo is not None and dt.astimezone(KST) < now
    except (ValueError, TypeError, AttributeError):
        return False

def main():
    now = datetime.now(KST)
    pages = 0
    labels = 0
    for page in sorted(ROOT.glob("org-*.html")):
        source = page.read_text(encoding="utf-8")
        match = ACTIVE.search(source)
        if not match:
            continue
        ids = JOB_LINK.findall(match.group(2))
        stale = {job_id for job_id, _ in ids if expired(job_id, now)}
        if not stale:
            continue
        # Keep links accessible and clearly label snapshot-expired entries.
        def annotate(link):
            job_id, attrs = link.group(1), link.group(2)
            if job_id not in stale or 'data-deadline-expired=' in attrs:
                return link.group(0)
            return f'<a href="jobs/{job_id}.html" data-deadline-expired="true" style="opacity:.7">'
        section = JOB_LINK.sub(annotate, match.group(2))
        for job_id in stale:
            section = re.sub(
                rf'(<a href="jobs/{job_id}\.html" data-deadline-expired="true"[^>]*>)(?!<span class="pill">마감일 경과)',
                r'\1<span class="pill">마감일 경과 · 원문 확인</span> ',
                section,
            )
        updated = source[:match.start(2)] + section + source[match.end(2):]
        updated = COUNT.sub(
            f'수록된 모집 공고 중 <b>{len(stale)}건</b>은 저장된 마감일이 지났어요',
            updated, count=1,
        )
        if updated != source:
            page.write_text(updated, encoding="utf-8")
            pages += 1
            labels += len(stale)
    print(f"Institution expired deadline labels (KST {now.date()}): {pages} pages, {labels} expired listings marked")

if __name__ == "__main__":
    main()
