"""Analyze source results and compute ticket-availability scores."""

from __future__ import annotations

from urllib.parse import urlparse

from .config import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    HIGH_CONFIDENCE_TERMS,
    HIGH_TERM_MAX_CONTRIBUTIONS,
    HIGH_TERM_SCORE,
    MAX_LINKS_PER_DOMAIN,
    MAX_TOTAL_TICKET_LINKS,
    SOLD_OUT_MIN_TERMS,
    SOLD_OUT_PENALTY,
    SOLD_OUT_TERMS,
    SUPPORT_TERM_MAX_CONTRIBUTIONS,
    SUPPORT_TERM_SCORE,
    SUPPORT_TERMS,
    TARGET_EVENT_TERMS,
    TICKET_LINK_MAX_CONTRIBUTIONS,
    TICKET_LINK_SCORE,
    TICKETING_DOMAINS,
    TRUSTED_SOURCE_PREFIXES,
)
from .models import Detection
from .sources.base import SourceResult


def _count_matches(text: str, terms: list[str], max_count: int) -> int:
    """Count how many distinct terms appear in text, capped at max_count."""
    count = 0
    for term in terms:
        if term in text:
            count += 1
            if count >= max_count:
                break
    return count


_STATIC_ASSET_EXTENSIONS = (
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".map",
    ".webp",
    ".avif",
)

_STATIC_PATH_SEGMENTS = ("/_next/", "/static/", "/assets/", "/dist/", "/build/")

# First-path-segment classification for ticketing-platform URLs.
# LISTING: nav only when there is no deeper slug (`/eventos` vs `/eventos/my-event`).
# SEARCH: always nav, regardless of depth.
# STATIC: help/auth/legal pages, always nav.
_LISTING_ROOTS = frozenset({"eventos", "evento", "categorias", "cidades", "cidade", "genero"})
_SEARCH_ROOTS = frozenset({"busca", "buscar", "pesquisa", "pesquisar", "search"})
_STATIC_ROOTS = frozenset(
    {
        "ajuda",
        "faq",
        "sobre",
        "termos",
        "privacidade",
        "contato",
        "login",
        "cadastro",
        "conta",
        "minha-conta",
        "ingressar",
    }
)


def _is_static_asset(url: str) -> bool:
    """Return True if URL looks like a static asset, not a ticket page."""
    lower = url.lower().split("?")[0]
    if any(lower.endswith(ext) for ext in _STATIC_ASSET_EXTENSIONS):
        return True
    return any(seg in lower for seg in _STATIC_PATH_SEGMENTS)


def _is_ticketing_nav_page(url: str) -> bool:
    """Return True if URL is a nav/search/help page, not an individual event page.

    Distinguishes `/eventos` (listing) from `/eventos/goiania-noise-2026` (event page).
    """
    parsed = urlparse(url.lower())
    path = parsed.path
    if path in ("", "/"):
        return True
    segments = [s for s in path.split("/") if s]
    if not segments:
        return True
    first = segments[0]
    if first in _STATIC_ROOTS:
        return True
    if first in _SEARCH_ROOTS:
        return True
    if first in _LISTING_ROOTS:
        # Nav only if there is no deeper slug after the listing root.
        return len(segments) < 2
    return False


def _find_ticket_links(links: list[str]) -> tuple[list[str], int]:
    """Return (display_links, distinct_domain_count).

    - Skips static assets and ticketing-platform nav/search pages.
    - Deduplicates by exact URL.
    - Caps URLs-per-domain via MAX_LINKS_PER_DOMAIN; total via MAX_TOTAL_TICKET_LINKS.
    - `distinct_domain_count` drives scoring (distinct platforms hosting the event).
    """
    display: list[str] = []
    seen_urls: set[str] = set()
    domain_counts: dict[str, int] = {}

    for link in links:
        if len(display) >= MAX_TOTAL_TICKET_LINKS:
            break
        link_lower = link.lower()
        if _is_static_asset(link_lower) or _is_ticketing_nav_page(link_lower):
            continue
        matched_domain = next((d for d in TICKETING_DOMAINS if d in link_lower), None)
        if matched_domain is None:
            continue
        if link in seen_urls:
            continue
        if domain_counts.get(matched_domain, 0) >= MAX_LINKS_PER_DOMAIN:
            continue
        seen_urls.add(link)
        domain_counts[matched_domain] = domain_counts.get(matched_domain, 0) + 1
        display.append(link)

    return display, len(domain_counts)


