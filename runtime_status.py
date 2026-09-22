"""Private operational state shared only with the native background host."""
from datetime import datetime, timezone
import json
import os

from configuration import home


def path():
    return home() / 'runtime-status.json'


def listener(active):
    target = path()
    if not active:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps({'pid': os.getpid(), 'wake_listening': True,
        'updated_at': datetime.now(timezone.utc).isoformat()}))
    temporary.chmod(0o600)
    temporary.replace(target)

