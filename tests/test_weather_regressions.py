import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from skills.weather import parse
from skills.usability import clean
from routed import RoutingAgent
import weather_location
from test_usability import fixture
from weather import normalize


class WeatherRegressionTests(unittest.TestCase):
    def test_canonical_and_activity_grammar_stays_weather(self):
        cases={"Kuzco. What's the weather today?":('forecast','today'),
            'Can I grill tonight?':('grill','tonight'),
            'Can I grill, tonight?':('grill','tonight'),
            'Can I grill out tonight?':('grill','tonight'),
            'Is it a good night to grill?':('grill','tonight'),
            'Would tonight be a good time for grilling?':('grill','tonight'),
            'Can we barbecue this evening?':('grill','tonight'),
            'Should I wear a jacket tonight?':('jacket','tonight'),
            'Do I need an umbrella tonight?':('umbrella','tonight'),
            'Should I bring my umbrella tomorrow?':('umbrella','tomorrow')}
        for prompt,intent in cases.items():
            with self.subTest(prompt=prompt):self.assertEqual(parse(clean(prompt)),intent)

    def test_activity_does_not_capture_recipes_documents_or_actions(self):
        for p in ['How do I grill chicken tonight?','What do my notes say about grilling?',
                  'Can I grill tonight and open Safari?','Do not grill tonight','Can I grill your argument?',
                  'Should I wear a jacket tonight according to my documents?','Is it a good night to delete files?']:
            self.assertIsNone(parse(clean(p)),p)

    def test_all_activity_forms_zero_llama_and_zero_rag(self):
        a=RoutingAgent('direct',Mock())
        with patch('weather.get_weather',return_value=normalize(fixture())),patch('main.search_documents') as rag,patch('main.chat') as llama:
            for p in ['Can I grill tonight?','Is it a good night to grill?','Should I wear a jacket tonight?']:
                a(p,history=[],personality='kuzco');self.assertEqual(a.last['effective'],'WEATHER')
                self.assertEqual(a.last['llm_calls'],0)
        rag.assert_not_called();llama.assert_not_called();a.session.ensure.assert_not_called()

    def test_same_location_entry_for_forecast_and_activities(self):
        with patch('weather_location.current',side_effect=ValueError('temporary')) as current,patch('weather.urllib.request.build_opener') as provider:
            a=RoutingAgent('direct',Mock())
            for p in ["What's the weather today?",'Can I grill tonight?','Do I need an umbrella?']:
                self.assertIn('current location',a(p))
            self.assertEqual(current.call_count,3);provider.assert_not_called()

    def test_helper_error_code_logged_without_coordinates_or_text(self):
        output=json.dumps({'error':'private external error detail','code':'location_timeout','latitude':42.12345})
        with patch('weather_location.subprocess.run',return_value=Mock(stdout=output)),self.assertLogs('kuzco.background',level='INFO') as logs:
            with self.assertRaises(ValueError):weather_location.current()
        self.assertIn('location_timeout',str(logs.output));self.assertNotIn('private',str(logs.output));self.assertNotIn('42.12345',str(logs.output))

    def test_background_permission_pending_fails_safely_then_time_works(self):
        output=json.dumps({'error':'Allow location for this background app.','code':'permission_required'})
        a=RoutingAgent('direct',Mock())
        with patch('weather_location.subprocess.run',return_value=Mock(stdout=output)),\
             patch('weather.urllib.request.build_opener') as provider:
            self.assertIn('current location',a("What's the weather today?"))
            self.assertIn('M',a('What time is it?'))
        provider.assert_not_called()

    def test_forecast_failure_then_success_preserves_agent(self):
        a=RoutingAgent('direct',Mock())
        with patch('weather.get_weather',side_effect=[{'error':'Location temporarily unavailable.'},normalize(fixture())]):
            self.assertIn('unavailable',a("What's the weather today?"))
            self.assertIn('high',a("What's the weather today?"))

    @unittest.skipUnless(Path('/usr/bin/xcrun').exists(),'Native fix filter requires the documented macOS Swift toolchain')
    def test_native_cached_then_fresh_fix_without_gui(self):
        # Execute the exact native filter used by the callback. No location manager,
        # microphone, GUI, network or permission request in this test.
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            script=Path(d)/'check.swift'
            script.write_text((root/'native/WeatherFix.swift').read_text()+'''
assert(!usableWeatherFix(age: -1200, accuracy: 100))
assert(!usableWeatherFix(age: 0, accuracy: -1))
assert(!usableWeatherFix(age: 0, accuracy: 20000))
assert(!usableWeatherFix(age: Double.nan, accuracy: 1))
let events = [(-1200.0, 100.0), (0.0, -1.0), (-1.0, 100.0)]
assert(events.firstIndex(where: { usableWeatherFix(age: $0.0, accuracy: $0.1) }) == 2)
''')
            subprocess.run(['/usr/bin/xcrun','swift',str(script)],check=True,capture_output=True,timeout=30)
