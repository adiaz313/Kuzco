"""Explicit setup-time downloads and native build. Never called by the agent."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit
from configuration import ROOT, asset, initialize


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('Asset redirects must retain HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def checksum(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def download(entry):
    destination = asset(entry['path'])
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists() and checksum(destination) == entry['sha256']:
        return destination
    if urlsplit(entry['url']).scheme != 'https':
        raise ValueError('Asset downloads require HTTPS')
    import certifi
    context = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), HTTPSRedirects())
    request = urllib.request.Request(entry['url'], headers={'User-Agent': 'Kuzco-Setup/1.0rc1'})
    # Only checked-in manifest URLs; no user/model-provided URL execution.
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            with opener.open(request, timeout=30) as response:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > entry['max_bytes']:
                        raise ValueError('Download exceeds expected size')
                    output.write(chunk)
            output.flush()
            if checksum(temporary) != entry['sha256']:
                raise ValueError('Asset checksum mismatch; refusing changed upstream content')
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def unpack(archive, destination):
    """Extract verified archives into staging; reject links and traversal explicitly."""
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        stage = Path(temporary)
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            if sum(m.size for m in members) > 250_000_000:
                raise ValueError('Archive exceeds extraction bound')
            for member in members:
                if member.issym() or member.islnk() or member.name.startswith('/') or '..' in Path(member.name).parts:
                    raise ValueError('Unsafe archive member')
            bundle.extractall(stage, filter='data')
        roots = list(stage.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise ValueError('Expected one archive root')
        # Re-running setup refreshes source from the hash-verified archive; no private state here.
        shutil.copytree(roots[0], destination, dirs_exist_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accept-model-terms', action='store_true', help='Read THIRD_PARTY.md before downloading upstream models')
    args = parser.parse_args(argv)
    if not args.accept_model_terms:
        parser.error('Read THIRD_PARTY.md, then pass --accept-model-terms to download public model assets')
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('This candidate supports Apple Silicon macOS 14+ only')
    initialize()
    for entry in json.loads((ROOT / 'assets.json').read_text()):
        print('Verifying/installing', entry['path'], flush=True)
        archive = download(entry)
        if 'extract' in entry:
            unpack(archive, asset(entry['extract']))
    cmake = str(Path(sys.executable).parent / 'cmake')
    source = asset('whisper.cpp')
    subprocess.run([cmake, '-S', str(source), '-B', str(source / 'build'),
                    '-DCMAKE_BUILD_TYPE=Release', '-DGGML_METAL=OFF', '-DWHISPER_BUILD_TESTS=OFF'], check=True, timeout=180)
    subprocess.run([cmake, '--build', str(source / 'build'), '--target', 'whisper-cli', '-j', '4'], check=True, timeout=600)
    subprocess.run(['/usr/bin/xcrun', 'swiftc', str(ROOT / 'native/Indicator.swift'),
                    '-o', str(asset('indicator'))], check=True, timeout=120)
    from weather_location import build
    build()
    from reminders import build as build_reminders
    build_reminders()
    from calendar_read import build as build_calendar
    build_calendar()
    from mac_control import build as build_mac_control
    build_mac_control()
    from maps_places import build as build_maps
    build_maps()
    print('Local voice assets and bounded macOS helpers installed. No service was installed or restarted.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Setup failed:', error, file=sys.stderr)
        sys.exit(1)
