"""Bounded metadata only. Never accepts action arguments, content or exceptions."""
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import threading

from configuration import home
PATH = home() / 'logs/security.jsonl'
_lock = threading.Lock()


def record(action, decision, outcome):
    from security_policy import TOOLS
    tool = TOOLS.get(action) if isinstance(action, str) else None
    row = {'timestamp': datetime.now(timezone.utc).isoformat(),
           'action': action if tool else 'unknown', 'risk': tool.risk.value if tool else 'UNCLASSIFIED',
           'decision': decision if decision in {'EXECUTE','CONFIRM','DENY'} else 'DENY',
           'outcome': outcome if outcome in {'evaluated','success','failure','requested','granted','denied'} else 'failure'}
    try:
        with _lock:
            PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(PATH, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            os.fchmod(fd, 0o600)
            os.close(fd)
            handler = RotatingFileHandler(PATH, maxBytes=128*1024, backupCount=2)
            try:
                handler.emit(logging.LogRecord('security', logging.INFO, '', 0, json.dumps(row), (), None))
                PATH.chmod(0o600)
            finally:
                handler.close()
    except OSError:
        pass  # Audit storage failure must not crash the voice service or grant access.
