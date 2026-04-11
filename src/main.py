"""Entrypoint: run one check cycle across all sources."""

from __future__ import annotations

import asyncio
import logging
import sys

from .analyzer import analyze
from .config import HEARTBEAT_HOURS_BRT
from .models import CheckResult
from .sources.base import Source
from .sources.bilheteria import BilheteriaSource
from .sources.google_search import GoogleSearchSource
from .sources.sympla import SymplaSource
from .sources.wix_site import WixSiteSource
from .state import compute_fingerprint, load_state, save_state, should_heartbeat
from .telegram_client import send_alert, send_heartbeat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _build_sources() -> list[Source]:
    return [
        WixSiteSource(),
        BilheteriaSource(),
        SymplaSource(),
        GoogleSearchSource(),
    ]


async def run_cycle() -> None:
    state = load_state()
    sources = _build_sources()
    errors: list[str] = []

    logger.info("Starting check cycle with %d sources", len(sources))

    # Fetch all sources concurrently
    fetch_tasks = [source.safe_fetch() for source in sources]
    fetch_results = await asyncio.gather(*fetch_tasks)

    # Flatten results and track errors
    all_source_results = []
    for source, results in zip(sources, fetch_results):
        if not results:
            errors.append(f"{source.name}: no results (fetch failed or empty)")
        all_source_results.extend(results)

    logger.info("Fetched %d source results (%d errors)", len(all_source_results), len(errors))

    # Analyze each source result
    detections = [analyze(result) for result in all_source_results]

    # Compute fingerprint
    fingerprint = compute_fingerprint(detections)

    check = CheckResult(
        detections=detections,
        fingerprint=fingerprint,
        errors=errors,
    )

    # Log summary
    for det in check.detections:
        if det.score > 0:
            logger.info(
                "Detection: %s — score=%d confidence=%s sold_out=%s",
                det.source, det.score, det.confidence, det.sold_out,
            )
    logger.info(
        "Cycle result: max_score=%d best_confidence=%s fingerprint=%s",
        check.max_score, check.best_confidence, fingerprint or "(empty)",
    )

    # Send alert if findings exist and fingerprint changed
    if check.has_findings and fingerprint != state.get("last_alert_fingerprint"):
        logger.info("New findings detected — sending alert")
        await send_alert(check)
        state["last_alert_fingerprint"] = fingerprint

    # Send heartbeat if enough time elapsed
    if should_heartbeat(state, HEARTBEAT_HOURS_BRT):
        logger.info("Sending heartbeat")
        await send_heartbeat()
        from datetime import datetime, timezone
        state["last_heartbeat"] = datetime.now(timezone.utc).isoformat()

    save_state(state)
    logger.info("State saved. Cycle complete.")


def main() -> None:
    try:
        asyncio.run(run_cycle())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception:
        logger.exception("Unhandled error in check cycle")
        sys.exit(1)


if __name__ == "__main__":
    main()
