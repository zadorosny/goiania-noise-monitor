"""Abstract base class for all ticket sources."""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """Raw data extracted from a source.

    `error` is set when the source fetched OK but produced no usable content
    (e.g. card selectors matched nothing — markup likely changed). It is
    collected into CheckResult.errors without breaking the cycle.
    """

    source_name: str
    text: str  # visible text, lowered
    links: list[str]  # all hrefs found
    error: str | None = None


class Source(abc.ABC):
    """Abstract source that can be checked for ticket availability."""

    name: str = "base"

    @abc.abstractmethod
    async def fetch(self) -> list[SourceResult]:
        """Fetch and return extracted data from this source.

        Returns a list because some sources check multiple URLs.
        """
        ...

    async def safe_fetch(self) -> list[SourceResult]:
        """Fetch with error handling — never raises."""
        try:
            return await self.fetch()
        except Exception as exc:
            logger.error("Source %s failed: %s", self.name, exc, exc_info=True)
            return []
