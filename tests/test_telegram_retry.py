"""Test Telegram send retry behavior by monkeypatching Bot."""

from __future__ import annotations

import pytest
from telegram.error import NetworkError

from src import telegram_client


class _FakeBot:
    def __init__(self, token: str):
        self.token = token
        self.calls = 0
        # Mutable class attribute — set per-test via _FakeBot.fail_times
        self._fail_remaining = _FakeBot.fail_times

    async def send_message(self, **_: object) -> None:
        self.calls += 1
        _FakeBot.total_calls += 1
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise NetworkError("simulated")
        return None


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    async def _no_sleep(_):
        return None

    monkeypatch.setattr(telegram_client.asyncio, "sleep", _no_sleep)


@pytest.fixture(autouse=True)
def _patch_bot(monkeypatch):
    # Patch the import inside _send_message's local scope by patching `telegram.Bot`.
    import telegram

    _FakeBot.fail_times = 0
    _FakeBot.total_calls = 0
    monkeypatch.setattr(telegram, "Bot", _FakeBot)
    yield


async def test_send_succeeds_first_try(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    _FakeBot.fail_times = 0
    await telegram_client._send_message("t", "c", "hello")
    assert _FakeBot.total_calls == 1


async def test_send_retries_on_network_error(monkeypatch):
    _FakeBot.fail_times = 2
    await telegram_client._send_message("t", "c", "hello")
    assert _FakeBot.total_calls == 3  # 2 failures + 1 success


async def test_send_gives_up_after_max_attempts(monkeypatch):
    _FakeBot.fail_times = 999  # always fail
    # Should NOT raise — _send_message logs and returns.
    await telegram_client._send_message("t", "c", "hello")
    assert _FakeBot.total_calls == telegram_client.TELEGRAM_RETRY_ATTEMPTS
