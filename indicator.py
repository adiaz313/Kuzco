"""Optional macOS renderer in an isolated process; state delivery never blocks voice."""
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent
from configuration import asset


class Indicator:
    def __init__(self):
        self.process = None
        self.pending = queue.Queue(maxsize=16)
        self.worker = None

    def __enter__(self):
        try:
            if sys.platform != "darwin":
                raise RuntimeError("the overlay requires macOS")
            source = ROOT / "native/Indicator.swift"
            binary = asset("indicator")
            binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
                print("Preparing local indicator…", flush=True)
                subprocess.run(["/usr/bin/xcrun", "swiftc", str(source), "-o", str(binary)],
                               check=True, capture_output=True, timeout=120)
            self.process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.worker = threading.Thread(target=self._deliver, daemon=True)
            self.worker.start()
        except Exception as error:
            print(f"Indicator unavailable: {error}; continuing with console states.", file=sys.stderr)
        return self

    def __call__(self, state):
        if self.process is None:
            return
        if self.process.poll() is not None:
            raise RuntimeError("display process exited")
        try:
            self.pending.put_nowait(state)
        except queue.Full:
            # A frozen display cannot stall microphone capture or agent execution.
            raise RuntimeError("display stopped accepting states")

    def _deliver(self):
        try:
            while True:
                state = self.pending.get()
                if state is None:
                    return
                self.process.stdin.write((state + "\n").encode("ascii"))
                self.process.stdin.flush()
        except (OSError, ValueError):
            pass  # The next state publication reports a dead helper.

    def __exit__(self, *args):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            try:
                self.pending.put_nowait(None)
            except queue.Full:
                pass
            if self.worker:
                self.worker.join(timeout=0.2)
            # Avoid closing a pipe held by a blocked writer on the voice thread.
            if not self.worker or not self.worker.is_alive():
                self.process.stdin.close()
