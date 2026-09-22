"""Wake lifecycle tests use fake audio/detection; no microphone or model needed."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import main
import voice
from speech_input import VoiceInputError
from speech_output import speak
from wake_input import WakeSpeechInput, request_text


class WakeTests(unittest.TestCase):
    def test_wake_name_cleanup_preserves_other_words(self):
        self.assertEqual(request_text("Kuzco, what time is it?"), "what time is it?")
        self.assertEqual(request_text("Hey Cusco!"), "")
        self.assertEqual(request_text("Cuz go, unmute."), "unmute.")
        self.assertEqual(request_text("Explain Kuzco."), "Explain Kuzco.")
        self.assertEqual(request_text("Costco is closed."), "Costco is closed.")

    def test_wake_session_history_silence_and_output_failure(self):
        listener = Mock()
        listener.listen.side_effect = ["Kuzco", "Kuzco, first", "Kuzco, follow-up", KeyboardInterrupt]
        histories = []
        def agent(prompt, **kwargs):
            histories.append(list(kwargs["history"]))
            kwargs["history"].append(prompt)
            return "Final answer."
        speaker = Mock(side_effect=[RuntimeError("speaker failed"), True])
        output = io.StringIO()
        with patch("builtins.input") as activation, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            voice.conversation(agent, listener=listener, speaker=speaker, wake=True)
        activation.assert_not_called()
        self.assertEqual(histories, [[], ["first"]])
        self.assertEqual(speaker.call_count, 2)
        self.assertIn("Heard: Kuzco, first", output.getvalue())
        self.assertIn("SPEAKING", output.getvalue())

    def test_input_failure_stops_without_agent_or_retry(self):
        listener = Mock()
        listener.listen.side_effect = VoiceInputError("permission denied")
        agent, speaker = Mock(), Mock()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            voice.conversation(agent, listener=listener, speaker=speaker, wake=True)
        self.assertEqual(listener.listen.call_count, 1)
        agent.assert_not_called()
        speaker.assert_not_called()

    def test_handoff_buffer_bounded_and_no_transcription_before_wake(self):
        listener = WakeSpeechInput(seconds=1)
        detector = listener.detector = Mock()
        # The synthetic prefix is consumed before the first microphone chunk.
        detector.is_ready.side_effect = [False] + [True, False] * 19 + [True]
        detector.get_result.side_effect = [""] * 19 + ["KUZCO"]
        stream = Mock()
        stream.read.return_value = (b"\x01\x00" * 1600, False)
        samples = Mock()
        samples.astype.return_value.__truediv__ = Mock(return_value=[])
        # No optional NumPy install is required for the regression suite.
        np = SimpleNamespace(frombuffer=Mock(return_value=samples), float32="float32")
        wake = Mock()
        with patch.dict("sys.modules", {"numpy": np}):
            pcm = listener.capture(stream, wake)
        wake.assert_called_once()
        self.assertEqual(len(pcm), (15 + 10) * 3200)
        self.assertEqual(stream.read.call_count, 30)

    def test_stream_closed_before_transcription_and_on_interrupt(self):
        listener = WakeSpeechInput()
        events = []
        class Stream:
            def __enter__(self): events.append("open"); return self
            def __exit__(self, *args): events.append("closed")
        sd = SimpleNamespace(query_devices=Mock(return_value={"max_input_channels": 1}),
                             RawInputStream=Mock(return_value=Stream()), PortAudioError=RuntimeError)
        listener.capture = Mock(return_value=b"audio")
        listener.transcribe = Mock(side_effect=lambda pcm: events.append("transcribe") or "hello")
        with patch.dict("sys.modules", {"sounddevice": sd}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(listener.listen(), "hello")
            self.assertEqual(events, ["open", "closed", "transcribe"])
            listener.capture.side_effect = KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt): listener.listen()
        self.assertEqual(events[-1], "closed")

    def test_british_voice_is_an_argument_and_final_text_uses_stdin(self):
        with patch("speech_output.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as process:
            speak("Hello, sir.", voice_name="Daniel")
        self.assertEqual(process.call_args.args[0], ["/usr/bin/say", "-v", "Daniel", "-f", "-"])
        self.assertEqual(process.call_args.kwargs["input"], "Hello, sir.")
        self.assertFalse(process.call_args.kwargs["shell"])

    @patch("listener_lock.ListenerLock", new=lambda: contextlib.nullcontext())
    def test_wake_cli_and_conflicts(self):
        with patch("sys.argv", ["main.py", "--wake", "--personality", "kuzco"]), patch("voice.conversation") as chat:
            self.assertEqual(main.main(), 0)
        self.assertTrue(chat.call_args.kwargs["wake"])
        # Default speech is selected by the shared voice entry point/config.
        self.assertNotIn("speaker", chat.call_args.kwargs)
        for flags in [["--wake", "--voice"], ["--wake", "--chat"], ["--wake", "hello"]]:
            with patch("sys.argv", ["main.py"] + flags), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main.main()
