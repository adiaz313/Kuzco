"""Read-only public HTTP fetching; no proxies, cookies, scripts or automatic redirects."""
import http.client
import ipaddress
import socket
import ssl
import zlib
from urllib.parse import urlsplit, urlunsplit, urljoin

MAX_BYTES = 2_000_000


def validate_url(url):
    if not isinstance(url, str) or len(url) > 1500 or any(c.isspace() or ord(c) < 32 for c in url):
        raise ValueError('Invalid webpage URL')
    parsed = urlsplit(url)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
            or parsed.password or parsed.port not in (None, 80, 443)):
        raise ValueError('Use a public HTTP(S) webpage URL')
    host = parsed.hostname.encode('idna').decode('ascii')
    if host.rstrip('.').lower() == 'localhost' or host.rstrip('.').lower().endswith(('.local', '.localhost')):
        raise ValueError('Local addresses are unavailable')
    return parsed, host


def public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Only public internet addresses are allowed')
    return addresses


def request_once(url):
    parsed, host = validate_url(url)
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    addresses = public_addresses(host, port)
    # Connect directly to the validated numeric address: no second DNS lookup or rebinding.
    family, kind, protocol, _, address = addresses[0]
    sock = socket.socket(family, kind, protocol)
    connection = http.client.HTTPConnection(host, port, timeout=6)
    try:
        sock.settimeout(6)
        sock.connect(address)
        if parsed.scheme == 'https':
            import certifi
            sock = ssl.create_default_context(cafile=certifi.where()).wrap_socket(sock, server_hostname=host)
        connection.sock = sock
        target = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
        connection.request('GET', target, headers={'User-Agent': 'Kuzco/0.1 (read-only page reader)',
                           'Accept': 'text/html,application/xhtml+xml', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        headers = dict((key.lower(), value) for key, value in response.getheaders())
        if response.status in (301, 302, 303, 307, 308):
            return response.status, headers, b''
        if response.status != 200:
            raise ValueError('Webpage returned an unsuccessful HTTP status')
        if headers.get('content-type', '').split(';')[0].strip().lower() not in ('text/html', 'application/xhtml+xml'):
            raise ValueError('Only HTML webpages are supported')
        encoding = headers.get('content-encoding', 'identity').lower()
        if encoding not in ('identity', 'gzip', 'deflate'):
            raise ValueError('Unsupported content encoding')
        if int(headers.get('content-length', '0')) > MAX_BYTES:
            raise ValueError('Webpage exceeds the size limit')
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Webpage exceeds the size limit')
        if encoding != 'identity':
            decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
            body = decoder.decompress(body, MAX_BYTES + 1)
            if len(body) > MAX_BYTES or decoder.unconsumed_tail or not decoder.eof:
                raise ValueError('Decompressed webpage exceeds limit or is incomplete')
        return response.status, headers, body
    finally:
        connection.close()
        sock.close()


def fetch(url, request=request_once):
    original = url
    seen = set()
    for _ in range(4):
        validate_url(url)
        if url in seen:
            raise ValueError('Redirect loop')
        seen.add(url)
        status, headers, body = request(url)
        if status in (301, 302, 303, 307, 308):
            if not headers.get('location'):
                raise ValueError('Redirect has no destination')
            url = urljoin(url, headers['location'])
            continue
        return {'requested_url': original, 'url': url, 'html': body,
                'http_last_modified': headers.get('last-modified', '')[:100]}
    raise ValueError('Too many redirects')
