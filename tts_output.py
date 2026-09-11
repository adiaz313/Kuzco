"""Shared explicit speech selection for CLI and background Kuzco."""
import json
from pathlib import Path
from speech_output import VoiceOutputError

ROOT = Path(__file__).resolve().parent
from configuration import settings_path, asset


def speak(answer, engine=None, voice_name=None):
    try:
        settings = json.loads(settings_path('tts_settings.json').read_text())
        selected = engine or ('macos' if voice_name else settings['engine'])
        if selected == 'piper':
            from piper_output import speak as piper_speak
            return piper_speak(answer, model=asset(settings['model']))
        if selected == 'macos':
            from speech_output import speak as macos_speak
            return macos_speak(answer, voice_name=voice_name or settings['macos_voice'])
        raise ValueError('Unknown TTS engine')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise VoiceOutputError('Speech configuration is invalid. The answer remains on screen.') from error
