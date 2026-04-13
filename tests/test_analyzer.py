"""Tests for the scoring analyzer."""

from __future__ import annotations

from src.analyzer import (
    _find_ticket_links,
    _is_static_asset,
    _is_ticketing_nav_page,
    analyze,
)
from src.sources.base import SourceResult


def _make(text: str = "", links: list[str] | None = None) -> SourceResult:
    return SourceResult(source_name="test", text=text.lower(), links=links or [])


# ---------- nav filter ----------


def test_nav_listing_root_is_nav():
    assert _is_ticketing_nav_page("https://www.sympla.com.br/eventos")
    assert _is_ticketing_nav_page("https://www.sympla.com.br/eventos/")
    assert _is_ticketing_nav_page("https://www.sympla.com.br/")
    assert _is_ticketing_nav_page("https://www.sympla.com.br")


def test_nav_listing_with_slug_is_event_page():
    # The bug being fixed: /eventos/slug is a real event, not nav.
    assert not _is_ticketing_nav_page("https://www.sympla.com.br/eventos/goiania-noise-festival-2026")
    assert not _is_ticketing_nav_page("https://www.bilheteriadigital.com/eventos/goiania-noise-2026")


def test_nav_search_paths_always_nav():
    assert _is_ticketing_nav_page("https://www.sympla.com.br/busca/goiania")
    assert _is_ticketing_nav_page("https://www.sympla.com.br/pesquisa?q=noise")
    assert _is_ticketing_nav_page("https://www.sympla.com.br/search/anything/here")


def test_nav_static_pages():
    assert _is_ticketing_nav_page("https://www.sympla.com.br/ajuda")
    assert _is_ticketing_nav_page("https://www.sympla.com.br/login")
    assert _is_ticketing_nav_page("https://www.sympla.com.br/termos")


def test_nav_eventos_with_query_and_no_slug():
    assert _is_ticketing_nav_page("https://www.sympla.com.br/eventos?s=foo")


# ---------- static asset filter ----------


def test_static_asset_extensions():
    assert _is_static_asset("https://cdn.example.com/app.js")
    assert _is_static_asset("https://cdn.example.com/logo.png")
    assert _is_static_asset("https://cdn.example.com/style.css?v=123")
    assert _is_static_asset("https://cdn.example.com/font.woff2")


def test_static_asset_paths():
    assert _is_static_asset("https://example.com/_next/static/chunk.js")
    assert _is_static_asset("https://example.com/assets/main.bundle")


def test_non_asset_urls_pass():
    assert not _is_static_asset("https://www.sympla.com.br/eventos/my-event")


# ---------- _find_ticket_links ----------


def test_find_ticket_links_dedups_and_caps_per_domain():
    links = [
        "https://www.sympla.com.br/evento/a",
        "https://www.sympla.com.br/evento/b",
        "https://www.sympla.com.br/evento/c",  # 3rd sympla — should be dropped (cap=2)
        "https://www.bilheteriadigital.com/eventos/x",
        "https://unrelated.com/page",  # not a ticketing domain
        "https://www.sympla.com.br/eventos",  # nav, drop
        "https://www.sympla.com.br/evento/a",  # dup
    ]
    display, distinct = _find_ticket_links(links)
    assert distinct == 2  # sympla + bilheteria
    # sympla capped at 2 URLs, bilheteria has 1
    assert len(display) == 3
    assert "https://www.sympla.com.br/evento/c" not in display
    assert "https://unrelated.com/page" not in display


def test_find_ticket_links_drops_static_assets():
    links = [
        "https://www.sympla.com.br/static/app.js",
        "https://www.sympla.com.br/evento/real",
    ]
    display, distinct = _find_ticket_links(links)
    assert distinct == 1
    assert display == ["https://www.sympla.com.br/evento/real"]


def test_find_ticket_links_empty_when_only_nav():
    links = [
        "https://www.sympla.com.br/eventos",
        "https://www.bilheteriadigital.com/busca/foo",
    ]
    display, distinct = _find_ticket_links(links)
    assert distinct == 0
    assert display == []


# ---------- analyze() ----------


def test_analyze_no_text_no_links_is_none():
    det = analyze(_make())
    assert det.score == 0
    assert det.confidence == "nenhuma"
    assert det.sold_out is False


def test_analyze_only_support_terms_does_not_score():
    # Support terms alone (without a high-confidence term) must not score.
    det = analyze(_make("tickets e valor disponível em breve"))
    assert det.score == 0


def test_analyze_high_confidence_term_scores():
    det = analyze(_make("compre seu ingresso do goiânia noise 2026"))
    assert det.score >= 15
    assert det.confidence in {"baixa", "média", "alta"}


def test_analyze_high_plus_support_plus_link_reaches_high():
    text = (
        "compre seu ingresso do goiânia noise 2026, 1º lote já disponível. "
        "ingressos à venda pelo ponto de venda oficial. ingresso inteira e meia-entrada."
    )
    links = ["https://www.sympla.com.br/evento/goiania-noise-2026"]
    det = analyze(_make(text, links))
    assert det.confidence == "alta"
    assert det.score >= 50
    assert det.ticket_links == ["https://www.sympla.com.br/evento/goiania-noise-2026"]


def test_analyze_sold_out_applies_penalty():
    text = "comprar ingresso goiânia noise — vendas encerradas. esgotado sold out. 1º lote esgotado."
    det = analyze(_make(text))
    assert det.sold_out is True
    # Some score may remain from high-confidence terms; penalty should pull it down.
    assert det.score < 25


def test_analyze_stray_esgotado_without_high_term_does_not_mark_sold_out():
    det = analyze(_make("esgotado vendas encerradas lotado"))
    assert det.sold_out is False


def test_analyze_two_ticket_domains_score_cap():
    text = "comprar ingresso goiânia noise 1º lote"
    links = [
        "https://www.sympla.com.br/evento/a",
        "https://www.bilheteriadigital.com/eventos/b",
        "https://www.eventim.com.br/event/c",  # 3rd distinct domain — scoring caps at 2
    ]
    det = analyze(_make(text, links))
    # Score should include 2 domains x TICKET_LINK_SCORE, not 3.
    # Just assert it's clamped at 100 and confidence is alta.
    assert det.score <= 100
    assert det.confidence == "alta"
    assert len(det.ticket_links) == 3  # display keeps all 3 (under total cap)
