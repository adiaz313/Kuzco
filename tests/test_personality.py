"""Both personas use the same dispatcher, evidence, history, and step budget."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import main
import personality


def response(**decision):
    return {"content": json.dumps(decision)}


class PersonalityTests(unittest.TestCase):
    def test_configuration_and_loading_from_any_directory(self):
        for name in ["default", "kuzco"]:
            context = personality.personality_context(name)
            self.assertIn("operational instructions", context)
            self.assertIn("Your name is " + ("Kuzco" if name == "kuzco" else "Jarvis"), context)
        for name in ["../kuzco", "/tmp/other", "", "Kuzco", None, "not_installed"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                personality.personality_context(name)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(personality, "PERSONALITIES", Path(directory)):
                Path(directory, "quiet.txt").write_text("Use a quiet, concise tone.")
                self.assertIn("quiet, concise", personality.personality_context("quiet"))
                Path(directory, "empty.txt").write_text("   ")
                with self.assertRaisesRegex(ValueError, "empty"):
                    personality.personality_context("empty")

    def test_persona_survives_all_steps_without_changing_evidence_or_requests(self):
        snapshots = []
        document = Path(__file__).resolve().parents[1] / "examples/notes.txt"
        for name in ["default", "kuzco"]:
            requests, history = [], []
            decisions = iter([
                response(tool="get_current_time", arguments={}),
                response(tool="search_documents", arguments={"query": "oat dog treat"}),
                response(tool="open_application", arguments={"application_name": "Calculator"}),
                response(answer="At noon, Calculator opened; the notes describe an oat-based dog treat [notes.txt, chunk 1]."),
            ])
            def send(payload):
                requests.append(payload)
                self.assertIn(personality.personality_context(name), payload["messages"][0]["content"])
                self.assertEqual(payload["model"], "meta-llama-3.1-8b-instruct")
                self.assertEqual(payload["response_format"]["json_schema"]["schema"], main.DECISION_SCHEMA)
                if len(requests) == 3:
                    result = json.loads(payload["messages"][-1]["content"])["tool_result"]
                    self.assertIn("dog treat", result["matches"][0]["text"])
                return next(decisions)
            with patch.object(main, "get_current_time", return_value={"local_datetime": "noon"}), patch.object(
                    main, "open_application", return_value={"opened": True}) as launch:
                main.run("Read the time, search Northwind notes, then open Calculator.", [document],
                         send=send, history=history, personality=name)
            launch.assert_called_once_with("Calculator")
            self.assertEqual(len(requests), 4)
            def follow_up(payload):
                self.assertIn(personality.personality_context(name), payload["messages"][0]["content"])
                self.assertIn("Calculator", payload["messages"][-2]["content"])
                return response(answer="Calculator.")
            main.run("Which app?", history=history, send=follow_up, personality=name)
            # Remove only the known personality text: everything else must match.
            for payload in requests:
                payload["messages"][0]["content"] = payload["messages"][0]["content"].replace(
                    personality.personality_context(name), "")
            snapshots.append((requests, history))
        self.assertEqual(snapshots[0], snapshots[1])

    def test_direct_answers_and_interactive_selection(self):
        for name in ["default", "kuzco"]:
            with patch.object(main, "execute_tool") as execute:
                answer = main.run("Explain RAG.", personality=name, send=lambda p: response(answer="RAG retrieves evidence."))
                self.assertEqual(answer, "RAG retrieves evidence.")
                execute.assert_not_called()
            output = io.StringIO()
            def send(payload):
                self.assertIn(personality.personality_context(name), payload["messages"][0]["content"])
                return response(answer="Hello.")
            with patch("builtins.input", side_effect=["Hello", "/exit"]), contextlib.redirect_stdout(output):
                main.conversation(personality=name, send=send)
            self.assertIn(f"({name})", output.getvalue())

    def test_failure_missing_evidence_malformed_response_and_limit(self):
        for name in ["default", "kuzco"]:
            with self.subTest(personality=name):
                replies = iter([
                    response(tool="open_application", arguments={"application_name": "MissingApp"}),
                    response(tool="search_documents", arguments={"query": "unknown"}),
                    response(answer="The app was not found, and no document evidence was available."),
                ])
                def send(payload):
                    if len(payload["messages"]) == 4:
                        result = json.loads(payload["messages"][-1]["content"])["tool_result"]
                        self.assertEqual(result, {"opened": False, "error": "App not found"})
                    if len(payload["messages"]) == 6:
                        self.assertEqual(json.loads(payload["messages"][-1]["content"])["tool_result"]["matches"], [])
                    return next(replies)
                with patch.object(main, "open_application", return_value={"opened": False, "error": "App not found"}):
                    self.assertIn("not found", main.run("Open MissingApp and find my notes.", send=send, personality=name))
                with patch.object(main, "execute_tool") as execute:
                    with self.assertRaises(ValueError):
                        main.run("bad", personality=name, send=lambda p: {"content": "broken"})
                    execute.assert_not_called()
                with patch.object(main, "get_current_time", return_value={"time": "noon"}) as clock:
                    with self.assertRaisesRegex(RuntimeError, "Maximum tool steps"):
                        main.run("loop", personality=name, max_steps=2,
                                 send=lambda p: response(tool="get_current_time", arguments={}))
                    self.assertEqual(clock.call_count, 2)

    def test_cli_selection_and_unknown_name(self):
        with patch("sys.argv", ["main.py", "--chat", "--personality", "kuzco"]), patch.object(main, "conversation") as conversation:
            self.assertEqual(main.main(), 0)
            agent = conversation.call_args.kwargs['agent']
            self.assertEqual(agent.policy, 'direct')
            conversation.assert_called_once_with([], False, 5, personality="kuzco", agent=agent)
        with patch("sys.argv", ["main.py", "--chat", "--personality", "not_installed"]), patch.object(
                main, "conversation") as conversation, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main.main(), 1)
            conversation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
