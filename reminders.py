"""Purpose-limited EventKit bridge; Apple Reminders owns storage and delivery."""
import json
import plistlib
import re
import subprocess

from configuration import ROOT, asset
from security_policy import enforced


def executable():
    return asset('Kuzco Reminders.app/Contents/MacOS/KuzcoReminders')


def build():
    binary = executable()
    binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    bundle = binary.parents[2]
    info = {'CFBundleIdentifier': 'local.kuzco.reminders',
            'CFBundleName': 'Kuzco Reminders', 'CFBundleExecutable': 'KuzcoReminders',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1', 'LSUIElement': True,
            'NSRemindersUsageDescription':
                'Kuzco accesses Apple Reminders only when you ask to create, list, complete, or remove a reminder.',
            'NSRemindersFullAccessUsageDescription':
                'Kuzco accesses Apple Reminders only when you ask to create, list, complete, or remove a reminder.'}
    (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native/Reminders.swift'),
                    '-o', str(binary)], check=True, timeout=120)
    for attempt in range(2):
        for attribute in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
            subprocess.run(['/usr/bin/xattr', '-r', '-d', attribute, str(bundle)],
                           capture_output=True, timeout=10)
        signed = subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-',
                                 '--identifier', 'local.kuzco.reminders', str(bundle)],
                                capture_output=True, text=True, timeout=30)
        if signed.returncode == 0:
            break
    if signed.returncode:
        raise RuntimeError('Could not sign the Reminders helper.')
    return binary


def _invoke(action, **fields):
    binary = executable()
    if not binary.is_file():
        return {'error': 'Reminders integration is not installed. Run the documented asset setup.'}
    try:
        result = subprocess.run([str(binary)], input=json.dumps({'action': action, **fields}) + '\n',
                                capture_output=True, text=True, timeout=65)
        if result.returncode:
            return {'error': 'Apple Reminders integration failed.'}
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError('Invalid response')
        if data.get('error') == 'permission_denied':
            return {'error': 'Reminders access was denied. Allow Kuzco Reminders in macOS Privacy & Security → Reminders.'}
        if data.get('error') == 'permission_timeout':
            return {'error': 'Reminders permission request timed out. Check the macOS permission prompt.'}
        if data.get('error'):
            return {'error': 'Apple Reminders could not complete the request (' + str(data['error'])[:50] + ').'}
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {'error': 'Apple Reminders is currently unavailable.'}


def _valid_title(title):
    if not isinstance(title, str) or not title.strip() or len(title) > 200 or '\n' in title:
        raise ValueError('Provide a short reminder title.')
    return title.strip()


@enforced('reminders_create')
def create(title, due_iso):
    title = _valid_title(title)
    if not isinstance(due_iso, str) or len(due_iso) > 40:
        raise ValueError('Invalid reminder time.')
    result = _invoke('create', title=title, due_iso=due_iso)
    result.pop('identifier', None)
    return result


@enforced('reminders_list')
def list_items():
    data = _invoke('list')
    if 'error' in data:
        return data
    items = data.get('items')
    if not isinstance(items, list):
        return {'error': 'Apple Reminders returned an invalid list.'}
    # Never send opaque EventKit identifiers, unrelated metadata, or an unbounded
    # personal list into the model/conversation. The bridge's 200-item cap is
    # retained internally for exact selection; only 20 entries leave this layer.
    return {'items': [{'title': str(item.get('title', ''))[:200],
                       'due_iso': str(item.get('due_iso', ''))[:40]}
                      for item in items[:20] if isinstance(item, dict)],
            'truncated': bool(data.get('truncated') or len(items) > 20)}


def _normalize(value):
    numbers = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
               'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}
    words = re.sub(r'[^\w ]', ' ', value.casefold()).split()
    # Whisper commonly alternates spoken numbers/digits and singular/plural.
    # Apply this only to item identity; a second match still fails closed.
    return ' '.join(numbers.get(word, word[:-1] if word.endswith('s') and len(word) > 3 else word)
                    for word in words)


def _choose(title):
    data = _invoke('list')
    if 'error' in data:
        return data
    items = data.get('items')
    if not isinstance(items, list) or data.get('truncated'):
        return {'error': 'Too many reminders to select safely; use Apple Reminders directly.'}
    needle = _normalize(title)
    matches = [item for item in items if isinstance(item, dict) and
               _normalize(str(item.get('title', ''))) == needle]
    if not matches:
        matches = [item for item in items if isinstance(item, dict) and
                   needle in _normalize(str(item.get('title', ''))).split(' ')]
    if len(matches) > 1:
        return {'error': 'More than one reminder matches. Please use its full, unique title.'}
    if not matches:
        return {'error': 'No matching reminder was found.'}
    identifier = matches[0].get('identifier')
    if not isinstance(identifier, str) or not identifier:
        return {'error': 'The matching reminder has no usable identifier.'}
    return {'identifier': identifier}


@enforced('reminders_complete')
def complete(title):
    chosen = _choose(_valid_title(title))
    if 'error' in chosen:
        return chosen
    return _invoke('complete', identifier=chosen['identifier'])


@enforced('reminders_remove')
def remove(title):
    chosen = _choose(_valid_title(title))
    if 'error' in chosen:
        return chosen
    return _invoke('remove', identifier=chosen['identifier'])


if __name__ == '__main__':
    build()
    print('Kuzco Reminders helper built. macOS will request Reminders access on first use.')
