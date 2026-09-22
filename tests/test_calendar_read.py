import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import calendar_read
from calendar_intent import parse
from routed import RoutingAgent
from security_policy import Decision, Risk, TOOLS, evaluate, request_scope


class CalendarReadTests(unittest.TestCase):
    def test_whole_request_routing_and_dates(self):
        now = datetime(2026, 11, 1, 23, 59, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(parse("What's on my calendar today?", now),
                         ('calendar_day', {'day': '2026-11-01'}, 'today'))
        self.assertEqual(parse("What's on my calendar tomorrow?", now),
                         ('calendar_day', {'day': '2026-11-02'}, 'tomorrow'))
        self.assertEqual(parse("Kuzco, what's my next meeting?"),
                         ('calendar_next', {'kind': 'timed'}, 'next_timed'))
        self.assertEqual(parse("What's my next event?"),
                         ('calendar_next', {'kind': 'event'}, 'next_event'))
        for phrase in ('Tell me how calendars work', 'Do not read my calendar today',
                       'My next meeting is tomorrow', 'What do I have today?',
                       'What is the weather tomorrow?', 'Remind me of my meeting'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse(phrase))

    def test_action_scoped_security(self):
        self.assertEqual(TOOLS['calendar_day'].risk, Risk.READ_ONLY)
        self.assertEqual(TOOLS['calendar_next'].risk, Risk.READ_ONLY)
        @request_scope
        def check(prompt, name, args):
            return evaluate(name, args)
        day = datetime.now().astimezone().date().isoformat()
        self.assertEqual(check("What's on my calendar today?", 'calendar_day', {'day': day}), Decision.EXECUTE)
        self.assertEqual(check("What's on my calendar today?", 'calendar_next', {'kind': 'event'}), Decision.DENY)
        self.assertEqual(check("What's my next meeting?", 'calendar_next', {'kind': 'timed'}), Decision.EXECUTE)
        self.assertEqual(check("What's my next meeting?", 'calendar_next', {'kind': 'event'}), Decision.DENY)
        self.assertEqual(check('Explain my calendar', 'calendar_day', {'day': day}), Decision.DENY)
        self.assertEqual(check('Do not read my calendar today', 'calendar_day', {'day': day}), Decision.DENY)
        self.assertEqual(check("What's on my calendar today?", 'calendar_day', {'day': '2020-01-01'}), Decision.DENY)
        self.assertEqual(evaluate('calendar_day', {'day': day}), Decision.DENY)

    def test_direct_product_path_avoids_model_and_history_content(self):
        session = Mock()
        session.ensure.side_effect = AssertionError('Calendar direct path must not load Llama')
        agent = RoutingAgent('direct', session)
        history = []
        event = {'title': 'Synthetic review', 'start_iso': '2026-09-20T14:00:00-04:00',
                 'end_iso': '2026-09-20T15:00:00-04:00', 'all_day': False,
                 'calendar': 'Synthetic', 'location': ''}
        with patch('calendar_read._invoke', return_value={'events': [event], 'truncated': False}) as native:
            answer = agent("What's on my calendar today?", history=history)
        self.assertIn('Synthetic review', answer)
        self.assertEqual(agent.last['llm_calls'], 0)
        native.assert_called_once_with('day', day=datetime.now().astimezone().date().isoformat())
        self.assertNotIn('Synthetic review', json.dumps(history))
        with patch('calendar_read._invoke', return_value={'events': [event], 'truncated': False}) as native:
            answer = agent("What's my next meeting?", history=history)
        self.assertIn('next timed calendar event', answer)
        native.assert_called_once_with('next', timed_only=True)

    def test_empty_error_multiple_and_all_day(self):
        from skills.calendar_readonly import _answer
        self.assertIn('no calendar events', _answer('today', {'events': [], 'truncated': False}, 'default'))
        self.assertIn('next 30 days', _answer('next_event', {'events': [], 'truncated': False}, 'default'))
        self.assertIn('timed calendar event', _answer('next_timed', {'events': [], 'truncated': False}, 'default'))
        self.assertIn('denied', _answer('today', {'error': 'Calendar access was denied.'}, 'default'))
        events = [
            {'title': 'All-day trip', 'start_iso': '2026-09-20T00:00:00-04:00',
             'end_iso': '2026-09-21T00:00:00-04:00', 'all_day': True},
            {'title': 'Afternoon review', 'start_iso': '2026-09-20T14:00:00-04:00',
             'end_iso': '2026-09-20T15:00:00-04:00', 'all_day': False}]
        answer = _answer('today', {'events': events, 'truncated': False}, 'default')
        self.assertIn('All-day trip (all day)', answer)
        self.assertIn('Afternoon review', answer)

    def test_bridge_failures_and_schema(self):
        with patch('calendar_read.executable', return_value=Path(__file__)), \
             patch('calendar_read.subprocess.run') as run:
            run.return_value = Mock(returncode=0, stdout='{"error":"permission_denied"}')
            self.assertIn('denied', calendar_read._invoke('day', day='2026-09-20')['error'])
            run.return_value = Mock(returncode=0, stdout='{"events":[],"truncated":false}')
            self.assertEqual(calendar_read._invoke('day', day='2026-09-20')['events'], [])
            run.return_value = Mock(returncode=0, stdout='{"events":"bad","truncated":false}')
            self.assertIn('unavailable', calendar_read._invoke('day', day='2026-09-20')['error'])
            run.return_value = Mock(returncode=0, stdout='{"events":[{"title":"x","start_iso":"2026-09-20T10:00:00Z","end_iso":"2026-09-20T11:00:00Z","all_day":false,"location":7}],"truncated":false}')
            self.assertIn('unavailable', calendar_read._invoke('range')['error'])
            run.side_effect = subprocess.TimeoutExpired('calendar', 55)
            self.assertIn('unavailable', calendar_read._invoke('day', day='2026-09-20')['error'])

    def test_read_only_native_boundary(self):
        source = (Path(__file__).resolve().parents[1] / 'native/CalendarRead.swift').read_text()
        self.assertIn('predicateForEvents', source)
        self.assertIn('requestFullAccessToEvents', source)
        self.assertNotIn('store.save(', source)
        self.assertNotIn('store.remove(', source)
        @request_scope
        def invalid(prompt):
            return calendar_read.range_events('bad', 'bad', 'all')
        self.assertIn('denied', invalid('What does my day look like?')['error'].lower())

    def test_background_host_declares_calendar_purpose(self):
        import plistlib
        import service
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'Kuzco Background.app'
            with patch('service.APP', app), patch('service.asset', return_value=Path(directory) / 'indicator'), \
                 patch('service.subprocess.run'):
                service.build()
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            self.assertIn('NSCalendarsFullAccessUsageDescription', info)
            self.assertIn('cannot change events', info['NSCalendarsFullAccessUsageDescription'])


if __name__ == '__main__':
    unittest.main()
