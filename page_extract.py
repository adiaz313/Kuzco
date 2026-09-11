"""Swappable HTML extraction and deterministic relevance selection. No network."""
import json
import re
from datetime import datetime
from retrieval import bm25_scores

MAX_EVIDENCE = 2600


def select_sections(text, query):
    # Scan the full extracted article, including deep sections, before selection.
    chunks = []
    pending = ''
    paragraphs = []
    for paragraph in text.splitlines():
        paragraph = ' '.join(paragraph.split())
        if not paragraph:
            continue
        pending = (pending+' '+paragraph).strip()
        # Keep short headings attached to their explanatory text.
        if len(pending) < 180:
            continue
        paragraphs.append(pending)
        pending = ''
    if pending:
        paragraphs.append(pending)
    for paragraph in paragraphs:
        # Overlap preserves context around sentences crossing a chunk boundary.
        for start in range(0, len(paragraph), 500):
            chunks.append(paragraph[start:start + 650])
    scores = bm25_scores(chunks, query)
    ranked = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))
    chosen, used = [], 0
    for i in ranked:
        if len(chosen) == 4 or used >= MAX_EVIDENCE:
            break
        excerpt = chunks[i][:MAX_EVIDENCE-used]
        chosen.append({'section': i + 1, 'text': excerpt, 'score': round(scores[i], 4)})
        used += len(excerpt)
    return sorted(chosen, key=lambda section: section['section'])


def extract(page, query):
    import trafilatura
    from lxml import html
    tree = html.fromstring(page['html'], parser=html.HTMLParser(no_network=True))
    title = tree.xpath('//meta[@property="og:title"]/@content') or tree.xpath('//title/text()')
    metadata = {'published': [], 'modified': []}
    def date(kind, raw, origin):
        if not isinstance(raw, str) or len(raw) > 80:
            return
        try:
            datetime.fromisoformat(raw.strip().replace('Z', '+00:00'))
        except ValueError:
            return
        if len(metadata[kind]) < 3 and not any(d['value'] == raw for d in metadata[kind]):
            metadata[kind].append({'value': raw, 'origin': origin})
    for tag, kind in [('article:published_time', 'published'), ('article:modified_time', 'modified')]:
        for value in tree.xpath('//meta[@property=$tag or @name=$tag]/@content', tag=tag):
            date(kind, value, tag)
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list) and any(t in ('Article', 'NewsArticle', 'BlogPosting', 'WebPage') for t in types):
                date('published', value.get('datePublished'), 'JSON-LD datePublished')
                date('modified', value.get('dateModified'), 'JSON-LD dateModified')
            if '@graph' in value:
                visit(value['@graph'])
    for script in tree.xpath('//script[@type="application/ld+json"]/text()')[:20]:
        try:
            visit(json.loads(script))
        except (ValueError, TypeError, RecursionError):
            pass
    text = trafilatura.extract(tree, favor_precision=True, fast=True, include_comments=False,
                               include_tables=True, include_links=False, with_metadata=False,
                               deduplicate=False)
    mode='precision'
    # Precision extraction can discard schedule/list rows and retain only headings.
    # Retry extraction (not HTTP) once with the same library on genuinely thin pages.
    if len((text or '').strip()) < 300:
        fallback=trafilatura.extract(page['html'],favor_precision=False,fast=True,
            include_comments=False,include_tables=True,include_links=False,
            with_metadata=False,deduplicate=False)
        if fallback and len(fallback.strip())>len((text or '').strip()):
            text=fallback
            mode='thin_page_fallback'
    if not text or not text.strip():
        raise ValueError('No readable main content found; page may require JavaScript or login')
    sections = select_sections(text, query)
    return {'title': ' '.join(title[0].split())[:180] if title else 'Untitled webpage',
            'dates': metadata, 'sections': sections, 'extracted_chars': len(text),
            'extraction_mode':mode,
            'selected_chars': sum(len(s['text']) for s in sections),
            'query_matched': any(s['score'] > 0 for s in sections),
            'selection_note': 'Excerpts only; omissions do not prove absence. Scores are word relevance, not truth.',
            'date_note': 'Dates are page-declared metadata, not verified event dates. Preserve tentative claims and attribution.'}
