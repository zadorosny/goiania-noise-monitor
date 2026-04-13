"""Tests for the Instagram source (Apify primary, picuki fallback)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from src.sources import _http
from src.sources.instagram import InstagramSource


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _noop(_):
        return None

    monkeypatch.setattr(_http.asyncio, "sleep", _noop)


def _recent(days_ago: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


@pytest.mark.asyncio
@respx.mock
async def test_apify_happy_path_returns_captions(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "fake-token")
    posts = [
        {
            "caption": "COMPRE SEU INGRESSO do Goiânia Noise 2026! 1º lote",
            "timestamp": _recent(1),
            "url": "https://www.instagram.com/p/AAA/",
            "hashtags": ["goianianoise", "ingressos"],
        },
        {
            "caption": "Save the date",
            "timestamp": _recent(3),
            "url": "https://www.instagram.com/p/BBB/",
        },
    ]
    respx.post("https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(200, json=posts)
    )

    results = await InstagramSource().fetch()
    assert len(results) == 1
    r = results[0]
    assert r.source_name == "instagram:apify"
    assert "compre seu ingresso" in r.text
    assert "1º lote" in r.text
    assert "https://www.instagram.com/p/AAA/" in r.links
    assert r.error is None


@pytest.mark.asyncio
@respx.mock
async def test_apify_filters_old_posts(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "fake-token")
    posts = [
        {"caption": "ancient post", "timestamp": _recent(90), "url": "x"},
        {"caption": "fresh post", "timestamp": _recent(2), "url": "y"},
    ]
    respx.post("https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(200, json=posts)
    )

    results = await InstagramSource().fetch()
    assert "fresh post" in results[0].text
    assert "ancient post" not in results[0].text


@pytest.mark.asyncio
@respx.mock
async def test_apify_failure_falls_back_to_picuki(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "fake-token")
    respx.post("https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(500)
    )
    picuki_html = """
    <html><body>
      <div class="photo">
        <div class="photo-description">COMPRE SEU INGRESSO GOIÂNIA NOISE 2026</div>
      </div>
    </body></html>
    """
    respx.get("https://www.picuki.com/profile/goianianoisefestival").mock(
        return_value=httpx.Response(200, text=picuki_html)
    )

    results = await InstagramSource().fetch()
    assert results[0].source_name == "instagram:picuki"
    assert "compre seu ingresso" in results[0].text


@pytest.mark.asyncio
@respx.mock
async def test_no_token_goes_straight_to_picuki(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    html = '<div class="photo-description">ingressos à venda Goiânia Noise 2026</div>'
    respx.get("https://www.picuki.com/profile/goianianoisefestival").mock(
        return_value=httpx.Response(200, text=html)
    )
    results = await InstagramSource().fetch()
    assert results[0].source_name == "instagram:picuki"
    assert "ingressos à venda" in results[0].text


@pytest.mark.asyncio
@respx.mock
async def test_picuki_no_caption_selectors_emits_error(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    respx.get("https://www.picuki.com/profile/goianianoisefestival").mock(
        return_value=httpx.Response(200, text="<html><body><div>nothing matching</div></body></html>")
    )
    results = await InstagramSource().fetch()
    assert results[0].error is not None
    assert "markup" in results[0].error.lower()


@pytest.mark.asyncio
async def test_empty_handle_returns_error(monkeypatch):
    monkeypatch.setattr("src.sources.instagram.INSTAGRAM_HANDLE", "")
    results = await InstagramSource().fetch()
    assert results[0].error == "INSTAGRAM_HANDLE not configured"
