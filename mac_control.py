"""Narrow native Mac controls. No arbitrary script, command, or app enumeration API."""
import json
import logging
import subprocess
import time

from configuration import ROOT, asset
from security_policy import enforced


def build():
    for source, target in [('AppFocus.swift', 'mac-focus'), ('Volume.swift', 'mac-volume')]:
        binary = asset(target)
        binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native' / source), '-o', str(binary)],
                       check=True, timeout=120)
    compiled = asset('music.scpt')
    subprocess.run(['/usr/bin/osacompile', '-o', str(compiled), str(ROOT / 'native/Music.applescript')],
                   check=True, timeout=30)


def _native(binary, *args):
    path = asset(binary)
    if not path.is_file():
        return {'error': 'Mac control assets are not installed. Run the documented setup.'}
    try:
        run = subprocess.run([str(path), *args], capture_output=True, text=True, timeout=8)
        if run.returncode:
            return {'error': 'macOS could not complete the action.'}
        data = json.loads(run.stdout)
        if not isinstance(data, dict):
            return {'error': 'Invalid macOS response.'}
        errors = {'no_output_device': 'No audio output device is available.',
                  'volume_unavailable': 'This output device does not offer adjustable system volume.',
                  'mute_unavailable': 'This output device does not offer system mute control.',
                  'volume_change_unverified': 'The volume change could not be verified.',
                  'mute_change_unverified': 'The mute change could not be verified.',
                  'invalid_percent': 'Choose a volume from 0 to 100 percent.'}
        if data.get('error') in errors:
            return {'error': errors[data['error']]}
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {'error': 'macOS control is currently unavailable.'}


@enforced('focus_application')
def focus_application(application_name):
    result = _native('mac-focus', application_name)
    if result.get('error') == 'not_running':
        return {'error': application_name + ' is not running.'}
    if result.get('error') == 'ambiguous_application':
        return {'error': 'More than one running app has that name.'}
    if result.get('focused') is not True and 'error' not in result:
        return {'error': 'macOS could not verify that the app came to the foreground.'}
    return result


@enforced('volume_adjust')
def volume_adjust(direction):
    return _native('mac-volume', 'adjust', direction)


@enforced('volume_set')
def volume_set(percent):
    return _native('mac-volume', 'set', percent)


@enforced('volume_mute')
def volume_mute(muted):
    return _native('mac-volume', 'mute', muted)


def _music(operation, name=''):
    def failed(category, message):
        logging.getLogger('kuzco.background').info(
            'Music action failed category=%s (content omitted)', category)
        return {'error': message}
    script = asset('music.scpt')
    if not script.is_file():
        return failed('not_installed', 'Music control is not installed. Run the documented setup.')
    previous_id = None
    if operation in {'next', 'previous'}:
        try:
            before = subprocess.run(['/usr/bin/osascript', str(script), 'track_id', ''],
                                    capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return failed('state_unavailable', 'Apple Music track could not be verified.')
        if before.returncode:
            return failed('state_unavailable', 'Apple Music track could not be verified.')
        previous_id = before.stdout.strip()
    try:
        result = subprocess.run(['/usr/bin/osascript', str(script), operation, name],
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return failed('timeout', 'Apple Music did not respond.')
    if result.returncode:
        error = result.stderr.lower()
        if '-1743' in error or 'not authorized' in error or 'not permitted' in error:
            return failed('permission', 'Allow Kuzco Background to control Music in macOS Privacy & Security → Automation.')
        return failed('native_error', 'Apple Music could not complete the request.')
    state = result.stdout.strip().lower()
    if state == 'not_found':
        return failed('not_found', 'That content was not found in your Music library.')
    if state == 'ambiguous':
        return failed('ambiguous', 'More than one Music item matches; please be more specific.')
    if state == 'unsupported':
        return failed('unsupported', 'That Music request is not supported yet.')
    if state == 'no_active_media':
        return failed('no_active_media', 'No Music track is active.')
    if state != 'accepted':
        return failed('invalid_state', 'Apple Music returned an unrecognized playback state.')
    expected = {'pause': {'paused', 'stopped'}}.get(operation, {'playing'})
    check = 'verify_' + operation if operation in {'playlist', 'song'} else 'state'
    deadline = time.monotonic() + 6
    back_retried = False
    while True:
        try:
            status = subprocess.run(['/usr/bin/osascript', str(script), check,
                                     name if check != 'state' else ''],
                                    capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return failed('state_unavailable', 'Apple Music playback could not be verified.')
        if status.returncode:
            return failed('state_unavailable', 'Apple Music playback could not be verified.')
        state = status.stdout.strip().lower()
        if state in expected:
            if operation in {'next', 'previous'}:
                try:
                    after = subprocess.run(['/usr/bin/osascript', str(script), 'track_id', ''],
                                           capture_output=True, text=True, timeout=8)
                except (OSError, subprocess.TimeoutExpired):
                    return failed('state_unavailable', 'Apple Music track could not be verified.')
                if after.returncode:
                    return failed('state_unavailable', 'Apple Music track could not be verified.')
                if after.stdout.strip() == previous_id:
                    if operation == 'previous' and not back_retried:
                        # Music's documented back-track restarts a song when it
                        # is well underway; a second press near the start goes
                        # to the prior song. Recheck identity before pressing.
                        time.sleep(0.25)
                        try:
                            current = subprocess.run(['/usr/bin/osascript', str(script), 'track_id', ''],
                                                     capture_output=True, text=True, timeout=8)
                        except (OSError, subprocess.TimeoutExpired):
                            return failed('state_unavailable', 'Apple Music track could not be verified.')
                        if current.returncode:
                            return failed('state_unavailable', 'Apple Music track could not be verified.')
                        if current.stdout.strip() != previous_id:
                            return {'player_state': state}
                        try:
                            again = subprocess.run(['/usr/bin/osascript', str(script), 'previous', ''],
                                                   capture_output=True, text=True, timeout=20)
                        except (OSError, subprocess.TimeoutExpired):
                            return failed('native_error', 'Apple Music could not complete the request.')
                        if again.returncode or again.stdout.strip().lower() != 'accepted':
                            return failed('native_error', 'Apple Music could not complete the request.')
                        back_retried = True
                        continue
                    if time.monotonic() >= deadline:
                        return failed('track_unchanged', 'Music did not change tracks; the current queue may have no other track.')
                    time.sleep(0.25)
                    continue
            return {'player_state': state}
        if state not in {'playing', 'paused', 'stopped', 'mismatch'}:
            return failed('invalid_state', 'Apple Music returned an unrecognized playback state.')
        if time.monotonic() >= deadline:
            if operation in {'playlist', 'song'}:
                return failed('selection_failed', 'Music did not select and play the requested content.')
            return failed('playback_failed', 'Music did not start playback.' if operation != 'pause'
                          else 'Music did not pause playback.')
        time.sleep(0.25)


@enforced('music_transport')
def music_transport(action):
    return _music(action)


@enforced('music_play_named')
def music_play_named(kind, name):
    if kind in {'artist', 'album'}:
        return {'error': 'Playing a named ' + kind + ' is not reliable through this Music library interface yet.'}
    return _music(kind, name)
