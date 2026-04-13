"""Persist and load monitor state from state.json."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import Detection

STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"

_DEFAULT_STATE: dict[str, Any] = {
    "last_check": None,
    "last_alert_fingerprint": None,
    "last_heartbeat": None,
    "empty_cycles_since_alert": 0,
}


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    """Load state from disk, returning defaults if missing/corrupt."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULT_STATE)

    # Ensure all keys exist, backfill defaults for any added schema fields.
    for key, default in _DEFAULT_STATE.items():
        data.setdefault(key, default)
    return data


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    """Write state to disk."""
    state["last_check"] = datetime.now(UTC).isoformat()
    # Drop legacy fields so state.json doesn't accumulate dead keys.
    for legacy in ("page_hash_wix_home", "page_hash_linktree"):
        state.pop(legacy, None)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compute_fingerprint(detections: list[Detection]) -> str:
    """Deterministic fingerprint of all detections with score > 0.

    SHA-256 of sorted (source, confidence, sold_out, sorted(ticket_links)),
    truncated to 32 hex chars for stable short form.
    """
    active = [d for d in detections if d.score > 0]
    if not active:
        return ""

    parts: list[str] = []
    for d in sorted(active, key=lambda x: x.source):
        links = ",".join(sorted(d.ticket_links))
        parts.append(f"{d.source}|{d.confidence}|{d.sold_out}|{links}")

    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def should_heartbeat(state: dict[str, Any], heartbeat_hours: list[int]) -> bool:
    """Return True if current BRT hour is a heartbeat hour and one hasn't been sent this hour."""
    brt = timezone(timedelta(hours=-3))
    now_brt = datetime.now(brt)

    if now_brt.hour not in heartbeat_hours:
        return False

    raw = state.get("last_heartbeat")
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(raw).astimezone(brt)
        return not (last.date() == now_brt.date() and last.hour == now_brt.hour)
    except (ValueError, TypeError):
        return True
