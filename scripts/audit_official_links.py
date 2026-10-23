"""Read-only, bounded ALIO official-link audit. Does not modify pages or publish posts."""
import argparse
import ipaddress
import json
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_https(url):
    try:
        p = urlsplit(str(url or '').strip())
        host = (p.hostname or '').lower().rstrip('.')
        if p.scheme != 'https' or not host or p.username or p.password or p.port not in (None, 443):
            return False
        if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')):
            return False
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_global for item in addresses
        )
    except (ValueError, OSError):
        return False


def check_url(url):
    if not public_https(url):
        return {'status': 'unsafe_or_unresolvable'}
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    for method in ('HEAD', 'GET'):
        req = Request(url, method=method, headers={'User-Agent': 'CareerPick-LinkAudit/1.0'})
        try:
            with opener.open(req, timeout=7) as response:
                return {'status': 'responded', 'http_status': response.status, 'method': method}
        except HTTPError as exc:
            if method == 'HEAD' and exc.code in (403, 404, 405, 410, 501):
                continue
            return {'status': 'http_error_or_redirect', 'http_status': exc.code, 'method': method}
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            return {'status': 'network_error', 'error_type': type(exc).__name__, 'method': method}
    return {'status': 'method_not_allowed'}



def triage(result):
    """HTTP status alone never proves whether applications are open."""
    status = result.get('status')
    code = result.get('http_status')
    if status == 'missing':
        return 'review_missing_link'
    if status == 'unsafe_or_unresolvable':
        return 'review_url_or_dns'
    if status == 'network_error':
        return 'retry_later'
    if status == 'responded':
        return 'reachable_not_verified'
    if status == 'http_error_or_redirect':
        if code in (404, 410):
            return 'review_missing_page'
        if code in (401, 403, 429):
            return 'access_restricted_or_rate_limited'
        if code in (301, 302, 303, 307, 308):
            return 'review_redirect_without_following'
        if isinstance(code, int) and 500 <= code < 600:
            return 'retry_server_error'
        return 'review_http_response'
    return 'review_unknown'

def audit(posts, limit, offset=0):
    eligible = [post for post in posts if isinstance(post, dict) and post.get('alio')]
    if not eligible:
        return []
    # Rotate through the ALIO feed instead of repeatedly auditing its first entries.
    start = offset % len(eligible)
    selected = (eligible[start:] + eligible[:start])[:limit]
    results = []
    for post in selected:
        if len(results) >= limit:
            break
        if not isinstance(post, dict) or not post.get('alio'):
            continue
        official = str(post.get('src') or post.get('url') or '').strip()
        if not official:
            results.append({'id': post.get('id'), 'status': 'missing', 'triage': 'review_missing_link'})
            continue
        try:
            host = urlsplit(official).hostname
        except ValueError:
            host = None
        outcome = check_url(official)
        results.append({'id': post.get('id'), 'host': host, **outcome, 'triage': triage(outcome)})
    return results


