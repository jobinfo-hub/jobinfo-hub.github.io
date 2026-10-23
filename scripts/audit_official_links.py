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
            if method == 'HEAD' and exc.code in (403, 405, 501):
                continue
            return {'status': 'http_error_or_redirect', 'http_status': exc.code, 'method': method}
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            return {'status': 'network_error', 'error_type': type(exc).__name__, 'method': method}
    return {'status': 'method_not_allowed'}


def audit(posts, limit):
    results = []
    for post in posts:
        if len(results) >= limit:
            break
        if not isinstance(post, dict) or not post.get('alio'):
            continue
        official = str(post.get('src') or post.get('url') or '').strip()
        if not official:
            results.append({'id': post.get('id'), 'status': 'missing'})
            continue
        outcome = check_url(official)
        results.append({'id': post.get('id'), 'host': urlsplit(official).hostname, **outcome})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--input', default=str(ROOT / 'alio.json'))
    parser.add_argument('--output', default=str(ROOT / 'link-audit-results.json'))
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        parser.error('--limit must be between 1 and 50')
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    results = audit(data.get('posts', []), args.limit)
    output = {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'note': 'HTTP responses do not prove the vacancy is active or applications are accepted. Redirects are not followed.',
        'checked_count': len(results),
        'results': results,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Audited {len(results)} official URLs; results: {args.output}")


if __name__ == '__main__':
    main()
