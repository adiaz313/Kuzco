"""Per-user macOS LaunchAgent management; never requires sudo."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time
import re

ROOT = Path(__file__).resolve().parent
from configuration import home, asset
LABEL = 'local.kuzco.background'
APP = home() / 'Kuzco Background.app'
LOGS = home() / 'logs'
PLIST = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
DOMAIN = f'gui/{os.getuid()}'
TARGET = f'{DOMAIN}/{LABEL}'


def definition(root=ROOT, app=APP):
    return {'Label': LABEL,
            'ProgramArguments': [str(app / 'Contents/MacOS/KuzcoBackground')],
            'WorkingDirectory': str(root), 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 60, 'ExitTimeOut': 12, 'ProcessType': 'Interactive',
            'LimitLoadToSessionType': 'Aqua', 'Umask': 0o077,
            'StandardOutPath': '/dev/null', 'StandardErrorPath': '/dev/null'}


def launchctl(*args, check=True):
    result = subprocess.run(['/bin/launchctl', *args], capture_output=True, text=True, timeout=20)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'launchctl failed')
    return result


def build():
    (APP / 'Contents/MacOS').mkdir(parents=True, exist_ok=True)
    info = {'CFBundleIdentifier': LABEL, 'CFBundleName': 'Kuzco Background',
            'CFBundleDisplayName': 'Kuzco Background', 'CFBundleExecutable': 'KuzcoBackground',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1', 'LSUIElement': True,
            'NSMicrophoneUsageDescription': 'Kuzco listens locally for its wake word and transcribes activated requests offline.',
            'KuzcoProject': str(ROOT), 'KuzcoHome': str(home())}
    (APP / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native/BackgroundLauncher.swift'),
                    '-o', str(APP / 'Contents/MacOS/KuzcoBackground')], check=True, timeout=120)
    # Finder metadata on this generated bundle can prevent local code signing.
    # Remove only those two signing-incompatible attributes, never privacy/quarantine data.
    for attribute in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
        subprocess.run(['/usr/bin/xattr', '-r', '-d', attribute, str(APP)],
                       capture_output=True, timeout=10)
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', '--identifier', LABEL, str(APP)],
                   check=True, timeout=30)
    # Build the existing display now, so startup doesn't need to compile it.
    asset('indicator').parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native/Indicator.swift'),
                    '-o', str(asset('indicator'))], check=True, timeout=120)


def stop():
    existing = launchctl('print', TARGET, check=False)
    if existing.returncode == 0:
        match = re.search(r'^\s*pid = (\d+)\s*$', existing.stdout, re.M)
        pid = int(match.group(1)) if match else None
        launchctl('bootout', TARGET)
        # bootout can return before teardown finishes. Never kickstart a dying job.
        deadline = time.monotonic() + 15
        while True:
            loaded = launchctl('print', TARGET, check=False).returncode == 0
            alive = False
            if pid:
                try:
                    os.kill(pid, 0)  # Probe only the exact launcher PID; do not kill it.
                    alive = True
                except ProcessLookupError:
                    pass
            if not loaded and not alive:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Background shutdown is still pending; inspect status/logs before starting again.')
            time.sleep(0.1)
    print('Background stopped. Automatic startup remains enabled for the next login.')


def start():
    if not PLIST.exists():
        raise RuntimeError('Not installed. Run python3 service.py install first.')
    launchctl('enable', TARGET)
    if launchctl('print', TARGET, check=False).returncode:
        launchctl('bootstrap', DOMAIN, str(PLIST))
    else:
        launchctl('kickstart', TARGET)  # Does not kill a healthy running job.
    print('Background start requested. Run python3 service.py status; check permission prompts.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'start', 'stop', 'restart', 'status', 'uninstall', 'permissions'])
    args = parser.parse_args(argv)
    try:
        if sys.platform != 'darwin':
            raise RuntimeError('Background service management requires macOS.')
        if args.action == 'install':
            if not (ROOT / '.venv/bin/python').exists():
                raise RuntimeError('Complete the locked installation in README.md first.')
            stop()
            build()
            PLIST.parent.mkdir(parents=True, exist_ok=True)
            temporary = PLIST.with_suffix('.tmp')
            temporary.write_bytes(plistlib.dumps(definition(ROOT)))
            temporary.chmod(0o600)
            temporary.replace(PLIST)
            start()
        elif args.action == 'start': start()
        elif args.action == 'stop': stop()
        elif args.action == 'restart':
            stop()
            start()
        elif args.action == 'uninstall':
            stop()
            launchctl('disable', TARGET)
            PLIST.unlink(missing_ok=True)
            print('Login startup removed. Project, app, and bounded logs retained.')
        elif args.action == 'permissions':
            if not APP.exists():
                raise RuntimeError('Run install first.')
            subprocess.run(['/usr/bin/open', '-W', str(APP), '--args', '--permissions-only'], check=True)
        else:
            result = launchctl('print', TARGET, check=False)
            print('Login configuration:', 'installed' if PLIST.exists() else 'not installed')
            if result.returncode:
                print('Background job: stopped/not loaded')
            else:
                reported = set()
                for line in result.stdout.splitlines():
                    for key in ['state =', 'pid =', 'last exit code =', 'runs =']:
                        if line.strip().startswith(key) and key not in reported:
                            print(line.strip())
                            reported.add(key)
            print('Logs:', LOGS)
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Service error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
