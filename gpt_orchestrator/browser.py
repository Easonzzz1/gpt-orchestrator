"""UI-only browser transport; deliberately does not run upstream channel.rs.

Uses Playwright's public browser API, NOT an official OpenAI automation API.
No CDP listener, cookie export, storage-state export, credential parsing,
authenticated fetch, private endpoint, extension or local tool server.
"""
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .core import ROOT, OrchestratorError


@contextmanager
def profile_lock():
    # Supported platforms: macOS/Linux (fcntl). Locks release on process exit.
    import fcntl
    state = ROOT / ".state"
    if state.is_symlink():
        raise OrchestratorError("Browser state cannot be a symbolic link")
    state.mkdir(mode=0o700, exist_ok=True)
    os.chmod(state, 0o700)
    with (state / "browser.lock").open("a+") as handle:
        os.chmod(handle.name, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OrchestratorError("Dedicated browser profile is busy; do not run concurrently")
        yield


def profile_path():
    profile = ROOT / ".state" / "browser-profile"
    marker = profile / ".gpt-orchestrator-owned"
    if profile.is_symlink() or (profile.parent.exists() and profile.parent.is_symlink()):
        raise OrchestratorError("Browser state/profile cannot be a symbolic link")
    if profile.exists() and not marker.is_file():
        raise OrchestratorError("Refusing an existing unowned browser profile")
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(profile, 0o700)
    marker.touch(mode=0o600, exist_ok=True)
    return profile


@contextmanager
def browser_context(config):
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        raise OrchestratorError("Browser dependency missing. Run scripts/setup-browser.sh")
    with profile_lock():
        profile = profile_path()
        with sync_playwright() as p:
            channel = config["browser"]["channel"]
            try:
                context = p.chromium.launch_persistent_context(
                    str(profile), headless=False,
                    channel="chrome" if channel == "chrome" else None,
                    chromium_sandbox=True,
                    ignore_default_args=["--password-store=basic", "--use-mock-keychain",
                                         "--unsafely-disable-devtools-self-xss-warnings", "--enable-unsafe-swiftshader"],
                    accept_downloads=False,
                )
                try:
                    yield context
                finally:
                    context.close()
            except PlaywrightError as exc:
                raise OrchestratorError("Browser launch/UI failed. Check Chrome and run from a regular local terminal; restricted agent sandboxes may block GUI apps. Inspect any possible submission before retrying.") from exc


def login(config):
    with browser_context(config) as context:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=60000)
        print("请在专用浏览器中手动登录，并选择你希望使用的 Chat 模型。不要导入其他浏览器的 Cookie。")
        input("完成后回到终端按 Enter 关闭浏览器：")


def visible(locator):
    return [locator.nth(i) for i in range(locator.count()) if locator.nth(i).is_visible()]


def wait_reply(page, settings, baseline, deadline, settle=None):
    """Conservative completion: new assistant + stable text + no Stop + Copy UI.

    If the site's UI changes this times out; it does not invent a completed reply.
    Rendered code content is read via inner_text; no scripts execute in the page.
    """
    settle = settings["settle_seconds"] if settle is None else settle
    previous, since = "", time.monotonic()
    while time.monotonic() < deadline:
        alerts = visible(page.locator(settings["error_selector"]))
        if alerts:
            raise OrchestratorError("Browser shows an alert/dialog. Inspect it manually; submission may have occurred. No retry.")
        assistants = page.locator(settings["assistant_selector"])
        if assistants.count() > baseline:
            last = assistants.last
            # inner_text(code) avoids rendered 'json / Copy code' UI labels.
            codes = last.locator("pre code")
            current = codes.first.inner_text() if codes.count() == 1 else last.inner_text()
            if current != previous:
                previous, since = current, time.monotonic()
            stop = visible(page.locator(settings["stop_selector"]))
            copy_selector = "button[data-testid='copy-turn-action-button'], button[aria-label='Copy'], button[aria-label='复制']"
            copy = last.locator(copy_selector)
            if not copy.count():
                turn = last.locator("xpath=ancestor::article[1]")
                if turn.count():
                    copy = turn.locator(copy_selector)
            if current.strip() and not stop and visible(copy) and time.monotonic() - since >= settle:
                return current
        page.wait_for_timeout(500)
    raise OrchestratorError("Reply did not complete within deadline. Inspect the browser conversation; do not resubmit blindly.")


def ask(config, prompt, before_submit):
    """Send exactly once. before_submit durably marks the ambiguous boundary."""
    settings = config["browser"]
    with browser_context(config) as context:
        # A fresh conversation per request prevents task-to-task contamination.
        page = context.new_page()
        page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=60000)
        page.locator(settings["composer_selector"]).first.wait_for(state="visible", timeout=30000)
        if not page.url.startswith("https://chatgpt.com/"):
            raise OrchestratorError("Unexpected page origin; no prompt sent")
        if visible(page.locator(settings["error_selector"])):
            raise OrchestratorError("Resolve browser dialog/login/rate limit manually; no prompt sent")
        composer = visible(page.locator(settings["composer_selector"]))
        if len(composer) != 1:
            raise OrchestratorError("Expected exactly one visible composer; no prompt sent")
        composer[0].fill(prompt)
        baseline = page.locator(settings["assistant_selector"]).count()
        send = visible(page.locator(settings["send_selector"]))
        if len(send) != 1 or not send[0].is_enabled():
            raise OrchestratorError("Send button unavailable; no prompt sent")
        before_submit()
        send[0].click(timeout=10000)
        text = wait_reply(page, settings, baseline, time.monotonic() + config["timeout_seconds"])
        return {"status": "completed", "result": {"text": text}, "conversation_url": page.url}
