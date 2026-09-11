"""Optional offline keyword activation. No agent or personality decisions here."""
from collections import deque
import re

from speech_input import LocalSpeechInput, RATE, ROOT, VoiceInputError
from voice_activity import EndOfSpeech, VoiceSettings, rms
from dataclasses import asdict
import json
import sys


from configuration import asset
MODEL = asset("sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20")


def request_text(transcript):
    """Remove only a leading wake name; preserve the raw transcription on screen."""
    return re.sub(r"^\s*(?:hey\s+)?(?:kuzco|cuzco|cusco|kusco|kuzko)\b[\s,.!?—:-]*",
                  "", transcript, count=1, flags=re.I).strip()


class WakeSpeechInput(LocalSpeechInput):
    def __init__(self, *args, settings=None, engine_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings if settings is not None else VoiceSettings.load()
        self.debug = False
        self.engine_settings = engine_settings

    def event(self, name, **details):
        if self.debug:
            print('[voice] ' + name + ' ' + json.dumps(details), file=sys.stderr, flush=True)

    def check_setup(self):
        super().check_setup()
        from wake_detector import WakeEngineSettings, OpenWakeWordDetector
        try:
            engine = self.engine_settings or WakeEngineSettings.load()
        except (ValueError, OSError, TypeError) as error:
            raise VoiceInputError('Invalid wake_engine.json configuration; see README.md.') from error
        self.event('wake engine', engine=engine.engine)
        self.__dict__.pop('frame_detector', None)
        if engine.engine == 'openwakeword':
            self.frame_detector = OpenWakeWordDetector(engine)
            self.event('OpenWakeWord candidate', threshold=engine.threshold)
            return
        try:
            import numpy
            import sherpa_onnx
        except (ImportError, OSError) as error:
            raise VoiceInputError("Complete the locked installation in README.md. Push-to-talk remains available.") from error
        paths = {"tokens": MODEL / "tokens.txt",
                 "encoder": MODEL / "encoder-epoch-13-avg-2-chunk-8-left-64.int8.onnx",
                 "decoder": MODEL / "decoder-epoch-13-avg-2-chunk-8-left-64.onnx",
                 "joiner": MODEL / "joiner-epoch-13-avg-2-chunk-8-left-64.int8.onnx",
                 "keywords_file": ROOT / "wake_words/kuzco.txt"}
        if not all(path.is_file() for path in paths.values()):
            raise VoiceInputError("Wake model/keyword files missing. See README.md; nothing is downloaded automatically.")
        self.detector = sherpa_onnx.KeywordSpotter(
            **{key: str(path) for key, path in paths.items()}, num_threads=1,
            provider="cpu", keywords_score=self.settings.wake_score,
            keywords_threshold=self.settings.wake_threshold,
            max_active_paths=self.settings.wake_paths)
        self.event("effective settings", **asdict(self.settings), max_capture_seconds=self.seconds)

    def capture(self, stream, on_wake):
        """Keep a short handoff buffer; idle audio is never sent to Whisper."""
        if hasattr(self, 'frame_detector'):
            return self.capture_frames(stream, on_wake)
        import numpy as np
        detector = self.detector
        def primed_state():
            state = detector.create_stream()
            # Supply context without waiting or dropping any real microphone audio.
            prefix = b"\0\0" * int(RATE * self.settings.detector_preroll_seconds)
            if prefix:
                samples = np.frombuffer(prefix, dtype="<i2").astype(np.float32) / 32768
                state.accept_waveform(RATE, samples)
                while detector.is_ready(state):
                    detector.decode_stream(state)
            return state
        state = primed_state()
        quiet_frames = 0
        levels = deque(maxlen=50)
        recent = deque(maxlen=15)  # 1.5 seconds; bounded even after hours idle.
        while True:
            pcm, overflow = stream.read(1600)
            if overflow:
                raise VoiceInputError("Microphone overflowed. Reduce system load or use --voice.")
            pcm = bytes(pcm)
            level = rms(pcm)
            # After a quiet gap, replay the preceding 200 ms into a fresh primed
            # stream. This gives the first wake attempt consistent acoustic context
            # without trimming its initial consonants or increasing sensitivity.
            if level >= self.settings.speech_rms and quiet_frames >= RATE * self.settings.wake_reset_silence_seconds:
                state = primed_state()
                for previous in list(recent)[-2:]:
                    state.accept_waveform(RATE, np.frombuffer(previous, dtype="<i2").astype(np.float32) / 32768)
                    while detector.is_ready(state):
                        detector.decode_stream(state)
                self.event("wake acoustic context refreshed")
            quiet_frames = quiet_frames + len(pcm) // 2 if level < self.settings.speech_rms else 0
            recent.append(pcm)
            levels.append(level)
            detector_samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
            state.accept_waveform(RATE, detector_samples)
            detected = False
            while detector.is_ready(state):
                detector.decode_stream(state)
                if detector.get_result(state):
                    detected = True
                    break
            if detected:
                on_wake()  # Immediate local confirmation; never wait for Llama.
                self.event("wake detected")
                # Estimate quiet background from earlier input, excluding recent wake audio.
                quiet = sorted(list(levels)[:-8])
                floor = quiet[len(quiet) // 5] if len(quiet) >= 12 else 0
                threshold = max(self.settings.speech_rms, floor * self.settings.noise_multiplier)
                self.event("request energy threshold", rms=round(threshold, 1))
                return self.capture_request(stream, list(recent), threshold)

    def capture_frames(self, stream, on_wake):
        """Shared microphone/recovery and request endpoint; replace only detection."""
        self.frame_detector.reset()
        recent = deque(maxlen=15)
        levels = deque(maxlen=50)
        while True:
            pcm, overflow = stream.read(1600)
            if overflow:
                raise VoiceInputError('Microphone overflowed. Reduce system load or use --voice.')
            pcm = bytes(pcm)
            recent.append(pcm)
            levels.append(rms(pcm))
            if self.frame_detector.feed(pcm):
                on_wake()
                self.event('wake detected', engine='openwakeword', score=self.frame_detector.score)
                quiet = sorted(list(levels)[:-8])
                floor = quiet[len(quiet)//5] if len(quiet) >= 12 else 0
                threshold = max(self.settings.speech_rms, floor * self.settings.noise_multiplier)
                return self.capture_request(stream, list(recent), threshold)

    def capture_request(self, stream, prefix=(), threshold=None):
        endpoint = EndOfSpeech(self.settings, threshold)
        chunks = list(prefix)
        remaining = int(self.seconds * RATE)
        reason = "maximum_timeout"
        while remaining:
            frames = min(1600, remaining)
            pcm, overflow = stream.read(frames)
            if overflow:
                raise VoiceInputError("Request audio overflowed; please try again.")
            pcm = bytes(pcm)
            chunks.append(pcm)
            remaining -= frames
            event = endpoint.feed(pcm)
            if event:
                self.event(event, capture_seconds=round(endpoint.elapsed, 2))
            if event == "silence_reached":
                reason = "silence"
                break
        self.last_capture = {"reason": reason, "seconds": round(endpoint.elapsed, 2),
                             "speech_detected": endpoint.speech_started}
        self.event("capture complete", **self.last_capture)
        # Keep the original handoff audio even if the energy gate misses a very short
        # request. Wake-only transcripts are still filtered by the existing adapter.
        return b"".join(chunks)

    def notify_listening(self):
        callback = getattr(self, "on_listening", None)
        if callback:
            callback()
        print("LISTENING — Kuzco detected. Speak your request.", flush=True)

    def listen(self):
        import sounddevice as sd
        from audio_buffer import AudioBuffer
        audio = AudioBuffer()
        try:
            if sd.query_devices(self.device, "input")["max_input_channels"] < 1:
                raise VoiceInputError("No microphone available. Check macOS Sound → Input.")
            self.event("opening microphone", device=self.device)
            with sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", device=self.device,
                                   blocksize=1600, callback=audio.callback):
                self.event("microphone stream ready")
                pcm = self.capture(audio, self.notify_listening)
        except sd.PortAudioError as error:
            raise VoiceInputError("Microphone unavailable or permission denied. Check macOS Microphone privacy and Sound input settings.") from error
        # The stream is closed before transcription, agent execution, and TTS.
        callback = getattr(self, "on_thinking", None)
        if callback:
            callback()
        print("TRANSCRIBING — microphone off.", flush=True)
        return self.transcribe(pcm)
