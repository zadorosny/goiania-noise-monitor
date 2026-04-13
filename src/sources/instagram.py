"""Source: Instagram profile posts via Apify, with picuki.com fallback.

Why two backends:
- Apify (actor `apify/instagram-scraper`) returns structured posts with
  captions, timestamps and URLs — reliable but needs an APIFY_TOKEN secret.
- picuki.com is a public third-party mirror with no login. Best-effort,
  but zero-cost and zero-setup.

Stories are NOT supported — they require a logged-in session cookie, which
is fragile to maintain in public CI and risks getting the account banned.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from ..config import (
    APIFY_INSTAGRAM_ACTOR,
    APIFY_SYNC_TIMEOUT_SECONDS,
    INSTAGRAM_HANDLE,
    INSTAGRAM_POST_MAX_AGE_DAYS,
    INSTAGRAM_POSTS_LIMIT,
    USER_AGENT,
)
from ._http import get_with_retry
from .base import Source, SourceResult

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s)>\"']+", re.IGNORECASE)

_APIFY_ENDPOINT_TMPL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"


def _extract_urls(text: str) -> list[str]:
    return _URL_RE.findall(text or "")


class InstagramSource(Source):
    name = "instagram"

    async def fetch(self) -> list[SourceResult]:
        handle = INSTAGRAM_HANDLE
        if not handle:
            return [
                SourceResult(
                    source_name=self.name,
                    text="",
                    links=[],
                    error="INSTAGRAM_HANDLE not configured",
                )
            ]

        token = os.environ.get("APIFY_TOKEN", "").strip()
        if token:
            try:
                return [await self._fetch_apify(handle, token)]
            except Exception as exc:
                logger.warning("instagram: apify failed (%s) — falling back to picuki", exc)

        return [await self._fetch_picuki(handle)]

    async def _fetch_apify(self, handle: str, token: str) -> SourceResult:
        """Call the Apify instagram-scraper actor synchronously and shape its output."""
        endpoint = _APIFY_ENDPOINT_TMPL.format(actor=APIFY_INSTAGRAM_ACTOR, token=token)
        payload = {
            "directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "posts",
            "resultsLimit": INSTAGRAM_POSTS_LIMIT,
            "addParentData": False,
        }
        async with httpx.AsyncClient(
            timeout=APIFY_SYNC_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            items = resp.json()

        if not isinstance(items, list):
            return SourceResult(
                source_name=f"{self.name}:apify",
                text="",
                links=[],
                error=f"apify returned non-list: {type(items).__name__}",
            )

        return self._result_from_posts(items, backend="apify")

    async def _fetch_picuki(self, handle: str) -> SourceResult:
        """Best-effort scrape of picuki.com (public mirror, no login)."""
        url = f"https://www.picuki.com/profile/{handle}"
        try:
            resp = await get_with_retry(url)
            resp.raise_for_status()
        except Exception as exc:
            return SourceResult(
                source_name=f"{self.name}:picuki",
                text="",
                links=[],
                error=f"picuki fetch failed: {exc}",
            )

        tree = HTMLParser(resp.text)
        # picuki renders each post with a caption in `.photo-description`;
        # newer layouts sometimes use `.post-description`. Try both.
        caption_nodes = tree.css(".photo-description") or tree.css(".post-description")
        if not caption_nodes:
            msg = "picuki: no caption elements matched — mirror markup may have changed"
            logger.warning("instagram: %s", msg)
            return SourceResult(
                source_name=f"{self.name}:picuki",
                text="",
                links=[],
                error=msg,
            )

        captions = [n.text(separator=" ", strip=True) for n in caption_nodes[:INSTAGRAM_POSTS_LIMIT]]
        joined = " ".join(c for c in captions if c).lower()
        links = _extract_urls(joined)
        return SourceResult(source_name=f"{self.name}:picuki", text=joined, links=links)

    def _result_from_posts(self, items: list[dict[str, Any]], *, backend: str) -> SourceResult:
        """Turn a list of post dicts into a SourceResult, filtering out old posts.

        We keep only posts within `INSTAGRAM_POST_MAX_AGE_DAYS` so that
        captions from past editions of the festival don't keep scoring.
        """
        cutoff = datetime.now(UTC) - timedelta(days=INSTAGRAM_POST_MAX_AGE_DAYS)
        captions: list[str] = []
        all_links: list[str] = []
        kept = 0

        for item in items:
            ts_raw = item.get("timestamp") or item.get("takenAtTimestamp")
            if ts_raw:
                try:
                    if isinstance(ts_raw, (int, float)):
                        ts = datetime.fromtimestamp(float(ts_raw), tz=UTC)
                    else:
                        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass  # keep post if timestamp is unreadable

            caption = str(item.get("caption") or "").strip()
            hashtags = item.get("hashtags") or []
            post_url = item.get("url")

            parts = [caption]
            if isinstance(hashtags, list) and hashtags:
                parts.append(" ".join(f"#{h}" for h in hashtags if isinstance(h, str)))
            fragment = " ".join(p for p in parts if p)
            if fragment:
                captions.append(fragment)
                kept += 1

            all_links.extend(_extract_urls(caption))
            if isinstance(post_url, str) and post_url:
                all_links.append(post_url)

        text = " ".join(captions).lower()
        logger.info(
            "instagram:%s kept %d of %d posts within %d days",
            backend,
            kept,
            len(items),
            INSTAGRAM_POST_MAX_AGE_DAYS,
        )
        return SourceResult(source_name=f"{self.name}:{backend}", text=text, links=all_links)
