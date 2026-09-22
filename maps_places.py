"""Narrow Apple MapKit adapter; structured data only, no UI automation."""
from datetime import datetime
import json
import logging
import math
import plistlib
import subprocess

from configuration import ROOT, asset
from security_policy import enforced


def executable():
    return asset('Kuzco Maps.app/Contents/MacOS/KuzcoMaps')


def build():
    binary = executable()
    binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    bundle = binary.parents[2]
    info = {'CFBundleIdentifier': 'local.kuzco.maps', 'CFBundleName': 'Kuzco Maps',
            'CFBundleExecutable': 'KuzcoMaps', 'CFBundlePackageType': 'APPL',
            'CFBundleVersion': '1', 'LSUIElement': True,
            'NSLocationUsageDescription': 'Kuzco uses current location only for a place or route request you make.',
            'NSLocationWhenInUseUsageDescription': 'Kuzco uses current location only for a place or route request you make.'}
    (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native/MapsPlaces.swift'),
                    '-o', str(binary)], check=True, timeout=120)
    for _ in range(2):
        for attribute in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
            subprocess.run(['/usr/bin/xattr', '-r', '-d', attribute, str(bundle),
                           ], capture_output=True, timeout=10)
        signed = subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-',
                                 '--identifier', 'local.kuzco.maps', str(bundle)],
                                capture_output=True, text=True, timeout=30)
        if signed.returncode == 0:
            break
    signed.check_returncode()
    return binary


def _invoke(action, **fields):
    if not executable().is_file():
        return {'error': 'Maps integration is not installed. Run the documented asset setup.'}
    try:
        run = subprocess.run([str(executable())], input=json.dumps({'action': action, **fields}) + '\n',
                             capture_output=True, text=True, timeout=20)
        if run.returncode or len(run.stdout) > 100_000:
            raise ValueError
        data = json.loads(run.stdout)
        data = _normalize(action, data)
        logging.getLogger('kuzco.background').info('Maps operation=%s outcome=%s candidates=%s',
            action, 'failure' if data.get('error') else 'success',
            len(data.get('results', data.get('candidates', []))))
        return data
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return {'error': 'provider_unavailable'}


def _safe_string(value, limit=500):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 and c not in '\t\r\n' for c in value):
        raise ValueError
    return ' '.join(value.split())


def _candidate(value):
    if not isinstance(value, dict) or not {'name', 'address', 'latitude', 'longitude', 'source'} <= set(value):
        raise ValueError
    allowed = {'name', 'address', 'latitude', 'longitude', 'source', 'provider_id',
               'category', 'phone', 'website', 'city', 'distance_meters'}
    if set(value) - allowed:
        raise ValueError
    result = {key: _safe_string(value[key]) for key in value
              if key not in {'latitude', 'longitude', 'distance_meters'}}
    latitude, longitude = value['latitude'], value['longitude']
    if (type(latitude) not in (int, float) or type(longitude) not in (int, float)
            or not math.isfinite(latitude) or not math.isfinite(longitude)
            or abs(latitude) > 90 or abs(longitude) > 180):
        raise ValueError
    result.update(latitude=float(latitude), longitude=float(longitude))
    if 'distance_meters' in value:
        distance = value['distance_meters']
        if type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0:
            raise ValueError
        result['distance_meters'] = float(distance)
    return result


def _normalize(action, data):
    if not isinstance(data, dict):
        raise ValueError
    if 'error' in data:
        allowed_errors = {'permission_denied', 'location_failed', 'provider_unavailable',
                          'no_result', 'ambiguous', 'destination_unresolved',
                          'origin_unresolved', 'route_unavailable', 'unsupported_mode',
                          'open_failed', 'timeout', 'invalid_request', 'unknown_action'}
        if data['error'] not in allowed_errors:
            raise ValueError
        result = {'error': data['error']}
        if 'candidates' in data:
            if not isinstance(data['candidates'], list) or len(data['candidates']) > 5:
                raise ValueError
            result['candidates'] = [_candidate(item) for item in data['candidates']]
        return result
    if action in {'search', 'search_around'}:
        if set(data) != {'results', 'provider'} or data['provider'] != 'Apple MapKit' \
                or not isinstance(data['results'], list) or len(data['results']) > 8:
            raise ValueError
        return {'results': [_candidate(item) for item in data['results']], 'provider': data['provider']}
    if action == 'open_route':
        if set(data) != {'opened', 'destination', 'mode'} or data['opened'] is not True:
            raise ValueError
        return {'opened': True, 'destination': _candidate(data['destination']),
                'mode': _safe_string(data['mode'], 10)}
    required = {'origin', 'destination', 'mode', 'distance_meters',
                'expected_travel_seconds', 'as_of', 'provider'}
    if set(data) != required or data['provider'] != 'Apple MapKit':
        raise ValueError
    for key in ('distance_meters', 'expected_travel_seconds'):
        if type(data[key]) not in (int, float) or not math.isfinite(data[key]) or data[key] < 0:
            raise ValueError
    try:
        datetime.fromisoformat(data['as_of'].replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        raise ValueError
    origin = data['origin'] if data['origin'] == 'current location' else _candidate(data['origin'])
    return {'origin': origin, 'destination': _candidate(data['destination']),
            'mode': _safe_string(data['mode'], 10),
            'distance_meters': float(data['distance_meters']),
            'expected_travel_seconds': float(data['expected_travel_seconds']),
            'as_of': data['as_of'], 'provider': data['provider']}


def _text(value, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid Maps argument')
    return value.strip()


@enforced('places_search')
def search_places(query, near):
    try:
        query = _text(query)
        if near not in {'true', 'false'}:
            raise ValueError
    except ValueError:
        return {'error': 'invalid_request'}
    return _invoke('search', query=query, near=near == 'true')


@enforced('route_estimate')
def estimate_route(origin, destination, mode):
    try:
        origin, destination = _text(origin), _text(destination)
        if mode not in {'driving', 'walking', 'transit', 'cycling'}:
            raise ValueError
    except ValueError:
        return {'error': 'invalid_request'}
    return _invoke('route', origin=origin, destination=destination, mode=mode)


@enforced('maps_open_route')
def open_route(destination, mode):
    try:
        destination = _text(destination)
        if mode not in {'driving', 'walking', 'transit', 'cycling'}:
            raise ValueError
    except ValueError:
        return {'error': 'invalid_request'}
    return _invoke('open_route', origin='current location', destination=destination, mode=mode)


if __name__ == '__main__':
    build()
    print('Kuzco Maps helper built. macOS may request location access on the first nearby or route request.')
