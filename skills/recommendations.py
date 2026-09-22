"""Concise deterministic selection from grounded MapKit candidates."""
import json
import logging
import time

from recommendation_intent import parse


def _miles(meters):
    miles = meters / 1609.344
    return f'{miles:.1f} miles' if miles < 10 else f'{round(miles)} miles'


def _bounded(result):
    unique = {}
    for item in result.get('results', []):
        key = item.get('provider_id') or (item.get('name', '').casefold(), item.get('city', '').casefold(),
                                          item.get('address', '').casefold())
        if key not in unique:
            unique[key] = item
    return sorted(unique.values(), key=lambda item: (
        item.get('distance_meters', float('inf')), item.get('name', '').casefold()))[:5]


def _error(result, personality):
    suffix = ', sir.' if personality == 'kuzco' else '.'
    messages = {
        'permission_denied': 'Location access is unavailable',
        'location_failed': 'Current location is unavailable',
        'provider_unavailable': 'Apple Maps information is unavailable',
        'timeout': 'The Maps request timed out',
        'no_result': 'I could not find a nearby grounded match',
        'calendar_unavailable': 'I could not read Calendar for that recommendation',
        'calendar_event_missing': 'I could not find an upcoming Calendar event',
        'calendar_location_missing': 'The next Calendar event has no usable location',
        'ambiguous': 'I could not resolve the requested search area',
        'destination_unresolved': 'I could not resolve the requested search area',
        'invalid_request': 'That recommendation request is invalid'}
    return messages.get(result.get('error'), 'I could not complete that place recommendation') + suffix


def _answer(task, result, personality):
    suffix = ', sir.' if personality == 'kuzco' else '.'
    if result.get('error'):
        return _error(result, personality)
    choices = _bounded(result)
    if not choices:
        return 'I could not find a nearby grounded match' + suffix
    first = choices[0]
    distance = first.get('distance_meters')
    if distance is None:
        return 'I found candidates, but Apple Maps did not provide enough distance information to choose responsibly' + suffix
    answer = f"{first['name']} is the closest grounded match at about {_miles(distance)} away"
    alternatives = [item['name'] for item in choices[1:3]]
    if alternatives:
        answer += '. Nearby alternatives are ' + (' and '.join(alternatives))
    if task['query'] not in {'coffee', 'coffee shop', 'restaurant'}:
        answer += f'. Apple Maps returned these for “{task["query"]},” but I cannot verify specific menu items'
    return answer + suffix


def handle(prompt, history, personality, execute, debug_print, debug):
    plan = parse(prompt)
    if not plan:
        return None
    started = time.perf_counter()
    action, arguments, task = plan
    if action == 'unsupported':
        answer = ('Apple Maps does not provide reliable ratings, prices, reviews, or current hours for that request'
                  + (', sir.' if personality == 'kuzco' else '.'))
        result = None
    else:
        result = execute({'function': {'name': action, 'arguments': json.dumps(arguments)}}, ())
        answer = _answer(task, result, personality)
    history.append([{'role': 'user', 'content': prompt},
        {'role': 'assistant', 'content': json.dumps({'recommendation_interaction':
            'error' if result and result.get('error') else 'completed'})},
        {'role': 'assistant', 'content': json.dumps({'answer': answer})}])
    logging.getLogger('kuzco.background').info('Recommendation skill calendar=%s outcome=%s candidates=%s',
        bool(task.get('calendar')), 'error' if result and result.get('error') else 'success',
        len(_bounded(result)) if result else 0)
    metrics = {'effective': 'RECOMMENDATIONS', 'routing_s': 0,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected Skill', 'recommendations')
    debug_print(debug, 'recommendation result summary', {'outcome':
        'error' if result and result.get('error') else 'completed',
        'candidate_count': len(_bounded(result)) if result else 0,
        'calendar': bool(task.get('calendar'))})
    debug_print(debug, 'final answer', answer)
    return answer, metrics
