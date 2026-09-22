"""Organization around existing safe tools; arithmetic evaluation is not added."""
import re
from .base import Skill

SKILL = Skill('mac_utility','Local clock, app launching and bounded Mac control.',
    '''Use get_current_time for actual local date/time. Never reuse an old clock reading.
Use open_application only to launch a named app, not to control it. Report the actual tool
result. A failed launch is not success. Bounded focus, volume and Apple Music actions
must match the current request and their actual tool result. Podcasts, app quit and
brightness are not supported. Acknowledge all completed requested operations.''',
    ('get_current_time','open_application'), 'conditional', 'direct Python when existing router can resolve safely',
    'current request and actual tool result', 'concise factual completion or failure',
    lambda p: bool(re.search(r'\b(?:time|date|clock|calculator)\b|\b(?:open|launch)\s+',p,re.I)))


def execute_direct(selected, execute, documents, personality):
    import json
    from direct_response import render
    args = {'application_name':selected.application} if selected.application else {}
    choice = {'tool':selected.tool,'arguments':args}
    result = execute({'function':{'name':selected.tool,'arguments':json.dumps(args)}},documents)
    return choice, result, render(selected.tool,result,personality)
