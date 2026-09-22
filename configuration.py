"""Installation-owned paths and small, non-secret user configuration.

KUZCO_HOME selects an independent installation's data. No legacy data is copied.
Model requests remain loopback-only. Secrets belong in credentials.py/Keychain.
"""
import os
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parent


def home():
    return Path(os.environ.get('KUZCO_HOME', Path.home() / 'Library/Application Support/Kuzco')).expanduser().resolve()


def settings_path(name):
    user = home() / 'config' / name
    return user if user.exists() else ROOT / name


def load():
    values = {'port': 1234, 'model': 'meta-llama-3.1-8b-instruct',
              'personality': 'kuzco', 'documents': []}
    path = home() / 'config' / 'kuzco.toml'
    if path.exists():
        supplied = tomllib.loads(path.read_text())
        if set(supplied) - set(values):
            raise ValueError('Unknown Kuzco configuration key; credentials must use Keychain')
        values.update(supplied)
    if type(values['port']) is not int or not 1024 <= values['port'] <= 65535:
        raise ValueError('port must be 1024–65535; host is always localhost')
    for key in ('model', 'personality'):
        if not isinstance(values[key], str) or not values[key] or len(values[key]) > 200:
            raise ValueError('Invalid ' + key)
    if not isinstance(values['documents'], list) or len(values['documents']) > 30:
        raise ValueError('documents must be a list of at most 30 file paths')
    if any(not isinstance(p, str) or not Path(p).expanduser().is_absolute() for p in values['documents']):
        raise ValueError('Configured documents must have absolute local paths')
    return values


def asset(relative):
    return home() / 'assets' / relative


def documents():
    # A moved/deleted optional document must not disable unrelated assistant
    # capabilities. Explicit --docs paths still fail fast in main.py.
    return [path for p in load()['documents'] if (path := Path(p).expanduser()).exists()]


def initialize():
    import shutil
    for directory in (home(), home() / 'config', home() / 'assets', home() / 'logs'):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('voice_settings.json', 'tts_settings.json', 'wake_engine.json', 'security_settings.json'):
        destination = home() / 'config' / name
        if not destination.exists():
            shutil.copyfile(ROOT / name, destination)
            destination.chmod(0o600)
    path = home() / 'config/kuzco.toml'
    if not path.exists():
        path.write_text('# No credentials here. Paths to your own documents only.\nport = 1234\nmodel = "meta-llama-3.1-8b-instruct"\npersonality = "kuzco"\ndocuments = []\n')
        path.chmod(0o600)


if __name__ == '__main__':
    initialize()
    print('Configuration initialized at', home() / 'config')
