"""Deployment adapter: bounded logs, microphone recovery, existing voice session."""
import contextlib
from functools import partial
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import sys
import threading

ROOT = Path(__file__).resolve().parent
from configuration import home, documents, load
LOGS = home() / 'logs'


def configure_logging(directory=LOGS):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    logger = logging.getLogger('kuzco.background')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(directory / 'runtime.log', maxBytes=512 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    return logger


class EventOutput:
    """Keep lifecycle/errors, omit spoken text and prompts from background logs."""
    def __init__(self, logger):
        self.logger = logger
        self.buffer = ''
        self.answer_continuation = False

    def write(self, text):
        self.buffer += text
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line.startswith('[state]'):
                self.answer_continuation = False
            elif self.answer_continuation:
                continue
            if line.startswith('Heard:'):
                line = 'Transcription completed (content omitted)'
            elif line.startswith('THINKING — request:'):
                line = 'Request processing'
            elif line.startswith('Jarvis:') and not line.startswith('Jarvis: Error:'):
                line = 'Final response ready (content omitted)'
                self.answer_continuation = True
            if line.strip():
                self.logger.info('%s', line[:1500])
        self.buffer = self.buffer[-1500:]
        return len(text)

    def flush(self):
        pass


def run():
    from assistant_state import AssistantState, State
    from indicator import Indicator
    from listener_lock import ListenerLock
    from speech_input import VoiceInputError
    from tts_output import speak
    from wake_input import WakeSpeechInput
    import main
    from routed import RoutingAgent
    import voice
    import sounddevice as sd
    from audio_devices import InputWatch, InputChanged, refresh, default_input
    from runtime_status import listener as listener_status

    logger = configure_logging()
    stopped, resumed = threading.Event(), threading.Event()
    def stop(signum, frame):
        stopped.set()
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGUSR1, lambda *_: resumed.set())

    class RecoveringInput(WakeSpeechInput):
        def capture(self, stream, on_wake):
            logger.info('Microphone initialized; wake listening active')
            listener_status(True)
            watch=InputWatch()
            if hasattr(self,'input_id'):watch.selected=self.input_id
            class ResumableStream:
                def read(self, frames):
                    watch.check()
                    if resumed.is_set():
                        resumed.clear()
                        raise VoiceInputError('Mac resumed; reopening microphone')
                    return stream.read(frames)
            try:
                return super().capture(ResumableStream(), on_wake)
            finally:
                listener_status(False)

        def listen(self):
            refresh_needed=False
            while not stopped.is_set():
                try:
                    current_input=default_input()
                    if hasattr(self,'input_id') and current_input is not None and current_input!=self.input_id:
                        refresh_needed=True
                    if refresh_needed:
                        # Previous with-stream has unwound: safe to rebuild device enumeration.
                        refresh(sd)
                        refresh_needed=False
                        logger.info('Audio runtime refreshed; following macOS selected input')
                    self.input_id=current_input
                    # Follow macOS's selected input, including headsets. Resolve
                    # afresh on each interaction/recovery rather than caching an index.
                    device = sd.query_devices(kind='input')
                    if device['max_input_channels'] < 1:
                        raise VoiceInputError('Selected microphone unavailable')
                    self.device = None
                    logger.info('Using selected microphone: %s', device['name'])
                    resumed.clear()
                    return super().listen()
                except (VoiceInputError, sd.PortAudioError) as error:
                    state.set(State.IDLE)
                    refresh_needed=True
                    if isinstance(error,InputChanged):
                        logger.info('%s',error)
                        continue
                    logger.warning('Voice input unavailable: %s; retrying in 15 seconds', error)
                    if stopped.wait(15):
                        raise KeyboardInterrupt
            raise KeyboardInterrupt

    routed_agent = RoutingAgent('direct')

    def agent(*args, **kwargs):
        try:
            return routed_agent(*args, **kwargs)
        except (ConnectionError, TimeoutError) as error:
            logger.warning('LM Studio unavailable: %s', error)
            # An explicit runtime status, not a fabricated Llama answer or tool result.
            return 'The local model is unavailable. Please start the LM Studio server and try again.'
        except RuntimeError as error:
            if not str(error).startswith('Local API HTTP '):
                raise
            logger.warning('LM Studio rejected the request: %s', str(error).split(':', 1)[0])
            return 'The local model could not process the request. Please check LM Studio and its loaded model, then try again.'

    logger.info('Background Kuzco started; pid=%s', __import__('os').getpid())
    listener_status(False)  # Remove stale readiness from an earlier process.
    try:
        with ListenerLock(), contextlib.redirect_stdout(EventOutput(logger)), contextlib.redirect_stderr(EventOutput(logger)):
            listener = RecoveringInput()
            with Indicator() as renderer:
                state = AssistantState(renderer)
                voice.conversation(agent, documents=documents(), personality=load()['personality'], wake=True, listener=listener,
                                   speaker=speak, state=state)
        logger.info('Background session exited')
        return 0
    except KeyboardInterrupt:
        logger.info('Background stopped')
        return 0
    except Exception:
        logger.exception('Background process failed')
        return 1
    finally:
        listener_status(False)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


if __name__ == '__main__':
    sys.exit(run())
