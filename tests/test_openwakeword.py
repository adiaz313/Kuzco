"""Candidate adapter tests: no optional runtime, microphone or downloaded models."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from speech_input import VoiceInputError
from wake_detector import OpenWakeWordDetector, WakeEngineSettings
from wake_input import WakeSpeechInput


class OpenWakeWordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ['kuzco.onnx','melspectrogram.onnx','embedding_model.onnx']:
            (self.root/name).write_bytes(b'fixture')
        self.settings = WakeEngineSettings('openwakeword',str(self.root/'kuzco.onnx'),0.5)
        self.model=Mock();self.model.predict.return_value={'kuzco':0.1}
        self.factory=Mock(return_value=self.model)

    def tearDown(self): self.tmp.cleanup()

    def detector(self): return OpenWakeWordDetector(self.settings,self.factory)

    def test_initialization_is_explicit_local_onnx_cpu(self):
        self.detector();kw=self.factory.call_args.kwargs
        self.assertEqual(kw['inference_framework'],'onnx');self.assertEqual(kw['ncpu'],1)
        self.assertEqual(kw['wakeword_models'],[str(self.root/'kuzco.onnx')])

    def test_default_stays_sherpa(self):
        self.assertEqual(WakeEngineSettings.load().engine,'sherpa')

    def test_configuration_validation(self):
        for value in [0,1,-1,float('nan'),True]:
            with self.assertRaises(ValueError): WakeEngineSettings(threshold=value)
        with self.assertRaises(ValueError): WakeEngineSettings(engine='unknown')
        with self.assertRaises(ValueError): WakeEngineSettings(model='')

    def test_config_rejects_unknown(self):
        p=self.root/'config.json';p.write_text('{"surprise":1}')
        with self.assertRaises(ValueError): WakeEngineSettings.load(p)

    def test_missing_model_does_not_substitute_phrase(self):
        (self.root/'kuzco.onnx').unlink()
        with self.assertRaises(VoiceInputError): self.detector()
        self.factory.assert_not_called()

    def test_initialization_failure(self):
        self.factory.side_effect=RuntimeError('bad model')
        with self.assertRaises(VoiceInputError): self.detector()

    def test_frame_buffer_threshold_and_reset(self):
        d=self.detector()
        with patch.dict('sys.modules',{'numpy':SimpleNamespace(frombuffer=lambda pcm,dtype:pcm)}):
            self.assertFalse(d.feed(b'\0'*1000));self.model.predict.assert_not_called()
            self.assertFalse(d.feed(b'\0'*2200));self.assertEqual(len(d.pending),640)
            self.model.predict.return_value={'kuzco':0.7}
            self.assertTrue(d.feed(b'\0'*2560))
        d.reset();self.assertEqual(d.pending,b'');self.assertEqual(d.score,0)

    def test_nonwake_audio_no_event(self):
        d=self.detector()
        with patch.dict('sys.modules',{'numpy':SimpleNamespace(frombuffer=lambda pcm,dtype:pcm)}):
            self.assertFalse(d.feed(b'\0'*2560))

    def test_malformed_score_fails_gracefully(self):
        d=self.detector();self.model.predict.return_value={'kuzco':float('nan')}
        with patch.dict('sys.modules',{'numpy':SimpleNamespace(frombuffer=lambda pcm,dtype:pcm)}):
            with self.assertRaises(VoiceInputError): d.feed(b'\0'*2560)

    def test_inference_failure(self):
        d=self.detector();self.model.predict.side_effect=RuntimeError('failed')
        with patch.dict('sys.modules',{'numpy':SimpleNamespace(frombuffer=lambda pcm,dtype:pcm)}):
            with self.assertRaises(VoiceInputError): d.feed(b'\0'*2560)

    def test_odd_pcm_rejected(self):
        d=self.detector()
        with patch.dict('sys.modules',{'numpy':SimpleNamespace()}):
            with self.assertRaises(VoiceInputError): d.feed(b'1')

    def test_immediate_callback_before_request_capture_and_repeated_cycles(self):
        listener=WakeSpeechInput();listener.frame_detector=Mock(score=0.8)
        events=[]
        listener.frame_detector.feed.side_effect=[False,True,True]
        listener.capture_request=Mock(side_effect=lambda *a:events.append('capture') or b'audio')
        stream=Mock();stream.read.return_value=(b'\0'*3200,False)
        for _ in range(2): listener.capture(stream,lambda:events.append('listening'))
        self.assertEqual(events,['listening','capture','listening','capture'])
        self.assertEqual(listener.frame_detector.reset.call_count,2)

    def test_microphone_recovery_error_propagates(self):
        listener=WakeSpeechInput();listener.frame_detector=Mock()
        stream=Mock();stream.read.side_effect=VoiceInputError('device disconnected')
        with self.assertRaises(VoiceInputError): listener.capture(stream,Mock())

    def test_overflow_no_wake(self):
        listener=WakeSpeechInput();listener.frame_detector=Mock()
        stream=Mock();stream.read.return_value=(b'\0'*3200,True)
        callback=Mock()
        with self.assertRaises(VoiceInputError): listener.capture(stream,callback)
        callback.assert_not_called()

    def test_setup_selects_candidate_only_when_requested(self):
        listener=WakeSpeechInput()
        with patch('speech_input.LocalSpeechInput.check_setup'), patch('wake_detector.WakeEngineSettings.load',return_value=self.settings), patch('wake_detector.OpenWakeWordDetector') as factory:
            listener.check_setup()
        factory.assert_called_once_with(self.settings)
        self.assertIs(listener.frame_detector,factory.return_value)

    def test_explicit_candidate_does_not_change_default_configuration(self):
        listener=WakeSpeechInput(engine_settings=self.settings)
        with patch('speech_input.LocalSpeechInput.check_setup'), patch('wake_detector.WakeEngineSettings.load') as load, patch('wake_detector.OpenWakeWordDetector') as factory:
            listener.check_setup()
        load.assert_not_called()
        factory.assert_called_once_with(self.settings)
        self.assertEqual(WakeEngineSettings.load().engine,'sherpa')
