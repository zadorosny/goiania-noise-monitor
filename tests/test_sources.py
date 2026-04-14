"""Tests for HTML source parsers using respx-mocked httpx responses."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from src.analyzer import analyze
from src.config import (
    BILHETERIA_SEARCH_URL,
    DUCKDUCKGO_URL,
    SYMPLA_SEARCH_URL,
)
from src.sources import _http
from src.sources.bilheteria import BilheteriaSource
from src.sources.google_search import GoogleSearchSource
from src.sources.sympla import SymplaSource

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _fast_http_retry(monkeypatch):
    """Skip exponential backoff sleeps inside the retry wrapper."""

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(_http.asyncio, "sleep", _no_sleep)


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.asyncio
@respx.mock
async def test_sympla_parses_cards_and_scores_high():
    respx.get(SYMPLA_SEARCH_URL).mock(return_value=httpx.Response(200, text=_load("sympla_with_event.html")))
    source = SymplaSource()
    results = await source.fetch()
    assert len(results) == 1
    result = results[0]
    assert "goiânia noise" in result.text
    det = analyze(result)
    assert det.score > 0


@pytest.mark.asyncio
@respx.mock
async def test_sympla_returns_empty_text_when_no_noise_in_cards():
    respx.get(SYMPLA_SEARCH_URL).mock(return_value=httpx.Response(200, text=_load("sympla_no_event.html")))
    source = SymplaSource()
    results = await source.fetch()
    assert results[0].text == ""
    det = analyze(results[0])
    assert det.score == 0


@pytest.mark.asyncio
@respx.mock
async def test_bilheteria_parses_cards():
    respx.get(BILHETERIA_SEARCH_URL).mock(
        return_value=httpx.Response(200, text=_load("bilheteria_with_event.html"))
    )
    source = BilheteriaSource()
    results = await source.fetch()
    assert len(results) == 1
    assert "goiânia noise" in results[0].text
    det = analyze(results[0])
    assert det.score > 0


@pytest.mark.asyncio
@respx.mock
async def test_duckduckgo_extracts_links_and_snippets():
    respx.get(DUCKDUCKGO_URL).mock(return_value=httpx.Response(200, text=_load("duckduckgo_results.html")))
    source = GoogleSearchSource()
    results = await source.fetch()
    assert len(results) == 1
    result = results[0]
    assert any("sympla.com.br" in link for link in result.links)
    assert any("bilheteriadigital.com" in link for link in result.links)
    assert "goiânia noise" in result.text or "compre" in result.text
    det = analyze(result)
    # Should hit high confidence thanks to snippets + ticketing links
    assert det.score >= 40


@pytest.mark.asyncio
@respx.mock
async def test_source_safe_fetch_swallows_errors():
    respx.get(SYMPLA_SEARCH_URL).mock(side_effect=httpx.ConnectError("boom"))
    source = SymplaSource()
    results = await source.safe_fetch()
    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_sympla_emits_error_when_payload_missing():
    # No `searchEventsResult` payload anywhere — parser should surface an
    # error so we can distinguish "markup broke" from "search returned zero
    # Goiânia Noise events" (which is a legitimate empty result).
    empty_html = "<html><body><div>just a plain page</div></body></html>"
    respx.get(SYMPLA_SEARCH_URL).mock(return_value=httpx.Response(200, text=empty_html))
    results = await SymplaSource().fetch()
    assert results[0].text == ""
    assert results[0].error is not None
    assert "markup" in results[0].error.lower()


@pytest.mark.asyncio
@respx.mock
async def test_bilheteria_emits_error_when_selectors_match_nothing():
    empty_html = "<html><body><header>Bilheteria</header></body></html>"
    respx.get(BILHETERIA_SEARCH_URL).mock(return_value=httpx.Response(200, text=empty_html))
    results = await BilheteriaSource().fetch()
    assert results[0].error is not None
    assert "markup" in results[0].error.lower()
