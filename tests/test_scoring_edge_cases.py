"""Red-team regression tests for analyze().

Each case here is a probe that previously exposed a false positive or a false
negative in the scoring rules. Keeping them as named tests means a future
refactor of `analyze()` has to justify why any of these flipped.

Source name matters: `wix_site` and `instagram:*` are domain-trusted, so the
target-event guard does not apply. Everything else must contain the festival
name to score.
"""

from __future__ import annotations

from src.analyzer import analyze
from src.sources.base import SourceResult


def _make(source: str, text: str, links: list[str] | None = None) -> SourceResult:
    return SourceResult(source_name=source, text=text.lower(), links=links or [])


# ---------------------------------------------------------------------------
# False positives — these must NOT alert (score 0, no sold_out).
# ---------------------------------------------------------------------------


def test_fp_news_article_about_past_edition():
    """News post retrospecting 2023 sale — must not re-alert on past-tense copy."""
    text = (
        "Em 2023, o primeiro lote do festival foi vendido em duas horas. "
        "Na época, a pré-venda virou assunto e a venda atingiu o lote promocional "
        "rapidamente, com inteira e meia entrada esgotadas no mesmo dia."
    )
    det = analyze(_make("google_search", text))
    assert det.score == 0
    assert det.confidence == "nenhuma"


def test_fp_cookie_banner_with_compre_agora():
    """E-commerce cookie/CTA boilerplate unrelated to the festival."""
    text = (
        "Este site utiliza cookies para melhorar sua experiência. Compre agora "
        "e receba frete grátis. Ingressos para cinema a partir de R$ 20."
    )
    det = analyze(_make("google_search", text))
    assert det.score == 0


def test_fp_ddg_snippet_past_festival():
    """DuckDuckGo snippet about a past festival edition with old sold-out terms."""
    text = (
        "Festival de rock — edição 2022 teve ingressos esgotados e vendas encerradas "
        "em poucos dias. Próxima edição a confirmar."
    )
    det = analyze(_make("google_search", text))
    assert det.score == 0
    assert det.sold_out is False


def test_fp_different_festival_similar_name():
    """A different festival that happens to contain 'noise' in its name."""
    text = (
        "São Paulo Noise 2026 — compre seu ingresso! 1º lote inteira e meia entrada "
        "disponíveis no ponto de venda oficial. Vendas abertas."
    )
    links = ["https://www.sympla.com.br/evento/sao-paulo-noise-2026"]
    det = analyze(_make("sympla", text, links))
    # Untrusted source + no "goiânia noise" → guarded out.
    assert det.score == 0
    assert det.confidence == "nenhuma"


def test_fp_generic_ticketing_boilerplate():
    """Ticketing platform footer/nav copy without any event name."""
    text = (
        "Ingressos à venda em todo o Brasil. Comprar ingresso com meia entrada "
        "e inteira no ponto de venda oficial. Vendas abertas para diversos eventos."
    )
    links = [
        "https://www.sympla.com.br/evento/algum-show",
        "https://www.bilheteriadigital.com/eventos/outro-show",
    ]
    det = analyze(_make("sympla", text, links))
    assert det.score == 0


# ---------------------------------------------------------------------------
# False negatives — these MUST alert.
# ---------------------------------------------------------------------------


def test_fn_garanta_o_seu_ingressos_liberados():
    """Caption-style phrasing that earlier term list missed entirely."""
    text = "garanta o seu! ingressos liberados goiânia noise 2026"
    det = analyze(_make("instagram:apify", text))
    assert det.score > 0
    assert det.confidence in {"baixa", "média", "alta"}


def test_fn_compre_o_seu_variant():
    text = "compre o seu ingresso para o goiânia noise 2026"
    det = analyze(_make("instagram:apify", text))
    assert det.score > 0


def test_fn_ingressos_ja_disponiveis_variant():
    text = "ingressos já disponíveis goiânia noise 2026"
    det = analyze(_make("instagram:apify", text))
    assert det.score > 0


# ---------------------------------------------------------------------------
# Edge cases — behavior we explicitly chose.
# ---------------------------------------------------------------------------


def test_edge_sold_out_flag_set_even_when_score_collapses():
    """sold_out must still be True even if the penalty drags score to 0.

    This documents option 3a: score collapse is accepted, but we retain the
    flag so future code (an alerter, the check_log) can still see that the
    source observed sold-out.
    """
    text = (
        "goiânia noise 2026 — comprar ingresso do primeiro lote. "
        "esgotado, vendas encerradas, sold out, lotado."
    )
    det = analyze(_make("sympla", text))
    assert det.sold_out is True


def test_edge_trusted_source_bypasses_target_event_guard():
    """wix_site and instagram:* don't need the event name in text — they are the event."""
    # Festival's own site talking about its own lots.
    text = "compre seu ingresso 1º lote já disponível. inteira e meia entrada."
    det = analyze(_make("wix_site", text))
    assert det.score > 0

    det_ig = analyze(_make("instagram:apify", text))
    assert det_ig.score > 0


def test_edge_untrusted_source_needs_event_name():
    """Mirror of the trusted-source test — same text on sympla yields 0."""
    text = "compre seu ingresso 1º lote já disponível. inteira e meia entrada."
    det = analyze(_make("sympla", text))
    assert det.score == 0
