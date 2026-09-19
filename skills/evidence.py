"""Small production plans for unambiguous read-only lookups, not a new agent.

The caller executes through the existing policy/tool dispatcher and step budget.
Keep full history in the session; omit it from a self-contained lookup's payload.
"""
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit
from .usability import clean
from retrieval import bm25_scores


def self_contained(prompt):
    return not re.search(r'\b(?:it|its|they|them|their|that|those|previous|earlier|again|above)\b',prompt,re.I)


def plan(prompt, skill):
    text=clean(prompt)
    if not self_contained(text) or len(text)>300 or re.search(r'["“”`;]|\b(?:then|also|open|launch|delete|send)\b',text):
        return None
    if skill.name=='document_analysis' and re.match(r"(?:what|how|does|do|is|are|summarize|find|search)\b",text):
        # Drop generic question words that can pull a later business-planning
        # section above the document's product overview. Keep distinctive nouns.
        words=re.findall(r"[a-z]+",text)
        ignored={'what','was','were','is','are','does','do','my','our','the','this','that','about','business','idea','ideas','product','proposing'}
        terms=[w for w in words if w not in ignored]
        query=' '.join(terms) or text
        return {'tool':'search_documents','arguments':{'query':query}}
    if skill.name=='web_research' and not re.search(r'https?://|\b(?:my|our|document|notes|remember)\b',text) and re.match(r"(?:what|who|when|where|which|how)\b",text):
        return {'tool':'search_web','arguments':{'query':text}}
    return None


def history_view(prompt, skill, history, planned):
    # Exact named definitions and explicit independent lookups need no old facts.
    # References retain complete recent turns, including evidence and side effects.
    if self_contained(prompt) and (planned or (skill.tools==() and re.match(r"(?:what(?: is|'s)|explain|briefly explain)\b",clean(prompt)))):
        return []
    return history


def schedule_source(prompt, result):
    if not re.search(r'\b(?:play|game|match)\b.*\bnext\b|\bnext\b.*\b(?:game|match)\b',prompt,re.I):
        return None
    rows=result.get('results',[])
    if not rows:return None
    scores=bm25_scores([r.get('title','')+' '+r.get('snippet','') for r in rows],prompt)
    def rank(pair):
        i,row=pair
        path=urlsplit(row.get('url','')).path.lower()
        # Prefer a schedule landing page over watch guides/roundups. No domain,
        # team, date or result is hardcoded; this is relevance, not authentication.
        return (int(bool(re.search(r'/schedule/?$',path))),
                int('official' in row.get('title','').lower()), scores[i])
    row=max(enumerate(rows),key=rank)[1]
    return row.get('url')


def schedule_answer(prompt, page, today=None):
    """Answer only a clear upcoming fixture on a matching schedule page."""
    question = re.fullmatch(r'(?:when|what time) (?:do|does) (?:the )?([a-z][a-z0-9 -]{1,40}?) play next', clean(prompt))
    if not question or not isinstance(page, dict) or page.get('error') or page.get('query_matched') is False:
        return None
    title, url = page.get('title', ''), page.get('url', '')
    if not isinstance(title, str) or not isinstance(url, str) or not re.search(r'/schedule/?$', urlsplit(url).path, re.I):
        return None
    subject = question[1].strip()
    if not re.search(r'\b' + re.escape(subject) + r'\b', title, re.I):
        return None
    sections = page.get('sections', [])
    if not isinstance(sections, list):
        return None
    text = ' '.join(row.get('text', '') for row in sections if isinstance(row, dict) and isinstance(row.get('text'), str))
    if 'REGULAR SEASON' not in text.upper():
        return None
    # The HTML title can be generic while the extracted schedule heading names
    # its season. Use only the heading, never a year mentioned in a game/article.
    heading = text[:250].split('PRESEASON', 1)[0]
    years = set(re.findall(r'\b20\d{2}\b', title + ' ' + heading))
    if len(years) != 1:
        return None
    year = int(next(iter(years)))
    today = today or date.today()
    if year != today.year:
        return None
    text = re.split(r'REGULAR SEASON', text, maxsplit=1, flags=re.I)[1]
    pattern = (r'WEEK\s+\d+\s*·\s*(Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+'
               r'(\d{2})/(\d{2})\s*·\s*(\d{1,2}:\d{2})\s*(AM|PM)\s+'
               r'(EDT|EST|ET|CDT|CST|CT|MDT|MST|MT|PDT|PST|PT)\b')
    future = []
    for match in re.finditer(pattern, text, re.I):
        try:
            day = date(year, int(match[2]), int(match[3]))
            datetime.strptime(match[4] + ' ' + match[5].upper(), '%I:%M %p')
        except ValueError:
            return None
        if day.strftime('%a').casefold() != match[1].casefold():
            return None
        if today < day <= today + timedelta(days=45):
            future.append((day, match[4], match[5].upper(), match[6].upper()))
    if not future:
        return None
    nearest = min(row[0] for row in future)
    choices = {row[1:] for row in future if row[0] == nearest}
    if len(choices) != 1:
        return None
    clock, meridiem, zone = next(iter(choices))
    when = f"{nearest.strftime('%A, %B')} {nearest.day} at {clock} {meridiem} {zone}"
    return f"The next listed game is {when}.\n\nSearch sources:\n[Schedule]({url})"


def short_document_quote(prompt, result):
    # A small, single retrieved passage can be quoted faithfully without a model
    # paraphrasing away its nouns or qualifications. Longer synthesis stays in 8B.
    if not (re.match(r"what\b.*\b(?:my|our)\b.*\bideas?\b",clean(prompt))
            or re.match(r"what product\b",clean(prompt))):
        return None
    matches=result.get('matches',[])
    if result.get('error') or not matches:return None
    # Ignore title-only hits when a substantive overview passage is available.
    row=next((m for m in matches if len(m.get('text','').strip())>=120),matches[0])
    text=row.get('text','').strip()
    if not text:return None
    # Keep the beginning of the authoritative passage bounded; the overview is
    # where product identity normally appears, while the source citation remains.
    excerpt=text[:650].rstrip()
    return 'The matching document passage says: '+excerpt+f"\n\n[{row['source']}, chunk {row['chunk']}]"
