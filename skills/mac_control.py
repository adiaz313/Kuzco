"""Fast bounded Mac actions; source wording is the policy authority, not a model."""
import json
import time

from mac_intent import parse


def handle(prompt, history, personality, execute, debug_print, debug):
    started = time.perf_counter()
    planned = parse(prompt)
    if planned is None:
        return None
    name, args = planned
    result = (None if name in {'clarify_media', 'unsupported_quit',
                              'unsupported_brightness', 'unsupported_podcast', 'unsupported_timer'} else
              execute({'function': {'name': name, 'arguments': json.dumps(args)}}, ()))
    if name == 'clarify_media':
        answer = 'Please say “play NAME song” or “play my NAME playlist.” Podcast playback is not supported yet.'
    elif name == 'unsupported_quit':
        answer = 'I cannot quit applications yet, because the voice confirmation step is not in place.'
    elif name == 'unsupported_brightness':
        answer = 'I cannot reliably change this Mac’s display brightness yet.'
    elif name == 'unsupported_podcast':
        answer = 'I cannot control Apple Podcasts reliably yet.'
    elif name == 'unsupported_timer':
        answer = 'I cannot create timers yet.'
    elif result.get('error'):
        answer = result['error']
    elif name == 'focus_application':
        answer = 'Switched to ' + args['application_name'] + '.'
    elif name == 'volume_adjust':
        answer = 'Volume ' + args['direction'] + ' to ' + str(result['percent']) + ' percent.'
    elif name == 'volume_set':
        answer = 'Volume set to ' + str(result['percent']) + ' percent.'
    elif name == 'volume_mute':
        answer = 'Muted.' if result.get('muted') is True else 'Unmuted.'
    elif name == 'music_transport':
        action = args['action']
        answer = {'play': 'Music is playing.', 'resume': 'Music resumed.',
                  'pause': 'Music paused.', 'next': 'Music accepted the next-track request.',
                  'previous': 'Music accepted the previous-track request.'}[action]
    else:
        answer = 'Music is playing the selected ' + args['kind'] + '.'
    if personality == 'kuzco' and result is not None and not result.get('error'):
        answer = answer[:-1] + ', sir.'
    # Native media/library details are not retained beyond this turn.
    history.append([{'role': 'assistant', 'content': json.dumps({
        'mac_action': name, 'outcome': 'clarification' if result is None else
        'error' if result.get('error') else 'completed'})}])
    metrics = {'effective': 'MAC_CONTROL', 'routing_s': time.perf_counter() - started,
               'total_s': time.perf_counter() - started, 'llm_calls': 0}
    debug_print(debug, 'Selected Skill', 'mac_utility')
    debug_print(debug, 'mac action', name)
    debug_print(debug, 'mac result', result)
    debug_print(debug, 'final answer', answer)
    return answer, metrics
