"""Bounded whole-request grammar for local place recommendations."""
import re


def _clean(prompt):
    text = ' '.join(prompt.lower().replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey )?(?:kuzco|cuzco|cusco|kusco|kuzko|cuz go)[\s,.!?—:-]+', '', text)
    text = re.sub(r'^please ', '', text)
    return re.sub(r',? please$', '', text).strip()


def parse(prompt):
    if not isinstance(prompt, str):
        return None
    text = _clean(prompt)
    if re.search(r'\b(?:cheap|cheapest|inexpensive|open now|highest rated|best rated|reviews?|stars?|price)\b', text):
        return 'unsupported', {}, {'reason': 'unsupported_metadata'}
    match = re.fullmatch(
        r'(?:recommend|find)(?: me)?(?: a| some)? '
        r'(lunch|dinner|food|restaurant|somewhere to eat) near my next appointment', text)
    if match:
        item = match[1]
        return 'recommend_places', {'query': 'restaurant', 'calendar_selector': 'next appointment'}, \
               {'query': 'restaurant', 'calendar': True, 'constraint': item}
    match = re.fullmatch(r'where should i (?:get|grab|go for) (coffee|lunch|dinner)(?: nearby)?', text)
    if match:
        item = match[1]
        query = 'coffee' if item == 'coffee' else 'restaurant'
        return 'recommend_places', {'query': query, 'calendar_selector': ''}, \
               {'query': query, 'calendar': False, 'constraint': item}
    if re.fullmatch(r'where should i eat(?: nearby)?', text):
        return 'recommend_places', {'query': 'restaurant', 'calendar_selector': ''}, \
               {'query': 'restaurant', 'calendar': False, 'constraint': 'food'}
    match = re.fullmatch(r'find me somewhere close for (lunch|dinner|coffee)', text)
    if match:
        item = match[1]
        query = 'coffee' if item == 'coffee' else 'restaurant'
        return 'recommend_places', {'query': query, 'calendar_selector': ''}, \
               {'query': query, 'calendar': False, 'constraint': item}
    match = re.fullmatch(r"(?:what's|what is) a good ([a-z0-9][a-z0-9 '&\-]*?) nearby", text)
    if match:
        query = match[1]
        return 'recommend_places', {'query': query, 'calendar_selector': ''}, \
               {'query': query, 'calendar': False, 'constraint': query}
    match = re.fullmatch(r'find me (?:a |some )?([a-z0-9][a-z0-9 &\-]*?) nearby', text)
    if match:
        item = match[1]
        query = 'restaurant' if item in {'lunch', 'dinner', 'somewhere to eat'} else item
        return 'recommend_places', {'query': query, 'calendar_selector': ''}, \
               {'query': query, 'calendar': False, 'constraint': item}
    return None
