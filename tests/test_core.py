import json
import tempfile
import unittest
from pathlib import Path

from gpt_orchestrator.core import (OrchestratorError, assert_shareable, delegation_prompt,
                                   load_config, parse_packet, read_context, route)


def packet(verdict="proceed"):
    return {"goal": "Add greeting", "summary": ["Use stdlib"],
            "plan": [{"step": 1, "action": "Add greeting", "target": "greeting.py", "success_criteria": "Greeting test passes"}],
            "risks": [], "tests": ["python3 -m unittest"], "acceptance": ["Greeting is visible"],
            "do_not_do": ["Do not publish"], "verdict": verdict}


class RoutingTests(unittest.TestCase):
    def test_chinese_code(self):
        result = route("修复登录接口的错误")
        self.assertEqual(result["sequence"], ["chat", "codex", "chat"])
        self.assertEqual(result["model_tier"], "cheap")

    def test_artifact_and_reasoning(self):
        self.assertEqual(route("Create a spreadsheet")["executor"], "work")
        self.assertEqual(route("Explain dependency injection")["sequence"], ["chat"])

    def test_explicit_override(self):
        self.assertEqual(route("Review code in a PDF", "reasoning")["kind"], "reasoning")
        self.assertEqual(route("A local check", "local")["sequence"], ["local"])

    def test_sensitive_never_dispatch(self):
        decision = route("Implement code", "code", sensitive=True)
        self.assertEqual(decision["executor"], "local")
        self.assertEqual(decision["planner"], "local")

    def test_complexity_and_unknown_usage(self):
        self.assertEqual(route("code", complexity="complex")["model_tier"], "strong")
        self.assertEqual(route("code")["quota_estimate"], "unknown")

    def test_empty_task_rejected(self):
        with self.assertRaises(OrchestratorError):
            route(" ")


class PacketTests(unittest.TestCase):
    def test_all_supported_renderings(self):
        raw = json.dumps(packet(), ensure_ascii=False)
        for text in (raw, "```json\n" + raw + "\n```", "JSON\n" + raw):
            self.assertEqual(parse_packet(text)["verdict"], "proceed")

    def test_reject_partial_extra_prose_multiple_objects(self):
        raw = json.dumps(packet())
        for text in (raw[:-10], "Here it is: " + raw, raw + raw, "[]"):
            with self.assertRaises(OrchestratorError):
                parse_packet(text)

    def test_reject_unexecutable_plan(self):
        for key in ("plan", "tests", "acceptance"):
            p = packet()
            p[key] = []
            with self.assertRaises(OrchestratorError):
                parse_packet(json.dumps(p))

    def test_invalid_step_and_unknown_fields(self):
        for edit in (lambda p: p.update(verdict="yes"), lambda p: p.update(extra=True),
                     lambda p: p["plan"][0].update(step=True), lambda p: p.update(summary="wrong")):
            p = packet()
            edit(p)
            with self.assertRaises(OrchestratorError):
                parse_packet(json.dumps(p))

    def test_blocked_and_review_can_have_no_steps(self):
        p = packet("blocked")
        p["plan"] = []
        self.assertEqual(parse_packet(json.dumps(p))["verdict"], "blocked")
        p["verdict"] = "proceed"
        self.assertEqual(parse_packet(json.dumps(p), "review")["plan"], [])

    def test_methodology_format_override(self):
        prompt = delegation_prompt("Add greeting", "some data", skill_text="Use Markdown")
        self.assertIn("Controller format adaptation", prompt)
        self.assertTrue(prompt.index("Controller format adaptation") > prompt.index("Use Markdown"))

    def test_protocol_shape_matches_pinned_source(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "integrations/chatgpt-use/delegation.upstream.rs").read_text()
        for key in packet():
            self.assertIn("pub " + key + ":", source)


class ContextTests(unittest.TestCase):
    def test_scope_budget_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "workspace"
            root.mkdir()
            (root / "safe.txt").write_text("hello")
            (base / "outside.txt").write_text("outside")
            (root / "escape.txt").symlink_to(base / "outside.txt")
            self.assertIn("hello", read_context(["safe.txt"], root, 100))
            for files, limit in [(["../outside.txt"], 100), (["escape.txt"], 100), (["safe.txt"], 2)]:
                with self.assertRaises(OrchestratorError):
                    read_context(files, root, limit)

    def test_hidden_and_secret_named_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in (".env", "cookies.json", "auth.json"):
                (root / name).write_text("data")
                with self.assertRaises(OrchestratorError):
                    read_context([name], root, 100)

    def test_obvious_secret(self):
        for text in ("api_key=abcdefghijklmno", "Bearer abcdefghijklmnopqrstuvwxyz", "-----BEGIN RSA PRIVATE KEY-----"):
            with self.assertRaises(OrchestratorError):
                assert_shareable(text)

    def test_config_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            for data in ({"max_web_calls": 0}, {"models": {"invalid": "x"}}, {"browser": {"settle_seconds": 0}}, {"unknown": True}):
                path.write_text(json.dumps(data))
                with self.assertRaises(OrchestratorError):
                    load_config(path)


if __name__ == "__main__":
    unittest.main()
