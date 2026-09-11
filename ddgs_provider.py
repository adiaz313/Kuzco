"""DDGS only. A disposable worker gives even stuck network threads a deadline."""
import json
from pathlib import Path
import subprocess
import sys


def search(query):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), '--worker'],
        input=json.dumps({'query': query}), text=True, capture_output=True,
        shell=False, timeout=15)
    if result.returncode or len(result.stdout) > 20000:
        raise RuntimeError('Search worker failed')
    return json.loads(result.stdout)


def worker(query):
    from ddgs import DDGS
    # One fixed engine, no auto fan-out, retries, page fetching, or API keys.
    rows = DDGS(timeout=6).text(query, backend='duckduckgo', region='us-en',
                               safesearch='moderate', max_results=5)
    def field(row, name, limit):
        value = row.get(name)
        return value[:limit] if isinstance(value, str) else None
    return [{'title': field(row, 'title', 180), 'url': field(row, 'href', 1500),
             'snippet': field(row, 'body', 800)} for row in rows[:5] if isinstance(row, dict)]


if __name__ == '__main__':
    try:
        print(json.dumps(worker(json.load(sys.stdin)['query'])))
    except Exception:
        # Provider exceptions can contain URLs/query details; keep them out of logs.
        sys.exit(1)
