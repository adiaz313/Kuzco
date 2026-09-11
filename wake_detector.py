"""Optional OpenWakeWord adapter: signed 16-bit mono 16 kHz PCM in, event out.

No microphone, STT, state renderer, personality, or model downloads live here.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path
from speech_input import ROOT, VoiceInputError

from configuration import settings_path
CONFIG = settings_path('wake_engine.json')


@dataclass(frozen=True)
class WakeEngineSettings:
    engine: str = 'sherpa'
    model: str = '.voice/openwakeword/kuzco.onnx'
    threshold: float = 0.5

    def __post_init__(self):
        if self.engine not in {'sherpa', 'openwakeword'}:
            raise ValueError('Wake engine must be sherpa or openwakeword')
        if not isinstance(self.model, str) or not self.model or Path(self.model).suffix != '.onnx':
            raise ValueError('OpenWakeWord requires a local .onnx model path')
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int,float)) or not math.isfinite(self.threshold) or not 0 < self.threshold < 1:
            raise ValueError('OpenWakeWord threshold must be between 0 and 1')

    @classmethod
    def load(cls, path=CONFIG):
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict) or set(data) - {'engine','model','threshold'}:
            raise ValueError('Invalid wake engine configuration')
        return cls(**data)


class OpenWakeWordDetector:
    """Replaceable reset/feed interface. 80 ms frames, one CPU inference thread."""
    def __init__(self, settings, factory=None):
        path = Path(settings.model).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        mel = path.parent / 'melspectrogram.onnx'
        embedding = path.parent / 'embedding_model.onnx'
        if not all(p.is_file() for p in (path, mel, embedding)):
            raise VoiceInputError('OpenWakeWord needs a trained Kuzco ONNX model and both feature models. It was rejected for v1; use Sherpa (README.md). No automatic download or phrase substitution occurs.')
        try:
            if factory is None:
                import onnxruntime
                onnxruntime.disable_telemetry_events()
                from openwakeword.model import Model
                factory = Model
            self.model = factory(wakeword_models=[str(path)], inference_framework='onnx',
                                 melspec_model_path=str(mel), embedding_model_path=str(embedding),
                                 ncpu=1, device='cpu')
        except Exception as error:
            raise VoiceInputError('OpenWakeWord initialization failed; restore sherpa in wake_engine.json or use push-to-talk.') from error
        self.key = path.stem
        self.threshold = settings.threshold
        self.score = 0.0
        self.pending = b''

    def reset(self):
        try:
            self.model.reset()
            self.pending = b''
            self.score = 0.0
        except Exception as error:
            raise VoiceInputError('OpenWakeWord reset failed; use the existing wake fallback.') from error

    def feed(self, pcm):
        import numpy as np
        if len(pcm) % 2:
            raise VoiceInputError('Wake detector requires 16-bit PCM samples')
        self.pending += pcm
        detected = False
        peak = 0.0
        try:
            while len(self.pending) >= 2560:
                frame, self.pending = self.pending[:2560], self.pending[2560:]
                scores = self.model.predict(np.frombuffer(frame,dtype='<i2'))
                self.score = float(scores[self.key])
                if not math.isfinite(self.score) or not 0 <= self.score <= 1:
                    raise ValueError('invalid confidence')
                peak = max(peak, self.score)
                detected |= self.score >= self.threshold
        except Exception as error:
            raise VoiceInputError('OpenWakeWord inference failed; use the existing wake fallback.') from error
        self.score = peak
        return detected
