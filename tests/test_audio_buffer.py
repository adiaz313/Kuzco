"""No live microphone or time-sensitive assertions."""
from queue import Empty
import unittest
from unittest.mock import Mock

from audio_buffer import AudioBuffer
from speech_input import VoiceInputError


class AudioBufferTests(unittest.TestCase):
    def test_exact_pcm_and_partial_reads(self):
        audio = AudioBuffer()
        audio.callback(b'abcd', 2, None, False)
        audio.callback(b'efgh', 2, None, False)
        self.assertEqual(audio.read(1), (b'ab', False))
        self.assertEqual(audio.read(3), (b'cdefgh', False))

    def test_disconnected_input_has_bounded_wait(self):
        audio = AudioBuffer()
        audio.blocks = Mock()
        audio.blocks.get.side_effect = Empty
        with self.assertRaisesRegex(VoiceInputError, 'stopped delivering'):
            audio.read(1600)
        audio.blocks.get.assert_called_once_with(timeout=2)

    def test_full_buffer_signals_overflow_without_blocking_callback(self):
        audio = AudioBuffer()
        for _ in range(25):
            audio.callback(b'ab', 1, None, False)
        self.assertEqual(audio.blocks.qsize(), 20)
        self.assertEqual(audio.read(1), (b'ab', True))

    def test_device_status_error_reaches_capture(self):
        audio = AudioBuffer()
        audio.callback(b'ab', 1, None, True)
        self.assertEqual(audio.read(1), (b'ab', True))
