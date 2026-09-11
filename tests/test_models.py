import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

import main
from models import FAST_MODEL, REASONING_MODEL, model_id


class ModelTests(unittest.TestCase):
    def test_configuration_and_invalid_selection(self):
        self.assertEqual(model_id(), REASONING_MODEL)
        self.assertEqual(model_id('fast'), FAST_MODEL)
        self.assertNotEqual(FAST_MODEL, REASONING_MODEL)
        with self.assertRaises(ValueError):
            model_id('automatic')

    def test_default_remains_reasoning(self):
        send = Mock(return_value={'content': '{"answer":"Hello"}'})
        main.run('Hello', send=send)
        self.assertEqual(send.call_args.args[0]['model'], REASONING_MODEL)

    def test_selected_model_used_through_all_steps(self):
        for role in ('fast', 'reasoning'):
            replies = [{'tool': 'get_current_time', 'arguments': {}},
                       {'tool': 'get_current_time', 'arguments': {}}, {'answer': 'Done'}]
            send = Mock(side_effect=[{'content': json.dumps(r)} for r in replies])
            main.run('Check the time twice', send=send, model=role)
            self.assertEqual(len(send.call_args_list), 3)
            self.assertTrue(all(c.args[0]['model'] == model_id(role) for c in send.call_args_list))

    def test_unavailable_model_does_not_fallback_or_damage_next_turn(self):
        for role in ('fast', 'reasoning'):
            history = []
            response = Mock(status=404)
            response.read.return_value = b'model unavailable'
            connection = Mock(); connection.getresponse.return_value = response
            with patch('main.http.client.HTTPConnection', return_value=connection):
                with self.assertRaisesRegex(RuntimeError, model_id(role)):
                    main.run('Hello', model=role, history=history)
            self.assertEqual(connection.request.call_count, 1)
            connection.close.assert_called_once()
            self.assertEqual(main.run('Hello again', history=history,
                send=lambda p: {'content': '{"answer":"Still working"}'}), 'Still working')

    def test_cli_and_chat_explicit_selection(self):
        with patch('sys.argv', ['main.py', '--model', 'fast', 'Hello']), patch('main.run', return_value='Hello') as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(), 0)
            self.assertEqual(run.call_args.kwargs['model'], 'fast')
        with patch('sys.argv', ['main.py', '--chat', '--model', 'fast']), patch('main.conversation') as chat:
            self.assertEqual(main.main(), 0)
            self.assertEqual(chat.call_args.kwargs['model'], 'fast')

    def test_chat_preserves_selection_and_history(self):
        seen = []
        def send(payload):
            seen.append(payload)
            return {'content': '{"answer":"Hello"}'}
        with patch('builtins.input', side_effect=['Hello', 'Again', '/exit']), contextlib.redirect_stdout(io.StringIO()):
            main.conversation(model='fast', send=send)
        self.assertTrue(all(p['model'] == FAST_MODEL for p in seen))
        self.assertGreater(len(seen[1]['messages']), len(seen[0]['messages']))

    def test_voice_adapter_passes_explicit_model_without_audio_changes(self):
        with patch('sys.argv', ['main.py', '--voice', '--model', 'fast']), patch('listener_lock.ListenerLock'), patch('voice.conversation') as session:
            self.assertEqual(main.main(), 0)
        agent = session.call_args.args[0]
        self.assertIs(agent.func, main.run)
        self.assertEqual(agent.keywords, {'model': 'fast'})
