"""Analyze source results and compute ticket-availability scores."""

from __future__ import annotations

from .config import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    HIGH_CONFIDENCE_TERMS,
    HIGH_TERM_MAX_CONTRIBUTIONS,
    HIGH_TERM_SCORE,
    SOLD_OUT_MIN_TERMS,
    SOLD_OUT_PENALTY,
    SOLD_OUT_TERMS,
    SUPPORT_TERM_MAX_CONTRIBUTIONS,
    SUPPORT_TERM_SCORE,
    TICKET_LINK_MAX_CONTRIBUTIONS,
    TICKET_LINK_SCORE,
    TICKETING_DOMAINS,
    SUPPORT_TERMS,
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
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".webp", ".avif",
)

_STATIC_PATH_SEGMENTS = ("/_next/", "/static/", "/assets/", "/dist/", "/build/")

# Navigation/search pages on ticketing platforms — not actual event links
_TICKETING_NAV_PATTERNS = (
    "/eventos?", "/eventos/", "/busca", "/pesquisa", "/search",
    "/categorias", "/cidades", "/ajuda", "/faq", "/sobre",
    "/termos", "/privacidade", "/contato", "/login", "/cadastro",
)


def _is_static_asset(url: str) -> bool:
    """Return True if URL looks like a static asset, not a ticket page."""
    lower = url.lower().split("?")[0]  # ignore query params
    if any(lower.endswith(ext) for ext in _STATIC_ASSET_EXTENSIONS):
        return True
    if any(seg in lower for seg in _STATIC_PATH_SEGMENTS):
        return True
    return False


def _is_ticketing_nav_page(url: str) -> bool:
    """Return True if URL is a navigation/search page on a ticketing site, not an event."""
    lower = url.lower()
    if any(pat in lower for pat in _TICKETING_NAV_PATTERNS):
        return True
    # Bare domain root (e.g. https://sympla.com.br/ or https://sympla.com.br)
    from urllib.parse import urlparse
    parsed = urlparse(lower)
    if parsed.path in ("", "/"):
        return True
    return False


def _find_ticket_links(links: list[str]) -> list[str]:
    """Return links pointing to known ticketing domains (excluding static assets and nav pages)."""
    found: list[str] = []
    seen_domains: set[str] = set()
    for link in links:
        link_lower = link.lower()
        if _is_static_asset(link_lower) or _is_ticketing_nav_page(link_lower):
            continue
        for domain in TICKETING_DOMAINS:
            if domain in link_lower and domain not in seen_domains:
                found.append(link)
                seen_domains.add(domain)
    return found


def _score_to_confidence(score: int) -> str:
    if score >= CONFIDENCE_HIGH:
        return "alta"
    if score >= CONFIDENCE_MEDIUM:
        return "média"
    if score > 0:
        return "baixa"
    return "nenhuma"


def analyze(result: SourceResult) -> Detection:
    """Analyze a single source result and return a Detection."""
    text = result.text
    evidence: list[str] = []
    score = 0

    # High confidence terms
    high_count = _count_matches(text, HIGH_CONFIDENCE_TERMS, HIGH_TERM_MAX_CONTRIBUTIONS)
    if high_count > 0:
        high_points = high_count * HIGH_TERM_SCORE
        score += high_points
        matched = [t for t in HIGH_CONFIDENCE_TERMS if t in text][:HIGH_TERM_MAX_CONTRIBUTIONS]
        evidence.append(f"Termos de alta confiança ({high_count}): {', '.join(matched)}")

    # Support terms — only count if at least 1 high term found
    if high_count > 0:
        support_count = _count_matches(text, SUPPORT_TERMS, SUPPORT_TERM_MAX_CONTRIBUTIONS)
        if support_count > 0:
            support_points = support_count * SUPPORT_TERM_SCORE
            score += support_points
            matched_support = [t for t in SUPPORT_TERMS if t in text][:SUPPORT_TERM_MAX_CONTRIBUTIONS]
            evidence.append(f"Termos de suporte ({support_count}): {', '.join(matched_support)}")

    # Ticket links
    ticket_links = _find_ticket_links(result.links)
    link_count = min(len(ticket_links), TICKET_LINK_MAX_CONTRIBUTIONS)
    if link_count > 0:
        link_points = link_count * TICKET_LINK_SCORE
        score += link_points
        evidence.append(f"Links de ticketing ({link_count}): {', '.join(ticket_links[:TICKET_LINK_MAX_CONTRIBUTIONS])}")

    # Sold-out check
    sold_out = False
    if high_count > 0:
        sold_count = _count_matches(text, SOLD_OUT_TERMS, len(SOLD_OUT_TERMS))
        if sold_count >= SOLD_OUT_MIN_TERMS:
            sold_out = True
            score -= SOLD_OUT_PENALTY
            matched_sold = [t for t in SOLD_OUT_TERMS if t in text]
            evidence.append(f"Termos de esgotamento ({sold_count}): {', '.join(matched_sold)}")

    # Clamp 0-100
    score = max(0, min(100, score))

    confidence = _score_to_confidence(score)

    return Detection(
        source=result.source_name,
        score=score,
        confidence=confidence,
        sold_out=sold_out,
        evidence=evidence,
        ticket_links=ticket_links[:TICKET_LINK_MAX_CONTRIBUTIONS],
    )
