"""Small production plans for unambiguous read-only lookups, not a new agent.

The caller executes through the existing policy/tool dispatcher and step budget.
Keep full history in the session; omit it from a self-contained lookup's payload.
"""
import json
import re
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
        return (int(bool(re.search(r'/schedule/?$',path))) * 4
                +int('official' in row.get('title','').lower()) * 2 +scores[i])
    row=max(enumerate(rows),key=rank)[1]
    return row.get('url')


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
