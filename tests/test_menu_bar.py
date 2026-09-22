import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

import runtime_status
import service


class MenuBarTests(unittest.TestCase):
    def test_listener_status_is_private_content_free_and_removable(self):
        with tempfile.TemporaryDirectory() as folder, patch('runtime_status.home', return_value=Path(folder)), \
             patch('runtime_status.os.getpid', return_value=321):
            runtime_status.listener(True)
            target = Path(folder) / 'runtime-status.json'
            value = json.loads(target.read_text())
            self.assertEqual(set(value), {'pid','wake_listening','updated_at'})
            self.assertEqual(value['pid'], 321); self.assertIs(value['wake_listening'], True)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            runtime_status.listener(False)
            self.assertFalse(target.exists())

    def test_background_host_declares_runtime_and_icon(self):
        source = (Path(__file__).resolve().parents[1] / 'native/BackgroundLauncher.swift').read_text()
        for text in ('NSStatusBar.system.statusItem', 'Kuzco Enabled', 'Quit Kuzco',
                     'runtime-status.json', '/api/v1/models', 'wakeListening'):
            self.assertIn(text, source)
        self.assertIn('15.0', source)
        self.assertIn('guard enabled, !shuttingDown, !childRunning', source)
        self.assertIn('process.terminate()', source)
        self.assertIn('launchctl', source)
        self.assertIn('bootout', source)
        self.assertIn('NSSwitch', source)
        self.assertIn('.systemGreen', source)
        self.assertNotIn('.systemOrange', source)
        self.assertIn('.systemRed', source)
        self.assertIn('.secondaryLabelColor', source)
        self.assertIn('.labelColor', source)
        self.assertIn('NSSize(width: 26, height: 26)', source)
        self.assertNotIn('item.isEnabled = false', source)
        self.assertNotIn('/v1/chat/completions', source)

    def test_local_model_status_is_binary_available_or_unavailable(self):
        source = (Path(__file__).resolve().parents[1] / 'native/BackgroundLauncher.swift').read_text()
        self.assertIn('next = "Available"', source)
        self.assertIn('modelState == "Available"', source)
        self.assertNotIn('modelState == "Running"', source)
        self.assertNotIn('loaded_instances', source)

    def test_service_build_copies_distinct_derived_icon_and_runtime_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); app = root / 'Kuzco Background.app'; data = root / 'data'
            (root/'native').mkdir(); (root/'native/BackgroundLauncher.swift').write_text('// source')
            (root/'native/Indicator.swift').write_text('// indicator')
            (root/'assets').mkdir(); (root/'assets/kuzco-menu-icon-statusbar.png').write_bytes(b'png')
            with patch.object(service,'ROOT',root),patch.object(service,'APP',app), \
                 patch('service.home',return_value=data),patch('service.asset',return_value=data/'assets/indicator'), \
                 patch('configuration.load',return_value={'port':1234,'model':'model-id'}), \
                 patch('service.subprocess.run'):
                service.build()
            info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
            self.assertEqual(info['KuzcoPort'],1234);self.assertEqual(info['KuzcoModel'],'model-id')
            self.assertEqual((app/'Contents/Resources/kuzco-menu-icon-statusbar.png').read_bytes(),b'png')

    def test_source_and_derived_assets_are_distinct(self):
        root=Path(__file__).resolve().parents[1]/'assets'
        source=root/'kuzco-menu-icon-source.png';derived=root/'kuzco-menu-icon-statusbar.png'
        self.assertTrue(source.is_file());self.assertTrue(derived.is_file())
        self.assertNotEqual(source.read_bytes(),derived.read_bytes())


if __name__ == '__main__':
    unittest.main()
