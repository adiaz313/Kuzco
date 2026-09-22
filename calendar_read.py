"""Read-only structured Calendar access; native Calendar remains authoritative."""
from datetime import date, datetime, timedelta
import json
import plistlib
import subprocess

from configuration import ROOT, asset
from security_policy import enforced


def executable():
    return asset('Kuzco Calendar.app/Contents/MacOS/KuzcoCalendar')


def build():
    binary = executable()
    binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    bundle = binary.parents[2]
    info = {'CFBundleIdentifier': 'local.kuzco.calendar',
            'CFBundleName': 'Kuzco Calendar', 'CFBundleExecutable': 'KuzcoCalendar',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1', 'LSUIElement': True,
            'NSCalendarsFullAccessUsageDescription':
                'Kuzco reads Apple Calendar events only when you explicitly ask about your schedule. It cannot change events.'}
    (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native/CalendarRead.swift'),
                    '-o', str(binary)], check=True, timeout=120)
    for attempt in range(2):
        for attribute in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
            subprocess.run(['/usr/bin/xattr', '-r', '-d', attribute, str(bundle)],
                           capture_output=True, timeout=10)
        signed = subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-',
                                 '--identifier', 'local.kuzco.calendar', str(bundle)],
                                capture_output=True, text=True, timeout=30)
        if signed.returncode == 0:
            break
    if signed.returncode:
        raise RuntimeError('Could not sign the Calendar helper.')
    return binary


def _invoke(action, **fields):
    binary = executable()
    if not binary.is_file():
        return {'error': 'Calendar integration is not installed. Run the documented asset setup.'}
    try:
        result = subprocess.run([str(binary)], input=json.dumps({'action': action, **fields}) + '\n',
                                capture_output=True, text=True, timeout=55)
        if result.returncode:
            return {'error': 'Apple Calendar integration failed.'}
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError('Invalid response')
        errors = {'permission_denied': 'Calendar access was denied. Allow Kuzco Calendar in macOS Privacy & Security → Calendars.',
                  'permission_timeout': 'Calendar permission request timed out. Check the macOS permission prompt.',
                  'invalid_range': 'Calendar date range is invalid.',
                  'unknown_action': 'That Calendar operation is unavailable.',
                  'invalid_request': 'Calendar request was invalid.'}
        if 'error' in data:
            return {'error': errors.get(data['error'], 'Apple Calendar could not complete the request.')}
        events = data.get('events')
        if (not isinstance(events, list) or len(events) > 50 or
                any(not isinstance(item, dict) or not isinstance(item.get('title'), str) or
                    not isinstance(item.get('start_iso'), str) or
                    not isinstance(item.get('end_iso'), str) or
                    not isinstance(item.get('all_day'), bool) or
                    ('location' in item and (not isinstance(item['location'], str) or
                                             len(item['location']) > 200)) for item in events) or
                not isinstance(data.get('truncated'), bool)):
            raise ValueError('Invalid events')
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {'error': 'Apple Calendar is currently unavailable.'}


@enforced('calendar_day')
def day(day):
    try:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError:
        return {'error': 'Invalid Calendar day.'}
    return _invoke('day', day=day)


@enforced('calendar_next')
def next_event(kind):
    if kind not in {'event', 'timed'}:
        return {'error': 'Unknown Calendar event kind.'}
    return _invoke('next', timed_only=kind == 'timed')


@enforced('calendar_range')
def range_events(start_iso, end_iso, kind):
    """Bounded overlap query used only by the deterministic Calendar Skill."""
    try:
        start, end = datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso)
        if start.tzinfo is None or end.tzinfo is None or not start < end or (end-start).total_seconds() > 31*86400:
            raise ValueError
    except (TypeError, ValueError):
        return {'error': 'Invalid Calendar date range.'}
    if kind not in {'all', 'timed'}:
        return {'error': 'Unknown Calendar event kind.'}
    return _invoke('range', start_iso=start_iso, end_iso=end_iso,
                   timed_only=kind == 'timed')


@enforced('greeting_calendar_context')
def greeting_structure():
    """Return only schedule shape for unsolicited greeting composition.

    Titles, locations and calendar names are deliberately discarded here and
    never reach the greeting layer.
    """
    now = datetime.now().astimezone()
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=now.tzinfo)
    result = _invoke('range', start_iso=start.isoformat(timespec='seconds'),
                     end_iso=(start + timedelta(days=1)).isoformat(timespec='seconds'),
                     timed_only=False)
    if result.get('error'):
        return {'error': result['error']}
    timed = []
    all_day = 0
    for event in result['events']:
        if event['all_day']:
            all_day += 1
            continue
        try:
            begin = datetime.fromisoformat(event['start_iso'])
            end = datetime.fromisoformat(event['end_iso'])
        except (TypeError, ValueError):
            continue
        timed.append((begin, end))
    timed.sort()
    upcoming = [begin for begin, end in timed if end > now]
    return {'timed_count': len(timed), 'all_day_count': all_day,
            'next_start_iso': upcoming[0].isoformat() if upcoming else None}


if __name__ == '__main__':
    build()
    print('Kuzco Calendar helper built. macOS will request Calendar access on first use.')
