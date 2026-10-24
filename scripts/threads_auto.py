#!/usr/bin/env python3
"""CareerPick Threads publisher. Commands: prepare, publish, preview, diagnose."""

import json
import os
import re
import sys
import time
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

MIN_DAYS = 5
MAX_DAYS = 20
MAX_DAILY = 5


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def save(data):
    HISTORY.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8'
    )


def parse_date(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).strip().replace('Z', '+00:00')
        )
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

    if isinstance(value, str):
        cleaned = value.strip().replace(',', '')
        if re.fullmatch(r'\d+', cleaned):
            return int(cleaned)

    return None


def regular(job):
    emp = job.get('emp', [])

    if isinstance(emp, str):
        emp = [emp]

    return isinstance(emp, list) and any(
        '정규직' in str(x) or '무기계약' in str(x)
        for x in emp
    )


def candidates(posts, history, today):
    blocked = {
        str(x) for x in history.get('posted_ids', [])
    }

    blocked.update(
        str(x.get('job_id'))
        for x in history.get('records', [])
        if x.get('job_id')
    )

    seen = set()
    found = []

    for job in posts:
        if not validate_candidate(job, today):
            continue

        jid = str(job.get('id', '')).strip()
        due = parse_date(job.get('due'))

        if not jid or not due or jid in blocked or jid in seen:
            continue

        days = (due - today).days

        if not MIN_DAYS <= days <= MAX_DAYS:
            continue

        if not job.get('title') or not job.get('org'):
            continue

        url = str(job.get('url', '')).strip()
        parsed = urllib.parse.urlparse(url)

        if (
            parsed.scheme != 'https'
            or parsed.hostname not in (
                'job.alio.go.kr',
                'jobinfo-hub.github.io'
            )
        ):
            continue

        seen.add(jid)

        count = parse_count(
            job.get('verified_hiring_count')
        )

        if count is None:
            count = parse_count(job.get('n'))

        if count is None:
            priority = 0
        elif count >= 100:
            priority = 4
        elif count >= 50:
            priority = 3
        elif count >= 30:
            priority = 2
        else:
            priority = 1

        found.append({
            'id': jid,
            'org': str(job['org']),
            'title': str(job['title']),
            'url': url,
            'due': str(due),
            'days': days,
            'regular': regular(job),
            'count': count,
            'employment': ' · '.join(map(str, job.get('emp', []))) if isinstance(job.get('emp'), list) else str(job.get('emp') or '공고 확인'),
            'location': str(job.get('location') or job.get('region') or '공고 확인'),
            'start': str(job.get('start') or job.get('start_date') or ''),
            'priority': priority
        })

    found.sort(
        key=lambda j: (
            -int(j['regular']),
            -j['priority'],
            -(j['count'] if j['count'] is not None else -1),
            j['days'],
            j['id']
        )
    )

    return found


def validate_candidate(job, today):
    """Return true only for currently eligible ALIO posts."""
    if not isinstance(job, dict):
        return False
    due = parse_date(job.get('due'))
    if due is None or not MIN_DAYS <= (due - today).days <= MAX_DAYS:
        return False
    if not str(job.get('id') or '').strip() or not job.get('title') or not job.get('org'):
        return False
    try:
        parsed = urllib.parse.urlparse(str(job.get('url') or '').strip())
    except ValueError:
        return False
    return parsed.scheme == 'https' and parsed.hostname in ('job.alio.go.kr', 'jobinfo-hub.github.io')


def compose(job):
    """Keep the primary image post short; details stay in the reply."""
    org = re.sub(r'\s+', ' ', str(job['org'])).strip()
    result = f'📢 공공기관 채용정보\n\n🏢 {org}'
    if len(result) > 500:
        raise ValueError('Organization name exceeds Threads post limit')
    return result


def api(method, path, token, params=None):
    url = API + path

    payload = None

    if params:
        url += '?' + urllib.parse.urlencode(params)

    if method == 'POST':
        payload = b''

    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:
            return json.load(response)

    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode(
            'utf-8',
            errors='replace'
        )

        print('')
        print('=== Threads API Error ===')
        print('HTTP status:', exc.code)
        print('Endpoint:', method, path)

        try:
            error_data = json.loads(raw_body)
            error = error_data.get('error', {})

            print('Error code:', error.get('code'))
            print(
                'Error subcode:',
                error.get('error_subcode')
            )
            print(
                'Error type:',
                error.get('type')
            )
            print(
                'Error message:',
                error.get('message')
            )
        except (ValueError, TypeError, AttributeError):
            print('Error response could not be parsed')

        print('=========================')

        raise RuntimeError(
            f'Threads API request failed: HTTP {exc.code}'
        ) from None

    except urllib.error.URLError as exc:
        print('Threads API network request failed')
        raise RuntimeError(
            'Threads API network error'
        ) from None


