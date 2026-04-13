"""Entrypoint: run one check cycle across all sources."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime

from .analyzer import analyze
from .check_log import append_entry as append_check_log
from .config import EMPTY_CYCLES_RESET_THRESHOLD, HEARTBEAT_HOURS_BRT
from .models import CheckResult
from .sources.base import Source
from .sources.bilheteria import BilheteriaSource
from .sources.google_search import GoogleSearchSource
from .sources.instagram import InstagramSource
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
        InstagramSource(),
    ]


async def run_cycle() -> None:
    state = load_state()
    sources = _build_sources()
    errors: list[str] = []

    logger.info("Starting check cycle with %d sources", len(sources))

    fetch_tasks = [source.safe_fetch() for source in sources]
    fetch_results = await asyncio.gather(*fetch_tasks)

    all_source_results = []
    for source, results in zip(sources, fetch_results, strict=True):
        if not results:
            errors.append(f"{source.name}: no results (fetch failed or empty)")
        for r in results:
            if r.error:
                errors.append(f"{r.source_name}: {r.error}")
        all_source_results.extend(results)

    logger.info("Fetched %d source results (%d errors)", len(all_source_results), len(errors))

    detections = [analyze(result) for result in all_source_results]
    fingerprint = compute_fingerprint(detections)

    check = CheckResult(
        detections=detections,
        fingerprint=fingerprint,
        errors=errors,
    )

    for det in check.detections:
        if det.score > 0:
            logger.info(
                "Detection: %s — score=%d confidence=%s sold_out=%s",
                det.source,
                det.score,
                det.confidence,
                det.sold_out,
            )

    prev_fingerprint = state.get("last_alert_fingerprint")
    prev_empty_cycles = state.get("empty_cycles_since_alert", 0)

    logger.info(
        "Cycle result: max_score=%d best_confidence=%s fingerprint=%s prev_fingerprint=%s empty_cycles=%d",
        check.max_score,
        check.best_confidence,
        fingerprint or "(empty)",
        prev_fingerprint or "(none)",
        prev_empty_cycles,
    )

    # Auto-reset: if we've had enough empty cycles in a row, forget the last
    # alert fingerprint so a re-opening of tickets re-alerts instead of being
    # suppressed by a stale fingerprint.
    if check.has_findings:
        state["empty_cycles_since_alert"] = 0
    else:
        state["empty_cycles_since_alert"] = prev_empty_cycles + 1
        if prev_fingerprint is not None and state["empty_cycles_since_alert"] >= EMPTY_CYCLES_RESET_THRESHOLD:
            logger.info(
                "Resetting last_alert_fingerprint after %d empty cycles",
                state["empty_cycles_since_alert"],
            )
            state["last_alert_fingerprint"] = None

    if check.has_findings and fingerprint != state.get("last_alert_fingerprint"):
        logger.info("New findings detected — sending alert")
        await send_alert(check)
        state["last_alert_fingerprint"] = fingerprint

    if should_heartbeat(state, HEARTBEAT_HOURS_BRT):
        logger.info("Sending heartbeat")
        await send_heartbeat()
        state["last_heartbeat"] = datetime.now(UTC).isoformat()

    save_state(state)
    append_check_log(check)
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
