"""No microphone, GUI, compiler, or model required."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import Mock, patch

from assistant_state import AssistantState, State
from speech_input import LocalSpeechInput
from wake_input import WakeSpeechInput
from indicator import Indicator
import main
import voice


class StateTests(unittest.TestCase):
    def test_explicit_states_deduplicate_and_isolate_renderer_failure(self):
        renderer = Mock(side_effect=RuntimeError("display failed"))
        state = AssistantState(renderer)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            state.set(State.IDLE)
            state.set(State.IDLE)
            state.set(State.LISTENING)
        renderer.assert_called_once_with("IDLE")
        self.assertEqual(state.current, State.LISTENING)
        with self.assertRaises(ValueError): state.set("not a state")

    def test_repeated_wake_cycles_and_capture_callback_timing(self):
        events = []
        state = AssistantState(events.append)
        class Listener(WakeSpeechInput):
            attempts = 0
            def check_setup(self): pass
            def capture(self, stream, on_wake):
                on_wake()
                self_test.assertEqual(state.current, State.LISTENING)
                return b"audio"
            def listen(self):
                self.attempts += 1
                if self.attempts == 4: raise KeyboardInterrupt
                self.capture(None, self.notify_listening)
                self.on_thinking()
                self_test.assertEqual(state.current, State.THINKING)
                return "Kuzco, request"
        self_test = self
        histories = []
        def agent(prompt, **kwargs):
            self.assertEqual(state.current, State.THINKING)
            histories.append(len(kwargs['history']))
            kwargs['history'].append(prompt)
            return "Answer"
        def speaker(answer): self.assertEqual(state.current, State.SPEAKING)
        with contextlib.redirect_stdout(io.StringIO()), patch('voice.time.sleep'):
            voice.conversation(agent, wake=True, listener=Listener(), speaker=speaker, state=state)
        self.assertEqual(events, ['IDLE'] + ['LISTENING', 'THINKING', 'SPEAKING', 'IDLE'] * 3)
        self.assertEqual(histories, [0, 1, 2])

    def test_ptt_thinking_begins_before_transcription(self):
        events = []
        state = AssistantState(events.append)
        listener = LocalSpeechInput()
        listener.check_setup = Mock()
        def record():
            self.assertEqual(state.current, State.LISTENING)
            return b'audio'
        def transcribe(pcm):
            self.assertEqual(state.current, State.THINKING)
            return 'Hello'
        listener.record = record
        listener.transcribe = transcribe
        with patch('builtins.input', side_effect=['', '/exit']), contextlib.redirect_stdout(io.StringIO()):
            voice.conversation(Mock(return_value='Hello'), listener=listener, speaker=Mock(), state=state)
        self.assertEqual(events, ['IDLE', 'LISTENING', 'THINKING', 'SPEAKING', 'IDLE'])

    def test_all_failure_paths_and_silence_return_idle(self):
        for failure in ['input', 'silence', 'agent', 'speaker', 'interrupt']:
            events = []
            state = AssistantState(events.append)
            listener, agent, speaker = Mock(), Mock(return_value='Answer'), Mock()
            listener.listen.return_value = 'request'
            if failure == 'input': listener.listen.side_effect = RuntimeError('input')
            if failure == 'silence': listener.listen.return_value = ''
            if failure == 'agent': agent.side_effect = RuntimeError('agent')
            if failure == 'speaker': speaker.side_effect = RuntimeError('speaker')
            if failure == 'interrupt': listener.listen.side_effect = KeyboardInterrupt
            with self.subTest(failure=failure), patch('builtins.input', side_effect=['', '/exit']), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                voice.conversation(agent, listener=listener, speaker=speaker, state=state)
            self.assertEqual(events[-1], 'IDLE')
            if failure in ['input', 'silence', 'agent', 'interrupt']:
                self.assertNotIn('SPEAKING', events)

    def test_broken_renderer_does_not_prevent_answer(self):
        listener = Mock()
        listener.listen.return_value = 'hello'
        speaker = Mock()
        with patch('builtins.input', side_effect=['', '/exit']), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            voice.conversation(Mock(return_value='Final'), listener=listener, speaker=speaker,
                               state=AssistantState(Mock(side_effect=RuntimeError('broken'))))
        speaker.assert_called_once_with('Final')

    def test_indicator_missing_compiler_and_full_queue_are_nonblocking(self):
        with patch('indicator.sys.platform', 'darwin'), patch('indicator.Path.exists', return_value=False), patch('indicator.subprocess.run', side_effect=OSError('no compiler')), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with Indicator() as indicator: indicator('LISTENING')
        indicator = Indicator()
        indicator.process = Mock()
        indicator.process.poll.return_value = None
        for _ in range(16): indicator('IDLE')
        with self.assertRaises(RuntimeError): indicator('LISTENING')

    def test_renderer_child_is_cleaned_up(self):
        indicator = Indicator()
        indicator.process = Mock()
        indicator.process.poll.return_value = None
        indicator.__exit__()
        indicator.process.terminate.assert_called_once()
        indicator.process.wait.assert_called_once_with(timeout=2)
        indicator.process.stdin.close.assert_called_once()

    @patch("listener_lock.ListenerLock", new=lambda: contextlib.nullcontext())
    def test_cli_opt_in_and_text_remains_without_renderer(self):
        with patch('sys.argv', ['main.py', '--wake', '--indicator']), patch('indicator.Indicator') as renderer, patch('voice.conversation') as session:
            self.assertEqual(main.main(), 0)
            self.assertIsInstance(session.call_args.kwargs['state'], AssistantState)
        with patch('sys.argv', ['main.py', '--chat']), patch('main.conversation'), patch('indicator.Indicator') as renderer:
            self.assertEqual(main.main(), 0)
            renderer.assert_not_called()
        with patch('sys.argv', ['main.py', '--chat', '--indicator']), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main.main()
