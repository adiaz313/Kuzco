"""Cheap social replies with at most one bounded, grounded observation."""
import random
import re
import json
from pathlib import Path
from .base import Skill


def matches(text):
    return bool(re.fullmatch(r"(?:hello|hi|hey)(?: kuzco)?|good (?:morning|afternoon|evening)|how are you(?: doing)?|what's up", text))


def respond(personality, previous=None, daypart=None, observation=None):
    path=Path(__file__).resolve().parents[1]/'personalities'/f'{personality}.greeting.json'
    if not path.exists():path=path.with_name('default.greeting.json')
    wording=json.loads(path.read_text())
    openings,endings=wording['openings'],wording['endings']
    if daypart:
        addressed = f'Good {daypart}, sir.' if personality == 'kuzco' else f'Good {daypart}.'
        openings = [addressed, *openings]
    choices = [a + ' ' + b for a in openings for b in endings
               if a + ' ' + b + ((' ' + observation) if observation else '') != previous]
    base = random.choice(choices)
    return base if not observation else base + ' ' + observation


SKILL=Skill('greeting','Immediate bounded social replies.','Optional context is bounded and never authoritative.',
    ('get_weather','greeting_calendar_context'), 'no','deterministic local composition','daypart and sanitized optional signals only',
    'short varied greeting',matches)
