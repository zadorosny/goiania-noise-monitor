"""Source: Instagram bio / Linktree page (Playwright required)."""

from __future__ import annotations

import json
import logging
import re

from playwright.async_api import async_playwright

from ..config import INSTAGRAM_URL, PLAYWRIGHT_TIMEOUT_MS, USER_AGENT
from .base import Source, SourceResult

logger = logging.getLogger(__name__)


class LinktreeSource(Source):
    name = "linktree"

    async def _discover_bio_url(self, page) -> str | None:
        """Try to extract the external URL from the Instagram profile page."""
        try:
            await page.goto(
                INSTAGRAM_URL,
                wait_until="networkidle",
                timeout=PLAYWRIGHT_TIMEOUT_MS,
            )
            await page.wait_for_timeout(2000)

            # Try meta tag og:description or page content for linktree URL
            html = await page.content()

            # Look for linktree / bio link patterns in the page HTML
            patterns = [
                r'(https?://linktr\.ee/[^\s"\'<>]+)',
                r'(https?://lnk\.bio/[^\s"\'<>]+)',
                r'(https?://bio\.link/[^\s"\'<>]+)',
                r'(https?://beacons\.ai/[^\s"\'<>]+)',
                r'"external_url"\s*:\s*"(https?://[^"]+)"',
            ]
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    return match.group(1)

            # Try extracting from visible links
            links = await page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.href)"
            )
            for link in links:
                for domain in ("linktr.ee", "lnk.bio", "bio.link", "beacons.ai"):
                    if domain in link:
                        return link

        except Exception as exc:
            logger.warning("Failed to discover bio URL from Instagram: %s", exc)

        # Fallback: try common linktree URL
        return "https://linktr.ee/goianianoisefestival"

    async def fetch(self) -> list[SourceResult]:
        results: list[SourceResult] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(user_agent=USER_AGENT, locale="pt-BR")
                page = await ctx.new_page()

                bio_url = await self._discover_bio_url(page)
                if not bio_url:
                    logger.warning("Could not discover bio/linktree URL")
                    return results

                logger.info("Fetching linktree/bio: %s", bio_url)
                await page.goto(
                    bio_url,
                    wait_until="networkidle",
                    timeout=PLAYWRIGHT_TIMEOUT_MS,
                )
                await page.wait_for_timeout(2000)

                html = await page.content()
                text = (await page.inner_text("body")).lower()
                links = await page.eval_on_selector_all(
                    "a[href]", "els => els.map(e => e.href)"
                )

                results.append(
                    SourceResult(
                        source_name=self.name,
                        text=text,
                        links=links,
                        raw_html=html,
                    )
                )
            finally:
                await browser.close()
        return results
