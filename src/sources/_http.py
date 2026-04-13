"""Shared httpx helpers: GET with exponential-backoff retry.

Wraps a single request with retries on transient failures (5xx + any
httpx.RequestError). Non-retryable 4xx responses are returned to the caller
unchanged — they usually mean "site says no" and retrying won't fix it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ..config import HTTPX_RETRY_ATTEMPTS, HTTPX_RETRY_BASE_DELAY, HTTPX_TIMEOUT_SECONDS, USER_AGENT

logger = logging.getLogger(__name__)


async def get_with_retry(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = HTTPX_TIMEOUT_SECONDS,
    attempts: int = HTTPX_RETRY_ATTEMPTS,
    base_delay: float = HTTPX_RETRY_BASE_DELAY,
    **client_kwargs: Any,
) -> httpx.Response:
    """GET `url` with up to `attempts` retries on 5xx / RequestError.

    Backoff is `base_delay * attempt**2` (1, 4, 9s by default for
    base_delay=1). The default User-Agent is set if the caller didn't
    override it. Raises the last exception if every attempt fails.
    """
    merged_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last_exc: Exception | None = None

    async with httpx.AsyncClient(
        headers=merged_headers,
        timeout=timeout,
        follow_redirects=True,
        **client_kwargs,
    ) as client:
        for attempt in range(1, attempts + 1):
            try:
                resp = await client.get(url)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == attempts:
                    logger.warning("http GET %s failed after %d attempts: %s", url, attempts, exc)
                    raise
                delay = base_delay * attempt * attempt
                logger.info(
                    "http GET %s transient error %s — retry %d/%d in %.1fs",
                    url,
                    type(exc).__name__,
                    attempt,
                    attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if 500 <= resp.status_code < 600 and attempt < attempts:
                delay = base_delay * attempt * attempt
                logger.info(
                    "http GET %s got %d — retry %d/%d in %.1fs",
                    url,
                    resp.status_code,
                    attempt,
                    attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            return resp

    # Should be unreachable: the final iteration either returned or raised.
    assert last_exc is not None
    raise last_exc
