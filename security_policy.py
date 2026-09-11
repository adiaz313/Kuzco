"""Trusted action policy. Model JSON supplies arguments, never risk or grants."""
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import inspect
import json
from pathlib import Path
import re
import secrets
import time
from types import MappingProxyType


class Risk(str, Enum):
    READ_ONLY = 'READ_ONLY'
    LOCAL_ACTION = 'LOCAL_ACTION'
    EXTERNAL_ACTION = 'EXTERNAL_ACTION'
    SENSITIVE_DESTRUCTIVE = 'SENSITIVE_DESTRUCTIVE'


class Decision(str, Enum):
    EXECUTE = 'EXECUTE'
    CONFIRM = 'CONFIRM'
    DENY = 'DENY'


@dataclass(frozen=True)
class Tool:
    risk: Risk
    fields: tuple
    limit: int = 500


TOOLS = MappingProxyType({
    'get_current_time': Tool(Risk.READ_ONLY, ()),
    'get_weather': Tool(Risk.READ_ONLY, ()),
    'search_documents': Tool(Risk.READ_ONLY, ('query',)),
    'search_web': Tool(Risk.READ_ONLY, ('query',), 300),
    'read_webpage': Tool(Risk.READ_ONLY, ('url', 'query'), 1500),
    'research_web': Tool(Risk.READ_ONLY, ('query',), 300),
    'open_application': Tool(Risk.LOCAL_ACTION, ('application_name',), 100),
    'memory_recall': Tool(Risk.READ_ONLY, ('topic',)),
    'memory_remember': Tool(Risk.LOCAL_ACTION, ('content',)),
    'memory_update': Tool(Risk.LOCAL_ACTION, ('target', 'content')),
    # Exact single-record deletion is an explicit local-state operation, not
    # arbitrary destructive filesystem access. No bulk memory deletion exists.
    'memory_forget': Tool(Risk.LOCAL_ACTION, ('target',)),
})
REQUEST = ContextVar('trusted_request', default=None)
from configuration import settings_path
CONFIG = settings_path('security_settings.json')


def request_scope(function):
    signature = inspect.signature(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        prompt = signature.bind(*args, **kwargs).arguments['prompt']
        token = REQUEST.set(prompt)
        try:
            return function(*args, **kwargs)
        finally:
            REQUEST.reset(token)
    return wrapped


def evaluate(name, args, registry=TOOLS):
    tool = registry.get(name) if isinstance(name, str) else None
    if tool is None or not isinstance(tool.risk, Risk):
        return Decision.DENY
    try:
        config = json.loads(CONFIG.read_text())
        disabled = config['disabled_tools']
        if not isinstance(disabled, list) or any(not isinstance(x, str) for x in disabled):
            return Decision.DENY
        if name in disabled:
            return Decision.DENY
    except (OSError, ValueError, KeyError, TypeError):
        return Decision.DENY
    if not isinstance(args, dict) or set(args) != set(tool.fields):
        return Decision.DENY
    if any(not isinstance(v, str) or len(v) > tool.limit or any(ord(c) < 32 for c in v)
           or (not v.strip() and name != 'memory_recall') for v in args.values()):
        return Decision.DENY
    if tool.risk == Risk.SENSITIVE_DESTRUCTIVE:
        return Decision.DENY  # No production capability in this class.
    if tool.risk == Risk.EXTERNAL_ACTION:
        return Decision.CONFIRM  # Reserved for explicitly registered future code.
    prompt = REQUEST.get()
    if name == 'open_application':
        app = args['application_name'].strip()
        if not app or not app[0].isalnum() or any(not (c.isalnum() or c in " .-'()+&") for c in app):
            return Decision.DENY
        if prompt is not None:
            # Only clauses in this turn's actual user request may name an action.
            # Quotes, negation and evidence/history cannot manufacture that intent.
            if re.search(r"\b(?:not|never|don't)\b|[\"“”`]|\b(?:says?|quote|example|definition)\b", prompt, re.I):
                return Decision.DENY
            pattern = r'(?:^|[,;]|\b(?:and|then))\s*(?:then\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?' + re.escape(app) + r'(?:[.!?,;]|\s+(?:and|then|please|for me)\b|$)'
            if not re.search(pattern, prompt.strip(), re.I):
                return Decision.DENY
    if name.startswith('memory_') and prompt is not None:
        from memory import parse
        parsed = parse(prompt)
        if not parsed or 'memory_' + parsed[0] != name or tuple(args.values()) != parsed[1]:
            return Decision.DENY
    return Decision.EXECUTE


class PolicyError(RuntimeError):
    pass


def require(name, args):
    decision = evaluate(name, args)
    from security_log import record
    record(name, decision.value, 'evaluated')
    if decision != Decision.EXECUTE:
        raise PolicyError('Security policy did not authorize this action. Ask for a permitted action explicitly.')


def enforced(name):
    """Also guard Python helper calls, including research's internal readers."""
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                bound = signature.bind(*args, **kwargs)
                proposed = {key: bound.arguments[key] for key in TOOLS[name].fields}
                require(name, proposed)
            except (PolicyError, KeyError, TypeError):
                return {'error': 'Action denied by security policy.'}
            return function(*args, **kwargs)
        return wrapped
    return decorate


class Confirmations:
    """Trusted UI only: one-use, exact-action, expiring, in-process grants.

    Not exposed as an LLM tool. No production tool currently requires this UI.
    Future integrations must call execute, not turn CONFIRM into permission.
    """
    def __init__(self):
        self.pending = {}

    def request(self, name, args):
        ticket = secrets.token_urlsafe(32)
        if len(self.pending) >= 32:
            self.pending.clear()
        self.pending[ticket] = (name, json.dumps(args, sort_keys=True), time.monotonic()+60, False)
        from security_log import record
        record(name, 'CONFIRM', 'requested')
        return ticket

    def respond(self, ticket, approved):
        if ticket not in self.pending or type(approved) is not bool:
            return False
        name, args, expires, _ = self.pending[ticket]
        if expires < time.monotonic():
            self.pending.pop(ticket, None)
            return False
        self.pending[ticket] = (name, args, expires, approved)
        from security_log import record
        record(name, 'CONFIRM', 'granted' if approved else 'denied')
        return True

    def execute(self, name, args, operation, ticket=None, registry=TOOLS):
        from security_log import record
        decision = evaluate(name, args, registry)
        record(name, decision.value, 'evaluated')
        if decision == Decision.CONFIRM:
            saved = self.pending.pop(ticket, None)
            valid = saved and saved[:2] == (name, json.dumps(args, sort_keys=True)) and saved[2] >= time.monotonic() and saved[3]
            if not valid:
                record(name, 'DENY', 'denied')
                raise PolicyError('Trusted confirmation required')
        elif decision != Decision.EXECUTE:
            raise PolicyError('Action denied')
        try:
            result = operation()
            record(name, 'EXECUTE', 'success')
            return result
        except Exception:
            record(name, 'EXECUTE', 'failure')
            raise
