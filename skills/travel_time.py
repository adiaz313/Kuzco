"""Grounded deterministic travel-time interpretation over MapKit and EventKit."""
from datetime import datetime, timedelta
import json
import logging
import time

from travel_intent import parse


def _duration(seconds):
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f'{minutes} minute' + ('s' if minutes != 1 else '')
    hours, minutes = divmod(minutes, 60)
    return f"{hours} hour{'s' if hours != 1 else ''}" + (f' {minutes} minutes' if minutes else '')


def _clock(value):
    return value.strftime('%I:%M %p').lstrip('0')


def _error(result, personality):
    suffix = ', sir.' if personality == 'kuzco' else '.'
    messages = {
        'permission_denied': 'Location access is unavailable',
        'location_failed': 'Current location is unavailable',
        'provider_unavailable': 'Apple Maps information is unavailable',
        'no_result': 'I could not resolve that destination',
        'ambiguous': 'I found multiple plausible destinations; please be more specific',
        'destination_unresolved': 'I could not resolve that destination',
        'route_unavailable': 'Apple Maps could not calculate that route',
        'unsupported_mode': 'That transport mode is unsupported',
        'calendar_unavailable': 'I could not read Calendar for that travel request',
        'calendar_event_missing': 'I could not find that upcoming Calendar event',
        'calendar_event_ambiguous': 'I found multiple matching Calendar events; please be more specific',
        'calendar_location_missing': 'I found the Calendar event, but it has no usable location',
        'malformed_result': 'The travel provider returned unusable information'}
    return messages.get(result.get('error'), 'I could not complete that travel calculation') + suffix


def _answer(task, result, personality, now=None):
    suffix = ', sir.' if personality == 'kuzco' else '.'
    if result.get('error'):
        return _error(result, personality), None
    current = (now or datetime.now().astimezone()).replace(microsecond=0)
    try:
        seconds = round(result['expected_travel_seconds'])
        if type(result['expected_travel_seconds']) not in (int, float) or seconds < 0 \
                or result['mode'] not in {'driving', 'walking', 'transit', 'cycling'}:
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        return _error({'error': 'malformed_result'}, personality), None
    buffer_seconds = task['buffer_minutes'] * 60
    route_words = _duration(seconds)
    mode = result['mode']
    target = datetime.fromisoformat(result['event_start_iso']) if task.get('calendar') else \
             datetime.fromisoformat(task['target_iso']) if task.get('target_iso') else None
    if task['task'] == 'duration':
        if target and target <= current:
            return 'That Calendar event has already started' + suffix, None
        answer = f'The current {mode} estimate is about {route_words}'
        if task['buffer_minutes']:
            answer += f', plus your {task["buffer_minutes"]}-minute buffer'
        context = {'mode': mode, 'route_seconds': seconds, 'target_iso': target.isoformat() if target else None,
                   'buffer_minutes': task['buffer_minutes']}
        return answer + suffix, context
    if target <= current:
        label = 'Calendar event has already started' if task.get('calendar') else 'target time has already passed'
        return 'That ' + label + suffix, None
    departure = target - timedelta(seconds=seconds + buffer_seconds)
    arrival = current + timedelta(seconds=seconds + buffer_seconds)
    context = {'mode': mode, 'route_seconds': seconds, 'target_iso': target.isoformat(),
               'departure_iso': departure.isoformat(), 'buffer_minutes': task['buffer_minutes']}
    buffer_words = f' including your {task["buffer_minutes"]}-minute buffer' if task['buffer_minutes'] else ''
    if task['task'] == 'leave':
        if departure <= current:
            return (f'You would need to leave now. The current {mode} estimate is about {route_words}'
                    + buffer_words + suffix), context
        return (f'Leave by about {_clock(departure)}. The current {mode} estimate is {route_words}'
                + buffer_words + suffix), context
    margin = round((target - arrival).total_seconds() / 60)
    if margin < 0:
        answer = f'The current estimate has you arriving about {abs(margin)} minutes after {_clock(target)}'
    elif margin < 10:
        answer = f'It looks tight; the current estimate has you arriving about {margin} minutes before {_clock(target)}'
    else:
        answer = f'The current estimate has you arriving about {margin} minutes before {_clock(target)}'
    return answer + buffer_words + suffix, context


def _previous(history):
    if not history:
        return None
    try:
        value = json.loads(history[-1][-1]['content']).get('travel_context')
        if (isinstance(value, dict) and set(value) <= {'mode', 'route_seconds', 'target_iso',
                'departure_iso', 'buffer_minutes'} and isinstance(value.get('departure_iso'), str)):
            return value
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def handle(prompt, history, personality, execute, debug_print, debug):
    plan = parse(prompt)
    if not plan:
        return None
    started = time.perf_counter()
    action, arguments, task = plan
    if action == 'unsupported':
        answer = ('That travel mode is unsupported' if task['task'] == 'unsupported_mode'
                  else 'That buffer is outside the supported range') + (', sir.' if personality == 'kuzco' else '.')
        result = None; context = None
    elif action == 'followup':
        context = _previous(history)
        if not context:
            return None
        departure = datetime.fromisoformat(context['departure_iso'])
        seconds = round((departure - datetime.now().astimezone()).total_seconds())
        if seconds <= 0:
            answer = 'You need to leave now' + (', sir.' if personality == 'kuzco' else '.')
        else:
            answer = 'You have about ' + _duration(seconds) + ' before you need to leave' + (', sir.' if personality == 'kuzco' else '.')
        result = None
    else:
        call = {'tool': action, 'arguments': arguments}
        result = execute({'function': {'name': action, 'arguments': json.dumps(arguments)}}, ())
        answer, context = _answer(task, result, personality)
    turn = [{'role': 'user', 'content': prompt}]
    if action not in {'unsupported', 'followup'}:
        turn.extend([{'role': 'assistant', 'content': json.dumps({'tool': action, 'arguments': arguments})},
                     {'role': 'user', 'content': json.dumps({'tool': action,
                         'tool_result': {'outcome': 'error' if result.get('error') else 'completed'},
                         'tool_call_id': 'call_1'})}])
    final = {'answer': answer}
    if context:
        final['travel_context'] = context
    turn.append({'role': 'assistant', 'content': json.dumps(final)})
    history.append(turn)
    logging.getLogger('kuzco.background').info('Travel skill calendar=%s outcome=%s mode=%s',
        bool(task.get('calendar')), 'error' if result and result.get('error') else 'success', arguments.get('mode', 'reused'))
    metrics = {'effective': 'TRAVEL_TIME', 'routing_s': 0,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected Skill', 'travel_time')
    debug_print(debug, 'travel result summary', {'outcome': 'error' if result and result.get('error') else 'completed',
        'calendar': bool(task.get('calendar')), 'mode': arguments.get('mode', 'reused')})
    debug_print(debug, 'final answer', answer)
    return answer, metrics
