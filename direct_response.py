"""Factual direct-tool response formatting, separate from route selection."""
from datetime import datetime
import json
from pathlib import Path


def render_memory(answer, personality):
    """Presentation only; never change the saved data or operation outcome."""
    if personality == 'kuzco' and '\n' not in answer:
        return answer.rstrip('.') + ', sir.'
    return answer


def render(tool, result, personality):
    path = Path(__file__).resolve().parent / 'personalities' / f'{personality}.direct.json'
    if not path.exists():
        path = path.with_name('default.direct.json')
    wording = json.loads(path.read_text())
    if result.get('error') or (tool == 'open_application' and result.get('opened') is not True):
        return wording['failure']
    if tool == 'get_current_time':
        clock = datetime.fromisoformat(result['local_datetime']).strftime('%I:%M %p').lstrip('0')
        return wording['time'].format(time=clock)
    return wording['opened'].format(application=result['application_name'])
