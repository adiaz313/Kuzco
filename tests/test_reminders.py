import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import main
import reminders
from reminder_intent import parse
from routed import RoutingAgent
from security_policy import Decision, Risk, TOOLS, evaluate, request_scope


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 19, 12, 0, tzinfo=ZoneInfo('America/Detroit'))

    def test_temporal_parsing_and_unscheduled_task(self):
        for phrase, expected in [
            ('Remind me in 30 minutes to switch the laundry', '2026-09-19T12:30:00-04:00'),
            ('Remind me in two hours to call John', '2026-09-19T14:00:00-04:00'),
            ('Remind me tomorrow at 3 PM to call John', '2026-09-20T15:00:00-04:00'),
            ('Remind me tonight to check the laundry', '2026-09-19T19:00:00-04:00'),
            ('Remind me tomorrow morning to call John', '2026-09-20T09:00:00-04:00'),
            ('Remind me on Monday morning to buy printer paper', '2026-09-21T09:00:00-04:00'),
            ('Remind me to buy printer paper on Monday morning', '2026-09-21T09:00:00-04:00'),
            ('Remind me Monday afternoon to buy printer paper', '2026-09-21T15:00:00-04:00'),
            ('Remind me on Monday evening to buy printer paper', '2026-09-21T19:00:00-04:00'),
            ('Remind me to buy printer paper tomorrow night', '2026-09-20T20:00:00-04:00'),
            ('Remind me Friday at 9 AM to check the car', '2026-09-25T09:00:00-04:00')]:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse(phrase, self.now)[1]['due_iso'], expected)
        self.assertEqual(parse('Add oil change to my reminders'),
                         ('reminders_create', {'title': 'oil change', 'due_iso': ''}))
        self.assertEqual(parse('Remind me tomorrow to call John', self.now)[0], 'clarify')
        self.assertEqual(parse('Remind me tomorrow at 3 to call John', self.now)[0], 'clarify')

    def test_weekday_daypart_uses_next_future_occurrence(self):
        monday_morning = datetime(2026, 9, 21, 8, tzinfo=ZoneInfo('America/Detroit'))
        monday_later = datetime(2026, 9, 21, 10, tzinfo=ZoneInfo('America/Detroit'))
        phrase = 'Remind me on Monday morning to buy printer paper'
        self.assertEqual(parse(phrase, monday_morning)[1]['due_iso'], '2026-09-21T09:00:00-04:00')
        self.assertEqual(parse(phrase, monday_later)[1]['due_iso'], '2026-09-28T09:00:00-04:00')

    def test_weekday_voice_path_is_direct_and_states_default(self):
        agent = self._agent()
        with patch('reminders._invoke', return_value={'created': True}):
            answer = agent('Kuzco, remind me on Monday morning to buy printer paper', personality='kuzco')
        self.assertIn('9:00 AM', answer)
        self.assertIn('sir', answer)
        self.assertEqual(agent.last['llm_calls'], 0)

    def test_routing_is_narrow_and_no_model(self):
        agent = RoutingAgent('direct', Mock())
        agent.session.ensure.side_effect = AssertionError('LLM loaded')
        with patch('reminders._invoke', return_value={'created': True}):
            answer = agent('Add oil change to my reminders', personality='kuzco')
        self.assertIn('oil change', answer)
        self.assertEqual(agent.last['llm_calls'], 0)
        for request in ('Explain what a reminder is', 'What do my documents say about reminders?',
                        'Search the web for reminder apps', 'Do not add oil change to my reminders'):
            self.assertIsNone(parse(request))

    def test_spoken_list_variants_stay_direct(self):
        for request in ('What reminders do I have?', 'What reminders do I have today?',
                        'What are my reminders?', 'Do I have any reminders?',
                        "What's on my reminder list?", 'Show me my reminders',
                        'What reminders do I have, Kuzco?'):
            with self.subTest(request=request), patch('reminders._invoke', return_value={'items': []}):
                agent = self._agent()
                self.assertIn('no incomplete', agent(request).lower())
                self.assertEqual(agent.last['llm_calls'], 0)

    def test_list_and_empty_and_bounds(self):
        items = [{'identifier': str(i), 'title': f'Task {i}', 'due_iso': ''} for i in range(30)]
        history = []
        with patch('reminders._invoke', return_value={'items': items, 'truncated': False}):
            answer = self._agent()('What reminders do I have?', history=history)
        self.assertIn('Task 0', answer)
        self.assertNotIn('Task 25', answer)
        self.assertNotIn('identifier', answer)
        self.assertNotIn('Task 0', json.dumps(history))
        with patch('reminders._invoke', return_value={'items': []}):
            self.assertIn('no incomplete', self._agent()('What reminders do I have?'))

    def test_unique_selection_missing_ambiguous_and_remove(self):
        items = [{'identifier': '1', 'title': 'Oil change'},
                 {'identifier': '2', 'title': 'Laundry'},
                 {'identifier': '3', 'title': 'Laundry'}]
        with patch('reminders._invoke', side_effect=lambda action, **kwargs: {'items': items} if action == 'list' else {'completed': True}) as native:
            self.assertIn('More than one', self._agent()('Mark Laundry complete'))
            self.assertEqual(native.call_count, 1)
        with patch('reminders._invoke', side_effect=lambda action, **kwargs: {'items': items} if action == 'list' else {'removed': True}) as native:
            self.assertIn('Removed Oil change', self._agent()('Remove my Oil change reminder'))
            self.assertEqual(native.call_args.args[0], 'remove')
            self.assertEqual(native.call_args.kwargs['identifier'], '1')
        with patch('reminders._invoke', return_value={'items': items}):
            self.assertIn('No matching', self._agent()('Mark Grocery complete'))
        self.assertEqual(reminders._normalize('phase two test'), reminders._normalize('phase 2 tests'))
        with patch('reminders._invoke', side_effect=lambda action, **kwargs:
                   {'items': [{'identifier': 'p2', 'title': 'phase 2 tests'}]} if action == 'list' else {'completed': True}) as native:
            self.assertIn('Marked phase two test complete', self._agent()('Mark phase two test complete'))
            self.assertEqual(native.call_args.kwargs['identifier'], 'p2')

    def test_ambiguous_references_clarify_without_model_or_native_call(self):
        for phrase in ('Mark it complete', 'Remove that reminder', 'What reminders are due next week?',
                       'What do I have on my reminders for tomorrow?'):
            with self.subTest(phrase=phrase), patch('reminders._invoke') as native:
                agent = self._agent()
                answer = agent(phrase)
                self.assertIn('?', answer)
                self.assertEqual(agent.last['llm_calls'], 0)
                native.assert_not_called()

    def test_explicit_remove_from_reminders(self):
        self.assertEqual(parse('Remove phase two test from my reminders'),
                         ('reminders_remove', {'title': 'phase two test'}))

    def test_permission_and_unavailable(self):
        import plistlib
        import service
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'Kuzco Background.app'
            with patch('service.APP', app), patch('service.asset', return_value=Path(directory) / 'indicator'), \
                 patch('service.subprocess.run'):
                service.build()
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            self.assertIn('NSRemindersUsageDescription', info)
            self.assertIn('NSRemindersFullAccessUsageDescription', info)
        with patch('reminders.executable', return_value=Path('/nonexistent/kuzco')):
            self.assertIn('not installed', reminders._invoke('list')['error'])
        with patch('reminders.executable', return_value=Path(__file__)), patch('reminders.subprocess.run') as run:
            run.return_value.returncode = 0
            for code, expected in [('permission_denied', 'denied'),
                                   ('permission_timeout', 'timed out'),
                                   ('read_timeout', 'could not complete')]:
                run.return_value.stdout = json.dumps({'error': code})
                self.assertIn(expected, reminders._invoke('list')['error'])
            run.side_effect = TimeoutError()
            self.assertIn('unavailable', reminders._invoke('list')['error'])

    def test_action_level_policy_and_untrusted_text(self):
        self.assertEqual(TOOLS['reminders_list'].risk, Risk.READ_ONLY)
        for name in ('reminders_create', 'reminders_complete', 'reminders_remove'):
            self.assertEqual(TOOLS[name].risk, Risk.LOCAL_ACTION)
        @request_scope
        def check(prompt, name, args):
            return evaluate(name, args)
        self.assertEqual(check('Add oil change to my reminders', 'reminders_create',
                               {'title': 'oil change', 'due_iso': ''}), Decision.EXECUTE)
        self.assertEqual(check('Explain what a reminder is', 'reminders_remove',
                               {'title': 'oil change'}), Decision.DENY)
        self.assertEqual(check('Search web for oil changes', 'reminders_remove',
                               {'title': 'oil change'}), Decision.DENY)
        self.assertEqual(check('Add oil change to my reminders', 'reminders_remove',
                               {'title': 'oil change'}), Decision.DENY)
        self.assertEqual(check('Remove my Oil change reminder', 'reminders_remove',
                               {'title': 'Other'}), Decision.DENY)

    def test_disabled_policy_and_no_private_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.json'
            path.write_text('{"disabled_tools":["reminders_create"]}')
            with patch('security_policy.CONFIG', path), patch('reminders._invoke') as native:
                self.assertIn('denied', self._agent()('Add oil change to my reminders').lower())
                native.assert_not_called()
        source = (Path(__file__).resolve().parents[1] / 'reminders.py').read_text()
        self.assertNotIn('logging.', source)

    def test_failed_action_log_omits_reminder_title(self):
        with patch('reminders._invoke', return_value={'error': 'No matching reminder was found.'}), \
             self.assertLogs('kuzco.background', level='INFO') as captured:
            self._agent()('Mark private doctor appointment complete')
        self.assertTrue(any('category=selection' in line for line in captured.output))
        self.assertNotIn('doctor', '\n'.join(captured.output))

    def test_tool_arguments_rejected(self):
        call = {'function': {'name': 'reminders_remove', 'arguments': json.dumps({'title': 'Oil change', 'command': 'delete all'})}}
        with patch('reminders._invoke') as native:
            self.assertIn('error', main.execute_tool(call, ()))
            native.assert_not_called()

    @staticmethod
    def _agent():
        session = Mock()
        session.ensure.side_effect = AssertionError('LLM loaded')
        return RoutingAgent('direct', session)
