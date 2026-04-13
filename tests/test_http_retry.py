"""Tests for the httpx retry wrapper."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.sources import _http


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _noop(_):
        return None

    monkeypatch.setattr(_http.asyncio, "sleep", _noop)


@pytest.mark.asyncio
@respx.mock
async def test_retry_returns_first_success():
    respx.get("https://x/").mock(return_value=httpx.Response(200, text="ok"))
    resp = await _http.get_with_retry("https://x/")
    assert resp.status_code == 200
    assert resp.text == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_retry_recovers_from_5xx():
    route = respx.get("https://x/").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, text="hello"),
        ]
    )
    resp = await _http.get_with_retry("https://x/", attempts=3)
    assert resp.status_code == 200
    assert resp.text == "hello"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_retry_recovers_from_request_error():
    route = respx.get("https://x/").mock(
        side_effect=[
            httpx.ConnectError("nope"),
            httpx.Response(200, text="ok"),
        ]
    )
    resp = await _http.get_with_retry("https://x/", attempts=3)
    assert resp.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_retry_gives_up_on_persistent_error():
    respx.get("https://x/").mock(side_effect=httpx.ConnectError("nope"))
    with pytest.raises(httpx.ConnectError):
        await _http.get_with_retry("https://x/", attempts=3)


@pytest.mark.asyncio
@respx.mock
async def test_retry_does_not_retry_4xx():
    route = respx.get("https://x/").mock(return_value=httpx.Response(404))
    resp = await _http.get_with_retry("https://x/", attempts=3)
    assert resp.status_code == 404
    assert route.call_count == 1
