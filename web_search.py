"""Small provider-independent, read-only search boundary. No page URLs are fetched."""
from datetime import datetime
import ipaddress
import json
import re
import subprocess
from urllib.parse import urlsplit

MAX_SEARCHES = 3


def normalize(rows):
    if not isinstance(rows, list):
        raise ValueError('Malformed search response')
    results, seen = [], set()
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        url = row.get('url')
        if not isinstance(url, str) or len(url) > 1500 or any(c.isspace() or ord(c) < 32 for c in url):
            continue
        try:
            parsed = urlsplit(url)
            domain = parsed.hostname
            if parsed.scheme not in ('http', 'https') or not domain or parsed.username or parsed.password:
                continue
            if domain == 'localhost' or domain.endswith(('.local', '.localhost')):
                continue
            try:
                if not ipaddress.ip_address(domain).is_global:
                    continue
            except ValueError:
                pass
        except ValueError:
            continue
        title, snippet = row.get('title'), row.get('snippet')
        if not isinstance(title, str) or not isinstance(snippet, str) or not (title.strip() and snippet.strip()):
            continue
        if url in seen:
            continue
        seen.add(url)
        item = {'title': title.strip()[:180], 'source': domain, 'url': url,
                'snippet': snippet.strip()[:800]}
        if isinstance(row.get('date'), str) and row['date'].strip():
            item['date'] = row['date'].strip()[:60]
        results.append(item)
        if len(results) == 5:
            break
    return results


from security_policy import enforced


@enforced('search_web')
def search_web(query, provider=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 300 or any(ord(c) < 32 for c in query):
        return {'results': [], 'error': 'Provide a short search query (1–300 characters).'}
    if provider is None:
        from ddgs_provider import search
        provider = search
    base = {'query': query.strip(), 'provider': 'DDGS', 'untrusted': True,
            'retrieved_at': datetime.now().astimezone().isoformat(timespec='seconds')}
    try:
        results = normalize(provider(query.strip()))
        return dict(base, results=results, **({} if results else {'error': 'No usable search evidence was found.'}))
    except (TimeoutError, subprocess.TimeoutExpired):
        return dict(base, results=[], error='Web search timed out. Current facts could not be verified.')
    except Exception:
        return dict(base, results=[], error='Web search is unavailable. Current facts could not be verified.')


def authorize_after_web(choice, prompt):
    """Untrusted evidence cannot authorize reading files or launching an app.

    Require the actual current user to name a local action. Follow-ups that only
    say 'open it' after web evidence must name the app explicitly instead.
    """
    tool, args = choice['tool'], choice['arguments']
    if tool in ('open_application', 'search_documents') and re.search(r"\b(?:not|never|don't|do not)\b", prompt, re.I):
        return False
    if tool == 'open_application':
        name = args.get('application_name')
        return (isinstance(name, str) and bool(re.search(
            r'\b(?:open|launch|start)\s+(?:the\s+)?' + re.escape(name) + r'\b', prompt, re.I)))
    if tool == 'search_documents':
        return bool(re.search(r'\b(?:my|our|local)\b.*\b(?:documents?|notes?|files?|ideas?)\b|\bsea\s*foods\b', prompt, re.I))
    if tool == 'get_current_time':
        return prompt.strip().casefold() in ('time', 'date') or bool(re.search(
            r"\b(?:what time is it|what(?:'s| is) (?:the )?(?:time|date)|current (?:local )?(?:time|date)|today'?s date|clock)\b", prompt, re.I))
    return tool in ('search_web', 'read_webpage', 'research_web')


# Public query expansion words, never private context. New entities must come
# from the user's request or returned public evidence, not documents/prompts.
QUERY_WORDS = set('''a an the and or of for in on at to from with is are was were
browser stable download downloads
what who when where how which my our next last latest current today tonight
tomorrow yesterday this week month year date time schedule schedules game games
kickoff start result results score scores won win loss weather forecast temperature
news official site release releases version versions price prices availability
new regular season company governor state eastern et est edt am pm nfl mlb
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday'''.split())


def query_allowed(query, prompt, history, turn):
    """Only user-supplied/public terms and neutral search vocabulary may leave.

    This deliberately rejects speculative entity expansion from private context.
    The model can retry using the user's own words. A short referential follow-up
    may reuse the previous user request, never its assistant/documents/tool data.
    """
    if not isinstance(query, str):
        return False
    words = lambda text: set(re.findall(r'\w+', text.casefold()))
    allowed = QUERY_WORDS | words(prompt)
    now = datetime.now()
    allowed |= {str(i) for i in range(32)} | {str(now.year + i) for i in (-1, 0, 1)}
    if history and re.search(r'\b(?:it|its|they|them|their|that|those)\b', prompt, re.I):
        allowed |= words(history[-1][0].get('content', ''))
    for message in turn:
        try:
            envelope = json.loads(message['content'])
            if isinstance(envelope, dict) and envelope.get('tool') == 'search_web':
                for row in envelope.get('tool_result', {}).get('results', []):
                    allowed |= words(' '.join(str(row.get(k, '')) for k in ('title', 'snippet', 'source', 'date')))
        except (ValueError, TypeError, AttributeError):
            continue
    return words(query) <= allowed


def source_footer(turn):
    """Visible metadata independent of the model remembering to print citations."""
    results = []
    for message in turn:
        try:
            envelope = json.loads(message['content'])
            if isinstance(envelope, dict) and envelope.get('tool') == 'search_web':
                results.extend(envelope.get('tool_result', {}).get('results', []))
            elif isinstance(envelope, dict) and envelope.get('tool') == 'read_webpage':
                page = envelope.get('tool_result', {})
                if page.get('url') and not page.get('error'):
                    results.append({'url': page['url'], 'title': page.get('title', 'Webpage')})
        except (ValueError, TypeError, AttributeError):
            continue
    links, seen = [], set()
    for row in reversed(results):
        url = row.get('url', '')
        if url and url not in seen:
            seen.add(url)
            title = re.sub(r'[\[\]\r\n]', '', row.get('title', 'Source'))
            links.append(f'[{title}]({url.replace("(", "%28").replace(")", "%29")})')
        if len(links) == 5:
            break
    return '\n\nSearch sources:\n' + '\n'.join(reversed(links)) if links else ''
