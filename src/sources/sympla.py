"""Source: Sympla event search (httpx + embedded JSON parsing).

Sympla's /eventos search is a Next.js RSC app — the results ship as an
escaped JSON payload inside the HTML, not as DOM cards. We detect the
payload first (`searchEventsResult`), then pull event URLs matching
`goiania-noise` from it. This lets us distinguish three states:

1. Payload present + matching event  → score it.
2. Payload present + no match        → empty text, no error (legit "no results").
3. Payload absent                    → emit parser-broken error so we know
                                        Sympla changed its page shape again.
"""

from __future__ import annotations

import logging
import re

from ..config import SYMPLA_SEARCH_URL
from ._http import get_with_retry
from .base import Source, SourceResult

logger = logging.getLogger(__name__)

# Marker that the embedded search-results payload rendered server-side.
# If this is missing, the page shape changed and we should alert on markup.
_PAYLOAD_MARKER = "searcheventsresult"

# Any /evento/<slug> path, captured from the raw HTML (the payload contains
# them as `"url":"https://www.sympla.com.br/evento/..."` plus relative
# variants; grab both and dedupe).
_EVENT_URL_RE = re.compile(
    r"https://www\.sympla\.com\.br/evento/[a-z0-9][a-z0-9\-/]*",
    re.IGNORECASE,
)

_NOISE_SLUG_FRAGMENTS = ("goiania-noise", "goiânia-noise", "goi%c3%a2nia-noise")


def _find_matching_event_urls(html_lower: str) -> list[str]:
    urls = set(_EVENT_URL_RE.findall(html_lower))
    return sorted(u for u in urls if any(frag in u for frag in _NOISE_SLUG_FRAGMENTS))


class SymplaSource(Source):
    name = "sympla"

    async def fetch(self) -> list[SourceResult]:
        resp = await get_with_retry(SYMPLA_SEARCH_URL)
        resp.raise_for_status()
        html_lower = resp.text.lower()

        if _PAYLOAD_MARKER not in html_lower:
            msg = "search payload missing — Sympla markup may have changed"
            logger.warning("sympla: %s", msg)
            return [SourceResult(source_name=self.name, text="", links=[], error=msg)]

        matching_urls = _find_matching_event_urls(html_lower)
        if not matching_urls:
            logger.info("sympla: search returned no 'goiânia noise' events")
            return [SourceResult(source_name=self.name, text="", links=[])]

        # We found at least one Goiânia Noise event page listed on Sympla —
        # that alone is a strong signal the sale is live. Emit text the
        # analyzer can score: the target-event term (passes the guard) plus
        # a ticketing cue, and hand over the URLs as ticket links.
        text = f"goiânia noise festival 2026 ingressos à venda {' '.join(matching_urls)}"
        logger.info("sympla: found %d goiânia noise event(s)", len(matching_urls))
        return [SourceResult(source_name=self.name, text=text, links=matching_urls)]
