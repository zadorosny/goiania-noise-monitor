"""Telegram notification client — send-only, no webhook."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from .config import TELEGRAM_RETRY_ATTEMPTS, TELEGRAM_RETRY_BASE_DELAY
from .models import CheckResult

logger = logging.getLogger(__name__)

# São Paulo timezone (UTC-3, no DST since 2019)
_SP_TZ = timezone(timedelta(hours=-3))

_CONFIDENCE_ICONS = {
    "alta": "\U0001f534",  # 🔴
    "média": "\U0001f7e1",  # 🟡
    "baixa": "\u26aa",  # ⚪
    "nenhuma": "",
}


def _format_alert(result: CheckResult) -> str:
    """Format an HTML alert message for Telegram."""
    now_sp = datetime.now(_SP_TZ).strftime("%d/%m/%Y %H:%M:%S")
    lines = ["<b>\U0001f3ab Alerta de Ingressos — Goiânia Noise 2026</b>"]
    lines.append(f"<i>{now_sp} (America/Sao_Paulo)</i>\n")

    for det in result.detections:
        if det.score == 0:
            continue

        icon = _CONFIDENCE_ICONS.get(det.confidence, "")
        status = " [ESGOTADO]" if det.sold_out else ""
        lines.append(f"{icon} <b>{det.source}</b> — score {det.score}, confiança {det.confidence}{status}")

        for ev in det.evidence:
            lines.append(f"  • {ev}")

        if det.ticket_links:
            for link in det.ticket_links:
                lines.append(f'  \U0001f517 <a href="{link}">{link}</a>')

        lines.append("")

    return "\n".join(lines)


def _format_heartbeat() -> str:
    now_sp = datetime.now(_SP_TZ).strftime("%d/%m/%Y %H:%M:%S")
    return (
        f"\u2705 Monitor ativo — Goiânia Noise 2026\n"
        f"0 ingressos detectados.\n"
        f"<i>{now_sp} (America/Sao_Paulo)</i>"
    )


async def send_alert(result: CheckResult) -> None:
    """Send a ticket alert to Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    await _send_message(token, chat_id, _format_alert(result))


async def send_heartbeat() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    await _send_message(token, chat_id, _format_heartbeat())


async def _send_message(token: str, chat_id: str, text: str) -> None:
    """Send a message via python-telegram-bot with exponential-backoff retry."""
    from telegram import Bot
    from telegram.error import NetworkError, RetryAfter, TimedOut

    bot = Bot(token=token)

    last_exc: Exception | None = None
    for attempt in range(1, TELEGRAM_RETRY_ATTEMPTS + 1):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info("Telegram message sent to chat %s (attempt %d)", chat_id, attempt)
            return
        except RetryAfter as exc:
            # Telegram rate limit — honor the server-provided delay.
            wait = float(getattr(exc, "retry_after", TELEGRAM_RETRY_BASE_DELAY))
            logger.warning("Telegram RetryAfter: waiting %.1fs (attempt %d)", wait, attempt)
            last_exc = exc
            await asyncio.sleep(wait)
        except (NetworkError, TimedOut) as exc:
            last_exc = exc
            if attempt == TELEGRAM_RETRY_ATTEMPTS:
                break
            delay = TELEGRAM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Telegram send failed (%s) — retrying in %.1fs (attempt %d/%d)",
                exc,
                delay,
                attempt,
                TELEGRAM_RETRY_ATTEMPTS,
            )
            await asyncio.sleep(delay)

    logger.error(
        "Telegram send permanently failed after %d attempts: %s",
        TELEGRAM_RETRY_ATTEMPTS,
        last_exc,
    )
