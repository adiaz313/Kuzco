import unittest
import inspect
from unittest.mock import patch
import tts_output
import voice
from speech_output import VoiceOutputError


class TTSSelectionTests(unittest.TestCase):
    def test_default_voice_path_uses_configured_piper(self):
        self.assertIs(inspect.signature(voice.conversation).parameters['speaker'].default, tts_output.speak)
        with patch('piper_output.speak', return_value=True) as output:
            self.assertTrue(tts_output.speak('Hello, sir.'))
            self.assertEqual(output.call_args.kwargs['model'].name, 'en_GB-northern_english_male-medium.onnx')

    def test_daniel_override(self):
        with patch('speech_output.speak', return_value=True) as output:
            tts_output.speak('Hello', engine='macos')
            output.assert_called_once_with('Hello', voice_name='Daniel')

    def test_failure_does_not_repeat_audio_with_another_backend(self):
        with patch('piper_output.speak', side_effect=VoiceOutputError('failed')), patch('speech_output.speak') as fallback:
            with self.assertRaises(VoiceOutputError):
                tts_output.speak('Hello')
            fallback.assert_not_called()

    def test_bad_configuration_is_reported(self):
        with patch('pathlib.Path.read_text', return_value='{}'), self.assertRaises(VoiceOutputError):
            tts_output.speak('Hello')
