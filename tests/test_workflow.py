import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gpt_orchestrator.cli import main
from gpt_orchestrator.core import OrchestratorError
from .test_core import packet


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / "run"
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.config = self.base / "config.json"
        self.fake = self.base / "fake-codex"
        self.fake.write_text("#!" + sys.executable + "\nimport pathlib,sys\na=sys.argv\np=pathlib.Path(a[a.index('--cd')+1]);(p/'executed.txt').write_text('done')\npathlib.Path(a[a.index('--output-last-message')+1]).write_text('changed executed.txt')\nprint('fake executor finished')\n")
        self.fake.chmod(0o700)
        self.config.write_text(json.dumps({"models": {"cheap": "test-only-model"}, "codex_binary": str(self.fake)}))
        self.reply = self.base / "reply.json"
        self.reply.write_text(json.dumps(packet()))

    def call(self, *argv, expected=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = main(["--config", str(self.config)] + [str(a) for a in argv])
        self.assertEqual(result, expected, err.getvalue() + out.getvalue())
        return out.getvalue(), err.getvalue()

    def plan(self, *extra):
        self.call("plan", "--task", "Implement greeting code", "--workspace", self.workspace, "--out", self.run, *extra)

    def import_plan(self, verdict="proceed"):
        self.reply.write_text(json.dumps(packet(verdict)))
        self.call("import-packet", "--run", self.run, "--file", self.reply)

    def execute(self, *extra, expected=0):
        return self.call("execute", "--run", self.run, *extra, expected=expected)

    def test_manual_plan_to_acceptance_with_fake_executor(self):
        self.plan()
        self.import_plan()
        out, _ = self.execute()
        self.assertIn('"dry_run": true', out)
        self.assertFalse((self.workspace / "executed.txt").exists())
        self.execute("--apply")
        self.assertTrue((self.workspace / "executed.txt").exists())
        self.call("verify", "--run", self.run, "--apply", "--", sys.executable, "-c", "assert open('executed.txt').read() == 'done'")
        (self.workspace / "evidence.txt").write_text("Executed file contains done. Local assertion passed; no other files changed in this fixture.")
        self.call("review", "--run", self.run, "--file", "evidence.txt")
        self.call("import-packet", "--run", self.run, "--stage", "review", "--file", self.reply)
        self.call("accept", "--run", self.run, expected=2)
        self.call("accept", "--run", self.run, "--confirm-acceptance")
        self.execute("--apply", "--retry", expected=2)
        self.call("import-packet", "--run", self.run, "--file", self.reply, expected=2)

    def test_blocked_plan_never_runs(self):
        self.plan()
        self.import_plan("blocked")
        self.execute("--apply", expected=2)
        self.assertFalse((self.workspace / "executed.txt").exists())

    def test_missing_model_requires_explicit_default(self):
        self.config.write_text(json.dumps({"codex_binary": str(self.fake)}))
        self.plan()
        self.import_plan()
        self.execute(expected=2)
        self.execute("--use-codex-default")

    def test_retries_and_budget_are_bounded(self):
        self.plan()
        self.import_plan()
        self.execute("--apply")
        self.execute("--apply", expected=2)
        self.execute("--apply", "--retry", "--tier", "standard", "--use-codex-default")
        self.execute("--apply", "--retry", expected=2)

    def test_failed_check_blocks_acceptance(self):
        self.plan()
        self.import_plan()
        self.execute("--apply")
        self.call("verify", "--run", self.run, "--apply", "--", sys.executable, "-c", "raise SystemExit(7)", expected=2)
        self.call("accept", "--run", self.run, "--confirm-acceptance", expected=2)
        state = json.loads((self.run / "run.json").read_text())
        self.assertEqual(state["checks"][0]["returncode"], 7)

    def test_review_invalidated_by_new_check(self):
        self.plan()
        self.import_plan()
        self.call("review", "--run", self.run)
        self.call("verify", "--run", self.run, "--apply", "--", sys.executable, "-c", "pass")
        self.call("import-packet", "--run", self.run, "--stage", "review", "--file", self.reply, expected=2)

    def test_sensitive_and_work_dispatch_refused(self):
        self.plan("--sensitive")
        self.import_plan()
        self.execute("--apply", expected=2)
        self.call("review", "--run", self.run, expected=2)

    def test_browser_malformed_packet_is_preserved_no_resubmit(self):
        def fake_ask(config, prompt, before_submit):
            before_submit()
            return {"status": "completed", "result": {"text": "partial reply"}}
        with mock.patch("gpt_orchestrator.browser.ask", side_effect=fake_ask) as ask:
            self.call("plan", "--task", "code", "--workspace", self.workspace, "--out", self.run,
                      "--backend", "browser", "--allow-web", expected=2)
            self.assertEqual(ask.call_count, 1)
        self.assertTrue((self.run / "plan-response.json").exists())
        state = json.loads((self.run / "run.json").read_text())
        self.assertEqual(state["web_calls"], 1)
        self.assertEqual(state["plan_submission"], "unknown")

    def test_browser_requires_explicit_opt_in(self):
        with mock.patch("gpt_orchestrator.browser.ask") as ask:
            self.call("plan", "--task", "code", "--workspace", self.workspace, "--out", self.run,
                      "--backend", "browser", expected=2)
            ask.assert_not_called()

    def test_unfinished_execution_blocks_acceptance(self):
        self.plan()
        self.import_plan()
        with mock.patch("gpt_orchestrator.cli.run_process", side_effect=OrchestratorError("timeout")):
            self.execute("--apply", expected=2)
        state = json.loads((self.run / "run.json").read_text())
        self.assertEqual(state["executions"][0]["status"], "unknown")
        self.execute("--apply", expected=2)


if __name__ == "__main__":
    unittest.main()
