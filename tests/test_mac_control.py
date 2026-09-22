import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main
from mac_intent import parse
from routed import RoutingAgent
from security_policy import Decision, Risk, TOOLS, evaluate, request_scope


class MacControlTests(unittest.TestCase):
    @staticmethod
    def agent():
        session = Mock()
        session.ensure.side_effect = AssertionError('Model should not load')
        return RoutingAgent('direct', session)

    def test_bounded_intents_and_false_positives(self):
        expected = {
            'Turn the volume down': ('volume_adjust', {'direction': 'down'}),
            'Turn down the volume': ('volume_adjust', {'direction': 'down'}),
            'Turn up the volume': ('volume_adjust', {'direction': 'up'}),
            'Increase the volume': ('volume_adjust', {'direction': 'up'}),
            'Make it quieter': ('volume_adjust', {'direction': 'down'}),
            'Turn it up': ('volume_adjust', {'direction': 'up'}),
            'Set the volume to 0 percent': ('volume_set', {'percent': '0'}),
            'Set the volume to 100%': ('volume_set', {'percent': '100'}),
            'Mute': ('volume_mute', {'muted': 'true'}),
            'Unmute': ('volume_mute', {'muted': 'false'}),
            'Cuz go, unmute.': ('volume_mute', {'muted': 'false'}),
            'Unmute, unmute, unmute.': ('volume_mute', {'muted': 'false'}),
            'Unmute unmute': ('volume_mute', {'muted': 'false'}),
            'Un mute': ('volume_mute', {'muted': 'false'}),
            'Unmute it': ('volume_mute', {'muted': 'false'}),
            'Take it off mute': ('volume_mute', {'muted': 'false'}),
            'Can you please unmute?': ('volume_mute', {'muted': 'false'}),
            'Switch to Safari': ('focus_application', {'application_name': 'safari'}),
            'Pause the music': ('music_transport', {'action': 'pause'}),
            'Skip this song': ('music_transport', {'action': 'next'}),
            'Play my Chill playlist': ('music_play_named', {'kind': 'playlist', 'name': 'chill'}),
            'Play Dreams song': ('music_play_named', {'kind': 'song', 'name': 'dreams'}),
            'Turn up the display brightness': ('unsupported_brightness', {}),
            'Set a timer for five minutes': ('unsupported_timer', {}),
        }
        for phrase, result in expected.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(parse(phrase), result)
        for phrase in ('Do not mute', 'Explain how volume works', 'The word quit sounds harsh',
                       'Tell me how to play music',
                       'I could play Fleetwood Mac', 'Set the volume to -1 percent',
                       'Mute, unmute', 'Tell me how to unmute, unmute',
                       'Do not turn up the volume', 'Tell me how to increase the volume'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse(phrase))
        self.assertEqual(parse('Play Fleetwood Mac'), ('clarify_media', {}))
        self.assertEqual(parse('Play the latest podcast episode'), ('unsupported_podcast', {}))
        self.assertEqual(parse('Quit Spotify'), ('unsupported_quit', {}))

    def test_deferred_controls_fail_honestly_without_model_or_native_action(self):
        agent = self.agent()
        self.assertIn('brightness', agent('Turn up the display brightness').lower())
        self.assertEqual(agent.last['llm_calls'], 0)
        self.assertIn('timers', agent('Set a timer for five minutes').lower())
        self.assertEqual(agent.last['llm_calls'], 0)

    def test_direct_execution_and_no_model(self):
        with patch('mac_control._native', return_value={'percent': 40}) as native:
            agent = self.agent()
            self.assertIn('40 percent', agent('Set the volume to 40 percent'))
            self.assertEqual(agent.last['llm_calls'], 0)
            native.assert_called_once_with('mac-volume', 'set', '40')
        with patch('mac_control._native', return_value={'focused': True}) as native:
            self.assertIn('Switched', self.agent()('Switch to Safari'))
            native.assert_called_once_with('mac-focus', 'safari')
        with patch('mac_control._music', return_value={'player_state': 'paused'}) as music:
            self.assertIn('paused', self.agent()('Pause the music'))
            music.assert_called_once_with('pause')
        with patch('mac_control._native', return_value={'muted': False}) as native:
            agent = self.agent()
            self.assertIn('Unmuted', agent('unmute, unmute, unmute.'))
            self.assertEqual(agent.last['llm_calls'], 0)
            native.assert_called_once_with('mac-volume', 'mute', 'false')
        with patch('mac_control._native', return_value={'muted': False}) as native:
            from wake_input import request_text
            agent = self.agent()
            self.assertIn('Unmuted', agent(request_text('Cuz go, unmute.')))
            self.assertEqual(agent.last['llm_calls'], 0)
            native.assert_called_once_with('mac-volume', 'mute', 'false')

    def test_policy_is_action_scoped(self):
        for action in ('focus_application', 'volume_adjust', 'volume_set', 'volume_mute',
                       'music_transport', 'music_play_named'):
            self.assertEqual(TOOLS[action].risk, Risk.LOCAL_ACTION)
        @request_scope
        def check(prompt, name, args):
            return evaluate(name, args)
        self.assertEqual(check('Mute', 'volume_mute', {'muted': 'true'}), Decision.EXECUTE)
        self.assertEqual(check('Mute', 'volume_mute', {'muted': 'false'}), Decision.DENY)
        self.assertEqual(check('Explain how to mute', 'volume_mute', {'muted': 'true'}), Decision.DENY)
        self.assertEqual(check('Set the volume to 101 percent', 'volume_set', {'percent': '101'}), Decision.DENY)
        self.assertEqual(check('Pause the music', 'music_transport', {'action': 'next'}), Decision.DENY)
        self.assertEqual(check('Play my Chill playlist', 'music_play_named',
                               {'kind': 'song', 'name': 'chill'}), Decision.DENY)

    def test_failures_do_not_claim_success(self):
        with patch('mac_control._native', return_value={'error': 'This output device does not offer adjustable system volume.'}):
            self.assertIn('does not offer', self.agent()('Turn the volume down'))
        with patch('mac_control._native', return_value={'error': 'not_running'}):
            self.assertIn('not running', self.agent()('Switch to Safari'))
        with patch('mac_control._music', return_value={'error': 'Music did not start playback.'}):
            self.assertIn('did not start', self.agent()('Play my Chill playlist'))

    def test_all_volume_modes_and_bounds_are_direct(self):
        for phrase, binary_args, response in [
            ('Turn the volume up', ('mac-volume', 'adjust', 'up'), {'percent': 100}),
            ('Turn the volume down', ('mac-volume', 'adjust', 'down'), {'percent': 0}),
            ('Set the volume to 0 percent', ('mac-volume', 'set', '0'), {'percent': 0}),
            ('Set the volume to 100 percent', ('mac-volume', 'set', '100'), {'percent': 100}),
            ('Mute', ('mac-volume', 'mute', 'true'), {'muted': True}),
            ('Unmute', ('mac-volume', 'mute', 'false'), {'muted': False}),
        ]:
            with self.subTest(phrase=phrase), patch('mac_control._native', return_value=response) as native:
                agent = self.agent()
                self.assertNotIn('denied', agent(phrase).lower())
                self.assertEqual(agent.last['llm_calls'], 0)
                native.assert_called_once_with(*binary_args)
        with patch('mac_control._native') as native:
            self.assertIn('denied', self.agent()('Set the volume to 101 percent').lower())
            native.assert_not_called()

    def test_music_transport_named_content_and_failure_mapping(self):
        for phrase, expected in [
            ('Play music', 'play'), ('Resume the music', 'resume'),
            ('Pause the music', 'pause'), ('Skip this song', 'next'),
            ('Previous track', 'previous')]:
            with self.subTest(phrase=phrase), patch('mac_control._music', return_value={'player_state': 'playing'}) as native:
                agent = self.agent()
                agent(phrase)
                self.assertEqual(agent.last['llm_calls'], 0)
                native.assert_called_once_with(expected)
        with patch('mac_control._music', return_value={'player_state': 'playing'}) as native:
            self.agent()('Play Dreams song')
            native.assert_called_once_with('song', 'dreams')
        with patch('mac_control._music') as native:
            self.assertIn('not reliable', self.agent()('Play Rumours album'))
            native.assert_not_called()
        for native_state, text in [('not_found', 'not found'), ('ambiguous', 'More than one')]:
            with self.subTest(native_state=native_state), \
                 patch('mac_control.asset', return_value=Path(__file__)), \
                 patch('mac_control.subprocess.run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = native_state
                self.assertIn(text.lower(), __import__('mac_control')._music('song', 'unknown').get('error', '').lower())
        with patch('mac_control.asset', return_value=Path(__file__)), \
             patch('mac_control.subprocess.run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'Not authorized to send Apple events. (-1743)'
            self.assertIn('Automation', __import__('mac_control')._music('play')['error'])

    def test_music_verifies_after_command_returns(self):
        with patch('mac_control.asset', return_value=Path(__file__)), \
             patch('mac_control.subprocess.run') as run:
            run.side_effect = [Mock(returncode=0, stdout='accepted'),
                               Mock(returncode=0, stdout='stopped'),
                               Mock(returncode=0, stdout='playing')]
            with patch('mac_control.time.sleep'):
                self.assertEqual(__import__('mac_control')._music('play'), {'player_state': 'playing'})
            self.assertEqual(run.call_count, 3)
            self.assertEqual(run.call_args.args[0][-2:], ['state', ''])
        with patch('mac_control.asset', return_value=Path(__file__)), \
             patch('mac_control.subprocess.run') as run:
            run.side_effect = [Mock(returncode=0, stdout='accepted'),
                               Mock(returncode=0, stdout='mismatch'),
                               Mock(returncode=0, stdout='playing')]
            with patch('mac_control.time.sleep'):
                self.assertEqual(__import__('mac_control')._music('playlist', 'Sample Mix'), {'player_state': 'playing'})
            self.assertEqual(run.call_args.args[0][-2:], ['verify_playlist', 'Sample Mix'])
        with patch('mac_control.asset', return_value=Path(__file__)), \
             patch('mac_control.subprocess.run') as run, \
             patch('mac_control.time.monotonic', side_effect=[0, 7]):
            run.side_effect = [Mock(returncode=0, stdout='track-A'),
                               Mock(returncode=0, stdout='accepted'),
                               Mock(returncode=0, stdout='playing'),
                               Mock(returncode=0, stdout='track-A')]
            self.assertIn('did not change tracks', __import__('mac_control')._music('next')['error'])
        with patch('mac_control.asset', return_value=Path(__file__)), \
             patch('mac_control.subprocess.run') as run, \
             patch('mac_control.time.sleep'):
            run.side_effect = [Mock(returncode=0, stdout='track-A'),
                               Mock(returncode=0, stdout='accepted'),
                               Mock(returncode=0, stdout='playing'),
                               Mock(returncode=0, stdout='track-A'),
                               Mock(returncode=0, stdout='track-A'),
                               Mock(returncode=0, stdout='accepted'),
                               Mock(returncode=0, stdout='playing'),
                               Mock(returncode=0, stdout='track-B')]
            self.assertEqual(__import__('mac_control')._music('previous'), {'player_state': 'playing'})
            self.assertEqual(run.call_count, 8)

    def test_fixed_script_and_no_arbitrary_script_tool(self):
        source = (Path(__file__).resolve().parents[1] / 'mac_control.py').read_text()
        script = (Path(__file__).resolve().parents[1] / 'native/Music.applescript').read_text()
        self.assertIn("['/usr/bin/osascript', str(script), operation, name]", source)
        self.assertIn('if player state is stopped then', script)
        self.assertIn('if player state is playing then return "playing"', script)
        self.assertIn('name of current playlist is item 2 of argv', script)
        self.assertNotIn('player state as text', script)
        self.assertNotIn('shell=True', source)
        self.assertNotIn('execute_applescript', {x['function']['name'] for x in main.TOOLS})
        self.assertNotIn('execute_shell', {x['function']['name'] for x in main.TOOLS})
        with patch('mac_control._music') as music:
            answer = self.agent()('Play Fleetwood Mac')
            self.assertIn('play NAME song', answer)
            music.assert_not_called()


if __name__ == '__main__':
    unittest.main()
