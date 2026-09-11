"""Bounded microphone capture and offline whisper.cpp transcription."""
from array import array
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave


ROOT = Path(__file__).resolve().parent
RATE = 16000


class VoiceInputError(RuntimeError):
    pass


class LocalSpeechInput:
    def __init__(self, seconds=8, device=None, executable=None, model=None):
        self.seconds = seconds
        self.device = device
        from configuration import asset
        self.executable = Path(executable) if executable else asset("whisper.cpp/build/bin/whisper-cli")
        self.model = Path(model) if model else asset("models/ggml-tiny.en.bin")

    def check_setup(self):
        if sys.platform != "darwin":
            raise VoiceInputError("Voice mode currently requires macOS.")
        if not 1 <= self.seconds <= 30:
            raise VoiceInputError("Recording duration must be between 1 and 30 seconds.")
        if not self.executable.is_file() or not self.model.is_file():
            raise VoiceInputError("Local Whisper binary/model missing. Follow README.md; no automatic downloads occur.")
        try:
            import sounddevice  # Optional dependency: text mode never imports it.
        except (ImportError, OSError) as error:
            raise VoiceInputError("Use the locked environment from README.md.") from error

    def record(self):
        """Open the microphone only here, after the user's Enter activation."""
        import sounddevice as sd
        try:
            info = sd.query_devices(self.device, "input")
            if info["max_input_channels"] < 1:
                raise VoiceInputError("No microphone input is available. Select an input in macOS Sound settings.")
        except sd.PortAudioError as error:
            raise VoiceInputError("No microphone found. Connect/select a microphone in macOS Sound settings.") from error
        chunks = []
        try:
            with sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", device=self.device) as stream:
                # Bounded audio: at most 30 seconds, with no capture while idle or speaking.
                remaining = int(self.seconds * RATE)
                while remaining:
                    frames = min(1600, remaining)
                    audio, overflow = stream.read(frames)
                    if overflow:
                        raise VoiceInputError("Microphone audio overflowed. Try again with less system load.")
                    chunks.append(bytes(audio))
                    remaining -= frames
        except sd.PortAudioError as error:
            raise VoiceInputError(
                "Microphone unavailable or permission denied. Check System Settings → Privacy & Security → "
                "Microphone for your terminal/host app, and Sound → Input. Then try again."
            ) from error
        return b"".join(chunks)

    @staticmethod
    def has_audio(pcm):
        """An inexpensive silence gate, not a speech detector."""
        if len(pcm) < RATE // 5 * 2 or len(pcm) % 2:
            return False
        samples = array("h", pcm)
        if sys.byteorder != "little":
            samples.byteswap()
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        return rms >= 100  # About -50 dBFS; avoid Whisper hallucinations on digital silence.

    def transcribe(self, pcm):
        if not self.has_audio(pcm):
            return ""
        # Audio and transcript artifacts are temporary and removed on success or failure.
        with tempfile.TemporaryDirectory(prefix="jarvis-speech-") as directory:
            wav_path = Path(directory) / "input.wav"
            output = Path(directory) / "transcript"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(RATE)
                wav.writeframes(pcm)
            command = [str(self.executable), "-m", str(self.model), "-f", str(wav_path),
                       "-l", "en", "-t", "4", "-ng", "-nt", "-np", "-otxt", "-of", str(output)]
            try:
                result = subprocess.run(command, shell=False, capture_output=True, text=True, timeout=90)
                if result.returncode:
                    raise VoiceInputError("Local transcription failed. Check the Whisper binary and model in README.md.")
                text = output.with_suffix(".txt").read_text(encoding="utf-8").strip()
            except (OSError, subprocess.TimeoutExpired) as error:
                raise VoiceInputError("Local transcription failed or timed out; your conversation is unchanged.") from error
        # Whisper sometimes emits only non-speech annotations.
        if not re.sub(r"\[[^\]]*\]|\([^)]*\)|[^\w]", "", text):
            return ""
        return text

    def listen(self):
        pcm = self.record()
        callback = getattr(self, "on_thinking", None)
        if callback:
            callback()
        return self.transcribe(pcm)
