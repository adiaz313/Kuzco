"""Local Piper speech; bounded worker keeps failures out of the agent."""
from pathlib import Path
import subprocess
import sys
import tempfile

from latency import measured
from speech_output import spoken_text, VoiceOutputError

from configuration import asset
DEFAULT_MODEL = asset('piper/en_GB-northern_english_male-medium.onnx')


def render(answer, destination, model=DEFAULT_MODEL):
    """Render only sanitized final prose. No runtime downloads or arbitrary commands."""
    text = spoken_text(answer)
    if not text:
        return False
    model = Path(model).resolve()
    if not model.is_file() or not Path(str(model) + '.json').is_file():
        raise VoiceOutputError('Piper voice is not installed. Daniel remains available.')
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(model), str(destination)],
            input=text, text=True, capture_output=True, shell=False, timeout=60)
        if result.returncode:
            raise VoiceOutputError('Piper synthesis failed. The answer remains on screen.')
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VoiceOutputError('Piper synthesis failed or timed out. The answer remains on screen.') from error
    return True


@measured('speech')
def speak(answer, model=DEFAULT_MODEL):
    with tempfile.TemporaryDirectory(prefix='kuzco-piper-') as directory:
        wav = Path(directory) / 'answer.wav'
        if not render(answer, wav, model):
            return False
        try:
            result = subprocess.run(['/usr/bin/afplay', str(wav)], shell=False,
                                    capture_output=True, timeout=120)
            if result.returncode:
                raise VoiceOutputError('Piper playback failed. The answer remains on screen.')
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VoiceOutputError('Piper playback failed or timed out. The answer remains on screen.') from error
    return True


if __name__ == '__main__':
    import json
    import wave
    import onnxruntime as ort
    from piper import PiperVoice
    # English/eSpeak runs locally; reject configs that could select a downloadable
    # phonemizer. The selected model and config are trusted local setup assets.
    model, destination = sys.argv[1:]
    config = json.loads(Path(model + '.json').read_text())
    if config.get('phoneme_type') != 'espeak':
        raise ValueError('This candidate supports local eSpeak voices only')
    ort.disable_telemetry_events()
    voice = PiperVoice.load(model, use_cuda=False)
    with wave.open(destination, 'wb') as wav:
        voice.synthesize_wav(sys.stdin.read(), wav)
