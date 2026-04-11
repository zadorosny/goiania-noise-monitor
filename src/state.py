"""Persist and load monitor state from state.json."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Detection

STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"

_DEFAULT_STATE: dict[str, Any] = {
    "last_check": None,
    "last_alert_fingerprint": None,
    "last_heartbeat": None,
    "page_hash_wix_home": None,
    "page_hash_linktree": None,
}


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    """Load state from disk, returning defaults if missing/corrupt."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Ensure all keys exist
        for key, default in _DEFAULT_STATE.items():
            data.setdefault(key, default)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULT_STATE)


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    """Write state to disk."""
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compute_fingerprint(detections: list[Detection]) -> str:
    """Deterministic fingerprint of all detections with score > 0.

    MD5 of sorted (source, confidence, sold_out, sorted(ticket_links)).
    """
    active = [d for d in detections if d.score > 0]
    if not active:
        return ""

    parts: list[str] = []
    for d in sorted(active, key=lambda x: x.source):
        links = ",".join(sorted(d.ticket_links))
        parts.append(f"{d.source}|{d.confidence}|{d.sold_out}|{links}")

    payload = "\n".join(parts)
    return hashlib.md5(payload.encode()).hexdigest()


def should_heartbeat(state: dict[str, Any], heartbeat_hours: list[int]) -> bool:
    """Return True if current BRT hour is a heartbeat hour and one hasn't been sent this hour."""
    from datetime import timedelta

    brt = timezone(timedelta(hours=-3))
    now_brt = datetime.now(brt)

    if now_brt.hour not in heartbeat_hours:
        return False

    raw = state.get("last_heartbeat")
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(raw).astimezone(brt)
        # Already sent during this same hour today
        return not (last.date() == now_brt.date() and last.hour == now_brt.hour)
    except (ValueError, TypeError):
        return True
