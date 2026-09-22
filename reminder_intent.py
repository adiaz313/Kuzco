"""Small, conservative parser for whole-request Reminders commands.

Only the user's current utterance is parsed. Source text and model output never
become authorization for a reminder mutation.
"""
from datetime import datetime, timedelta
import os
import re
from zoneinfo import ZoneInfo

NUMBERS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
           'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
           'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty': 40,
           'forty-five': 45, 'sixty': 60}
WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
DAYPART_HOURS = {'morning': 9, 'afternoon': 15, 'evening': 19, 'night': 20}


def local_zone():
    path = os.path.realpath('/etc/localtime')
    marker = '/zoneinfo/'
    if marker not in path:
        raise ValueError('Local timezone is unavailable; set the reminder in Apple Reminders.')
    return ZoneInfo(path.split(marker, 1)[1])


def _number(word):
    return int(word) if word.isdecimal() else NUMBERS.get(word)


def _due(when, now):
    zone = now.tzinfo
    if when == 'tonight':
        when = 'today evening'
    relative = re.fullmatch(r'in (\d{1,4}|[a-z-]+) (minutes?|hours?)', when)
    if relative:
        amount = _number(relative[1])
        if amount is None or not 1 <= amount <= 1440:
            return None
        minutes = amount * (60 if relative[2].startswith('hour') else 1)
        if minutes > 10080:
            return None
        return now + timedelta(minutes=minutes)
    absolute = re.fullmatch(
        r'(?:on )?(next )?(tomorrow|today|' + '|'.join(WEEKDAYS) +
        r')(?: (morning|afternoon|evening|night)| at (1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm))?', when)
    if not absolute:
        return None
    next_word, day, daypart, hour, minute, meridiem = absolute.groups()
    if next_word and day in {'today', 'tomorrow'}:
        return None
    if day == 'today':
        date = now.date()
    elif day == 'tomorrow':
        date = (now + timedelta(days=1)).date()
    else:
        offset = (WEEKDAYS.index(day) - now.weekday()) % 7
        if next_word and offset == 0:
            offset = 7
        date = (now + timedelta(days=offset)).date()
    if hour is None and daypart is None:
        return None  # A day without a time is ambiguous for a notification.
    hour = DAYPART_HOURS[daypart] if daypart else int(hour) % 12 + (12 if meridiem == 'pm' else 0)
    value = datetime(date.year, date.month, date.day, hour, int(minute or 0), tzinfo=zone)
    # Reject nonexistent DST wall times instead of silently shifting the alert.
    if value.astimezone(ZoneInfo('UTC')).astimezone(zone).replace(tzinfo=None) != value.replace(tzinfo=None):
        return None
    if value <= now and day in WEEKDAYS:
        value += timedelta(days=7)
    return value if value > now else None


def parse(prompt, now=None):
    if not isinstance(prompt, str):
        return None
    text = ' '.join(prompt.replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey\s+)?(?:kuzco|cuzco|cusco|kusco|kuzko)[\s,.!?—:-]+', '', text, flags=re.I)
    text = re.sub(r'^please\s+', '', text, flags=re.I)
    text = re.sub(r',?\s+please$', '', text, flags=re.I)
    text = re.sub(r',?\s+(?:kuzco|cuzco|cusco|kusco|kuzko)$', '', text, flags=re.I)
    if re.fullmatch(r"(?:(?:what|which) reminders? (?:do i have|are on my list)(?: (?:today|right now))?|what (?:are|is) my reminders?|do i have any reminders?|what do i (?:need|have) to do|(?:show|list|read)(?: me)? (?:my )?(?:reminders|tasks)|what(?:'s| is) (?:on|in) my (?:reminders|reminder|to-do) list)", text, flags=re.I):
        return 'reminders_list', {}
    if re.fullmatch(r'(?:mark|complete|finish|check off) (?:it|that|this) (?:as )?(?:complete|done)|(?:remove|cancel|delete) (?:it|that|this)(?: reminder)?', text, flags=re.I):
        return 'clarify_action', {}
    match = re.fullmatch(r'(?:mark|complete|finish|check off) (.+?) (?:as )?(?:complete|done)', text, flags=re.I)
    if match:
        return 'reminders_complete', {'title': match[1].strip()}
    match = re.fullmatch(r'(?:complete|finish) (?:my |the )?(.+?) reminder', text, flags=re.I)
    if match:
        return 'reminders_complete', {'title': match[1].strip()}
    match = re.fullmatch(r'(?:cancel|delete|remove) (?:my |the )?(.+?) (?:reminder|from my reminders)', text, flags=re.I)
    if match:
        return 'reminders_remove', {'title': match[1].strip()}
    match = re.fullmatch(r'add (.+?) to (?:my )?(?:reminders|list|to-do list)', text, flags=re.I)
    if match:
        return 'reminders_create', {'title': match[1].strip(), 'due_iso': ''}
    match = re.fullmatch(r'remind me to (.+) on ((?:next )?(?:today|tomorrow|(?:' + '|'.join(WEEKDAYS) + r'))(?: .+)?)', text, flags=re.I)
    if match:
        try:
            now = now or datetime.now(local_zone())
            due = _due('on ' + match[2].lower(), now)
        except ValueError:
            return 'clarify', {}
        if due is None:
            return 'clarify', {}
        return 'reminders_create', {'title': match[1].strip(), 'due_iso': due.isoformat(timespec='seconds')}
    match = re.fullmatch(r'remind me to (.+) (in .+|tonight|(?:next )?(?:today|tomorrow|(?:' + '|'.join(WEEKDAYS) + r'))(?: .+)?)', text, flags=re.I)
    if match:
        try:
            now = now or datetime.now(local_zone())
            due = _due(match[2].lower(), now)
        except ValueError:
            return 'clarify', {}
        if due is None:
            return 'clarify', {}
        return 'reminders_create', {'title': match[1].strip(), 'due_iso': due.isoformat(timespec='seconds')}
    match = re.fullmatch(r'remind me (.+?) to (.+)', text, flags=re.I)
    if match:
        try:
            now = now or datetime.now(local_zone())
            due = _due(match[1].lower(), now)
        except ValueError:
            return 'clarify', {}
        if due is None:
            return 'clarify', {}
        return 'reminders_create', {'title': match[2].strip(), 'due_iso': due.isoformat(timespec='seconds')}
    if text.lower().startswith('remind me '):
        return 'clarify', {}
    if (re.search(r'\breminders?\b', text, flags=re.I)
            and re.match(r'^(?:what|which|show|list|read|do i have)\b', text, flags=re.I)
            and not re.search(r'\b(?:documents?|files?|notes?|web|explain|definition|mean|means)\b', text, flags=re.I)):
        return 'clarify_list', {}
    return None
