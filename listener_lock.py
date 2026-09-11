"""One microphone-owning Kuzco per logged-in user, released automatically on exit."""
import fcntl
import os
from pathlib import Path
import tempfile

LOCK_PATH = Path(tempfile.gettempdir()) / f"kuzco-listener-{os.getuid()}.lock"


class ListenerLock:
    def __init__(self, path=LOCK_PATH):
        self.path = path
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            self.fd = None
            raise RuntimeError("Another Kuzco voice instance is already listening. Run 'python3 service.py stop' or exit the foreground instance first.") from None
        os.ftruncate(self.fd, 0)
        os.write(self.fd, str(os.getpid()).encode())
        return self

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        # Never unlink: another process may already hold/open this same inode.
