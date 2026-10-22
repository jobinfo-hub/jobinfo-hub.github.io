#!/usr/bin/env python3
"""CareerPick Threads publisher. Commands: prepare, publish, preview."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'alio.json'
HISTORY = ROOT / 'threads_posted.json'
KST = ZoneInfo('Asia/Seoul')
API = 'https://graph.threads.net/v1.0'
MIN_DAYS, MAX_DAYS, MAX_DAILY = 5, 20, 5


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def save(data):
    HISTORY.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_date(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
        return dt.astimezone(KST).date() if dt.tzinfo else dt.date()
    except (ValueError, TypeError):
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None


def parse_count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r'\d+', value.strip().replace(',', '')):
        return int(value.strip().replace(',', ''))
    return None


def regular(job):
    emp = job.get('emp', [])
    if isinstance(emp, str):
        emp = [emp]
    return isinstance(emp, list) and any('정규직' in str(x) or '무기계약' in str(x) for x in emp)


def candidates(posts, history, today):
    blocked = {str(x) for x in history.get('posted_ids', [])}
    blocked.update(str(x.get('job_id')) for x in history.get('records', []) if x.get('job_id'))
    seen, found = set(), []
    for job in posts:
        if not isinstance(job, dict):
            continue
        jid = str(job.get('id', '')).strip()
        due = parse_date(job.get('due'))
        if not jid or not due or jid in blocked or jid in seen:
            continue
        days = (due - today).days
        if not MIN_DAYS <= days <= MAX_DAYS or not job.get('title') or not job.get('org'):
            continue
        url = str(job.get('url', '')).strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in ('job.alio.go.kr', 'jobinfo-hub.github.io'):
            continue
        seen.add(jid)
        count = parse_count(job.get('verified_hiring_count'))
        if count is None:
            count = parse_count(job.get('n'))
        priority = 0 if count is None else 4 if count >= 100 else 3 if count >= 50 else 2 if count >= 30 else 1
        found.append({'id': jid, 'org': str(job['org']), 'title': str(job['title']), 'url': url,
                      'due': str(due), 'days': days, 'regular': regular(job), 'count': count, 'priority': priority})
    found.sort(key=lambda j: (-int(j['regular']), -j['priority'], -(j['count'] if j['count'] is not None else -1), j['days'], j['id']))
    return found


def compose(job):
    title = re.sub(r'\s+', ' ', job['title']).strip()
    org = re.sub(r'\s+', ' ', job['org']).strip()
    if title.startswith('[' + org + ']'):
        title = title[len(org) + 2:].strip()
    head = f'📢 공공기관 채용정보\n\n🏢 {org}\n📌 {title}'
    tail = (f"\n👥 모집인원: {job['count']}명" if job['count'] is not None else '\n👥 모집인원: 공고 확인')
    tail += f"\n📅 마감: {job['due']} (D-{job['days']})\n🔗 공고 확인: {job['url']}\n\n#커리어픽 #공공기관채용"
    max_chars = 490
    if len(head + tail) > max_chars:
        title = title[:max(20, len(title) - (len(head + tail) - max_chars) - 1)].rstrip() + '…'
        head = f'📢 공공기관 채용정보\n\n🏢 {org}\n📌 {title}'
    result = head + tail
    if len(result) > 500:
        raise ValueError('Post exceeds 500 characters')
    return result


def api(method, path, token, params=None):
    url = API + path
    payload = urllib.parse.urlencode(params or {}).encode('utf-8') if method == 'POST' else None
    if method == 'GET' and params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=payload, method=method,
                                 headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')[:1000]
        raise RuntimeError(f'Threads API HTTP {exc.code}: {body}') from None


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else 'preview'
    if command not in ('prepare', 'publish', 'preview'):
        raise ValueError('Use prepare, publish or preview')
    today = datetime.now(KST).date().isoformat()
    history = load(HISTORY, {'posted_ids': [], 'records': []})
    history.setdefault('posted_ids', [])
    history.setdefault('records', [])
    if command == 'publish':
        pending = [r for r in history['records'] if r.get('status') == 'pending' and r.get('run_id') == os.getenv('GITHUB_RUN_ID', '')]
        if len(pending) != 1:
            print('No pending post for this run. Nothing to publish.')
            return
        record = pending[0]
        if os.getenv('THREADS_ENABLED', 'false').lower() != 'true':
            print('Publishing disabled. Pending reservation requires manual reconciliation.')
            return
        token = os.environ['THREADS_ACCESS_TOKEN']
        user_id = os.environ['THREADS_USER_ID']
        # On uncertain API outcome leave pending; do not automatically retry.
        container = api('POST', f'/{user_id}/threads', token, {'media_type': 'TEXT', 'text': record['text']})
        if not container.get('id'):
            raise RuntimeError('Container creation did not return an ID')
        published = api('POST', f'/{user_id}/threads_publish', token, {'creation_id': container['id']})
        if not published.get('id'):
            raise RuntimeError('Publish did not return a post ID')
        record['status'] = 'published'
        record['threads_post_id'] = str(published['id'])
        record['published_at'] = datetime.now(KST).isoformat()
        if record['job_id'] not in history['posted_ids']:
            history['posted_ids'].append(record['job_id'])
        save(history)
        print('Published Threads post ID:', record['threads_post_id'])
        return
    posts = load(DATA, {'posts': []}).get('posts', [])
    if not isinstance(posts, list):
        raise ValueError('alio.json posts must be a list')
    chosen = candidates(posts, history, date.fromisoformat(today))
    print(f'Source: {len(posts)}; eligible: {len(chosen)}')
    if command == 'preview':
        for job in chosen[:5]:
            print('\n' + compose(job))
        print('\nPreview only; nothing published.')
        return
    if os.getenv('THREADS_ENABLED', 'false').lower() != 'true':
        print('Publishing disabled; no reservation made.')
        return
    daily = sum(r.get('reserved_date') == today and r.get('status') in ('pending', 'published') for r in history['records'])
    if daily >= MAX_DAILY or not chosen:
        print(f'No reservation. Daily reserved: {daily}/{MAX_DAILY}; eligible: {len(chosen)}')
        return
    job = chosen[0]
    history['records'].append({'job_id': job['id'], 'reserved_date': today, 'status': 'pending',
                               'run_id': os.environ['GITHUB_RUN_ID'], 'created_at': datetime.now(KST).isoformat(),
                               'text': compose(job)})
    save(history)
    print('Reserved job:', job['id'])
    print(compose(job))


if __name__ == '__main__':
    main()