def _score_to_confidence(score: int) -> str:
    if score >= CONFIDENCE_HIGH:
        return "alta"
    if score >= CONFIDENCE_MEDIUM:
        return "média"
    if score > 0:
        return "baixa"
    return "nenhuma"


def _is_trusted_source(source_name: str) -> bool:
    return any(source_name.startswith(p) for p in TRUSTED_SOURCE_PREFIXES)


def _mentions_target_event(text: str) -> bool:
    return any(term in text for term in TARGET_EVENT_TERMS)


def analyze(result: SourceResult) -> Detection:
    """Analyze a single source result and return a Detection.

    Untrusted sources (search engines, ticketing listings) must mention the
    festival name to score at all. Otherwise a news article about a past
    edition, a similarly-named event, or generic ticketing boilerplate can
    build up a score from stray high-confidence terms.
    """
    text = result.text
    evidence: list[str] = []
    score = 0

    # Trusted sources (the festival's own site, its Instagram) are domain-
    # gated — anything they say is about this event by construction.
    if not _is_trusted_source(result.source_name) and not _mentions_target_event(text):
        return Detection(
            source=result.source_name,
            score=0,
            confidence="nenhuma",
            sold_out=False,
            evidence=[],
            ticket_links=[],
        )

    high_count = _count_matches(text, HIGH_CONFIDENCE_TERMS, HIGH_TERM_MAX_CONTRIBUTIONS)
    if high_count > 0:
        score += high_count * HIGH_TERM_SCORE
        matched = [t for t in HIGH_CONFIDENCE_TERMS if t in text][:HIGH_TERM_MAX_CONTRIBUTIONS]
        evidence.append(f"Termos de alta confiança ({high_count}): {', '.join(matched)}")

    # Support terms only count when at least 1 high-confidence term already fired,
    # so a bare "ingresso" in unrelated footer text can't build up a score on its own.
    if high_count > 0:
        support_count = _count_matches(text, SUPPORT_TERMS, SUPPORT_TERM_MAX_CONTRIBUTIONS)
        if support_count > 0:
            score += support_count * SUPPORT_TERM_SCORE
            matched_support = [t for t in SUPPORT_TERMS if t in text][:SUPPORT_TERM_MAX_CONTRIBUTIONS]
            evidence.append(f"Termos de suporte ({support_count}): {', '.join(matched_support)}")

    ticket_links, distinct_domains = _find_ticket_links(result.links)
    scoring_count = min(distinct_domains, TICKET_LINK_MAX_CONTRIBUTIONS)
    if scoring_count > 0:
        score += scoring_count * TICKET_LINK_SCORE
        evidence.append(
            f"Links de ticketing ({distinct_domains} domínio(s), {len(ticket_links)} url(s)): "
            f"{', '.join(ticket_links)}"
        )

    # Sold-out gated on high_count > 0: same rationale as support terms —
    # avoids a stray "esgotado" in header/footer from marking as sold out.
    sold_out = False
    if high_count > 0:
        sold_count = _count_matches(text, SOLD_OUT_TERMS, len(SOLD_OUT_TERMS))
        if sold_count >= SOLD_OUT_MIN_TERMS:
            sold_out = True
            score -= SOLD_OUT_PENALTY
            matched_sold = [t for t in SOLD_OUT_TERMS if t in text]
            evidence.append(f"Termos de esgotamento ({sold_count}): {', '.join(matched_sold)}")

    score = max(0, min(100, score))
    confidence = _score_to_confidence(score)

    return Detection(
        source=result.source_name,
        score=score,
        confidence=confidence,
        sold_out=sold_out,
        evidence=evidence,
        ticket_links=ticket_links,
    )
