"""Offline tests: no real microphone, speech, downloads, or model calls."""
from array import array
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

import main
from speech_input import LocalSpeechInput, RATE, VoiceInputError
import speech_output
import voice


def decision(**choice):
    return {"content": json.dumps(choice)}


class VoiceTests(unittest.TestCase):
    def test_voice_uses_existing_agent_history_and_only_speaks_final_answers(self):
        listener = Mock()
        listener.listen.side_effect = ["What time is it?", "Open Calculator.",
                                       "Which app was that?", "Explain what an embedding is."]
        replies = iter([decision(tool="get_current_time", arguments={}), decision(answer="It is noon."),
                        decision(tool="open_application", arguments={"application_name": "Calculator"}),
                        decision(answer="Calculator is open."), decision(answer="Calculator."),
                        decision(answer="An embedding is a numerical representation.")])
        payloads = []
        def send(payload):
            payloads.append(payload)
            return next(replies)
        def agent(*args, **kwargs):
            return main.run(*args, **kwargs, send=send)
        speaker = Mock()
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("builtins.input", side_effect=["", "", "", "", "/exit"]), patch.object(
                main, "open_application", return_value={"opened": True}) as launch, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            voice.conversation(agent, debug=True, personality="kuzco", listener=listener, speaker=speaker)
        launch.assert_called_once_with("Calculator")
        self.assertEqual([c.args[0] for c in speaker.call_args_list], ["It is noon.", "Calculator is open.", "Calculator.", "An embedding is a numerical representation."])
        self.assertIn("Heard: Which app was that?", stdout.getvalue())
        self.assertIn("raw tool result", stderr.getvalue())
        self.assertIn("Calculator is open.", json.dumps(payloads[-1]))
        self.assertIn("Your name is Kuzco", payloads[-1]["messages"][0]["content"])

    def test_silence_input_failure_and_agent_failure_do_not_speak(self):
        listener = Mock()
        listener.listen.side_effect = ["", VoiceInputError("permission denied"), "bad request", "hello"]
        agent = Mock(side_effect=[RuntimeError("developer error"), "Hello."])
        speaker = Mock()
        out = io.StringIO()
        with patch("builtins.input", side_effect=["", "", "", "", "/exit"]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            voice.conversation(agent, listener=listener, speaker=speaker)
        self.assertEqual(agent.call_count, 2)
        speaker.assert_called_once_with("Hello.")
        self.assertIn("No recognizable speech", out.getvalue())
        self.assertIn("permission denied", out.getvalue())

    def test_speech_failure_preserves_history_and_next_turn(self):
        listener = Mock()
        listener.listen.side_effect = ["first", "follow-up"]
        def agent(prompt, **kwargs):
            history = kwargs["history"]
            if prompt == "follow-up":
                self.assertEqual(history, ["first"])
            history.append(prompt)
            return "A final answer."
        speaker = Mock(side_effect=[RuntimeError("output unavailable"), True])
        with patch("builtins.input", side_effect=["", "", "/exit"]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            voice.conversation(agent, listener=listener, speaker=speaker)
        self.assertEqual(speaker.call_count, 2)

    def test_capture_only_after_activation_and_bounded(self):
        listener = Mock()
        with patch("builtins.input", side_effect=["typed text", "/exit"]), contextlib.redirect_stdout(io.StringIO()):
            voice.conversation(Mock(), listener=listener)
        listener.listen.assert_not_called()
        reads = []
        class Stream:
            def __enter__(self): return self
            def __exit__(self, *args): reads.append("closed")
            def read(self, frames):
                reads.append(frames)
                return b"\x01\x00" * frames, False
        sd = SimpleNamespace(query_devices=Mock(return_value={"max_input_channels": 1}),
                             RawInputStream=Mock(return_value=Stream()), PortAudioError=RuntimeError)
        with patch.dict("sys.modules", {"sounddevice": sd}):
            pcm = LocalSpeechInput(seconds=1).record()
        self.assertEqual(len(pcm), RATE * 2)
        self.assertEqual(sum(reads[:-1]), RATE)
        self.assertEqual(reads[-1], "closed")

    def test_missing_microphone_permission_and_overflow(self):
        for failure in ["missing", "denied", "overflow"]:
            sd = Mock()
            sd.PortAudioError = RuntimeError
            sd.query_devices.return_value = {"max_input_channels": 1}
            if failure == "missing":
                sd.query_devices.side_effect = RuntimeError("no device")
            elif failure == "denied":
                sd.RawInputStream.side_effect = RuntimeError("permission denied")
            else:
                sd.RawInputStream.return_value.__enter__ = Mock(return_value=Mock(read=Mock(return_value=(b"", True))))
                sd.RawInputStream.return_value.__exit__ = Mock(return_value=False)
            with self.subTest(failure=failure), patch.dict("sys.modules", {"sounddevice": sd}), self.assertRaises(VoiceInputError):
                LocalSpeechInput(seconds=1).record()

    def test_silent_audio_never_runs_whisper(self):
        with patch("speech_input.subprocess.run") as run:
            self.assertEqual(LocalSpeechInput().transcribe(b"\x00\x00" * RATE), "")
            self.assertEqual(LocalSpeechInput().transcribe(b""), "")
            run.assert_not_called()

    def test_transcription_command_format_and_temporary_cleanup(self):
        pcm = array("h", [1000, -1000] * RATE).tobytes()
        paths = []
        def process(command, **kwargs):
            wav_path = Path(command[command.index("-f") + 1])
            paths.append(wav_path)
            with wave.open(str(wav_path)) as wav:
                self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()), (RATE, 1, 2))
            output = Path(command[command.index("-of") + 1]).with_suffix(".txt")
            output.write_text("What time is it?")
            self.assertIn("-ng", command)
            self.assertFalse(kwargs["shell"])
            return subprocess.CompletedProcess(command, 0)
        with patch("speech_input.subprocess.run", side_effect=process):
            self.assertEqual(LocalSpeechInput().transcribe(pcm), "What time is it?")
        self.assertFalse(paths[0].exists())
        with patch("speech_input.subprocess.run", side_effect=subprocess.TimeoutExpired("whisper", 90)), self.assertRaises(VoiceInputError):
            LocalSpeechInput().transcribe(pcm)

    def test_tts_only_prose_and_fixed_stdin_command(self):
        text = 'Hello. ```json\n{"tool":"internal"}\n``` <think>private</think> [[rate 999]]'
        with patch("speech_output.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(speech_output.speak(text))
            args, kwargs = run.call_args
            self.assertEqual(args[0], ["/usr/bin/say", "-f", "-"])
            self.assertEqual(kwargs["input"].strip(), "Hello.")
            self.assertFalse(kwargs["shell"])
        for text in ['{"tool":"internal"}', '[{"x":1}]', '```json\n{}\n```', '[debug] request']:
            with patch("speech_output.subprocess.run") as run:
                self.assertFalse(speech_output.speak(text))
                run.assert_not_called()
        self.assertEqual(speech_output.spoken_text('Result: {"internal": 1} Done.'), 'Result:  Done.')
        with patch("speech_output.subprocess.run", side_effect=OSError("no output")), self.assertRaises(speech_output.VoiceOutputError):
            speech_output.speak("Hello.")

    @patch("listener_lock.ListenerLock", new=lambda: contextlib.nullcontext())
    def test_voice_cli_and_mode_conflict(self):
        with patch("sys.argv", ["main.py", "--voice", "--personality", "kuzco"]), patch("voice.conversation") as conversation:
            self.assertEqual(main.main(), 0)
            agent = conversation.call_args.args[0]
            self.assertEqual(agent.policy, 'direct')
            conversation.assert_called_once_with(agent, [], False, 5, "kuzco", 8, None)
        with patch("sys.argv", ["main.py", "--voice", "--chat"]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main.main()


if __name__ == "__main__":
    unittest.main()
