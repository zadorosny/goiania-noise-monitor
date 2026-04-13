"""Tests for state persistence, fingerprinting, and heartbeat logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.models import Detection
from src.state import (
    _DEFAULT_STATE,
    compute_fingerprint,
    load_state,
    save_state,
    should_heartbeat,
)


def _det(source: str, score: int = 50, confidence: str = "alta", links: list[str] | None = None) -> Detection:
    return Detection(
        source=source,
        score=score,
        confidence=confidence,
        sold_out=False,
        evidence=[],
        ticket_links=links or [],
    )


# ---------- fingerprint ----------


def test_fingerprint_empty_when_no_active_detections():
    assert compute_fingerprint([]) == ""
    assert compute_fingerprint([_det("s", score=0, confidence="nenhuma")]) == ""


def test_fingerprint_stable_across_order():
    a = _det("sympla", links=["https://x", "https://y"])
    b = _det("wix")
    fp1 = compute_fingerprint([a, b])
    fp2 = compute_fingerprint([b, a])
    assert fp1 == fp2 != ""


def test_fingerprint_changes_on_confidence_change():
    fp1 = compute_fingerprint([_det("wix", confidence="alta")])
    fp2 = compute_fingerprint([_det("wix", confidence="média")])
    assert fp1 != fp2


def test_fingerprint_changes_on_link_set():
    fp1 = compute_fingerprint([_det("wix", links=["https://a"])])
    fp2 = compute_fingerprint([_det("wix", links=["https://b"])])
    assert fp1 != fp2


# ---------- state load/save ----------


def test_load_state_missing_file_returns_defaults(tmp_path: Path):
    path = tmp_path / "missing.json"
    state = load_state(path)
    assert state == _DEFAULT_STATE
    # load_state returns a copy — mutation shouldn't leak to defaults.
    state["last_check"] = "x"
    assert _DEFAULT_STATE["last_check"] is None


def test_load_state_corrupt_file_returns_defaults(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("not json {")
    assert load_state(path) == _DEFAULT_STATE


def test_load_state_backfills_new_keys(tmp_path: Path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"last_check": "2026-01-01T00:00:00+00:00"}))
    state = load_state(path)
    assert "empty_cycles_since_alert" in state
    assert state["empty_cycles_since_alert"] == 0


def test_save_state_drops_legacy_keys(tmp_path: Path):
    path = tmp_path / "state.json"
    state = dict(_DEFAULT_STATE)
    state["page_hash_wix_home"] = "legacy"
    state["page_hash_linktree"] = "legacy"
    save_state(state, path)
    persisted = json.loads(path.read_text())
    assert "page_hash_wix_home" not in persisted
    assert "page_hash_linktree" not in persisted
    assert "last_check" in persisted


# ---------- heartbeat ----------


def _brt(hour: int) -> datetime:
    return datetime.now(timezone(timedelta(hours=-3))).replace(hour=hour, minute=0, second=0, microsecond=0)


def test_heartbeat_skipped_outside_hours():
    # Use an hour unlikely to be configured
    state = {"last_heartbeat": None}
    assert should_heartbeat(state, heartbeat_hours=[25]) is False  # impossible hour


def test_heartbeat_fires_when_never_sent():
    brt_now = datetime.now(timezone(timedelta(hours=-3)))
    state = {"last_heartbeat": None}
    assert should_heartbeat(state, heartbeat_hours=[brt_now.hour]) is True


def test_heartbeat_skipped_when_already_sent_this_hour():
    brt_now = datetime.now(timezone(timedelta(hours=-3)))
    state = {"last_heartbeat": brt_now.isoformat()}
    assert should_heartbeat(state, heartbeat_hours=[brt_now.hour]) is False


def test_heartbeat_corrupt_timestamp_falls_through():
    brt_now = datetime.now(timezone(timedelta(hours=-3)))
    state = {"last_heartbeat": "not-a-date"}
    assert should_heartbeat(state, heartbeat_hours=[brt_now.hour]) is True
