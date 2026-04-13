"""Source: DuckDuckGo HTML search (httpx + selectolax, no JS, no captcha)."""

from __future__ import annotations

import logging

from selectolax.parser import HTMLParser

from ..config import DUCKDUCKGO_URL
from ._http import get_with_retry
from .base import Source, SourceResult

logger = logging.getLogger(__name__)


def _extract_result_links(tree: HTMLParser) -> list[str]:
    """Extract actual result URLs from DDG HTML results.

    DDG wraps result titles in <a class="result__a">. Fall back to any
    external link if that class selector misses (markup drift).
    """
    links: list[str] = []
    for a in tree.css("a.result__a"):
        href = a.attributes.get("href") or ""
        if href.startswith("http"):
            links.append(href)
    if links:
        return links
    for a in tree.css("a[href]"):
        href = a.attributes.get("href") or ""
        if href.startswith("http") and "duckduckgo.com" not in href:
            links.append(href)
    return links


def _extract_snippet_text(tree: HTMLParser) -> str:
    """Extract lowered text from DDG result snippets."""
    nodes = tree.css("a.result__snippet, .result__snippet")
    if nodes:
        chunks = [n.text(separator=" ", strip=True) for n in nodes]
        joined = " ".join(c for c in chunks if c).lower()
        if joined:
            return joined
    # Fallback: body text (lower bar because DDG layout is small)
    body = tree.body
    if body is None:
        return ""
    return body.text(separator=" ", strip=True).lower()


class GoogleSearchSource(Source):
    name = "duckduckgo_search"

    async def fetch(self) -> list[SourceResult]:
        resp = await get_with_retry(DUCKDUCKGO_URL)
        resp.raise_for_status()
        html = resp.text

        tree = HTMLParser(html)
        text = _extract_snippet_text(tree)
        links = _extract_result_links(tree)

        return [SourceResult(source_name=self.name, text=text, links=links)]
