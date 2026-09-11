"""Small PCM-energy endpoint detector; no transcription, models, or extra packages."""
from array import array
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys

from configuration import settings_path
SETTINGS = settings_path('voice_settings.json')


@dataclass(frozen=True)
class VoiceSettings:
    wake_threshold: float = 0.25
    wake_score: float = 0.5
    wake_paths: int = 8
    wake_reset_silence_seconds: float = 1.0
    silence_seconds: float = 2.0
    speech_rms: float = 200
    noise_multiplier: float = 3.0
    speech_start_seconds: float = 0.2
    wake_tail_seconds: float = 0.3
    detector_preroll_seconds: float = 0.5

    def __post_init__(self):
        limits = {'wake_threshold': (0.01, 1), 'wake_score': (0.1, 5),
                  'wake_paths': (1, 16), 'wake_reset_silence_seconds': (0.5, 3),
                  'silence_seconds': (0.5, 4), 'speech_rms': (20, 10000),
                  'noise_multiplier': (1, 10), 'speech_start_seconds': (0.1, 0.5),
                  'wake_tail_seconds': (0, 0.8), 'detector_preroll_seconds': (0, 1)}
        if type(self.wake_paths) is not int:
            raise ValueError("wake_paths must be an integer")
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f'{key} must be a number between {low} and {high}')

    @classmethod
    def load(cls, path=SETTINGS):
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError('Unknown voice setting or invalid settings object')
        return cls(**data)


def rms(pcm):
    if not pcm:
        return 0.0
    samples = array('h', pcm)
    if sys.byteorder != 'little': samples.byteswap()
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


class EndOfSpeech:
    """WAITING -> SPEECH -> sustained silence; wake tail cannot start the timer."""
    def __init__(self, settings, threshold=None):
        self.settings = settings
        self.threshold = settings.speech_rms if threshold is None else threshold
        self.elapsed = 0.0
        self.speech_started = False
        self.voiced = 0.0
        self.silent = 0.0

    def feed(self, pcm, rate=16000):
        duration = len(pcm) / (2 * rate)
        previous = self.elapsed
        self.elapsed += duration
        # Exclude wake-word decay, but retain these samples for transcription.
        eligible = max(0.0, self.elapsed - max(previous, self.settings.wake_tail_seconds))
        if eligible <= 1e-8: return None
        if rms(pcm) >= self.threshold:
            self.voiced += eligible
            self.silent = 0.0
            if not self.speech_started and self.voiced + 1e-8 >= self.settings.speech_start_seconds:
                self.speech_started = True
                return 'speech_started'
        else:
            self.voiced = 0.0
            if self.speech_started:
                self.silent += eligible
                if self.silent + 1e-8 >= self.settings.silence_seconds:
                    return 'silence_reached'
        return None
