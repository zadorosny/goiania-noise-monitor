# Goiânia Noise Ticket Monitor <!-- v1 -->

Monitor automatizado de disponibilidade de ingressos do **31º Goiânia Noise Festival** (7–10 maio 2026). Roda como cron no GitHub Actions e notifica via Telegram.

## Fontes monitoradas

| # | Fonte | Método | Prioridade |
|---|-------|--------|------------|
| 1 | Instagram bio / Linktree | Playwright | Alta |
| 2 | Site oficial (Wix SPA) | Playwright | Alta |
| 3 | Bilheteria Digital | httpx | Média |
| 4 | Sympla | httpx | Média |
| 5 | Eventim | httpx | Baixa |
| 6 | DuckDuckGo (meta-busca) | httpx | Baixa |

## Como funciona

1. A cada 15 minutos (horário comercial) ou 1 hora (madrugada), o workflow busca todas as fontes
2. O **analyzer** pontua cada resultado com base em termos de confiança e links de ticketing
3. Se o fingerprint das detecções mudou, envia **alerta** no Telegram
4. A cada 12 horas, envia **heartbeat** para confirmar que o monitor está ativo
5. O estado é persistido em `state.json` via commit automático

## Setup

### 1. Criar bot no Telegram

1. Abra o [@BotFather](https://t.me/BotFather) no Telegram
2. Envie `/newbot` e siga as instruções
3. Copie o **token** (formato `123456:ABC-DEF...`)

### 2. Obter seu chat ID

1. Abra o [@userinfobot](https://t.me/userinfobot) no Telegram
2. Envie qualquer mensagem
3. Copie o **chat ID** numérico

### 3. Configurar secrets no GitHub

No repositório, vá em **Settings → Secrets and variables → Actions** e adicione:

| Secret | Valor |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | Token do BotFather |
| `TELEGRAM_CHAT_ID` | Seu chat ID |

### 4. Ativar o workflow

Vá em **Actions** no repositório e ative os workflows. O cron começa automaticamente.

Para rodar manualmente: **Actions → Ticket Monitor → Run workflow**.

### 5. Rodar localmente (opcional)

```bash
cp .env.example .env
# edite .env com seus tokens

uv sync
uv run playwright install chromium --with-deps
uv run python -m src.main
```

## Scoring

| Tipo | Pontos | Máx. contribuições |
|------|--------|-------------------|
| Termo de alta confiança | +15 | 4 (= 60 pts) |
| Termo de suporte | +3 | 5 (= 15 pts) |
| Link de ticketing | +20 | 2 (= 40 pts) |
| Termos de esgotamento | -30 | — |

**Confiança**: alta ≥ 50, média ≥ 25, baixa > 0.

## Stack

- Python 3.12+ / uv
- Playwright (Chromium headless)
- httpx
- python-telegram-bot
- GitHub Actions (cron)
