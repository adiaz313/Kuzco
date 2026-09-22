import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from routed import RoutingAgent
from security_policy import Decision, Risk, TOOLS, evaluate, request_scope
from skills.calendar_skill import parse, _summary


NOW = datetime(2026, 9, 21, 10, 0, tzinfo=timezone(timedelta(hours=-4)))


def event(title, start, end, all_day=False):
    return {'title': title, 'start_iso': start, 'end_iso': end,
            'all_day': all_day, 'calendar': 'Synthetic'}


class CalendarSkillTests(unittest.TestCase):
    def test_bounded_task_routing(self):
        cases = {
            'What does my day look like?': ('overview', '2026-09-21T00:00:00-04:00', '2026-09-22T00:00:00-04:00', 'all'),
            'What does tomorrow look like?': ('overview', '2026-09-22T00:00:00-04:00', '2026-09-23T00:00:00-04:00', 'all'),
            "What's my afternoon like?": ('period', '2026-09-21T12:00:00-04:00', '2026-09-21T17:00:00-04:00', 'all'),
            'Do I have anything after lunch?': ('period', '2026-09-21T13:00:00-04:00', '2026-09-22T00:00:00-04:00', 'all'),
            'How much time do I have before my next meeting?': ('until', '2026-09-21T10:00:00-04:00', '2026-10-21T10:00:00-04:00', 'timed'),
            'When is my first meeting tomorrow?': ('first', '2026-09-22T00:00:00-04:00', '2026-09-23T00:00:00-04:00', 'timed'),
            'When is my last timed event today?': ('last', '2026-09-21T00:00:00-04:00', '2026-09-22T00:00:00-04:00', 'timed'),
            'Do I have back-to-back meetings?': ('back_to_back', '2026-09-21T00:00:00-04:00', '2026-09-22T00:00:00-04:00', 'timed')}
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                action, args, task = parse(phrase, NOW)
                self.assertEqual(action, 'calendar_range')
                self.assertEqual((task['task'], args['start_iso'], args['end_iso'], args['kind']), expected)
        for phrase in ('Tell me what a busy day means', 'Do not check my afternoon',
                       'My first meeting was useful', 'Search the web for calendar skills',
                       'What is on my calendar today?', 'What is my next meeting?'):
            self.assertIsNone(parse(phrase, NOW))

    def test_summary_computation(self):
        events = [
            event('Holiday', '2026-09-21T00:00:00-04:00', '2026-09-22T00:00:00-04:00', True),
            event('Review', '2026-09-21T13:00:00-04:00', '2026-09-21T14:00:00-04:00'),
            event('Planning', '2026-09-21T14:05:00-04:00', '2026-09-21T15:00:00-04:00')]
        result = {'events': events, 'truncated': False}
        overview = _summary({'task': 'overview', 'period': 'today'}, result, NOW, 'default')
        self.assertIn('3 events', overview)
        self.assertIn('1 all-day', overview)
        self.assertIn('Holiday', overview)
        self.assertIn('Planning', overview)
        self.assertIn('1 hour', _summary({'task': 'until'}, {'events': events[1:2]},
                                        datetime(2026, 9, 21, 12, tzinfo=NOW.tzinfo), 'default'))
        self.assertIn('already in progress', _summary({'task': 'until'}, {'events': events[1:2]},
                        datetime(2026, 9, 21, 13, 30, tzinfo=NOW.tzinfo), 'default'))
        self.assertIn('Review', _summary({'task': 'first', 'period': 'today'},
                                        {'events': events[1:], 'truncated': False}, NOW, 'default'))
        self.assertIn('Planning', _summary({'task': 'last', 'period': 'today'},
                                          {'events': events[1:], 'truncated': False}, NOW, 'default'))
        self.assertIn('back-to-back', _summary({'task': 'back_to_back', 'period': 'today'},
                                              {'events': events[1:], 'truncated': False}, NOW, 'default'))
        overlapping = [events[1], event('Conflict', '2026-09-21T13:30:00-04:00', '2026-09-21T14:30:00-04:00')]
        self.assertIn('no back-to-back', _summary({'task': 'back_to_back', 'period': 'today'},
                                                 {'events': overlapping, 'truncated': False}, NOW, 'default'))
        self.assertIn('no events', _summary({'task': 'period', 'period': 'this afternoon'},
                                           {'events': [], 'truncated': False}, NOW, 'default'))
        self.assertIn('no timed events', _summary({'task': 'first', 'period': 'tomorrow'},
                                                 {'events': [], 'truncated': False}, NOW, 'default'))
        self.assertIn('no back-to-back', _summary({'task': 'back_to_back', 'period': 'today'},
                                                 {'events': [], 'truncated': False}, NOW, 'default'))
        far = event('Therapy', '2026-09-24T13:00:00-04:00', '2026-09-24T14:00:00-04:00')
        self.assertIn('3 days and 3 hours', _summary({'task': 'until'},
                      {'events': [far], 'truncated': False}, NOW, 'default'))

    def test_policy_and_direct_path(self):
        self.assertEqual(TOOLS['calendar_range'].risk, Risk.READ_ONLY)
        @request_scope
        def check(prompt, name, args):
            return evaluate(name, args)
        plan = parse('What does my day look like?')
        self.assertEqual(check('What does my day look like?', plan[0], plan[1]), Decision.EXECUTE)
        self.assertEqual(check('Do not check my calendar', plan[0], plan[1]), Decision.DENY)
        wrong = dict(plan[1], kind='timed')
        self.assertEqual(check('What does my day look like?', plan[0], wrong), Decision.DENY)

        session = Mock()
        session.ensure.side_effect = AssertionError('Calendar Skill must not load Llama')
        agent = RoutingAgent('direct', session)
        history = []
        data = {'events': [event('Review', '2026-09-21T13:00:00-04:00',
                                 '2026-09-21T14:00:00-04:00')], 'truncated': False}
        with patch('calendar_read._invoke', return_value=data):
            answer = agent('What does my day look like?', history=history)
        self.assertIn('Review', answer)
        self.assertEqual(agent.last['llm_calls'], 0)
        self.assertNotIn('Review', json.dumps(history))

    def test_phase5_routes_stay_phase5(self):
        session = Mock()
        session.ensure.side_effect = AssertionError('No model')
        agent = RoutingAgent('direct', session)
        with patch('calendar_read._invoke', return_value={'events': [], 'truncated': False}):
            agent("What's on my calendar today?")
            self.assertEqual(agent.last['effective'], 'CALENDAR_READ')
            agent("What's my next meeting?")
            self.assertEqual(agent.last['effective'], 'CALENDAR_READ')

    def test_failures_are_grounded(self):
        self.assertEqual(_summary({'task': 'overview', 'period': 'today'},
                                  {'error': 'Calendar access was denied.'}, NOW, 'kuzco'),
                         'Calendar access was denied.')
        self.assertNotIn('free', _summary({'task': 'period', 'period': 'this afternoon'},
                                         {'events': [], 'truncated': False}, NOW, 'kuzco').lower())


if __name__ == '__main__':
    unittest.main()
