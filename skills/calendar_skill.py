"""Deterministic schedule interpretation over bounded Phase 5 EventKit data."""
from datetime import datetime, timedelta
import json
import re
import time


def _clean(prompt):
    text = ' '.join(prompt.lower().replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey )?(?:kuzco|cuzco|cusco|kusco|kuzko|cuz go)[\s,.!?—:-]+', '', text)
    text = re.sub(r'^please ', '', text)
    text = re.sub(r'^(?:can|could|would) you (?:please )?(?:tell me )?', '', text)
    return re.sub(r',? please$', '', text)


def _day_bounds(now, offset=0):
    day = (now + timedelta(days=offset)).date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=now.tzinfo)
    return start, start + timedelta(days=1)


def _args(start, end, kind='all'):
    return {'start_iso': start.isoformat(timespec='seconds'),
            'end_iso': end.isoformat(timespec='seconds'), 'kind': kind}


def parse(prompt, now=None):
    if not isinstance(prompt, str):
        return None
    text = _clean(prompt)
    current = (now if now is not None else datetime.now().astimezone()).replace(second=0, microsecond=0)
    if re.fullmatch(r"what does my day look like|what(?:'s| is) my day like|what does today look like", text):
        start, end = _day_bounds(current)
        return 'calendar_range', _args(start, end), {'task': 'overview', 'period': 'today'}
    if re.fullmatch(r"what does tomorrow look like|what(?:'s| is) tomorrow like", text):
        start, end = _day_bounds(current, 1)
        return 'calendar_range', _args(start, end), {'task': 'overview', 'period': 'tomorrow'}
    if re.fullmatch(r"how busy is my afternoon|what do i have this afternoon|"
                    r"what(?:'s| is) my afternoon like|what does my afternoon look like", text):
        start, end = _day_bounds(current)
        return 'calendar_range', _args(start + timedelta(hours=12), start + timedelta(hours=17)), \
               {'task': 'period', 'period': 'this afternoon'}
    if re.fullmatch(r"do i have anything after lunch", text):
        start, end = _day_bounds(current)
        return 'calendar_range', _args(start + timedelta(hours=13), end), \
               {'task': 'period', 'period': 'after lunch'}
    match = re.fullmatch(r"(?:how much time do i have before|how long until) my next (meeting|appointment|event)", text)
    if match:
        kind = 'timed' if match[1] in {'meeting', 'appointment'} else 'all'
        return 'calendar_range', _args(current, current + timedelta(days=30), kind), \
               {'task': 'until', 'kind': kind}
    match = re.fullmatch(r"when is my (first|last) (?:meeting|appointment|timed event) (today|tomorrow)", text)
    if match:
        start, end = _day_bounds(current, match[2] == 'tomorrow')
        return 'calendar_range', _args(start, end, 'timed'), \
               {'task': match[1], 'period': match[2]}
    if re.fullmatch(r"do i have (?:any )?back-to-back (?:meetings|appointments|timed events)(?: today)?", text):
        start, end = _day_bounds(current)
        return 'calendar_range', _args(start, end, 'timed'), \
               {'task': 'back_to_back', 'period': 'today'}
    return None


def _events(result):
    return sorted(result.get('events', []), key=lambda event: (event['start_iso'], event['end_iso'], event['title']))


def _clock(event):
    if event['all_day']:
        return 'all day'
    return datetime.fromisoformat(event['start_iso']).astimezone().strftime('%-I:%M %p')


def _summary(task, result, now, personality):
    if result.get('error'):
        return result['error']
    events = _events(result)
    suffix = ', sir.' if personality == 'kuzco' else '.'
    name, period = task['task'], task.get('period', '')
    if not events:
        if name == 'until':
            return 'I found no upcoming calendar event in the next 30 days' + suffix
        if name in {'first', 'last'}:
            return 'Your calendar has no timed events ' + period + suffix
        if name == 'back_to_back':
            return 'Your calendar shows no back-to-back timed events today' + suffix
        return 'Your calendar has no events ' + period + suffix
    if name in {'overview', 'period'}:
        timed = [event for event in events if not event['all_day']]
        all_day = len(events) - len(timed)
        if all_day == len(events):
            count = str(all_day) + (' all-day event' if all_day == 1 else ' all-day events')
        elif all_day:
            count = str(len(events)) + ' events, including ' + str(all_day) + ' all-day'
        else:
            count = str(len(events)) + (' event' if len(events) == 1 else ' events')
        detail = ' First: ' + events[0]['title'] + ' at ' + _clock(events[0]) + '.'
        if len(events) > 1:
            detail += ' Last: ' + events[-1]['title'] + ' at ' + _clock(events[-1]) + '.'
        return 'Your calendar has ' + count + ' ' + period + '.' + detail
    if name == 'until':
        event = events[0]
        start = datetime.fromisoformat(event['start_iso']).astimezone()
        end = datetime.fromisoformat(event['end_iso']).astimezone()
        if start <= now < end:
            return event['title'] + ' is already in progress' + suffix
        seconds = max(0, int((start - now).total_seconds()))
        minutes = (seconds + 30) // 60
        if minutes < 60:
            duration = str(minutes) + (' minute' if minutes == 1 else ' minutes')
        else:
            hours, remainder = divmod(minutes, 60)
            days, hours = divmod(hours, 24)
            parts = []
            if days:
                parts.append(str(days) + (' day' if days == 1 else ' days'))
            if hours:
                parts.append(str(hours) + (' hour' if hours == 1 else ' hours'))
            if not days and remainder:
                parts.append(str(remainder) + ' minutes')
            duration = ' and '.join(parts)
        return 'You have ' + duration + ' before ' + event['title'] + suffix
    if name in {'first', 'last'}:
        event = events[0] if name == 'first' else events[-1]
        return 'Your ' + name + ' timed calendar event ' + period + ' is ' + event['title'] + ' at ' + _clock(event) + suffix
    pairs = []
    for previous, following in zip(events, events[1:]):
        gap = (datetime.fromisoformat(following['start_iso']) -
               datetime.fromisoformat(previous['end_iso'])).total_seconds()
        if 0 <= gap <= 300:
            pairs.append((previous, following))
    if not pairs:
        return 'Your calendar shows no back-to-back timed events today' + suffix
    first, second = pairs[0]
    return first['title'] + ' and ' + second['title'] + ' are back-to-back at ' + _clock(second) + suffix


def handle(prompt, history, personality, execute, debug_print, debug):
    started = time.perf_counter()
    plan = parse(prompt)
    if plan is None:
        return None
    action, args, task = plan
    result = execute({'function': {'name': action, 'arguments': json.dumps(args)}}, ())
    answer = _summary(task, result, datetime.now().astimezone(), personality)
    history.append([{'role': 'assistant', 'content': json.dumps({
        'calendar_skill': task['task'], 'outcome': 'error' if result.get('error') else 'completed'})}])
    metrics = {'effective': 'CALENDAR_SKILL', 'routing_s': time.perf_counter() - started,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected Skill', 'calendar')
    debug_print(debug, 'calendar task', task)
    debug_print(debug, 'calendar result', result)
    debug_print(debug, 'final answer', answer)
    return answer, metrics
