"""Bounded PCM handoff: disappearing hardware cannot block Python's read forever."""
from queue import Empty, Full, Queue
from threading import Event

from speech_input import VoiceInputError


class AudioBuffer:
    def __init__(self):
        self.blocks = Queue(maxsize=20)  # At most two seconds at 100 ms/block.
        self.overflow = Event()
        self.pending = b""

    def callback(self, data, frames, timing, status):
        # Audio callback: copy only. No device queries, logging or model work.
        if status:
            self.overflow.set()
        try:
            self.blocks.put_nowait(bytes(data))
        except Full:
            self.overflow.set()

    def read(self, frames):
        size = frames * 2  # mono int16
        while len(self.pending) < size:
            try:
                self.pending += self.blocks.get(timeout=2)
            except Empty as error:
                raise VoiceInputError(
                    "Microphone stopped delivering audio; reopening selected input"
                ) from error
        audio, self.pending = self.pending[:size], self.pending[size:]
        return audio, self.overflow.is_set()
