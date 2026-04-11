"""Source: Eventim search (httpx, no JS needed)."""

from __future__ import annotations

import logging
import re

import httpx

from ..config import EVENTIM_SEARCH_URL, HTTPX_TIMEOUT_SECONDS, USER_AGENT
from .base import Source, SourceResult

logger = logging.getLogger(__name__)


def _extract_card_text(html: str) -> str:
    """Extract text from event result cards."""
    for pattern in [
        r'class="[^"]*product-card[^"]*"[^>]*>(.*?)</(?:div|a|article)>',
        r'class="[^"]*search-result[^"]*"[^>]*>(.*?)</(?:div|section)>',
        r'class="[^"]*event-card[^"]*"[^>]*>(.*?)</(?:div|a|article)>',
    ]:
        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
        if matches:
            return " ".join(matches).lower()

    text = re.sub(r"<[^>]+>", " ", html)
    return text.lower()


def _extract_links(html: str) -> list[str]:
    return re.findall(r'href="(https?://[^"]+)"', html, re.IGNORECASE)


class EventimSource(Source):
    name = "eventim"

    async def fetch(self) -> list[SourceResult]:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=HTTPX_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(EVENTIM_SEARCH_URL)
            resp.raise_for_status()
            html = resp.text

        card_text = _extract_card_text(html)
        links = _extract_links(html)

        noise_in_cards = "goiânia noise" in card_text or "goiania noise" in card_text
        if not noise_in_cards:
            logger.info("Eventim: no 'goiânia noise' found in result cards")
            return [
                SourceResult(
                    source_name=self.name,
                    text="",
                    links=[],
                    raw_html=html,
                )
            ]

        return [
            SourceResult(
                source_name=self.name,
                text=card_text,
                links=[],
                raw_html=html,
            )
        ]
