"""Source: Bilheteria Digital search (httpx + selectolax, no JS)."""

from __future__ import annotations

import logging

from selectolax.parser import HTMLParser

from ..config import BILHETERIA_SEARCH_URL
from ._http import get_with_retry
from .base import Source, SourceResult

logger = logging.getLogger(__name__)

_CARD_SELECTORS = (
    "[class*='card-event']",
    "[class*='event-card']",
    "[class*='search-result']",
    "[class*='evento']",
    "[class*='result']",
    "article",
)


def _extract_cards_text(tree: HTMLParser) -> tuple[str, bool]:
    """Return (lowered_text, selectors_matched).

    `selectors_matched` is False only when *none* of the card selectors
    produced a single node — a signal that the page layout changed and the
    parser is blind, which is distinct from "cards exist, but contain no
    matching event".
    """
    for selector in _CARD_SELECTORS:
        nodes = tree.css(selector)
        if nodes:
            chunks = [n.text(separator=" ", strip=True) for n in nodes]
            joined = " ".join(c for c in chunks if c).lower()
            return joined, True
    return "", False


class BilheteriaSource(Source):
    name = "bilheteria_digital"

    async def fetch(self) -> list[SourceResult]:
        resp = await get_with_retry(BILHETERIA_SEARCH_URL)
        resp.raise_for_status()
        html = resp.text

        tree = HTMLParser(html)
        card_text, matched = _extract_cards_text(tree)

        if not matched:
            msg = "no card selectors matched — Bilheteria markup may have changed"
            logger.warning("bilheteria_digital: %s", msg)
            return [SourceResult(source_name=self.name, text="", links=[], error=msg)]

        noise_in_cards = "goiânia noise" in card_text or "goiania noise" in card_text
        if not noise_in_cards:
            logger.info("Bilheteria Digital: no 'goiânia noise' found in result cards")
            return [SourceResult(source_name=self.name, text="", links=[])]

        return [SourceResult(source_name=self.name, text=card_text, links=[])]
