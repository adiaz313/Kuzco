import json
import unittest
from unittest.mock import Mock, patch

import latency
import main


class LatencyTests(unittest.TestCase):
    def test_measurement_preserves_result_without_logging_content(self):
        logger = Mock()
        with patch.object(latency, 'LOGGER', logger):
            function = latency.measured('tool')(lambda call: {'ok': True})
            self.assertEqual(function({'function': {'name': 'search_web', 'arguments': 'PRIVATE'}}), {'ok': True})
        self.assertEqual(logger.info.call_count, 2)
        self.assertNotIn('PRIVATE', str(logger.info.call_args_list))

    def test_measurement_preserves_error_and_disabled_fast_path(self):
        logger = Mock(); logger.isEnabledFor.return_value = False
        with patch.object(latency, 'LOGGER', logger):
            self.assertEqual(latency.measured('llama')(lambda: 'ok')(), 'ok')
        logger.info.assert_not_called()
        logger.isEnabledFor.return_value = True
        with patch.object(latency, 'LOGGER', logger):
            with self.assertRaisesRegex(ValueError, 'broken'):
                latency.measured('speech')(Mock(side_effect=ValueError('broken')))()
        self.assertEqual(logger.info.call_count, 2)

    def test_logging_failure_does_not_break_a_request(self):
        logger = Mock(); logger.info.side_effect = OSError('disk full')
        with patch.object(latency, 'LOGGER', logger):
            self.assertEqual(latency.measured('speech')(lambda: 'ok')(), 'ok')

    def test_web_policy_once_in_system_not_repeated_in_history(self):
        history, seen = [], []
        decisions = iter([{'tool': 'search_web', 'arguments': {'query': 'news'}},
                          {'tool': 'search_web', 'arguments': {'query': 'latest news'}}, {'answer': 'Unverified.'}])
        def send(payload):
            seen.append(payload)
            return {'content': json.dumps(next(decisions))}
        with patch('main.search_web', return_value={'results': []}):
            main.run('Latest news?', send=send, history=history)
        self.assertNotIn(main.WEB_GUIDANCE, seen[0]['messages'][0]['content'])
        for payload in seen[1:]:
            self.assertEqual(payload['messages'][0]['content'].count(main.WEB_GUIDANCE), 1)
            self.assertEqual(sum(m['role'] == 'system' for m in payload['messages']), 1)
        self.assertNotIn(main.WEB_GUIDANCE, str(history))

    def test_local_time_has_no_detailed_web_policy_or_provider_import(self):
        replies = iter([{'tool': 'get_current_time', 'arguments': {}}, {'answer': 'Time.'}])
        def send(payload):
            self.assertNotIn(main.WEB_GUIDANCE, payload['messages'][0]['content'])
            return {'content': json.dumps(next(replies))}
        with patch('main.search_web') as search:
            self.assertEqual(main.run('What time is it?', send=send), 'Time.')
        search.assert_not_called()