def verify_account(token, expected_id=None):
    """Use the authenticated Threads ID; strictly verify the account username."""
    print('')
    print('=== Threads Account Verification ===')

    account = api(
        'GET',
        '/me',
        token,
        {'fields': 'id,username'}
    )
    actual_id = str(account.get('id', '')).strip()
    username = str(account.get('username', '')).strip().lstrip('@')

    if not actual_id.isdigit():
        raise RuntimeError('Threads API returned an invalid user ID')

    # Never rely on a manually typed ID to identify the account.
    # Prevent publishing to another account if the token is replaced.
    expected_username = os.environ.get(
        'THREADS_EXPECTED_USERNAME', 'hid_119'
    ).strip().lstrip('@')
    if not expected_username:
        raise RuntimeError('Missing expected Threads username')
    if username.casefold() != expected_username.casefold():
        raise RuntimeError(
            'Token belongs to a different Threads account: '
            + username
        )

    print('API username:', username)
    print('Account ID obtained directly from Threads API')
    print('Account verification successful')
    return actual_id



def compose_reply(job):
    count = f"{job['count']}명" if job.get('count') is not None else '공고 확인'
    start = job.get('start', '').strip()
    period = (start + ' ~ ' if start else '마감 ') + job['due']
    return (
        f"🏢 기관명: {job['org']}\n\n"
        f"📌 고용형태: {job.get('employment') or '공고 확인'}\n\n"
        f"👥 채용인원: {count}\n\n"
        f"📍 근무지: {job.get('location') or '공고 확인'}\n\n"
        f"📅 접수기간: {period}\n\n"
        "🔗 자세한 채용공고: 커리어픽 프로필링크"
    )[:500]


def create_media(token, params):
    container = api('POST', '/me/threads', token, params)
    creation_id = container.get('id')
    if not creation_id:
        raise RuntimeError('Threads container ID missing')

    # Image containers are asynchronous. Publishing immediately after creation
    # can fail while Threads is still processing the media.
    if params.get('media_type') == 'IMAGE':
        for attempt in range(24):
            status = api('GET', '/' + str(creation_id), token,
                         {'fields': 'status,error_message'})
            state = str(status.get('status', '')).upper()
            print('Threads media processing:', state, f'({attempt + 1}/24)')
            if state == 'FINISHED':
                # Give Meta's publish endpoint time to observe the ready media.
                # A successful status check may precede propagation.
                time.sleep(10)
                break
            if state in ('ERROR', 'EXPIRED'):
                raise RuntimeError(
                    'Threads media processing failed: '
                    + str(status.get('error_message') or state)
                )
            time.sleep(5)
        else:
            raise RuntimeError(
                'Threads media processing timed out; do not publish prematurely'
            )

    print('Threads media container created; attempting final publish')
    try:
        published = api('POST', '/me/threads_publish', token,
                        {'creation_id': creation_id})
    except RuntimeError:
        # An API failure is not proof that the remote publish did not happen.
        # Preserve the pending reservation for manual reconciliation.
        print('Final Threads publish not confirmed; keep reservation pending')
        raise
    post_id = published.get('id')
    if not post_id:
        raise RuntimeError('Threads publish ID missing')
    return str(post_id)


def image_ready(url):
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status == 200 and response.headers.get('Content-Type', '').startswith('image/')
    except (urllib.error.URLError, TimeoutError):
        return False


def publish_post(record, history):
    if os.getenv(
        'THREADS_ENABLED', 'false'
    ).lower() != 'true':
        print(
            'Publishing disabled. '
            'Pending reservation requires manual reconciliation.'
        )
        return

    token = os.environ.get(
        'THREADS_ACCESS_TOKEN', ''
    )

    user_id = os.environ.get(
        'THREADS_USER_ID', ''
    ).strip()

    if not token:
        raise RuntimeError('Missing THREADS_ACCESS_TOKEN')

    # Verify username and use the ID returned by the token's account.
    user_id = verify_account(token, user_id)

    print('')
    print('=== Threads Publishing ===')
    if not record.get('threads_post_id'):
        image_url = record.get('image_url', '')
        if image_url and image_ready(image_url):
            print('Publishing image post')
            params = {'media_type': 'IMAGE', 'image_url': image_url, 'text': record['text']}
        elif image_url:
            raise RuntimeError('Public image not ready; preserve reservation and retry later')
        else:
            params = {'media_type': 'TEXT', 'text': record['text']}
        post_id = create_media(token, params)
        record['status'] = 'published'
        record['threads_post_id'] = post_id
        record['published_at'] = datetime.now(KST).isoformat()
        if record['job_id'] not in history['posted_ids']:
            history['posted_ids'].append(record['job_id'])
        save(history)
        print('Published Threads post ID:', post_id)

    if record.get('reply_post_id'):
        return
    # Threads may not accept a reply immediately after the parent image post.
    # Check that the parent is readable and allow propagation before creating
    # the reply. Never retry an ambiguous publish automatically.
    try:
        parent = api('GET', '/' + str(record['threads_post_id']), token,
                     {'fields': 'id'})
        if str(parent.get('id', '')) != str(record['threads_post_id']):
            raise RuntimeError('Parent post not yet confirmed by Threads API')
        if record.get('published_at'):
            print('Waiting 20 seconds before first reply to new parent post')
            time.sleep(20)
        reply_id = create_media(token, {
            'media_type': 'TEXT',
            'text': record.get('reply_text', '🔗 자세한 채용공고: 커리어픽 프로필링크'),
            'reply_to_id': record['threads_post_id']
        })
        record['reply_post_id'] = reply_id
        record['reply_published_at'] = datetime.now(KST).isoformat()
        save(history)
        print('Published reply ID:', reply_id)
    except RuntimeError as exc:
        print('Reply publish failed; original post remains recorded:', str(exc))
        # Keep post ID for manual reconciliation; never publish the original again.
        record['reply_status'] = 'needs_review'
        record['reply_failure_reason'] = str(exc)[:300]
        record['reply_failed_at'] = datetime.now(KST).isoformat()
        save(history)


