"""Cheap social replies: compositional variation, no network or model context."""
import random
import re
import json
from pathlib import Path
from .base import Skill


def matches(text):
    return bool(re.fullmatch(r"(?:hello|hi|hey)(?: kuzco)?|good (?:morning|afternoon|evening)|how are you(?: doing)?|what's up", text))


def respond(personality, previous=None):
    path=Path(__file__).resolve().parents[1]/'personalities'/f'{personality}.greeting.json'
    if not path.exists():path=path.with_name('default.greeting.json')
    wording=json.loads(path.read_text())
    openings,endings=wording['openings'],wording['endings']
    choices = [a + ' ' + b for a in openings for b in endings if a + ' ' + b != previous]
    return random.choice(choices)


SKILL=Skill('greeting','Immediate bounded social replies.','No tools, network or model calls.',
    (), 'no','compositional local wording','current greeting and previous response only',
    'short varied greeting',matches)
