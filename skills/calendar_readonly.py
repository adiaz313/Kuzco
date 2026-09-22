"""Small direct presentation of explicit Calendar reads; no Calendar Skill yet."""
from datetime import datetime
import json
import time

from calendar_intent import parse


def _when(event):
    if event['all_day']:
        return 'all day'
    start = datetime.fromisoformat(event['start_iso']).astimezone()
    end = datetime.fromisoformat(event['end_iso']).astimezone()
    return start.strftime('%-I:%M %p') + ' to ' + end.strftime('%-I:%M %p')


def _answer(intent, result, personality):
    if result.get('error'):
        return result['error']
    events = result['events']
    suffix = ', sir.' if personality == 'kuzco' else '.'
    if not events:
        if intent.startswith('next_'):
            what = 'timed calendar event' if intent == 'next_timed' else 'calendar event'
            return 'I found no upcoming ' + what + ' in the next 30 days' + suffix
        return 'I found no calendar events for ' + intent + suffix
    if intent.startswith('next_'):
        event = events[0]
        start = datetime.fromisoformat(event['start_iso']).astimezone()
        when = start.strftime('%A at %-I:%M %p') if not event['all_day'] else start.strftime('%A, all day')
        what = 'timed calendar event' if intent == 'next_timed' else 'calendar event'
        return 'Your next ' + what + ' is ' + event['title'] + ', ' + when + suffix
    shown = events[:4]
    parts = [event['title'] + ' (' + _when(event) + ')' for event in shown]
    more = ' There are more events.' if result['truncated'] or len(events) > len(shown) else ''
    return 'On your calendar ' + intent + ': ' + '; '.join(parts) + '.' + more


def handle(prompt, history, personality, execute, debug_print, debug):
    started = time.perf_counter()
    planned = parse(prompt)
    if planned is None:
        return None
    action, args, intent = planned
    result = execute({'function': {'name': action, 'arguments': json.dumps(args)}}, ())
    answer = _answer(intent, result, personality)
    # Calendar contents must not become general conversation/model context.
    history.append([{'role': 'assistant', 'content': json.dumps({
        'calendar_query': intent, 'outcome': 'error' if result.get('error') else 'completed'})}])
    metrics = {'effective': 'CALENDAR_READ', 'routing_s': time.perf_counter() - started,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected integration', 'calendar_read')
    debug_print(debug, 'calendar action', action)
    # Explicit debug may show sensitive events; ordinary logs never do.
    debug_print(debug, 'calendar result', result)
    debug_print(debug, 'final answer', answer)
    return answer, metrics
