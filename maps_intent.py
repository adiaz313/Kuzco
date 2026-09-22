"""Whole-request grammar for bounded Phase 8 place and route primitives."""
import re


def _clean(prompt):
    text = ' '.join(prompt.lower().replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey )?(?:kuzco|cuzco|cusco|kusco|kuzko|cuz go)[\s,.!?—:-]+', '', text)
    text = re.sub(r'^please ', '', text)
    text = re.sub(r'^(?:can|could|would) you (?:please )?', '', text)
    return re.sub(r',? please$', '', text).strip()


def parse(prompt):
    if not isinstance(prompt, str):
        return None
    text = _clean(prompt)
    match = re.fullmatch(r'(?:find(?: me)?|where can i (?:find|get)) (?:a |some )?(?:place to get )?(.+?) near me', text)
    if match:
        return 'places_search', {'query': match[1], 'near': 'true'}, 'place'
    match = re.fullmatch(r'(?:where is|find|look up) (.+?)( near me)?', text)
    if match:
        return 'places_search', {'query': match[1], 'near': 'true' if match[2] else 'false'}, 'place'
    match = re.fullmatch(r'(?:how far away is|how long (?:does|would) it take to (?:drive|walk|cycle|get) to) (.+?)(?: from here)?', text)
    if match:
        mode = 'walking' if 'walk' in text else 'cycling' if 'cycle' in text else 'driving'
        return 'route_estimate', {'origin': 'current location', 'destination': match[1], 'mode': mode}, 'route'
    match = re.fullmatch(r'how long is the (?:(driving|walking|transit|cycling) )?route from (.+) to (.+)', text)
    if match:
        return 'route_estimate', {'origin': match[2], 'destination': match[3],
                                  'mode': match[1] or 'driving'}, 'route'
    match = re.fullmatch(r'open (?:(driving|walking|transit|cycling) )?directions to (.+)', text)
    if match:
        return 'maps_open_route', {'destination': match[2], 'mode': match[1] or 'driving'}, 'open'
    return None
