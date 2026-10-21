"""Optional real Chrome tests on synthetic DOM only; no ChatGPT request/login."""
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gpt_orchestrator.browser import browser_context, profile_path, wait_reply
from gpt_orchestrator.core import OrchestratorError, load_config


class ProfileBoundaryTests(unittest.TestCase):
    def test_unowned_profile_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".state/browser-profile").mkdir(parents=True)
            with mock.patch("gpt_orchestrator.browser.ROOT", root):
                with self.assertRaises(OrchestratorError):
                    profile_path()

    def test_owned_profile_is_private(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch("gpt_orchestrator.browser.ROOT", Path(temp)):
                profile = profile_path()
                self.assertEqual(profile.stat().st_mode & 0o777, 0o700)
                self.assertTrue((profile / ".gpt-orchestrator-owned").is_file())


@unittest.skipUnless(os.environ.get("ORCHESTRATOR_BROWSER_TEST") == "1" and importlib.util.find_spec("playwright"), "Optional real Chrome fixture; set ORCHESTRATOR_BROWSER_TEST=1")
class BrowserFixtureTests(unittest.TestCase):
    def test_real_browser_completion_dialog_and_timeout(self):
        config = load_config()
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch("gpt_orchestrator.browser.ROOT", Path(temp)):
                with browser_context(config) as context:
                    page = context.new_page()
                    page.set_content('<article><div data-message-author-role="assistant"><pre><code>{"goal":"fixture"}</code></pre></div><button data-testid="copy-turn-action-button">Copy</button></article>')
                    text = wait_reply(page, config["browser"], 0, time.monotonic() + 3, settle=0)
                    self.assertEqual(text, '{"goal":"fixture"}')
                    with self.assertRaises(OrchestratorError):
                        wait_reply(page, config["browser"], 1, time.monotonic() + 0.1, settle=0)
                    page.set_content('<div role="alert">Rate limit</div>')
                    with self.assertRaises(OrchestratorError):
                        wait_reply(page, config["browser"], 0, time.monotonic() + 3, settle=0)


if __name__ == "__main__":
    unittest.main()
