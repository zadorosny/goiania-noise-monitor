# Goiânia Noise Ticket Monitor — Spec para Claude Code

Monitor de disponibilidade de ingressos do Goiânia Noise Festival, rodando como cron no GitHub Actions, notificando via Telegram. Substitui uma versão anterior em Google Apps Script que sofria com: site Wix renderizado client-side (HTML vazio no fetch), quota de UrlFetch, slugs chutados gerando falsos positivos, e Instagram público inútil sem login.

## Objetivo

Detectar o mais cedo possível quando os ingressos da edição 2026 entrarem em pré-venda ou venda geral, e disparar uma mensagem no Telegram. Zero falso-negativo é mais importante que zero falso-positivo — prefiro ser acordado à toa do que perder o 1º lote.

## Stack

- **Python 3.12**
- **Playwright** (Chromium headless) — obrigatório porque o site oficial é Wix SPA
- **httpx** — para endpoints que são HTML estático (Sympla, Bilheteria Digital search)
- **python-telegram-bot** (v21+) — envio de mensagens e, opcionalmente, webhook via polling manual
- **pydantic** v2 — para os modelos de Detection/Result
- **GitHub Actions** — cron a cada 15 minutos durante janela ativa, estado persistido via commit em `state.json` ou via Actions cache
- **uv** para gerenciamento de dependências (mais rápido que pip no CI)

## Estrutura do repo

```
goiania-noise-monitor/
├── .github/workflows/monitor.yml
├── src/
│   ├── __init__.py
│   ├── main.py              # entrypoint: roda 1 ciclo de check
│   ├── config.py            # constantes, termos, URLs
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py          # classe Source abstrata
│   │   ├── wix_site.py      # site oficial (Playwright)
│   │   ├── linktree.py      # bio/linktree (Playwright, mais importante)
│   │   ├── sympla.py        # busca Sympla (httpx)
│   │   ├── bilheteria.py    # busca Bilheteria Digital (httpx)
│   │   ├── eventim.py       # busca Eventim (httpx)
│   │   └── google_search.py # site:bilheteriadigital.com "goiânia noise"
│   ├── analyzer.py          # score, evidence, confidence
│   ├── telegram_client.py   # wrapper simples sobre python-telegram-bot
│   ├── state.py             # load/save state.json, fingerprint
│   └── models.py            # Detection, CheckResult (pydantic)
├── tests/
│   ├── fixtures/            # HTMLs salvos de páginas reais para teste
│   ├── test_analyzer.py
│   └── test_sources.py
├── state.json               # commitado, contém last_fingerprint, last_heartbeat
├── pyproject.toml
├── README.md
└── .env.example
```

## Fontes a monitorar (em ordem de prioridade)

1. **Linktree/bio do Instagram** — onde o link de ingresso aparece PRIMEIRO. Descobrir a URL do linktree via Playwright abrindo `instagram.com/goianianoisefestival` e extraindo o `external_url` do JSON embutido (`window._sharedData` ou meta tags). Depois, fazer fetch do linktree e analisar todos os links.
2. **Site oficial Wix** — `goianianoisefestival.com.br`, `/order-online`, `/experiences`. Usar Playwright com `wait_until="networkidle"` e timeout de 20s. Extrair texto visível via `page.inner_text("body")` E todos os hrefs via `page.eval_on_selector_all("a", "els => els.map(e => e.href)")`.
3. **Bilheteria Digital** — busca pública `bilheteriadigital.com/pesquisa?q=goiania+noise`. Validar resultado dentro do container de card de evento (não no rodapé). Pode usar httpx puro.
4. **Sympla** — `sympla.com.br/eventos?s=goiania+noise+festival`. httpx puro. Validar via seletor CSS do card de resultado.
5. **Eventim** — idem.
6. **Google Search** — query `site:bilheteriadigital.com OR site:sympla.com.br "goiânia noise" 2026`. Scrape simples de `html.duckduckgo.com` (sem JS, sem captcha) em vez do Google para evitar bloqueio.

Instagram direto fica de fora — não funciona sem login.

## Analyzer — regras de score

Reaproveitar a lógica do script antigo, com ajustes:

- **Termos de alta confiança** (`HIGH_CONFIDENCE_TERMS`): +15 cada, máximo 4 contribuições → +60. Lista: "comprar ingresso", "garanta seu ingresso", "1º lote", "2º lote", "primeiro lote", "lote promocional", "meia-entrada", "inteira", "ponto de venda", etc.
- **Termos de suporte**: +3 cada, máx 5, só contam se houver ≥1 high. → +15
- **Links para domínios de ticketing**: +20 cada, máx 2 → +40. Domínios: bilheteriadigital.com, sympla.com.br, eventim.com.br, eventbrite.com.br, uhuu.com, ingresse.com, lets.events.
- **Sold-out check**: se ≥2 termos de esgotamento E há high terms, marcar `sold_out=True` e subtrair 30. Termos: "esgotado", "sold out", "vendas encerradas", "lotado", "indisponível".
- **Clamp** 0–100. Confidence: `≥50 alta`, `≥25 média`, `>0 baixa`, `0 nenhuma`.