def self_test():
    """Offline-only audit checks; no network requests or data mutations."""
    from unittest.mock import patch

    posts = [
        {'id': 'a1', 'alio': True, 'src': 'https://example.org/jobs'},
        {'id': 'a2', 'alio': True, 'src': ''},
        {'id': 'a3', 'alio': True, 'src': 'https://[broken'},
        {'id': 'x4', 'alio': False, 'src': 'https://example.org'},
    ]
    with patch(__name__ + '.check_url', return_value={'status': 'responded', 'http_status': 200}):
        rows = audit(posts, 3)
    assert len(rows) == 3
    assert rows[0]['status'] == 'responded'
    assert rows[1]['status'] == 'missing'
    assert rows[2]['host'] is None
    assert all(row['id'] != 'x4' for row in rows)
    assert len(audit([], 20)) == 0
    assert triage({'status': 'http_error_or_redirect', 'http_status': 404}) == 'review_missing_page'
    # HEAD 404 may be a false negative; confirm using GET before classifying.
    from urllib.error import HTTPError
    from unittest.mock import MagicMock
    opener = MagicMock()
    ok_response = MagicMock()
    ok_response.__enter__.return_value.status = 200
    opener.open.side_effect = [HTTPError('https://example.org', 404, 'Not Found', {}, None), ok_response]
    with patch(__name__ + '.public_https', return_value=True), patch(__name__ + '.build_opener', return_value=opener):
        confirmed = check_url('https://example.org/jobs')
    assert confirmed == {'status': 'responded', 'http_status': 200, 'method': 'GET'}
    assert opener.open.call_count == 2
    assert triage({'status': 'http_error_or_redirect', 'http_status': 403}) == 'access_restricted_or_rate_limited'
    assert triage({'status': 'http_error_or_redirect', 'http_status': 302}) == 'review_redirect_without_following'
    assert triage({'status': 'http_error_or_redirect', 'http_status': 503}) == 'retry_server_error'
    assert triage({'status': 'responded', 'http_status': 200}) == 'reachable_not_verified'
    assert triage({'status': 'network_error'}) == 'retry_later'
    with patch(__name__ + '.check_url', return_value={'status': 'responded', 'http_status': 200}):
        rotated = audit(posts, 1, offset=1)
    assert rotated[0]['id'] == 'a2'
    summary_text = markdown_summary({'checked_count': 2, 'triage_summary': {'review_missing_page': 1, 'retry_later': 1}})
    assert '404/410' in summary_text and '네트워크 오류' in summary_text
    assert '점검 수: 2건' in summary_text
    print('CareerPick official link audit offline tests: PASS')



TRIAGE_KO = {
    'reachable_not_verified': '접속 응답 확인(채용 유효성 별도 확인)',
    'review_missing_page': '404/410: 페이지 확인 필요',
    'review_missing_link': '공식 링크 누락',
    'review_url_or_dns': '주소 형식 또는 DNS 확인 필요',
    'access_restricted_or_rate_limited': '접근 제한/요청 제한',
    'review_redirect_without_following': '이동 주소 확인 필요',
    'retry_server_error': '서버 오류: 나중에 재점검',
    'retry_later': '네트워크 오류: 나중에 재점검',
    'review_http_response': 'HTTP 응답 수동 검토',
    'review_unknown': '기타 수동 검토',
}


def markdown_summary(report):
    """Safe human-readable summary without untrusted titles or URLs."""
    lines = [
        '## 커리어픽 공식 채용 링크 점검',
        '',
        f"점검 수: {report['checked_count']}건",
        '',
        '| 분류 | 건수 |',
        '| --- | ---: |',
    ]
    for key, count in sorted(report['triage_summary'].items()):
        lines.append(f"| {TRIAGE_KO.get(key, '기타')} | {count} |")
    lines.extend([
        '',
        'HTTP 응답만으로 채용 진행 여부를 확정하지 않습니다.',
        '접근 제한(403 등)과 일시적인 서버 오류는 링크 삭제 근거가 아닙니다.',
        '개별 공고 ID 및 오류 내용은 업로드된 JSON 보고서를 확인하세요.',
        '',
    ])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--input', default=str(ROOT / 'alio.json'))
    parser.add_argument('--output', default=str(ROOT / 'link-audit-results.json'))
    parser.add_argument('--markdown-output', default=str(ROOT / 'link-audit-summary.md'))
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--rotate-weekly', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not 1 <= args.limit <= 50:
        parser.error('--limit must be between 1 and 50')
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    # Weekly audit advances through the feed in batches; manual runs start at the top.
    offset = (datetime.now(timezone.utc).date().toordinal() // 7) * args.limit if args.rotate_weekly else 0
    results = audit(data.get('posts', []), args.limit, offset=offset)
    summary = {}
    for result in results:
        category = result['triage']
        summary[category] = summary.get(category, 0) + 1
    output = {
        'triage_summary': dict(sorted(summary.items())),
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'note': 'HTTP responses do not prove the vacancy is active or applications are accepted. Redirects are not followed.',
        'checked_count': len(results),
        'sample_offset': offset,
        'results': results,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path(args.markdown_output).write_text(markdown_summary(output), encoding='utf-8')
    print(f"Audited {len(results)} official URLs; results: {args.output}")


if __name__ == '__main__':
    main()
