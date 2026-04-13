"""Source: official Wix website (requires Playwright for client-side rendering)."""

from __future__ import annotations

import logging

from playwright.async_api import async_playwright

from ..config import (
    PLAYWRIGHT_HYDRATION_TIMEOUT_MS,
    PLAYWRIGHT_MIN_HYDRATION_MS,
    PLAYWRIGHT_TIMEOUT_MS,
    USER_AGENT,
    WIX_URLS,
)
from .base import Source, SourceResult

logger = logging.getLogger(__name__)


class WixSiteSource(Source):
    name = "wix_site"

    async def fetch(self) -> list[SourceResult]:
        results: list[SourceResult] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(user_agent=USER_AGENT, locale="pt-BR")
                page = await ctx.new_page()
                for url in WIX_URLS:
                    try:
                        await page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=PLAYWRIGHT_TIMEOUT_MS,
                        )
                        # Wait for Wix client-side hydration: prefer networkidle
                        # (true signal that scripts finished) and fall back to a
                        # short fixed wait if networkidle doesn't settle in time.
                        try:
                            await page.wait_for_load_state(
                                "networkidle", timeout=PLAYWRIGHT_HYDRATION_TIMEOUT_MS
                            )
                        except Exception:
                            logger.info("Wix: networkidle did not settle for %s — using min wait", url)
                            await page.wait_for_timeout(PLAYWRIGHT_MIN_HYDRATION_MS)
                        else:
                            # Even with networkidle, give late-binding Wix widgets a beat.
                            await page.wait_for_timeout(PLAYWRIGHT_MIN_HYDRATION_MS)

                        text = (await page.inner_text("body")).lower()
                        links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")

                        # Hydration sanity check: Wix homepages after hydration
                        # always produce several KB of text. < 200 chars means
                        # we likely captured a skeleton, not the real content.
                        error = None
                        if len(text) < 200:
                            error = f"content too short ({len(text)} chars) — hydration likely failed"
                            logger.warning("wix_site: %s (%s)", error, url)

                        results.append(
                            SourceResult(
                                source_name=f"{self.name}:{url}",
                                text=text,
                                links=links,
                                error=error,
                            )
                        )
                    except Exception as exc:
                        logger.warning("Wix fetch failed for %s: %s", url, exc)
            finally:
                await browser.close()
        return results