Validação crítica que o script antigo não fazia: no Sympla/Bilheteria, antes de analisar, confirmar que o termo "goiânia noise" aparece dentro de um card de resultado de busca (usar seletor CSS específico de cada plataforma, definir em `sources/*.py`). Isso elimina falso positivo de menu/rodapé.

## Wix SPA — detalhe importante

O site oficial é Wix e renderiza cliente-side. Em `wix_site.py`:

```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    ctx = await browser.new_context(user_agent=UA, locale="pt-BR")
    page = await ctx.new_page()
    await page.goto(url, wait_until="networkidle", timeout=25000)
    await page.wait_for_timeout(2000)  # Wix pós-hidration
    html = await page.content()
    text = (await page.inner_text("body")).lower()
    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    await browser.close()
```

Para o hash de mudança de página, hashear apenas o `inner_text` (não o HTML) e remover dígitos/datas/UUIDs antes do hash — assim evita re-trigger por timestamp ou ID de sessão.

## Estado persistido (`state.json`)

```json
{
  "last_check": "2026-04-10T12:00:00Z",
  "last_alert_fingerprint": "abc123...",
  "last_heartbeat": "2026-04-10T06:00:00Z",
  "page_hash_wix_home": "...",
  "page_hash_linktree": "..."
}
```

Duas opções de persistência — implementar **ambas** e decidir via env var `STATE_BACKEND`:

1. **Commit no repo** (`git add state.json && git commit && git push`) usando o `GITHUB_TOKEN` dentro da action. Simples, histórico grátis, mas polui commits.
2. **GitHub Actions cache** (`actions/cache@v4`) com key rotativa. Mais limpo, mas cache tem TTL de 7 dias.

Default = commit. Incluir no workflow um step que faz `git diff --quiet state.json || (git add state.json && git commit -m "state: update [skip ci]" && git push)`.

## Telegram

Apenas **envio** nesta versão — sem webhook, sem comandos. Simplifica muito (sem precisar de servidor). Se o usuário quiser comandos depois, adicionar um segundo workflow com polling `getUpdates` num cron separado.

Secrets via GitHub Actions secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

Mensagem de alerta: HTML parse mode, com ícones por confiança (🔴 alta, 🟡 média, ⚪ baixa), evidências em bullets, links de ticketing destacados, timestamp em America/Sao_Paulo.

**Fingerprint**: MD5 ordenado de `(source, confidence, sold_out, sorted(ticket_links))` de todas detections com score > 0. Só notifica se fingerprint mudou vs `last_alert_fingerprint`.

**Heartbeat**: uma vez a cada 12h, mesmo sem findings, envia "✅ Monitor ativo, 0 ingressos detectados". Útil pra saber que o cron não quebrou.

## GitHub Actions workflow

```yaml
name: Ticket Monitor
on:
  schedule:
    - cron: "*/15 * * * *"   # a cada 15 min
  workflow_dispatch:          # permite rodar manual
concurrency:
  group: monitor
  cancel-in-progress: false
jobs:
  check:
    runs-on: ubuntu-latest
    permissions:
      contents: write         # pra commitar state.json
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - run: uv run playwright install chromium --with-deps
      - run: uv run python -m src.main
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
      - name: Commit state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git diff --quiet state.json || (git add state.json && git commit -m "state: update [skip ci]" && git push)
```

15 min é folgado durante janela ativa. Fora de janela (ex: 02h-08h BRT), reduzir para 1h via cron separado ou lógica no próprio script.

## Testes

- `test_analyzer.py`: fixtures de HTML (salvar páginas reais em `tests/fixtures/`) — uma com ingressos disponíveis, uma esgotada, uma sem ingressos, uma com só menu rodapé. Cada fixture tem o score esperado.
- `test_sources.py`: mock do Playwright/httpx, testa extração de texto/links.
- Rodar `pytest` no workflow como step antes do monitor, mas `continue-on-error: true` pra não bloquear notificação por teste flaky.

## Critérios de aceitação

1. `uv run python -m src.main` roda localmente com `.env` preenchido e envia mensagem de teste no primeiro run.
2. Workflow commita `state.json` apenas quando muda.
3. Em fixture de página sem ingressos, analyzer retorna score 0 e nenhum alerta é enviado.
4. Em fixture com "1º lote" + link pra bilheteriadigital.com, analyzer retorna confidence "alta".
5. Rodando 2x seguidas com mesmo resultado, 2ª execução NÃO envia alerta (fingerprint).
6. Heartbeat dispara se `now - last_heartbeat > 12h`.
7. README com instruções de setup de 0 a rodando: criar bot no BotFather, pegar chat_id, adicionar secrets, ativar Actions.

## Não fazer

- Não implementar webhook do Telegram nesta versão.
- Não usar API oficial do Instagram.
- Não chutar slugs de URL (`/goiania-noise-2026`, `/31-goiania-noise-festival` etc). Usar apenas busca + linktree.
- Não hashear HTML bruto do Wix — só texto visível.
- Não usar Google Search direto (bloqueia) — usar DuckDuckGo HTML.

## Entregáveis

1. Repo completo conforme estrutura acima.
2. README.md com setup passo-a-passo.
3. `.env.example`.
4. Pelo menos 4 fixtures de HTML reais em `tests/fixtures/`.
5. Workflow verde no primeiro push (com os secrets configurados).
