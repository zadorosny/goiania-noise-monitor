"""Source: official Wix website (requires Playwright for client-side rendering)."""

from __future__ import annotations

import logging

from playwright.async_api import async_playwright

from ..config import PLAYWRIGHT_TIMEOUT_MS, USER_AGENT, WIX_URLS
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
                            wait_until="networkidle",
                            timeout=PLAYWRIGHT_TIMEOUT_MS,
                        )
                        # Extra wait for Wix post-hydration
                        await page.wait_for_timeout(2000)

                        html = await page.content()
                        text = (await page.inner_text("body")).lower()
                        links = await page.eval_on_selector_all(
                            "a[href]", "els => els.map(e => e.href)"
                        )

                        results.append(
                            SourceResult(
                                source_name=f"{self.name}:{url}",
                                text=text,
                                links=links,
                                raw_html=html,
                            )
                        )
                    except Exception as exc:
                        logger.warning("Wix fetch failed for %s: %s", url, exc)
            finally:
                await browser.close()
        return results
