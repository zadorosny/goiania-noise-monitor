"""Append-only JSONL log of every check cycle.

One line per run_cycle — captures the post-analysis summary so you can
inspect history without scrolling through every GitHub Actions log.
Rotated in-place: keeps only the last `CHECK_LOG_MAX_LINES` entries so
the file doesn't grow unbounded.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CHECK_LOG_MAX_LINES, CHECK_LOG_PATH_NAME
from .models import CheckResult

logger = logging.getLogger(__name__)

CHECK_LOG_PATH = Path(__file__).resolve().parent.parent / CHECK_LOG_PATH_NAME


def append_entry(result: CheckResult, path: Path = CHECK_LOG_PATH) -> None:
    """Append one line summarizing `result` and trim the log to the tail."""
    entry: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "max_score": result.max_score,
        "best_confidence": result.best_confidence,
        "fingerprint": result.fingerprint or "",
        "errors": result.errors,
        "source_scores": [
            {
                "source": d.source,
                "score": d.score,
                "confidence": d.confidence,
                "sold_out": d.sold_out,
            }
            for d in result.detections
        ],
    }

    line = json.dumps(entry, ensure_ascii=False)

    try:
        existing: list[str] = []
        if path.exists():
            existing = path.read_text(encoding="utf-8").splitlines()
        existing.append(line)
        if len(existing) > CHECK_LOG_MAX_LINES:
            existing = existing[-CHECK_LOG_MAX_LINES:]
        path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    except OSError as exc:
        # Observability must never break the cycle — log and move on.
        logger.warning("check_log: failed to write %s: %s", path, exc)
