"""Scripted Llama decisions make loop/state tests deterministic and offline."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

import main


def response(**decision):
    return {"content": json.dumps(decision)}


class ConversationTests(unittest.TestCase):
    def test_multi_step_and_follow_up_history(self):
        history = []
        replies = iter([
            response(tool="get_current_time", arguments={}),
            response(tool="open_application", arguments={"application_name": "Calculator"}),
            response(answer="It is noon; Calculator was opened."),
        ])
        def send(payload):
            count = len(payload["messages"])
            if count == 4:
                self.assertIn("local_datetime", payload["messages"][-1]["content"])
            if count == 6:
                self.assertIn('"opened": true', payload["messages"][-1]["content"])
            return next(replies)
        with patch.object(main, "open_application", return_value={"opened": True}) as launch:
            main.run("What time is it, then open Calculator?", history=history, send=send)
        launch.assert_called_once_with("Calculator")
        def follow_up(payload):
            messages = payload["messages"]
            self.assertEqual(messages[1]["content"], "What time is it, then open Calculator?")
            self.assertIn('"tool": "get_current_time"', messages[2]["content"])
            self.assertIn("local_datetime", messages[3]["content"])
            self.assertIn("Calculator", messages[-2]["content"])
            self.assertEqual(messages[-1]["content"], "Which app was that?")
            return response(answer="Calculator.")
        self.assertEqual(main.run("Which app was that?", history=history, send=follow_up), "Calculator.")
        self.assertEqual(len(history), 2)

    def test_exact_step_limit_and_final_answer_chance(self):
        for finish in [True, False]:
            calls = []
            def send(payload):
                calls.append(payload)
                if finish and len(calls) == 3:
                    self.assertIn("remaining for this request: 0", payload["messages"][0]["content"])
                    return response(answer="Finished.")
                return response(tool="get_current_time", arguments={})
            history = []
            with patch.object(main, "get_current_time", return_value={"time": "noon"}) as clock:
                if finish:
                    self.assertEqual(main.run("time", send=send, max_steps=2, history=history), "Finished.")
                else:
                    with self.assertRaisesRegex(RuntimeError, "requested tool was not executed"):
                        main.run("time", send=send, max_steps=2, history=history)
                    self.assertIn("jarvis_status", history[0][-1]["content"])
                self.assertEqual(clock.call_count, 2)
            self.assertEqual(len(calls), 3)

    def test_malformed_decisions_never_execute(self):
        malformed = [None, {}, {"content": None}, {"content": "not JSON"},
            {"content": '{"tool":'}, {"content": "[]"}, {"content": "null"},
            {"content": '{"tool":"get_current_time","arguments":{}}\n{"answer":"Done"}'},
            response(answer=""), response(answer=123),
            response(tool="open_application", arguments=[]),
            response(tool="open_application"),
            response(answer="Done", tool="open_application", arguments={}),
            {"content": "```json"}, {"content": "```json\n{}"}]
        with patch.object(main, "execute_tool") as execute:
            for message in malformed:
                with self.subTest(message=message), self.assertRaises(ValueError):
                    main.run("open an app", send=lambda p: message)
            execute.assert_not_called()
        self.assertEqual(main.parse_decision({"content": '```json\n{"answer":"Hi"}\n```'}), {"answer": "Hi"})

    def test_tool_error_can_be_corrected(self):
        replies = iter([response(tool="unknown", arguments={}),
                        response(tool="get_current_time", arguments={}),
                        response(answer="Here is the time.")])
        def send(payload):
            if len(payload["messages"]) == 4:
                self.assertIn("error", payload["messages"][-1]["content"])
            return next(replies)
        self.assertEqual(main.run("time", send=send), "Here is the time.")

    def test_failure_preserves_executed_action(self):
        history = []
        replies = iter([response(tool="open_application", arguments={"application_name": "Calculator"}),
                        {"content": "broken"}])
        with patch.object(main, "open_application", return_value={"opened": True}):
            with self.assertRaises(ValueError):
                main.run("open Calculator", history=history, send=lambda p: next(replies))
        saved = json.dumps(history)
        self.assertIn("Calculator", saved)
        self.assertIn("tool_result", saved)
        self.assertIn("jarvis_status", saved)

    def test_interactive_multiple_requests_error_recovery_and_exit(self):
        replies = iter([response(answer="Hello."), {"content": "broken"}, response(answer="Still here.")])
        seen = []
        def send(payload):
            seen.append(payload)
            return next(replies)
        output = io.StringIO()
        with patch("builtins.input", side_effect=["", "Hello", "Bad turn", "Are you still there?", "/exit"]), contextlib.redirect_stdout(output):
            main.conversation(send=send)
        self.assertEqual(len(seen), 3)
        self.assertIn("Jarvis: Hello.", output.getvalue())
        self.assertIn("Jarvis: Error:", output.getvalue())
        self.assertIn("Jarvis: Still here.", output.getvalue())
        self.assertIn("Hello", json.dumps(seen[-1]))
        self.assertIn("jarvis_status", json.dumps(seen[-1]))

    def test_history_is_bounded_by_whole_turns_and_session_local(self):
        history = []
        for i in range(9):
            main.run(f"request {i}", history=history, send=lambda p: response(answer="OK"))
        self.assertEqual(len(history), main.HISTORY_TURNS)
        self.assertEqual(history[0][0]["content"], "request 3")
        self.assertTrue(all(len(turn) == 2 for turn in history))
        with patch.object(main, "HISTORY_CHARS", 600):
            main.run("new", history=history, send=lambda p: response(answer="OK"))
            self.assertLessEqual(sum(len(json.dumps(t)) for t in history), 600)
        def fresh(payload):
            self.assertEqual(len(payload["messages"]), 2)
            return response(answer="Fresh session.")
        main.run("new session", send=fresh)

    def test_invalid_limit_and_eof(self):
        for value in [0, -1, 21, True]:
            with self.assertRaises(ValueError):
                main.run("hi", max_steps=value)
        with patch("builtins.input", side_effect=EOFError), contextlib.redirect_stdout(io.StringIO()):
            main.conversation()


if __name__ == "__main__":
    unittest.main()