def main():
    command = (
        sys.argv[1]
        if len(sys.argv) > 1
        else 'preview'
    )

    if command not in (
        'prepare',
        'publish',
        'preview',
        'diagnose'
    ):
        raise ValueError(
            'Use prepare, publish, preview or diagnose'
        )

    today = datetime.now(
        KST
    ).date().isoformat()

    history = load(
        HISTORY,
        {
            'posted_ids': [],
            'records': []
        }
    )

    history.setdefault('posted_ids', [])
    history.setdefault('records', [])

    if command == 'diagnose':
        # Read-only diagnostic: no publishing and no history mutation.
        pending_records = [
            r for r in history['records'] if r.get('status') == 'pending'
        ]
        for record in pending_records:
            print(
                'Unresolved reservation:',
                'job_id=' + str(record.get('job_id', '')),
                'run_id=' + str(record.get('run_id', '')),
                'created_at=' + str(record.get('created_at', '')),
                'has_post_id=' + str(bool(record.get('threads_post_id')))
            )

        token = os.environ.get('THREADS_ACCESS_TOKEN', '')
        configured_id = os.environ.get('THREADS_USER_ID', '')
        if not token:
            raise RuntimeError('Missing THREADS_ACCESS_TOKEN')
        actual_id = verify_account(token, configured_id)
        # Scan a bounded number of remote pages without mutating history.
        # A missing match is inconclusive, even if every page was scanned.
        if pending_records:
            try:
                remote_posts = []
                after = None
                more_pages = False
                for page in range(10):
                    params = {'fields': 'id,text,timestamp', 'limit': 100}
                    if after:
                        params['after'] = after
                    remote = api('GET', '/me/threads', token, params)
                    remote_posts.extend(remote.get('data', []))
                    paging = remote.get('paging') or {}
                    cursors = paging.get('cursors') or {}
                    next_after = cursors.get('after')
                    more_pages = bool(paging.get('next'))
                    if not more_pages or not next_after or next_after == after:
                        break
                    after = next_after
                print('Remote reconciliation scanned posts:', len(remote_posts))
                for record in pending_records:
                    matches = [
                        str(post.get('id', ''))
                        for post in remote_posts
                        if post.get('text') == record.get('text')
                        and str(post.get('id', '')).isdigit()
                    ]
                    print('Remote match for job', record.get('job_id'),
                          'count:', len(matches))
                    if len(matches) == 1:
                        print('Confirmed remote post ID:', matches[0])
                    elif len(matches) > 1:
                        print('Multiple remote matches; manual review required')
                    else:
                        print('No exact match in scanned posts; not proof of absence')
                if more_pages:
                    print('Additional remote pages may exist; reconciliation incomplete')
            except (RuntimeError, ValueError, TypeError) as exc:
                print('Remote reconciliation unavailable:', type(exc).__name__)
        print('Publishing enabled:', os.getenv('THREADS_ENABLED', 'false'))
        # Report legacy posts without recorded replies; do not auto-reply.
        missing_replies = [
            r for r in history['records']
            if r.get('status') == 'published'
            and r.get('threads_post_id')
            and not r.get('reply_post_id')
        ]
        print('Published posts missing recorded reply:', len(missing_replies))
        for record in missing_replies:
            print('Missing reply for job:', record.get('job_id'),
                  'has_reply_text:', bool(record.get('reply_text')),
                  'reply_status:', record.get('reply_status', 'unknown'))
        print('Pending reservations:', sum(
            r.get('status') == 'pending' for r in history['records']
        ))
        # Make the scheduled diagnostic result actionable in GitHub's run summary.
        if os.getenv('GITHUB_STEP_SUMMARY'):
            summary_path = Path(os.environ['GITHUB_STEP_SUMMARY'])
            published_count = sum(r.get('status') == 'published' for r in history['records'])
            pending_count = len(pending_records)
            with summary_path.open('a', encoding='utf-8') as summary:
                summary.write('## CareerPick Threads diagnostic\\n\\n'.replace('\\n', '\n'))
                summary.write(f'- Pending reservations: **{pending_count}**\\n'.replace('\\n', '\n'))
                summary.write(f'- Published records: **{published_count}**\\n'.replace('\\n', '\n'))
                summary.write(f'- Published posts without recorded reply: **{len(missing_replies)}**\\n'.replace('\\n', '\n'))
                if pending_count:
                    summary.write('- **Action needed:** inspect remote match results in the job log before reconciling.\\n'.replace('\\n', '\n'))
                if missing_replies:
                    summary.write('- **Review:** legacy missing replies are not automatically reposted.\\n'.replace('\\n', '\n'))
        print('Published records:', sum(
            r.get('status') == 'published' for r in history['records']
        ))
        print('Account ID:', actual_id)
        try:
            limits = api('GET', '/me/threads_publishing_limit', token,
                         {'fields': 'quota_usage,config'})
            print('Publishing limit response:', json.dumps(limits, ensure_ascii=False))
        except RuntimeError as exc:
            print('Publishing limit check failed:', str(exc))
        print('Diagnostic only: no post was created, no history changed.')
        return

    if command == 'publish':
        run_id = os.getenv(
            'GITHUB_RUN_ID', ''
        )

        if not run_id:
            raise RuntimeError(
                'GITHUB_RUN_ID is required for publishing'
            )

        pending = [
            record
            for record in history['records']
            if (
                record.get('status') in ('pending', 'published')
                and record.get('run_id') == run_id
                and not record.get('reply_post_id')
            )
        ]

        if len(pending) != 1:
            print(
                'No unique pending post for this run. '
                'Nothing to publish.'
            )
            return

        publish_post(
            pending[0],
            history
        )

        return

    posts = load(
        DATA,
        {'posts': []}
    ).get('posts', [])

    if not isinstance(posts, list):
        raise ValueError(
            'alio.json posts must be a list'
        )

    chosen = candidates(
        posts,
        history,
        date.fromisoformat(today)
    )

    print(
        f'Source: {len(posts)}; '
        f'eligible: {len(chosen)}'
    )

    if command == 'preview':
        for job in chosen[:5]:
            print('')
            print(compose(job))

        print('')
        print(
            'Preview only; nothing published.'
        )
        return

    if os.getenv(
        'THREADS_ENABLED', 'false'
    ).lower() != 'true':
        print(
            'Publishing disabled; no reservation made.'
        )
        return

    daily = sum(
        record.get('reserved_date') == today
        and record.get('status') in (
            'pending',
            'published'
        )
        for record in history['records']
    )

    has_waiting = any(r.get('status') == 'pending' and r.get('image_url') and not r.get('threads_post_id') for r in history['records'])
    if (daily >= MAX_DAILY and not has_waiting) or (not chosen and not has_waiting):
        print(
            f'No reservation. '
            f'Daily reserved: {daily}/{MAX_DAILY}; '
            f'eligible: {len(chosen)}'
        )
        return

    run_id = os.getenv(
        'GITHUB_RUN_ID', ''
    )

    if not run_id:
        raise RuntimeError(
            'GITHUB_RUN_ID is required for reservation'
        )

    # Resume an unfinished image reservation rather than reserving another job.
    waiting = [
        r for r in history['records']
        if r.get('status') == 'pending' and r.get('image_url')
        and not r.get('threads_post_id')
    ]
    if waiting:
        waiting.sort(key=lambda r: r.get('created_at', ''))
        print(
            'Unresolved pending Threads reservation:',
            waiting[0].get('job_id'),
            '- manual reconciliation required before another publish attempt.'
        )
        print('No new reservation created; avoiding possible duplicate post.')
        return

    job = chosen[0]

    history['records'].append({
        'job_id': job['id'],
        'reserved_date': today,
        'status': 'pending',
        'run_id': run_id,
        'created_at': datetime.now(
            KST
        ).isoformat(),
        'text': compose(job),
        'reply_text': compose_reply(job),
        'image_url': 'https://jobinfo-hub.github.io/threads-images/' + urllib.parse.quote(re.sub(r'[^A-Za-z0-9_-]', '_', job['id'])[:70] + '.jpg'),
        'image_job': job
    })

    save(history)

    print('Reserved job:', job['id'])
    print(compose(job))


if __name__ == '__main__':
    main()
