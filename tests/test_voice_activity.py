"""Audio endpoint tests: generated PCM, no microphone or external model."""
from array import array
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
import contextlib
import io

from speech_input import VoiceInputError
from voice_activity import EndOfSpeech, VoiceSettings, rms
from wake_input import WakeSpeechInput

QUIET = b'\0\0' * 1600
SPEECH = array('h', [1500, -1500] * 800).tobytes()


def feed(detector, pcm, count):
    return [detector.feed(pcm) for _ in range(count)]


class VoiceActivityTests(unittest.TestCase):
    def test_rms_and_settings_validation(self):
        self.assertEqual(rms(QUIET), 0)
        self.assertEqual(rms(SPEECH), 1500)
        for name, value in [('wake_threshold', 0), ('wake_score', 99),
                            ('silence_seconds', .1), ('speech_rms', True),
                            ('wake_tail_seconds', -1), ('speech_rms', float('nan'))]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                VoiceSettings(**{name: value})

    def test_config_load_defaults_custom_and_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({'silence_seconds': 1.5, 'wake_threshold': .3}))
            settings = VoiceSettings.load(path)
            self.assertEqual(settings.silence_seconds, 1.5)
            self.assertEqual(settings.wake_threshold, .3)
            self.assertEqual(settings.speech_rms, 200)
            for text in ['[]', '{"unknown": 1}', '{']:
                path.write_text(text)
                with self.assertRaises(ValueError): VoiceSettings.load(path)

    def test_wait_for_request_and_ignore_wake_tail(self):
        endpoint = EndOfSpeech(VoiceSettings())
        feed(endpoint, SPEECH, 3)  # Only wake decay, not actual request speech.
        events = feed(endpoint, QUIET, 40)
        self.assertFalse(endpoint.speech_started)
        self.assertNotIn('silence_reached', events)
        self.assertIn('speech_started', feed(endpoint, SPEECH, 3))
        self.assertNotIn('silence_reached', feed(endpoint, QUIET, 19))
        self.assertEqual(endpoint.feed(QUIET), 'silence_reached')

    def test_one_second_pause_does_not_end_request(self):
        endpoint = EndOfSpeech(VoiceSettings())
        feed(endpoint, QUIET, 3)
        feed(endpoint, SPEECH, 5)
        self.assertNotIn('silence_reached', feed(endpoint, QUIET, 10))
        feed(endpoint, SPEECH, 4)
        self.assertNotIn('silence_reached', feed(endpoint, QUIET, 19))
        self.assertEqual(endpoint.feed(QUIET), 'silence_reached')

    def test_isolated_pop_does_not_start_silence_countdown(self):
        endpoint = EndOfSpeech(VoiceSettings())
        feed(endpoint, QUIET, 4)
        endpoint.feed(SPEECH)
        self.assertNotIn('silence_reached', feed(endpoint, QUIET, 30))
        self.assertFalse(endpoint.speech_started)

    def test_configurable_silence_and_noise_threshold(self):
        endpoint = EndOfSpeech(replace(VoiceSettings(), silence_seconds=1.5), threshold=2000)
        feed(endpoint, SPEECH, 8)
        self.assertFalse(endpoint.speech_started)  # Background louder than speech floor.
        endpoint.threshold = 200
        feed(endpoint, SPEECH, 3)
        self.assertNotIn('silence_reached', feed(endpoint, QUIET, 14))
        self.assertEqual(endpoint.feed(QUIET), 'silence_reached')

    def test_capture_short_request_ends_early_and_retains_handoff(self):
        listener = WakeSpeechInput(settings=VoiceSettings())
        listener.event = Mock()
        stream = Mock()
        stream.read.side_effect = [(pcm, False) for pcm in [QUIET]*3 + [SPEECH]*5 + [QUIET]*20]
        pcm = listener.capture_request(stream, [b'prefix'])
        self.assertTrue(pcm.startswith(b'prefix'))
        self.assertEqual(listener.last_capture, {'reason': 'silence', 'seconds': 2.8, 'speech_detected': True})
        self.assertEqual(stream.read.call_count, 28)
        self.assertTrue(any(c.args[0] == 'speech_started' for c in listener.event.call_args_list))

    def test_silence_only_and_continuous_audio_hit_hard_maximum(self):
        for pcm in [QUIET, SPEECH]:
            listener = WakeSpeechInput(settings=VoiceSettings())
            stream = Mock(read=Mock(return_value=(pcm, False)))
            audio = listener.capture_request(stream)
            self.assertEqual(len(audio), 16000 * 2 * 8)
            self.assertEqual(listener.last_capture['reason'], 'maximum_timeout')
            self.assertEqual(listener.last_capture['seconds'], 8)

    def test_wake_context_is_refreshed_after_quiet_without_dropping_audio(self):
        listener = WakeSpeechInput(settings=VoiceSettings())
        listener.detector = Mock()
        listener.detector.is_ready.return_value = False
        first, second = Mock(), Mock()
        listener.detector.create_stream.side_effect = [first, second]
        samples = Mock()
        samples.astype.return_value.__truediv__ = Mock(return_value=[])
        np = SimpleNamespace(frombuffer=Mock(return_value=samples), float32='float32')
        stream = Mock()
        stream.read.side_effect = [(QUIET, False)] * 15 + [(SPEECH, False), EOFError()]
        with patch.dict('sys.modules', {'numpy': np}), self.assertRaises(EOFError):
            listener.capture(stream, Mock())
        self.assertEqual(listener.detector.create_stream.call_count, 2)
        # New prefix, two previous audio chunks (protect consonants), and current chunk.
        self.assertEqual(second.accept_waveform.call_count, 4)
        self.assertEqual(stream.read.call_count, 17)

    def test_effective_wake_configuration_reaches_detector_and_debug(self):
        settings = replace(VoiceSettings(), wake_threshold=.3, wake_score=.7, wake_paths=6)
        listener = WakeSpeechInput(settings=settings)
        listener.debug = True
        factory = Mock()
        out = io.StringIO()
        with patch('speech_input.LocalSpeechInput.check_setup'), patch('pathlib.Path.is_file', return_value=True), patch.dict('sys.modules', {'numpy': Mock(), 'sherpa_onnx': SimpleNamespace(KeywordSpotter=factory)}), contextlib.redirect_stderr(out):
            listener.check_setup()
        self.assertEqual(factory.call_args.kwargs['keywords_threshold'], .3)
        self.assertEqual(factory.call_args.kwargs['keywords_score'], .7)
        self.assertEqual(factory.call_args.kwargs['max_active_paths'], 6)
        self.assertIn('effective settings', out.getvalue())
        self.assertIn('silence_seconds', out.getvalue())

    def test_capture_overflow_does_not_transcribe(self):
        listener = WakeSpeechInput(settings=VoiceSettings())
        listener.transcribe = Mock()
        with self.assertRaises(VoiceInputError):
            listener.capture_request(Mock(read=Mock(return_value=(SPEECH, True))))
        listener.transcribe.assert_not_called()
