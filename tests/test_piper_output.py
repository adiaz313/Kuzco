import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import main
import piper_output as piper
from speech_output import VoiceOutputError


class PiperOutputTests(unittest.TestCase):
    def test_internal_output_is_never_rendered(self):
        with patch.object(piper.subprocess, 'run') as run:
            self.assertFalse(piper.render('{"tool":"private"}', '/unused'))
            self.assertFalse(piper.speak('[debug] private'))
            run.assert_not_called()

    def test_missing_voice_is_explicit(self):
        with self.assertRaises(VoiceOutputError):
            piper.render('Hello', '/unused', '/missing/kuzco.onnx')

    def test_final_prose_through_stdin_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'voice.onnx'
            model.touch()
            Path(str(model) + '.json').write_text('{}')
            with patch.object(piper.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertTrue(piper.render('Hello, sir. https://example.com [S1]', '/unused', model))
                self.assertEqual(run.call_args.kwargs['input'], 'Hello, sir.')
                self.assertFalse(run.call_args.kwargs['shell'])
                self.assertEqual(run.call_args.kwargs['timeout'], 60)
            for failure in [OSError('failed'), subprocess.TimeoutExpired('piper', 60)]:
                with patch.object(piper.subprocess, 'run', side_effect=failure), self.assertRaises(VoiceOutputError):
                    piper.render('Hello', '/unused', model)
            with patch.object(piper.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), self.assertRaises(VoiceOutputError):
                piper.render('Hello', '/unused', model)

    def test_playback_failure_cleans_private_audio(self):
        paths = []
        def render(answer, path, model):
            paths.append(path)
            path.write_bytes(b'audio')
            return True
        with patch.object(piper, 'render', side_effect=render), patch.object(piper.subprocess, 'run', side_effect=OSError('device')), self.assertRaises(VoiceOutputError):
            piper.speak('Hello')
        self.assertFalse(paths[0].exists())

    @patch('listener_lock.ListenerLock', new=lambda: contextlib.nullcontext())
    def test_candidate_cli_is_opt_in(self):
        with patch('sys.argv', ['main.py', '--voice', '--tts-engine', 'piper']), patch('voice.conversation') as chat:
            self.assertEqual(main.main(), 0)
            with patch('piper_output.speak', return_value=True) as output:
                chat.call_args.kwargs['speaker']('Hello')
                output.assert_called_once()
        with patch('sys.argv', ['main.py', '--chat', '--tts-engine', 'piper']), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main.main()
