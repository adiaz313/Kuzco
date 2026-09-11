"""One bounded webpage worker; agent authorization is independent of extraction."""
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


def allowed_url(url, prompt, turn):
    if not isinstance(url, str):
        return False
    explicit = re.findall(r'https?://[^\s<>"\]]+', prompt)
    if url in explicit or url in [item.rstrip('.,!?') for item in explicit]:
        return True
    for message in turn:
        try:
            item = json.loads(message['content'])
            if item.get('tool') == 'search_web' and any(row.get('url') == url for row in item.get('tool_result', {}).get('results', [])):
                return True
        except (ValueError, TypeError, AttributeError):
            pass
    return False


from security_policy import enforced


@enforced('read_webpage')
def read_webpage(url, query):
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return {'error': 'Provide a short local relevance query.'}
    try:
        from page_fetch import validate_url
        validate_url(url)
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'],
                                 input=json.dumps({'url': url, 'query': query}), text=True,
                                 capture_output=True, shell=False, timeout=20)
        if process.returncode or len(process.stdout) > 16000:
            raise ValueError('Webpage reader failed')
        return json.loads(process.stdout)
    except subprocess.TimeoutExpired:
        return {'untrusted': True, 'error': 'Webpage reading timed out; page facts could not be verified.'}
    except Exception:
        return {'untrusted': True, 'error': 'Webpage unavailable or unsupported; page facts could not be verified.'}


def worker(url, query):
    from page_fetch import fetch
    from page_extract import extract
    page = fetch(url)
    result = extract(page, query)
    return dict(result, url=page['url'], requested_url=page['requested_url'],
                source=urlsplit(page['url']).hostname, http_last_modified=page['http_last_modified'],
                retrieved_at=datetime.now().astimezone().isoformat(timespec='seconds'), untrusted=True)


if __name__ == '__main__':
    try:
        print(json.dumps(worker(**json.load(sys.stdin))))
    except Exception:
        sys.exit(1)
