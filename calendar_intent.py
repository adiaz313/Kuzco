"""Only explicit, complete Calendar requests enter the Phase 5 direct path."""
from datetime import datetime, timedelta
import re


def parse(prompt, now=None):
    if not isinstance(prompt, str):
        return None
    text = ' '.join(prompt.lower().replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey )?(?:kuzco|cuzco|cusco|kusco|kuzko|cuz go)[\s,.!?—:-]+', '', text)
    text = re.sub(r'^please ', '', text)
    text = re.sub(r'^(?:can|could|would) you (?:please )?(?:tell me )?', '', text)
    text = re.sub(r',? please$', '', text)
    if re.fullmatch(r"(?:what(?:'s| is)|show me|tell me) (?:on )?my calendar (?:for )?(today|tomorrow)|"
                    r"what do i have on my calendar (today|tomorrow)", text):
        day = 'tomorrow' if 'tomorrow' in text else 'today'
        current = now if now is not None else datetime.now().astimezone()
        return ('calendar_day', {'day': (current.date() + timedelta(days=day == 'tomorrow')).isoformat()}, day)
    match = re.fullmatch(r"(?:what(?:'s| is)|when is) my next (?:calendar )?(event|meeting|appointment)", text)
    if match:
        kind = 'timed' if match[1] in {'meeting', 'appointment'} else 'event'
        return ('calendar_next', {'kind': kind}, 'next_' + kind)
    return None
