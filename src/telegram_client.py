"""Telegram notification client — send-only, no webhook."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

from .models import CheckResult, Detection

logger = logging.getLogger(__name__)

# São Paulo timezone (UTC-3)
_SP_TZ = timezone(timedelta(hours=-3))

_CONFIDENCE_ICONS = {
    "alta": "\U0001f534",   # 🔴
    "média": "\U0001f7e1",  # 🟡
    "baixa": "\u26aa",      # ⚪
    "nenhuma": "",
}


def _format_alert(result: CheckResult) -> str:
    """Format an HTML alert message for Telegram."""
    now_sp = datetime.now(_SP_TZ).strftime("%d/%m/%Y %H:%M:%S")
    lines = [f"<b>\U0001f3ab Alerta de Ingressos — Goiânia Noise 2026</b>"]
    lines.append(f"<i>{now_sp} (America/Sao_Paulo)</i>\n")

    for det in result.detections:
        if det.score == 0:
            continue

        icon = _CONFIDENCE_ICONS.get(det.confidence, "")
        status = " [ESGOTADO]" if det.sold_out else ""
        lines.append(
            f"{icon} <b>{det.source}</b> — "
            f"score {det.score}, confiança {det.confidence}{status}"
        )

        for ev in det.evidence:
            lines.append(f"  • {ev}")

        if det.ticket_links:
            for link in det.ticket_links:
                lines.append(f"  \U0001f517 <a href=\"{link}\">{link}</a>")

        lines.append("")

    return "\n".join(lines)


def _format_heartbeat() -> str:
    """Format a heartbeat message."""
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

    text = _format_alert(result)
    await _send_message(token, chat_id, text)


async def send_heartbeat() -> None:
    """Send a heartbeat message to Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    text = _format_heartbeat()
    await _send_message(token, chat_id, text)


async def _send_message(token: str, chat_id: str, text: str) -> None:
    """Send a message via python-telegram-bot."""
    from telegram import Bot

    bot = Bot(token=token)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    logger.info("Telegram message sent to chat %s", chat_id)
