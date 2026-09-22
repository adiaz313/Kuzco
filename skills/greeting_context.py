"""Bounded optional context for greetings; only sanitized signals escape workers."""
from contextvars import copy_context
from datetime import datetime
import json
import queue
import threading
import time
from zoneinfo import ZoneInfo


BUDGET_SECONDS = 0.35
CACHE_SECONDS = 300
_cache = {}
_lock = threading.Lock()


def daypart(now=None):
    hour = (now or datetime.now().astimezone()).hour
    return 'morning' if hour < 12 else 'afternoon' if hour < 18 else 'evening'


def _weather_signal(data):
    if not isinstance(data, dict) or data.get('error'):
        return None
    try:
        now = datetime.now(ZoneInfo(data['timezone']))
        current = data['current']
        today = [h for h in data['hours'] if datetime.fromisoformat(h['time']).date() == now.date()
                 and datetime.fromisoformat(h['time']) >= now.replace(minute=0, second=0, microsecond=0)]
        rain = max((h['rain'] for h in today), default=0)
        codes = [current['code'], *(h['code'] for h in today)]
        temperature = current['temperature']
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if any(code >= 95 for code in codes):
        return ('weather', 'Thunderstorms are possible today.')
    if any(code in {71, 73, 75, 77, 85, 86} for code in codes):
        return ('weather', 'Snow is in the forecast today.')
    if rain >= 60:
        return ('weather', 'Rain looks likely today.')
    if temperature <= 25:
        return ('weather', 'It is exceptionally cold outside.')
    if temperature >= 90:
        return ('weather', 'It is exceptionally hot outside.')
    return None


def _calendar_signal(data):
    if not isinstance(data, dict) or data.get('error'):
        return None
    try:
        count = data['timed_count']
        next_start = data['next_start_iso']
        if type(count) is not int or count < 0 or (next_start is not None and not isinstance(next_start, str)):
            return None
        now = datetime.now().astimezone()
        if next_start:
            delta = (datetime.fromisoformat(next_start) - now).total_seconds()
            if 0 <= delta <= 90 * 60:
                return ('calendar', 'You have a calendar event coming up fairly soon.')
        if count >= 4:
            return ('calendar', 'Your calendar looks fairly busy today.')
    except (TypeError, ValueError, KeyError, OverflowError):
        return None
    return None


def _call(execute, tool, sanitizer, output):
    result = execute({'function': {'name': tool, 'arguments': '{}'}}, ())
    signal = sanitizer(result)
    with _lock:
        _cache[tool] = (time.monotonic(), signal)
    output.put((tool, signal))


def gather(execute, budget=BUDGET_SECONDS):
    """Return zero or one observation without making optional context mandatory."""
    output = queue.Queue()
    sources = [('get_weather', _weather_signal),
               ('greeting_calendar_context', _calendar_signal)]
    signals = {}
    pending = []
    now = time.monotonic()
    with _lock:
        cached = dict(_cache)
    for tool, sanitizer in sources:
        stamp, value = cached.get(tool, (0, None))
        if stamp and now - stamp <= CACHE_SECONDS:
            signals[tool] = value
            continue
        context = copy_context()
        thread = threading.Thread(target=lambda c=context, t=tool, s=sanitizer:
                                  c.run(_call, execute, t, s, output), daemon=True,
                                  name='kuzco-greeting-context')
        thread.start()
        pending.append(tool)
    deadline = time.monotonic() + max(0, budget)
    while pending:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            tool, value = output.get(timeout=remaining)
        except queue.Empty:
            break
        signals[tool] = value
        pending.remove(tool)
    # Weather earns priority only when it is notable; otherwise schedule shape
    # may contribute. Both are already sentence-sized and contain no raw data.
    selected = signals.get('get_weather') or signals.get('greeting_calendar_context')
    return selected[1] if selected else None


def reset_cache():
    with _lock:
        _cache.clear()
