"""Whole-request clock/date recognition. No calendar actions or inferred zones."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .base import Skill


def parse(text):
    text=re.sub(r'^(?:can|could|would) you (?:please )?(?:tell me |give me )', '', text)
    text=re.sub(r'^tell me (?:please )?', '', text)
    match = re.fullmatch(r"(?:what time (?:is it|it is)|what(?: is|'s) the (?:(?:current|local) )*time|the (?:(?:current|local) )*time)(?: (?:right )?now)?(?: in (utc|london|new york|tokyo))?", text)
    if match:
        return ('time', match[1])
    if re.fullmatch(r"what(?:'s| is) (?:today's date|the date)|what date is it|what day is it(?: today)?", text):
        return ('date', None)
    return None


def respond(intent, result, personality):
    if result.get('error'):
        return 'I could not read the clock' + (', sir.' if personality == 'kuzco' else '.')
    now = datetime.fromisoformat(result['local_datetime'])
    kind, zone = intent
    if zone:
        now = now.astimezone(ZoneInfo({'utc':'UTC','london':'Europe/London','new york':'America/New_York','tokyo':'Asia/Tokyo'}[zone]))
    value = now.strftime('%A, %B %d, %Y') if kind == 'date' else now.strftime('%I:%M %p').lstrip('0')
    return "It's " + value + (' in ' + zone.title() if zone else '') + (', sir.' if personality == 'kuzco' else '.')


SKILL=Skill('timekeeping','Immediate local clock and bounded named timezones.',
    'Read the current clock through policy; never use a cached reading.',('get_current_time',),
    'no','deterministic parsing and formatting','current request and clock result','concise time or date',lambda p:bool(parse(p)))
