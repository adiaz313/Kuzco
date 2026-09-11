import contextlib
from datetime import datetime
import io
import json
from pathlib import Path
import unittest
import subprocess
from unittest.mock import patch

import main


def tool(name, arguments):
    return {"id": "call_1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments)}}


class JarvisTests(unittest.TestCase):
    def test_application_json_loop(self):
        for name in ["Calculator", "Safari", "JarvisNoSuchApp987654"]:
            with self.subTest(name=name):
                missing = name.startswith("Jarvis")
                def send(payload):
                    if len(payload["messages"]) == 2:
                        return {"content": json.dumps({"tool": "open_application",
                            "arguments": {"application_name": name}})}
                    result = json.loads(payload["messages"][-1]["content"])["tool_result"]
                    self.assertEqual(result["application_name"], name)
                    self.assertEqual(result["opened"], not missing)
                    if missing:
                        self.assertIn("error", result)
                    return {"content": json.dumps({"answer": "Could not open the app." if missing else "Opened the app."})}
                log = io.StringIO()
                process = subprocess.CompletedProcess([], int(missing), "", "Application not found" if missing else "")
                with patch.object(main.sys, "platform", "darwin"), patch.object(
                        main.subprocess, "run", return_value=process) as launch, contextlib.redirect_stderr(log):
                    answer = main.run(f"Open {name}.", debug=True, send=send)
                launch.assert_called_once_with(["/usr/bin/open", "-a", name], shell=False,
                                               capture_output=True, text=True, timeout=15)
                self.assertIn("Could not" if missing else "Opened", answer)
                for text in ["Llama response / decision", name, "raw tool result", "final answer"]:
                    self.assertIn(text, log.getvalue())

    def test_application_rejects_commands_paths_and_extra_arguments(self):
        with patch.object(main.subprocess, "run") as launch:
            for name in [None, "", "-a Safari", "/Applications/Safari.app", "https://example.com",
                         "Safari; touch /tmp/test", "$(whoami)", "Safari\n--args", "x" * 101]:
                result = main.execute_tool(tool("open_application", {"application_name": name}), [])
                self.assertIn("error", result)
            self.assertIn("error", main.execute_tool(tool("open_application", {
                "application_name": "Safari", "args": ["https://example.com"]}), []))
            launch.assert_not_called()

    def test_application_timeout_and_platform(self):
        with patch.object(main.sys, "platform", "darwin"), patch.object(main.subprocess, "run",
                side_effect=subprocess.TimeoutExpired("open", 15)):
            self.assertFalse(main.open_application("Safari")["opened"])
        with patch.object(main.sys, "platform", "linux"), patch.object(main.subprocess, "run") as launch:
            self.assertIn("macOS", main.open_application("Safari")["error"])
            launch.assert_not_called()

    def test_rag_direct_answer(self):
        with patch.object(main, "execute_tool") as execute:
            answer = main.run("Explain what RAG is.", send=lambda p: {
                "content": '{"answer": "RAG retrieves source passages to help generate an answer."}'})
        self.assertIn("retrieves", answer)
        execute.assert_not_called()

    def test_real_clock(self):
        before = datetime.now().astimezone()
        actual = datetime.fromisoformat(main.get_current_time()["local_datetime"])
        self.assertLess(abs((actual - before).total_seconds()), 2)
        self.assertEqual(actual.utcoffset(), before.utcoffset())

    def test_time_loop_and_debug(self):
        requests = []
        def send(payload):
            requests.append(payload)
            if len(requests) == 1:
                return {"content": '{"tool": "get_current_time", "arguments": {}}'}
            result_message = payload["messages"][-1]
            self.assertNotIn("tools", payload)
            self.assertEqual(result_message["role"], "user")
            self.assertEqual(json.loads(result_message["content"])["tool_call_id"], "call_1")
            self.assertIn("local_datetime", json.loads(result_message["content"])["tool_result"])
            return {"content": json.dumps({"answer": "Here is the current time."})}
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            self.assertEqual(main.run("What time is it?", debug=True, send=send),
                             "Here is the current time.")
        for label in ["request to Llama", "Llama chose a tool", "chosen tool and arguments",
                      "raw tool result", "final answer"]:
            self.assertIn(label, log.getvalue())

    def test_document_loop(self):
        document = Path(__file__).resolve().parents[1] / "examples/notes.txt"
        def send(payload):
            if len(payload["messages"]) == 2:
                return {"content": '{"tool": "search_documents", "arguments": {"query": "oat based dog treat"}}'}
            matches = json.loads(payload["messages"][-1]["content"])["tool_result"]["matches"]
            self.assertIn("dog treat", matches[0]["text"])
            self.assertEqual(matches[0]["source"], "notes.txt")
            return {"content": json.dumps({"answer": "An oat-based dog treat [notes.txt, chunk 1]."})}
        self.assertIn("dog treat", main.run("What was the Northwind product idea?", [document], send=send))

    def test_direct_answer(self):
        with patch.object(main, "execute_tool") as execute:
            answer = main.run("Explain what an embedding is.", send=lambda p: {
                "content": json.dumps({"answer": "An embedding represents information as a list of numbers."})})
        self.assertIn("numbers", answer)
        execute.assert_not_called()

    def test_json_protocol(self):
        replies = iter([{"content": json.dumps({"tool": "get_current_time", "arguments": {}})},
                        {"content": json.dumps({"answer": "The clock result is available."})}])
        self.assertEqual(main.run("time", send=lambda p: next(replies)),
                         "The clock result is available.")
        self.assertEqual(main.run("hello", send=lambda p: {
            "content": '{"answer": "Hello!"}'}), "Hello!")

    def test_no_documents_or_no_matches(self):
        self.assertEqual(main.search_documents("unrelated mineral")["matches"], [])
        document = Path(__file__).resolve().parents[1] / "examples/notes.txt"
        self.assertEqual(main.search_documents("xyzzy", [document])["matches"], [])

    def test_invalid_calls(self):
        for call in [tool("delete_files", {}), tool("get_current_time", {"extra": 1}),
                     tool("search_documents", {"query": ""}),
                     tool("search_documents", {"query": 123})]:
            self.assertIn("error", main.execute_tool(call, []))
        call = tool("get_current_time", {})
        call["function"]["arguments"] = "broken JSON"
        self.assertIn("error", main.execute_tool(call, []))

    def test_loop_limit(self):
        with self.assertRaisesRegex(RuntimeError, "Maximum tool steps"):
            main.run("loop", send=lambda p: {"content": '{"tool": "get_current_time", "arguments": {}}'})


if __name__ == "__main__":
    unittest.main()
