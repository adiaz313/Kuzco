"""Narrow Core Location adapter for weather; no public location tool or tracking."""
import json
import plistlib
import subprocess
import logging
from configuration import ROOT,asset


def executable():
    return asset('Kuzco Weather.app/Contents/MacOS/KuzcoWeather')


def current():
    try:
        run=subprocess.run([str(executable())],capture_output=True,text=True,timeout=15,check=True)
        data=json.loads(run.stdout)
        if 'error' in data:
            code=data.get('code')
            if code not in {'permission_required','permission_denied','location_failed','location_timeout'}:code='location_failed'
            logging.getLogger('kuzco.background').info('Weather location outcome=%s',code)
            raise ValueError('Location unavailable')
        logging.getLogger('kuzco.background').info('Weather location outcome=success')
        return data
    except (OSError,subprocess.SubprocessError,ValueError) as error:
        raise ValueError('Current location unavailable; it may be temporarily unavailable or permission may be denied.') from error


def build():
    binary=executable()
    binary.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    bundle=binary.parents[2]
    info={'CFBundleIdentifier':'local.kuzco.weather','CFBundleName':'Kuzco Weather',
          'CFBundleExecutable':'KuzcoWeather','CFBundlePackageType':'APPL','CFBundleVersion':'1',
          'LSUIElement':True,'NSLocationUsageDescription':'Kuzco uses approximate current location only when you ask for weather.',
          'NSLocationWhenInUseUsageDescription':'Kuzco uses approximate current location only when you ask for weather.'}
    (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    # Swift requires top-level entry code to be main.swift in a multi-file build.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='kuzco-weather-build-') as directory:
        from pathlib import Path
        entry=Path(directory)/'main.swift'
        entry.write_text((ROOT/'native/WeatherLocation.swift').read_text())
        subprocess.run(['/usr/bin/xcrun','swiftc',str(ROOT/'native/WeatherFix.swift'),str(entry),'-o',str(binary)],check=True,timeout=120)
    # Finder may reattach metadata while a bundle in Documents is being updated.
    # Retry this local signing operation once, removing only signing-incompatible metadata.
    for attempt in range(2):
        for attribute in ('com.apple.FinderInfo','com.apple.ResourceFork'):
            subprocess.run(['/usr/bin/xattr','-r','-d',attribute,str(bundle)],capture_output=True,timeout=10)
        signed=subprocess.run(['/usr/bin/codesign','--force','--sign','-','--identifier','local.kuzco.weather',str(bundle)],capture_output=True,text=True,timeout=30)
        if signed.returncode==0:break
    signed.check_returncode()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize',action='store_true')
    args=parser.parse_args()
    if not args.authorize or not executable().exists():build()
    if args.authorize:
        subprocess.run([str(executable()),'--authorize'],check=True,timeout=65)
    else:print('Weather location helper built. Run with --authorize to allow weather location access.')
