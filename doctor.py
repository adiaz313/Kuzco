"""Read-only installation checks; --live sends two synthetic local model requests."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
from configuration import ROOT, asset, home, load


def verify_template(path):
    expected = (ROOT / 'runtime/llama31.jinja').read_text()
    text = Path(path).expanduser().read_text()
    if Path(path).suffix == '.json':
        config = json.loads(text)
        fields = config.get('load', {}).get('fields', [])
        templates = [f['value']['jinjaPromptTemplate']['template'] for f in fields
                     if f.get('key') == 'llm.load.promptTemplate']
        if len(templates) != 1:
            raise ValueError('Expected one explicit model template in saved configuration')
        text = templates[0]
    if text != expected:
        raise ValueError('Template differs from runtime/llama31.jinja; follow docs/RUNTIME.md')
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--template-config', help='Saved per-model JSON or exported active Jinja template to verify')
    args = parser.parse_args(argv)
    failures = []
    def check(name, operation):
        try:
            value = operation()
            print('PASS', name, '' if value is None else value)
        except Exception as error:
            failures.append(name)
            print('FAIL', name, str(error))
    def platform_check():
        if sys.platform != 'darwin' or platform.machine() != 'arm64' or int(platform.mac_ver()[0].split('.')[0]) < 14:
            raise ValueError('Requires Apple Silicon macOS 14+')
        if sys.version_info[:3] != (3, 14, 7):
            raise ValueError('Use the pinned Python 3.14.7 environment')
    check('platform/Python', platform_check)
    check('configuration', lambda: (load(), None)[1])
    def models():
        from install_assets import checksum
        for entry in json.loads((ROOT / 'assets.json').read_text()):
            if checksum(asset(entry['path'])) != entry['sha256']:
                raise ValueError('Asset checksum mismatch: ' + entry['path'])
        for name in ['whisper.cpp/build/bin/whisper-cli', 'indicator']:
            if not asset(name).is_file():
                raise ValueError('Missing built ' + name)
    check('voice assets and builds', models)
    def voice_setup():
        from wake_input import WakeSpeechInput
        WakeSpeechInput().check_setup()  # No microphone capture.
    check('Sherpa/Whisper setup', voice_setup)
    if args.template_config:
        check('explicit LM Studio template', lambda: verify_template(args.template_config))
    else:
        print('REQUIRED: configure runtime/llama31.jinja in LM Studio; verify with --template-config. See docs/RUNTIME.md.')
        failures.append('template not verified')
    if args.live:
        from main import chat
        from models import model_id
        def plain():
            result = chat({'model': model_id(), 'messages': [{'role': 'user', 'content': 'Reply with only the word Hello.'}],
                           'tool_choice': 'none', 'temperature': 0, 'max_tokens': 30})
            if result.get('content', '').strip().rstrip('.!') != 'Hello' or result.get('tool_calls'):
                raise ValueError('Unexpected no-tools response; inspect the active runtime template')
        def structured():
            result = chat({'model': model_id(), 'messages': [{'role':'user', 'content':'Reply with a JSON answer saying Hello.'}],
                           'tool_choice':'none', 'temperature':0, 'max_tokens':60,
                           'response_format':{'type':'json_schema','json_schema':{'name':'check','schema':{
                               'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}}}})
            if not isinstance(json.loads(result['content']).get('answer'), str):
                raise ValueError('Structured output is unavailable')
        check('local no-tools response', plain)
        check('local structured response', structured)
    print('Data location:', home())
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
