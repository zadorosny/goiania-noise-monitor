"""Source: Sympla event search (httpx, no JS needed)."""

from __future__ import annotations

import logging

import httpx
from ..config import HTTPX_TIMEOUT_SECONDS, SYMPLA_SEARCH_URL, USER_AGENT
from .base import Source, SourceResult

logger = logging.getLogger(__name__)

# CSS-like pattern: Sympla wraps each event card in an <a> with class containing
# "sympla-card" or similar.  We extract text only from result cards, not the
# entire page, to avoid false positives from header/footer.
_CARD_MARKER = "sympla-card"


def _extract_card_text(html: str) -> str:
    """Extract text content likely belonging to event result cards.

    Falls back to full body text if no card markers are found.
    """
    lower = html.lower()
    # Check for card markers in the HTML
    if _CARD_MARKER in lower:
        # Grab chunks around card markers (rough but effective)
        import re

        cards = re.findall(
            r'class="[^"]*sympla-card[^"]*"[^>]*>(.*?)</(?:a|div|article)>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if cards:
            return " ".join(cards).lower()

    # Also check for event-list or search-results containers
    import re

    # Generic result container patterns
    for pattern in [
        r'class="[^"]*search-result[^"]*"[^>]*>(.*?)</(?:div|section)>',
        r'class="[^"]*event-card[^"]*"[^>]*>(.*?)</(?:div|a|article)>',
        r'class="[^"]*event-list[^"]*"[^>]*>(.*?)</(?:div|section)>',
    ]:
        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
        if matches:
            return " ".join(matches).lower()

    # Fallback: return all text but flag it
    import re as _re

    text = _re.sub(r"<[^>]+>", " ", html)
    return text.lower()


def _extract_links(html: str) -> list[str]:
    import re
    return re.findall(r'href="(https?://[^"]+)"', html, re.IGNORECASE)


class SymplaSource(Source):
    name = "sympla"

    async def fetch(self) -> list[SourceResult]:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=HTTPX_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(SYMPLA_SEARCH_URL)
            resp.raise_for_status()
            html = resp.text

        card_text = _extract_card_text(html)
        links = _extract_links(html)

        # Only include if "goiânia noise" or "goiania noise" appears in card text
        noise_in_cards = "goiânia noise" in card_text or "goiania noise" in card_text
        if not noise_in_cards:
            logger.info("Sympla: no 'goiânia noise' found in result cards")
            return [
                SourceResult(
                    source_name=self.name,
                    text="",
                    links=[],
                    raw_html=html,
                )
            ]

        # Don't return self-referential links — ticket link detection
        # is only useful for sources that point TO ticketing platforms.
        return [
            SourceResult(
                source_name=self.name,
                text=card_text,
                links=[],
                raw_html=html,
            )
        ]
