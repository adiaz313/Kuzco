"""Small explicit registry; ambiguous/mixed requests retain general orchestration."""
from .base import Skill
from .web_research import SKILL as WEB
from .document_analysis import SKILL as DOCUMENT
from .mac_utility import SKILL as MAC
from router import route, Destination
import re

REGISTRY = (WEB, DOCUMENT, MAC)
# Production pre-model Skills; kept separate from the unchanged LLM Skill selector.
from .greeting import SKILL as GREETING
from .timekeeping import SKILL as TIMEKEEPING
from .weather import SKILL as WEATHER
FAST_REGISTRY = (WEATHER, TIMEKEEPING, GREETING)
GENERAL = Skill('general','General reasoning and conservative mixed-task fallback.',
    '''For local date/time use get_current_time; application launches use open_application.
Personal document questions use search_documents. Current external facts require search_web,
read_webpage or research_web; never guess current facts without evidence. If a task crosses
categories, coordinate the available tools within the budget. Stable knowledge needs no tool.''',
    None,'yes','existing general agent','request and recent history','concise accurate response',lambda p:True)
CONVERSATION = Skill('general',GENERAL.description,'Answer this stable conversational request directly.',
    (),'yes','local 8B answer','request and recent history','concise accurate response',lambda p:True)


def select(prompt):
    if WEB.plan(prompt):
        return WEB
    if re.fullmatch(r'(?:open|launch)\s+(?:it|that)[.!?]?',prompt.strip(),re.I):
        return GENERAL
    matches = [skill for skill in REGISTRY if skill.matches(prompt)]
    if len(matches) == 1:
        return matches[0]
    if not matches and route(prompt).destination == Destination.FAST:
        return CONVERSATION
    return GENERAL
