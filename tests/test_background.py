"""Service tests are isolated: no login configuration, mic, GUI or launchd edits."""
import contextlib
import io
import json
import logging
from pathlib import Path
import plistlib
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import background
from listener_lock import ListenerLock
import service


class BackgroundTests(unittest.TestCase):
    def test_device_change_closes_stream_before_refresh_without_restart(self):
        from audio_devices import InputChanged
        logger=Mock();logger.handlers=[]
        opened=[False];attempts=[]
        class Base:
            def capture(self,stream,on_wake):return stream.read(1600)
            def listen(self):
                attempts.append(1);opened[0]=True
                try:
                    stream=Mock();stream.read.return_value=(b'pcm',False)
                    self.capture(stream,Mock());return 'hello'
                finally:opened[0]=False
        first,second=Mock(),Mock()
        first.check.side_effect=InputChanged('changed')
        stop=Mock();stop.is_set.return_value=False
        resume=Mock();resume.is_set.return_value=False
        sd=SimpleNamespace(PortAudioError=RuntimeError,query_devices=lambda **k:{'name':'selected','max_input_channels':1})
        def refresh(_):self.assertFalse(opened[0])
        def conversation(agent,**kwargs):self.assertEqual(kwargs['listener'].listen(),'hello')
        with patch('background.configure_logging',return_value=logger),patch('background.signal.signal'),patch('background.threading.Event',side_effect=[stop,resume]),patch('listener_lock.ListenerLock'),patch('indicator.Indicator'),patch('wake_input.WakeSpeechInput',Base),patch('voice.conversation',side_effect=conversation),patch.dict('sys.modules',{'sounddevice':sd}),patch('audio_devices.InputWatch',side_effect=[first,second]),patch('audio_devices.default_input',return_value=1),patch('audio_devices.refresh',side_effect=refresh) as reset,patch('runtime_status.listener'):
            self.assertEqual(background.run(),0)
        self.assertEqual(len(attempts),2);reset.assert_called_once();stop.wait.assert_not_called()

    def setUp(self):
        # Production routing checks residency; ordinary tests never contact LM Studio.
        patcher = patch('model_session.ModelSession.ensure', return_value={'reused': True})
        self.residency = patcher.start()
        self.addCleanup(patcher.stop)

    def test_background_direct_time_bypasses_model(self):
        logger = Mock()
        logger.handlers = []
        def session(agent, **kwargs):
            answer = agent('What time is it?', personality='kuzco', history=[])
            self.assertIn('sir', answer)
        with patch('background.configure_logging', return_value=logger), patch('background.signal.signal'), patch('listener_lock.ListenerLock'), patch('indicator.Indicator'), patch('voice.conversation', side_effect=session), patch('main.chat') as chat, patch.dict('sys.modules', {'sounddevice': SimpleNamespace(PortAudioError=RuntimeError)}):
            self.assertEqual(background.run(), 0)
        chat.assert_not_called()
        self.residency.assert_not_called()

    def test_lock_rejects_duplicates_and_releases_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'listener.lock'
            with self.assertRaises(ValueError):
                with ListenerLock(path):
                    with self.assertRaisesRegex(RuntimeError, 'already listening'):
                        with ListenerLock(path): pass
                    raise ValueError('interrupted')
            with ListenerLock(path): pass
            self.assertTrue(path.exists())

    def test_plist_uses_exact_paths_keepalive_and_user_session(self):
        config = service.definition(Path('/tmp/project with spaces'), Path('/tmp/Kuzco Background.app'))
        self.assertEqual(config['ProgramArguments'], ['/tmp/Kuzco Background.app/Contents/MacOS/KuzcoBackground'])
        self.assertTrue(config['KeepAlive'])
        self.assertEqual(config['ThrottleInterval'], 60)
        self.assertEqual(config['LimitLoadToSessionType'], 'Aqua')
        self.assertNotIn('UserName', config)
        self.assertEqual(plistlib.loads(plistlib.dumps(config)), config)

    def test_install_and_remove_only_temporary_login_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.venv/bin').mkdir(parents=True)
            (root / '.venv/bin/python').touch()
            plist = root / 'LaunchAgents/test.plist'
            with patch.object(service, 'ROOT', root), patch.object(service, 'PLIST', plist), patch.object(service, 'build') as build, patch.object(service, 'stop'), patch.object(service, 'start') as start, patch.object(service, 'launchctl') as ctl, patch('service.sys.platform', 'darwin'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(service.main(['install']), 0)
                build.assert_called_once()
                start.assert_called_once()
                self.assertTrue(plist.exists())
                self.assertEqual(service.main(['uninstall']), 0)
                self.assertFalse(plist.exists())
                ctl.assert_called_once_with('disable', service.TARGET)

    def test_stop_and_start_use_only_owned_job_no_broad_kills(self):
        with patch.object(service, 'launchctl', side_effect=[SimpleNamespace(returncode=0, stdout=''), SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]) as ctl, contextlib.redirect_stdout(io.StringIO()):
            service.stop()
            self.assertEqual([c.args for c in ctl.call_args_list], [('print', service.TARGET), ('bootout', service.TARGET), ('print', service.TARGET)])
        with tempfile.TemporaryDirectory() as folder:
            plist = Path(folder) / 'owned.plist'; plist.touch()
            with patch.object(service, 'PLIST', plist), patch.object(service, 'launchctl', return_value=SimpleNamespace(returncode=0)) as ctl, contextlib.redirect_stdout(io.StringIO()):
                service.start()
                self.assertIn(('kickstart', service.TARGET), [c.args for c in ctl.call_args_list])
                self.assertNotIn(('kickstart', '-k', service.TARGET), [c.args for c in ctl.call_args_list])

    def test_stop_waits_for_delayed_launchd_teardown(self):
        responses = [SimpleNamespace(returncode=0, stdout=''), SimpleNamespace(returncode=0),
                     SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]
        with patch.object(service, 'launchctl', side_effect=responses), patch('service.time.sleep') as sleep, contextlib.redirect_stdout(io.StringIO()):
            service.stop()
        sleep.assert_called_once_with(0.1)

    def test_logs_rotate_and_omit_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            logger = background.configure_logging(Path(folder))
            handler = logger.handlers[-1]
            handler.maxBytes = 150
            output = background.EventOutput(logger)
            output.write('Heard: PRIVATE PROMPT\nTHINKING — request: PRIVATE PROMPT\nJarvis: PRIVATE ANSWER\n')
            for _ in range(30): output.write('[state] IDLE\n')
            for h in list(logger.handlers): h.close(); logger.removeHandler(h)
            files = list(Path(folder).glob('runtime.log*'))
            self.assertLessEqual(len(files), 4)
            contents = ''.join(p.read_text() for p in files)
            self.assertNotIn('PRIVATE', contents)
            self.assertIn('[state] IDLE', contents)

    def test_background_lm_failure_recovers_without_changing_agent(self):
        # The voice adapter and models are replaced, but the runtime agent wrapper runs.
        fake_logger = Mock()
        fake_logger.handlers = []
        outcomes = []
        def session(agent, **kwargs):
            outcomes.append(agent('time', history=[]))
            outcomes.append(agent('time', history=[]))
        with patch('background.configure_logging', return_value=fake_logger), patch('background.signal.signal'), patch('listener_lock.ListenerLock'), patch('indicator.Indicator'), patch('voice.conversation', side_effect=session), patch('main.run', side_effect=[ConnectionRefusedError('offline'), 'Current time, sir.']), patch.dict('sys.modules', {'sounddevice': SimpleNamespace(PortAudioError=RuntimeError)}):
            self.assertEqual(background.run(), 0)
        self.assertIn('LM Studio', outcomes[0])
        self.assertEqual(outcomes[1], 'Current time, sir.')
        fake_logger.warning.assert_called_once()

    def test_unloaded_model_status_does_not_mask_agent_budget_error(self):
        logger = Mock(); logger.handlers = []
        def session(agent, **kwargs):
            self.assertIn('loaded model', agent('time'))
            with self.assertRaisesRegex(RuntimeError, 'Maximum tool steps'):
                agent('time')
        with patch('background.configure_logging', return_value=logger), patch('background.signal.signal'), patch('listener_lock.ListenerLock'), patch('indicator.Indicator'), patch('voice.conversation', side_effect=session), patch('main.run', side_effect=[RuntimeError('Local API HTTP 400: no model'), RuntimeError('Maximum tool steps')]), patch.dict('sys.modules', {'sounddevice': SimpleNamespace(PortAudioError=RuntimeError)}):
            self.assertEqual(background.run(), 0)

    def test_microphone_retry_keeps_session_and_loads_no_extra_model(self):
        from speech_input import VoiceInputError
        fake_logger = Mock(); fake_logger.handlers = []
        attempts = []
        class Base:
            def __init__(self): pass
            def listen(self):
                attempts.append(self.device)
                if len(attempts) == 1: raise VoiceInputError('device lost')
                return 'hello'
        stop_event = Mock(); stop_event.is_set.return_value = False; stop_event.wait.return_value = False
        resume_event = Mock()
        sd = SimpleNamespace(PortAudioError=RuntimeError, query_devices=lambda **kwargs: {'name': 'AirPods', 'max_input_channels': 1}, _terminate=Mock(), _initialize=Mock())
        def session(agent, **kwargs): self.assertEqual(kwargs['listener'].listen(), 'hello')
        with patch('background.configure_logging', return_value=fake_logger), patch('background.signal.signal'), patch('background.threading.Event', side_effect=[stop_event, resume_event]), patch('listener_lock.ListenerLock'), patch('indicator.Indicator'), patch('wake_input.WakeSpeechInput', Base), patch('voice.conversation', side_effect=session), patch.dict('sys.modules', {'sounddevice': sd}):
            self.assertEqual(background.run(), 0)
        self.assertEqual(attempts, [None, None])
        sd._terminate.assert_called_once();sd._initialize.assert_called_once()
        stop_event.wait.assert_called_once_with(15)

    def test_audio_read_does_not_poll_device_selection(self):
        # Device enumeration inside active capture can stall CoreAudio. Resolve
        # selection only before opening the stream, never during its reads.
        fake_logger = Mock(); fake_logger.handlers = []
        class Base:
            def capture(self, stream, on_wake):
                return stream.read(1600)
        sd = SimpleNamespace(PortAudioError=RuntimeError,
            query_devices=Mock(side_effect=AssertionError('Must not enumerate during capture')))
        def session(agent, **kwargs):
            stream = Mock(); stream.read.return_value = (b'pcm', False)
            self.assertEqual(kwargs['listener'].capture(stream, Mock()), (b'pcm', False))
            sd.query_devices.assert_not_called()
        with patch('background.configure_logging', return_value=fake_logger), patch('background.signal.signal'), patch('listener_lock.ListenerLock'), patch('indicator.Indicator'), patch('wake_input.WakeSpeechInput', Base), patch('voice.conversation', side_effect=session), patch.dict('sys.modules', {'sounddevice': sd}), patch('runtime_status.listener'):
            self.assertEqual(background.run(), 0)
