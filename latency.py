"""Content-free timings in the existing rotating background log."""
from functools import wraps
import logging
import time

LOGGER = logging.getLogger('kuzco.background.timing')
TOOL_NAMES = {'get_current_time', 'search_documents', 'open_application', 'search_web', 'get_weather', 'read_webpage', 'research_web'}


def measured(kind):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            if not LOGGER.isEnabledFor(logging.INFO):
                return function(*args, **kwargs)
            detail = ''
            try:
                if kind == 'tool' and args:
                    name = args[0].get('function', {}).get('name')
                    detail = name if isinstance(name, str) and name in TOOL_NAMES else 'invalid'
                elif kind == 'llama' and args:
                    detail = 'prompt_chars=' + str(sum(len(m.get('content', '')) for m in args[0].get('messages', [])))
            except Exception:
                detail = 'unavailable'
            def log(event, seconds):
                try:
                    LOGGER.info('Timing %s %s %s seconds=%.4f', kind, event, detail, seconds)
                except Exception:
                    pass  # Measurement failure must never affect an interaction.
            start = time.perf_counter()
            log('begin', 0)
            try:
                return function(*args, **kwargs)
            finally:
                log('end', time.perf_counter() - start)
        return call
    return decorate
