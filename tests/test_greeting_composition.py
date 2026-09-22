import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from routed import RoutingAgent
from security_policy import Decision, Risk, TOOLS, evaluate, request_scope
from skills import greeting
from skills import greeting_context as context


class GreetingCompositionTests(unittest.TestCase):
    def setUp(self):
        context.reset_cache()

    def agent(self):
        session = Mock()
        session.ensure.side_effect = AssertionError('Greeting must not load Llama')
        return RoutingAgent('direct', session)

    def test_dayparts_and_bounded_personality(self):
        for hour, expected in [(8, 'morning'), (14, 'afternoon'), (20, 'evening')]:
            now = datetime(2026, 9, 21, hour, tzinfo=timezone.utc)
            self.assertEqual(context.daypart(now), expected)
            answer = greeting.respond('kuzco', daypart=expected)
            self.assertIn('sir', answer)
            self.assertLess(len(answer), 150)

    def test_weather_and_calendar_signals_are_truthful_and_structural(self):
        now = datetime.now(ZoneInfo('America/Detroit')).replace(microsecond=0)
        weather = {'timezone': 'America/Detroit', 'current': {'temperature': 65, 'code': 1},
                   'hours': [{'time': now.isoformat(), 'temperature': 65,
                              'rain': 80, 'wind': 4, 'code': 3}]}
        self.assertEqual(context._weather_signal(weather)[1], 'Rain looks likely today.')
        private = {'timed_count': 5, 'all_day_count': 1,
                   'next_start_iso': (now + timedelta(hours=3)).isoformat(),
                   'title': 'Private medical appointment', 'location': 'Private address'}
        signal = context._calendar_signal(private)[1]
        self.assertIn('busy', signal)
        self.assertNotIn('medical', signal)
        self.assertNotIn('address', signal)

    def test_selects_at_most_one_observation_and_weather_has_priority(self):
        now = datetime.now(ZoneInfo('America/Detroit')).replace(microsecond=0)
        def execute(call, documents):
            name = call['function']['name']
            if name == 'get_weather':
                return {'timezone': 'America/Detroit', 'current': {'temperature': 95, 'code': 0},
                        'hours': [{'time': now.isoformat(), 'temperature': 95,
                                   'rain': 0, 'wind': 1, 'code': 0}]}
            return {'timed_count': 8, 'all_day_count': 0,
                    'next_start_iso': (now + timedelta(minutes=20)).isoformat()}
        self.assertEqual(context.gather(execute), 'It is exceptionally hot outside.')

    def test_optional_failures_and_timeout_fall_back_immediately(self):
        def failed(call, documents):
            return {'error': 'unavailable'}
        self.assertIsNone(context.gather(failed))
        context.reset_cache()
        def slow(call, documents):
            time.sleep(.2)
            return {'error': 'late'}
        started = time.perf_counter()
        self.assertIsNone(context.gather(slow, budget=.02))
        self.assertLess(time.perf_counter() - started, .08)

    def test_direct_greeting_has_zero_llm_and_no_raw_context_in_history(self):
        agent = self.agent()
        history = []
        with patch('skills.greeting_context.gather', return_value='Your calendar looks fairly busy today.'):
            answer = agent('Good morning, Kuzco.', personality='kuzco', history=history)
        self.assertIn('busy', answer)
        self.assertEqual(agent.last['llm_calls'], 0)
        self.assertNotIn('events', json.dumps(history))
        self.assertNotIn('title', json.dumps(history))

    def test_calendar_context_policy_is_read_only_and_greeting_only(self):
        self.assertEqual(TOOLS['greeting_calendar_context'].risk, Risk.READ_ONLY)
        @request_scope
        def decision(prompt):
            return evaluate('greeting_calendar_context', {})
        self.assertEqual(decision('Good morning, Kuzco.'), Decision.EXECUTE)
        self.assertEqual(decision("What's on my calendar today?"), Decision.DENY)
        self.assertEqual(evaluate('greeting_calendar_context', {}), Decision.DENY)

    def test_native_calendar_adapter_discards_event_content(self):
        import calendar_read
        now = datetime.now().astimezone()
        raw = {'events': [{'title': 'Private title', 'location': 'Private location',
                           'calendar': 'Private calendar', 'all_day': False,
                           'start_iso': (now + timedelta(hours=2)).isoformat(),
                           'end_iso': (now + timedelta(hours=3)).isoformat()}],
               'truncated': False}
        @request_scope
        def read(prompt):
            with patch('calendar_read._invoke', return_value=raw):
                return calendar_read.greeting_structure()
        result = read('Hello, Kuzco.')
        self.assertEqual(set(result), {'timed_count', 'all_day_count', 'next_start_iso'})
        self.assertNotIn('Private', json.dumps(result))

    def test_normal_weather_and_light_calendar_may_be_omitted(self):
        now = datetime.now(ZoneInfo('America/Detroit')).replace(microsecond=0)
        normal = {'timezone': 'America/Detroit', 'current': {'temperature': 65, 'code': 1},
                  'hours': [{'time': now.isoformat(), 'temperature': 65,
                             'rain': 10, 'wind': 2, 'code': 1}]}
        self.assertIsNone(context._weather_signal(normal))
        self.assertIsNone(context._calendar_signal(
            {'timed_count': 1, 'all_day_count': 0,
             'next_start_iso': (now + timedelta(hours=4)).isoformat()}))


if __name__ == '__main__':
    unittest.main()
