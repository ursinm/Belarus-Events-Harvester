from __future__ import annotations
from typing import Optional
from contextlib import contextmanager

from playwright.sync_api import sync_playwright


@contextmanager
def browser_context():
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        pw.stop()


def render_html(url: str, wait_selector: Optional[str] = None, timeout_ms: int = 10000) -> str:
    with browser_context() as ctx:
        page = ctx.new_page()
        page.goto(url, timeout=timeout_ms)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except Exception:
                pass
        return page.content()


