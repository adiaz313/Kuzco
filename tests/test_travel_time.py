import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import travel
from routed import RoutingAgent
from security_policy import Decision, Risk, TOOLS, evaluate, request_scope
from skills.travel_time import _answer
from travel_intent import parse


NOW = datetime(2026, 9, 21, 14, 0, tzinfo=timezone(timedelta(hours=-4)))


def route(seconds=1200, mode='driving'):
    return {'origin': 'current location',
            'destination': {'name': 'Comerica Park', 'address': 'Private', 'latitude': 0,
                            'longitude': 0, 'source': 'Apple MapKit'},
            'mode': mode, 'distance_meters': 10000,
            'expected_travel_seconds': seconds, 'as_of': NOW.isoformat(),
            'provider': 'Apple MapKit'}


class TravelTimeTests(unittest.TestCase):
    def test_bounded_intents_modes_deadlines_and_buffers(self):
        cases = {
            'How long will it take me to get to Comerica Park?': ('duration', 'driving', 'comerica park', 0),
            'How long would it take me to walk to Comerica Park?': ('duration', 'walking', 'comerica park', 0),
            'Can I get to Comerica Park by 3?': ('feasibility', 'driving', 'comerica park', 0),
            'When should I leave to get to Comerica Park by 3?': ('leave', 'driving', 'comerica park', 0),
            'When should I leave to get to Comerica Park by 3 with 15 minutes to park?': ('leave', 'driving', 'comerica park', 15),
            'When should I leave for my dentist appointment?': ('leave', 'driving', '', 0),
            'How long will it take to get to my next appointment?': ('duration', 'driving', '', 0)}
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                action, args, task = parse(prompt, NOW)
                self.assertEqual(action, 'travel_route')
                self.assertEqual((task['task'], args['mode'], args['destination'], task['buffer_minutes']), expected)
        self.assertEqual(parse('How long will it take to fly to Paris?', NOW)[0], 'unsupported')
        self.assertIsNone(parse('Recommend somewhere to eat', NOW))

    def test_leave_feasibility_buffer_and_estimate_language(self):
        leave = {'task': 'leave', 'target_iso': NOW.replace(hour=15).isoformat(),
                 'buffer_minutes': 0, 'calendar': False}
        answer, context = _answer(leave, route(1200), 'kuzco', NOW)
        self.assertIn('2:40 PM', answer); self.assertIn('current', answer); self.assertIn('sir', answer)
        buffered = dict(leave, buffer_minutes=15)
        answer, _ = _answer(buffered, route(1200), 'default', NOW)
        self.assertIn('2:25 PM', answer); self.assertIn('15-minute buffer', answer)
        feasible = dict(leave, task='feasibility')
        self.assertIn('40 minutes before', _answer(feasible, route(1200), 'default', NOW)[0])
        tight_now = NOW.replace(hour=14, minute=35)
        self.assertIn('looks tight', _answer(feasible, route(1200), 'default', tight_now)[0])
        late_now = NOW.replace(hour=14, minute=50)
        self.assertIn('after', _answer(feasible, route(1200), 'default', late_now)[0])

    def test_passed_target_departure_event_and_malformed(self):
        task = {'task': 'leave', 'target_iso': NOW.replace(hour=13).isoformat(),
                'buffer_minutes': 0, 'calendar': False}
        self.assertIn('passed', _answer(task, route(), 'default', NOW)[0])
        task['target_iso'] = NOW.replace(hour=14, minute=10).isoformat()
        self.assertIn('leave now', _answer(task, route(), 'default', NOW)[0])
        calendar = dict(task, calendar=True, target_iso=None)
        result = dict(route(), event_start_iso=NOW.replace(hour=13).isoformat(), calendar_event=True)
        self.assertIn('already started', _answer(calendar, result, 'default', NOW)[0])
        self.assertIn('unusable', _answer({'task':'duration','target_iso':None,'buffer_minutes':0,'calendar':False},
                                          {'expected_travel_seconds':'bad'}, 'default', NOW)[0])

    def test_calendar_resolution_missing_ambiguous_location_and_success(self):
        future = datetime.now().astimezone().replace(microsecond=0) + timedelta(hours=2)
        event = {'title': 'Dentist appointment', 'location': 'Dental Office',
                 'start_iso': future.isoformat(), 'end_iso': (future + timedelta(hours=1)).isoformat(),
                 'all_day': False}
        with patch('calendar_read._invoke', return_value={'events':[event], 'truncated':False}), \
             patch('maps_places._invoke', return_value=route()) as maps:
            result = travel.route.__wrapped__('', 'dentist appointment', 'driving')
        self.assertEqual(result['event_start_iso'], future.isoformat()); maps.assert_called_once()
        self.assertEqual(maps.call_args.kwargs['destination'], 'Dental Office')
        with patch('calendar_read._invoke', return_value={'events':[event], 'truncated':False}) as calendar, \
             patch('maps_places._invoke', return_value=route()):
            travel.route.__wrapped__('', 'next appointment', 'driving')
        self.assertIs(calendar.call_args.kwargs['include_location'], True)
        with patch('calendar_read._invoke', return_value={'events':[], 'truncated':False}):
            self.assertEqual(travel.route.__wrapped__('', 'dentist appointment', 'driving')['error'], 'calendar_event_missing')
        second = dict(event, start_iso=(future + timedelta(days=7)).isoformat())
        with patch('calendar_read._invoke', return_value={'events':[event, second], 'truncated':False}):
            self.assertEqual(travel.route.__wrapped__('', 'dentist appointment', 'driving')['error'], 'calendar_event_ambiguous')
        missing = dict(event, location='')
        with patch('calendar_read._invoke', return_value={'events':[missing], 'truncated':False}):
            self.assertEqual(travel.route.__wrapped__('', 'dentist appointment', 'driving')['error'], 'calendar_location_missing')

    def test_security_exact_request_and_read_only(self):
        self.assertEqual(TOOLS['travel_route'].risk, Risk.READ_ONLY)
        @request_scope
        def decision(prompt, name, args):
            return evaluate(name, args)
        plan = parse('When should I leave to get to Comerica Park by 3?', NOW)
        self.assertEqual(decision('When should I leave to get to Comerica Park by 3?', plan[0], plan[1]), Decision.EXECUTE)
        self.assertEqual(decision('How long is the route?', plan[0], plan[1]), Decision.DENY)
        self.assertEqual(evaluate(plan[0], plan[1]), Decision.DENY)

    def test_direct_agent_followup_zero_model_and_private_calendar_history(self):
        session = Mock(); session.ensure.side_effect = AssertionError('Travel Skill must not load Llama')
        agent = RoutingAgent('direct', session); history = []
        with patch('travel.route.__wrapped__', return_value=route(1200)):
            # Patch the provider boundary used beneath the enforced function.
            with patch('maps_places._invoke', return_value=route(1200)):
                answer = agent('When should I leave to get to Comerica Park by 3 tomorrow?', history=history, personality='kuzco')
        self.assertIn('Leave by', answer); self.assertEqual(agent.last['llm_calls'], 0)
        self.assertNotIn('latitude', json.dumps(history)); self.assertNotIn('Private', json.dumps(history))
        follow = agent('How much time do I have before I need to leave?', history=history, personality='kuzco')
        self.assertIn('leave', follow); self.assertEqual(agent.last['llm_calls'], 0)

    def test_failures_are_distinct_and_no_fabricated_buffer(self):
        task = {'task':'duration','target_iso':None,'buffer_minutes':0,'calendar':False}
        for error, word in [('ambiguous','multiple'),('calendar_location_missing','location'),
                            ('calendar_unavailable','Calendar'),('route_unavailable','route'),
                            ('permission_denied','Location')]:
            self.assertIn(word, _answer(task, {'error':error}, 'default', NOW)[0])
        answer, _ = _answer(task, route(1320), 'default', NOW)
        self.assertIn('22 minutes', answer); self.assertNotIn('buffer', answer)


if __name__ == '__main__':
    unittest.main()
