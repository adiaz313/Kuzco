"""Bounded deterministic grammar for the Phase 9 Travel Time Skill."""
from datetime import datetime, timedelta
import re


MODES = {'drive': 'driving', 'driving': 'driving', 'walk': 'walking',
         'walking': 'walking', 'cycle': 'cycling', 'cycling': 'cycling',
         'transit': 'transit'}


def _clean(prompt):
    text = ' '.join(prompt.lower().replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey )?(?:kuzco|cuzco|cusco|kusco|kuzko|cuz go)[\s,.!?—:-]+', '', text)
    text = re.sub(r'^please ', '', text)
    return re.sub(r',? please$', '', text).strip()


def _deadline(value, now):
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s+(today|tomorrow))?', value)
    if not match:
        return None
    hour, minute = int(match[1]), int(match[2] or 0)
    if not 0 <= minute <= 59 or not 1 <= hour <= 12:
        return None
    marker = match[3]
    if marker == 'am':
        hour %= 12
    elif marker == 'pm' or marker is None and hour <= 7:
        hour = hour % 12 + 12
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if match[4] == 'tomorrow':
        target += timedelta(days=1)
    return target


def _buffer(text):
    match = re.search(r'(?:,?\s+(?:with|and give me))\s+(\d{1,3})\s+minutes?(?:\s+to park|\s+of buffer)?$', text)
    if not match:
        return text, 0
    value = int(match[1])
    if value > 180:
        return None, None
    return text[:match.start()].strip(), value


def _mode(text):
    for word, mode in MODES.items():
        if re.search(rf'\b{word}\b', text):
            return mode
    return 'driving'


def parse(prompt, now=None):
    if not isinstance(prompt, str):
        return None
    text, buffer = _buffer(_clean(prompt))
    if text is None:
        return ('unsupported', {}, {'task': 'unsupported_buffer'})
    current = (now or datetime.now().astimezone()).replace(microsecond=0)
    if re.fullmatch(r'how much time do i have before i need to leave', text):
        return ('followup', {}, {'task': 'remaining'})
    if re.search(r'\b(?:fly|flying|scooter|scootering)\b', text):
        return ('unsupported', {}, {'task': 'unsupported_mode'})

    calendar = re.fullmatch(r"(when should i leave|how long (?:will|does) it take(?: me)?) (?:to get to |for )my (next appointment|[a-z0-9][a-z0-9 '\-]* appointment)", text)
    if calendar:
        task = 'leave' if calendar[1].startswith('when') else 'duration'
        args = {'destination': '', 'calendar_selector': calendar[2], 'mode': _mode(text)}
        return 'travel_route', args, {'task': task, 'target_iso': None, 'buffer_minutes': buffer, 'calendar': True}

    match = re.fullmatch(r'how long (?:will|does|would) it take(?: me)? to (?:(drive|walk|cycle)|get) to (.+)', text)
    if match:
        mode = MODES.get(match[1], _mode(text))
        return 'travel_route', {'destination': match[2], 'calendar_selector': '', 'mode': mode}, \
               {'task': 'duration', 'target_iso': None, 'buffer_minutes': buffer, 'calendar': False}

    match = re.fullmatch(r'(can i (?:make it|get)|when should i leave(?: to get)?) to (.+) by (.+)', text)
    if match:
        target = _deadline(match[3], current)
        if target is None:
            return None
        task = 'feasibility' if match[1].startswith('can') else 'leave'
        return 'travel_route', {'destination': match[2], 'calendar_selector': '', 'mode': _mode(text)}, \
               {'task': task, 'target_iso': target.isoformat(), 'buffer_minutes': buffer, 'calendar': False}
    return None
