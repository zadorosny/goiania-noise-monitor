"""Source: Sympla event search (httpx + selectolax, no JS)."""

from __future__ import annotations

import logging

from selectolax.parser import HTMLParser

from ..config import SYMPLA_SEARCH_URL
from ._http import get_with_retry
from .base import Source, SourceResult

logger = logging.getLogger(__name__)

# Cards on Sympla search carry class hooks like "sympla-card", "EventCard"
# or nest inside search-results containers. CSS selectors are more stable
# against attribute-order and whitespace changes than regex.
_CARD_SELECTORS = (
    "[class*='sympla-card']",
    "[class*='EventCard']",
    "[class*='event-card']",
    "[class*='search-result']",
    "[class*='event-list'] article",
    "[class*='event-list'] a",
)


def _extract_cards_text(tree: HTMLParser) -> tuple[str, bool]:
    """Return (lowered_text, selectors_matched).

    `selectors_matched` is False only when *none* of the card selectors
    produced nodes — signal that Sympla's markup changed and the parser
    is blind, which is distinct from "found cards, none about this event".
    """
    for selector in _CARD_SELECTORS:
        nodes = tree.css(selector)
        if nodes:
            chunks = [n.text(separator=" ", strip=True) for n in nodes]
            joined = " ".join(c for c in chunks if c).lower()
            return joined, True
    return "", False


class SymplaSource(Source):
    name = "sympla"

    async def fetch(self) -> list[SourceResult]:
        resp = await get_with_retry(SYMPLA_SEARCH_URL)
        resp.raise_for_status()
        html = resp.text

        tree = HTMLParser(html)
        card_text, matched = _extract_cards_text(tree)

        if not matched:
            msg = "no card selectors matched — Sympla markup may have changed"
            logger.warning("sympla: %s", msg)
            return [SourceResult(source_name=self.name, text="", links=[], error=msg)]

        # Only score when "goiânia noise" actually appears in card text —
        # avoids false positives from menu/footer/SEO copy outside cards.
        noise_in_cards = "goiânia noise" in card_text or "goiania noise" in card_text
        if not noise_in_cards:
            logger.info("Sympla: no 'goiânia noise' found in result cards")
            return [SourceResult(source_name=self.name, text="", links=[])]

        # Links intentionally empty — Sympla pointing at itself adds no
        # cross-platform signal; scoring relies on card text.
        return [SourceResult(source_name=self.name, text=card_text, links=[])]
