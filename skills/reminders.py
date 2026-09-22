"""Direct Reminders responses; no model inference or unsolicited list access."""
from datetime import datetime
import json
import logging
import time

from reminder_intent import parse


def handle(prompt, history, personality, execute, debug_print, debug):
    started = time.perf_counter()
    plan = parse(prompt)
    if plan is None:
        return None
    title = ''
    if plan[0] == 'clarify':
        answer = 'When should I remind you? “Monday morning” or “Monday at 3 PM” will do.'
        result = None
    elif plan[0] == 'clarify_action':
        answer = 'Which reminder? Please say its name, for example, “mark oil change complete.”'
        result = None
    elif plan[0] == 'clarify_list':
        answer = 'I can list your incomplete reminders. Please ask, “What reminders do I have?”'
        result = None
    else:
        name, args = plan
        title = args.get('title', '')
        result = execute({'function': {'name': name, 'arguments': json.dumps(args)}}, ())
        if result.get('error'):
            error = result['error'].lower()
            category = ('permission' if 'permission' in error or 'access was denied' in error else
                        'selection' if 'matching reminder' in error or 'more than one' in error else
                        'policy' if 'security policy' in error else 'native')
            logging.getLogger('kuzco.background').info(
                'Reminder action failed action=%s category=%s (content omitted)', name, category)
        if result.get('error'):
            answer = result['error']
        elif name == 'reminders_create':
            answer = 'Added ' + title + (' for ' + datetime.fromisoformat(args['due_iso']).strftime('%A, %B %-d at %-I:%M %p') if args['due_iso'] else ' to your reminders') + '.'
        elif name == 'reminders_complete':
            answer = 'Marked ' + title + ' complete.'
        elif name == 'reminders_remove':
            answer = 'Removed ' + title + ' from your reminders.'
        else:
            items = result.get('items', [])
            if not items:
                answer = 'You have no incomplete reminders.'
            else:
                answer = 'Your reminders: ' + '; '.join(item['title'] for item in items[:10])
                if len(items) > 10 or result.get('truncated'):
                    answer += '; and more'
                answer += '.'
        if personality == 'kuzco' and not result.get('error'):
            answer = answer[:-1] + ', sir.'
    # Reminder contents are private. Keep only a small action/outcome marker in
    # session history, so unrelated later Llama calls never receive the list.
    history.append([{'role': 'assistant', 'content': json.dumps({
        'reminder_action': plan[0], 'outcome': 'error' if result and result.get('error') else 'completed'})}])
    metrics = {'effective': 'REMINDERS', 'routing_s': time.perf_counter() - started,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected Skill', 'reminders')
    if result is not None:
        debug_print(debug, 'reminder action', plan[0])
        debug_print(debug, 'reminder result', {'error': result.get('error'),
            'created': result.get('created'), 'completed': result.get('completed'),
            'removed': result.get('removed'), 'count': len(result.get('items', [])),
            'truncated': result.get('truncated')})
    debug_print(debug, 'final answer', answer)
    return answer, metrics
