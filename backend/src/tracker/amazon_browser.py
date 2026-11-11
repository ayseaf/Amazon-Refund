from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tracker.amazon_urls import require_read_only


class AmazonBrowserUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserPage:
    url: str
    status: int
    html: str


class PlaywrightVisibleBrowser:
    """Visible Chromium window. The app never types into the page.

    Cookies live in memory for the run. The temporary profile directory is
    removed when the window closes. The encrypted session, if the person
    finishes sign-in, is stored by the session vault, not in this directory.
    """

    def __init__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise AmazonBrowserUnavailable(
                "Playwright is not installed. On your Mac, install the amazon extra and Chromium, "
                "then start the app again. No Amazon page was opened."
            ) from exc
        self._profile = Path(tempfile.mkdtemp(prefix="apt-amazon-"))
        os.chmod(self._profile, 0o700)
        self._playwright = sync_playwright().start()
        self._context = None
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self._profile),
                headless=False,
                viewport={"width": 1280, "height": 900},
            )
        except Exception as exc:
            self.close()
            raise AmazonBrowserUnavailable(
                "The visible browser did not open. On your Mac, run playwright install chromium "
                "and try again. No Amazon page was opened."
            ) from exc
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def goto(self, url: str) -> BrowserPage:
        require_read_only(url)
        response = self._page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        status = response.status if response is not None else 0
        return BrowserPage(self._page.url, status, self._page.content())

    def snapshot(self) -> BrowserPage:
        return BrowserPage(self._page.url, 200, self._page.content())

    def cookies(self) -> list[dict]:
        return list(self._context.cookies("https://www.amazon.com"))

    def add_cookies(self, cookies: list[dict]) -> None:
        if cookies:
            self._context.add_cookies(cookies)

    def hold(self, seconds: float) -> None:
        if seconds > 0:
            self._page.wait_for_timeout(int(seconds * 1000))

    def close(self) -> None:
        context = getattr(self, "_context", None)
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
            self._context = None
        playwright = getattr(self, "_playwright", None)
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
            self._playwright = None
        profile = getattr(self, "_profile", None)
        if profile is not None:
            shutil.rmtree(profile, ignore_errors=True)


def open_visible_browser() -> PlaywrightVisibleBrowser:
    return PlaywrightVisibleBrowser()
