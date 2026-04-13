"""Tests for the check_log.jsonl observability writer."""

from __future__ import annotations

import json
from pathlib import Path

from src.check_log import append_entry
from src.models import CheckResult, Detection


def _check(score: int = 30, fingerprint: str = "abc", errors: list[str] | None = None) -> CheckResult:
    return CheckResult(
        detections=[
            Detection(source="wix", score=score, confidence="média", sold_out=False, evidence=[]),
        ],
        fingerprint=fingerprint,
        errors=errors or [],
    )


def test_append_creates_file(tmp_path: Path):
    log = tmp_path / "check_log.jsonl"
    append_entry(_check(), path=log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["max_score"] == 30
    assert data["fingerprint"] == "abc"
    assert data["source_scores"][0]["source"] == "wix"


def test_append_adds_new_line(tmp_path: Path):
    log = tmp_path / "check_log.jsonl"
    append_entry(_check(score=10), path=log)
    append_entry(_check(score=50), path=log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["max_score"] == 10
    assert json.loads(lines[1])["max_score"] == 50


def test_rotation_keeps_tail(tmp_path: Path, monkeypatch):
    # Shrink the cap so the test is fast and the intent obvious.
    monkeypatch.setattr("src.check_log.CHECK_LOG_MAX_LINES", 3)
    log = tmp_path / "check_log.jsonl"
    for i in range(5):
        append_entry(_check(score=i * 10, fingerprint=f"fp{i}"), path=log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["fingerprint"] == "fp2"
    assert json.loads(lines[-1])["fingerprint"] == "fp4"


def test_append_errors_are_preserved(tmp_path: Path):
    log = tmp_path / "check_log.jsonl"
    append_entry(_check(errors=["sympla: markup changed"]), path=log)
    data = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert data["errors"] == ["sympla: markup changed"]
