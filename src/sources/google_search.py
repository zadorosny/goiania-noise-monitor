"""Source: DuckDuckGo HTML search (no JS, no captcha)."""

from __future__ import annotations

import logging
import re

import httpx

from ..config import DUCKDUCKGO_URL, HTTPX_TIMEOUT_SECONDS, USER_AGENT
from .base import Source, SourceResult

logger = logging.getLogger(__name__)


def _extract_result_links(html: str) -> list[str]:
    """Extract actual result links (not DDG internal links)."""
    # DuckDuckGo HTML results use class="result__a" for result links
    links = re.findall(r'class="result__a"[^>]*href="(https?://[^"]+)"', html, re.IGNORECASE)
    if not links:
        # Fallback: grab all external links
        all_links = re.findall(r'href="(https?://[^"]+)"', html, re.IGNORECASE)
        links = [l for l in all_links if "duckduckgo.com" not in l]
    return links


def _extract_snippet_text(html: str) -> str:
    """Extract text from search result snippets."""
    # DDG HTML uses class="result__snippet"
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|div|td|span)>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if snippets:
        text = " ".join(snippets)
        text = re.sub(r"<[^>]+>", " ", text)
        return text.lower()

    # Fallback: strip all tags
    text = re.sub(r"<[^>]+>", " ", html)
    return text.lower()


class GoogleSearchSource(Source):
    name = "duckduckgo_search"

    async def fetch(self) -> list[SourceResult]:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=HTTPX_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(DUCKDUCKGO_URL)
            resp.raise_for_status()
            html = resp.text

        text = _extract_snippet_text(html)
        links = _extract_result_links(html)

        return [
            SourceResult(
                source_name=self.name,
                text=text,
                links=links,
                raw_html=html,
            )
        ]
