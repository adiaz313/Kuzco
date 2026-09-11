"""Explicit interface lifecycle, independent of models and renderers."""
from enum import Enum
import sys


class State(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


class AssistantState:
    def __init__(self, renderer=None):
        self.current = None
        self.renderer = renderer

    def set(self, state):
        state = State(state)
        if state == self.current:
            return
        self.current = state
        print(f"[state] {state.value}", flush=True)
        if self.renderer:
            try:
                self.renderer(state.value)
            except Exception as error:
                print(f"Indicator unavailable: {error}; voice continues.", file=sys.stderr)
                self.renderer = None
