"""Deterministic presentation for grounded Phase 8 MapKit primitives."""
from datetime import datetime
import json
import time

from maps_intent import parse


def _duration(seconds):
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f'{minutes} minute' + ('s' if minutes != 1 else '')
    hours, minutes = divmod(minutes, 60)
    result = f'{hours} hour' + ('s' if hours != 1 else '')
    return result + (f' {minutes} minutes' if minutes else '')


def _distance(meters):
    miles = meters / 1609.344
    return f'{miles:.1f} miles' if miles < 10 else f'{round(miles)} miles'


def _choices(result):
    values = result.get('candidates', result.get('results', []))
    return values if isinstance(values, list) else []


def _answer(kind, result, personality):
    suffix = ', sir.' if personality == 'kuzco' else '.'
    error = result.get('error')
    choices = _choices(result)
    if error == 'ambiguous' or (kind == 'place' and len(choices) > 1):
        cities = sorted({item.get('city') for item in choices if item.get('city')})
        area = (' in ' + cities[0]) if len(cities) == 1 else ''
        return ('I found several plausible matches' + area +
                '. Please specify a neighborhood, street, or exact location' + suffix)
    if error == 'no_result' or (kind == 'place' and not choices and not error):
        return 'I could not find that place' + suffix
    errors = {'permission_denied': 'Location access is unavailable',
              'location_failed': 'Current location is unavailable',
              'timeout': 'The Maps request timed out',
              'provider_unavailable': 'Apple Maps information is unavailable',
              'route_unavailable': 'Apple Maps could not calculate that route',
              'unsupported_mode': 'That transport mode is unsupported',
              'origin_unresolved': 'I could not resolve the route origin',
              'destination_unresolved': 'I could not resolve the destination',
              'open_failed': 'Apple Maps could not open that route'}
    if error:
        return errors.get(error, 'The Maps request could not be completed') + suffix
    if kind == 'place':
        item = choices[0]
        return f"{item['name']} is in {item.get('city') or item['address']}" + suffix
    if kind == 'open':
        item = result['destination']
        return f"Directions to {item['name']} are open in Apple Maps" + suffix
    item = result['destination']
    return (f"The current {result['mode']} estimate to {item['name']} is "
            f"{_duration(result['expected_travel_seconds'])} over {_distance(result['distance_meters'])}" + suffix)


def handle(prompt, history, personality, execute, debug_print, debug):
    plan = parse(prompt)
    if not plan:
        return None
    started = time.perf_counter()
    action, arguments, kind = plan
    call = {'tool': action, 'arguments': arguments}
    result = execute({'function': {'name': action, 'arguments': json.dumps(arguments)}}, ())
    answer = _answer(kind, result, personality)
    # Retain the user's request and final answer, but no coordinates, route
    # payload, provider identifiers, or raw place candidates.
    turn = [{'role': 'user', 'content': prompt},
            {'role': 'assistant', 'content': json.dumps(call)},
            {'role': 'user', 'content': json.dumps({'tool': action,
                'tool_result': {'outcome': 'error' if result.get('error') else 'completed'},
                'tool_call_id': 'call_1'})},
            {'role': 'assistant', 'content': json.dumps({'answer': answer})}]
    history.append(turn)
    metrics = {'effective': 'MAPS_PLACES', 'routing_s': 0,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected integration', 'maps_places')
    debug_print(debug, 'Maps action', {'tool': action, 'arguments': arguments})
    debug_print(debug, 'Maps result summary', {'outcome': 'error' if result.get('error') else 'completed',
        'candidate_count': len(_choices(result))})
    debug_print(debug, 'final answer', answer)
    return answer, metrics
