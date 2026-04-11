# Goiânia Noise Ticket Monitor — Spec V2.2

Consolidação de V2.1 + 10 melhorias adicionais, com ordem de implementação ajustada ao calendário real do evento (**7 a 10 de maio de 2026**). Hoje é 10 de abril de 2026 — restam 27 dias.

Restrições mantidas de V1/V2.1:
- Sem scraping/API de Instagram
- Sem Google Search direto (DuckDuckGo HTML)
- Sem webhook do Telegram
- Envio Telegram via `httpx` direto na API
- Single workflow, sem `repository_dispatch`

## Objetivo

Maximizar chance de pegar o 1º lote da edição 2026 com latência mínima, mantendo observabilidade alta e escalando sensibilidade conforme a proximidade do evento.

---

## Parte A — Base V2.1 (referência resumida)

Mantidos integralmente da V2.1 anterior:
- **Upgrade 5** — Estado por source com auto-disable (5 erros → 2h pausado)
- **Upgrade 4** — Snapshot de evidências via artifact do Actions (primário), `last_evidence_id` no state
- **Upgrade 2** — `first_seen_link` com rate-limit obrigatório e TTL 90 dias
- **Upgrade 6** — Fallback Linktree → Wix formalizado
- **Upgrade 1** — Fast mode single-workflow com `fast_mode_until` e early-return
- **Upgrade 3** — Envio inicial + `editMessageText` in-place (tipos `INITIAL/UPDATE/BREAK/HEARTBEAT`)

Ver `SPEC_goiania_noise_monitor.md` (V1) e V2.1 para detalhes.

---

## Parte B — Novos upgrades V2.2

### #3 — Dedup canônica de URL (pré-requisito)

Aplicada em `seen_ticket_links` **e** no cálculo de fingerprint global.

```python
def canonicalize(url: str) -> str:
    # lowercase scheme + host
    # remove fragment (#...)
    # remove query params: utm_*, fbclid, gclid, mc_cid, mc_eid, ref, _ga
    # preserva: id, lote, session, evento, e
    # remove trailing slash (exceto root)
```

Teste unitário obrigatório com ≥10 casos cobrindo UTMs, fragment, ordem de params, case de host.

### #8 — Modo evento próximo com calendário fixo (PRIORIDADE ALTA)

```python
# src/config.py
EVENT_DATES = ("2026-05-07", "2026-05-10")
PRE_EVENT_WINDOW_DAYS = 30
CRITICAL_WINDOW_DAYS = 7
```

Quatro fases, função `get_phase(now, event_dates) -> Phase`:

**NORMAL** (>30 dias antes): comportamento V2.1 padrão.

**PRE_EVENT** (30 a 7 dias antes):
- Peso de `new_link`: +20 → +30
- Fast-mode ativa com score ≥ 25 (não só ≥50)
- Duração fast-mode: 90min → 3h
- Cron madrugada: 1x/h → 1x a cada 30min

**CRITICAL** (≤7 dias até fim do evento):
- Cron fixo 2min, 24h/dia
- Fast-mode sempre ligado (ignora `fast_mode_until`)
- Qualquer `new_link` em `TICKETING_DOMAINS` dispara `INITIAL` mesmo com score 0 no texto
- `disable_notification` noturno DESLIGADO
- Healthcheck sintético: 1x/dia → 4x/dia

**DORMANT** (>10/05/2026): 1 run/dia, `HEARTBEAT` semanal. Atualizar `EVENT_DATES` para recomeçar ciclo.

Estado novo:
```json
{
  "current_phase": "pre_event",
  "phase_transition_at": "2026-04-07T00:00:00Z"
}
```

Na transição de fase, envia `HEARTBEAT` especial: "📅 Entrando em fase CRÍTICA — evento em 7 dias".

### #6 — Golden cases

```
tests/fixtures/golden/
  ├── wix_2025_sold_out/{page.html, expected.json, captured_at.txt}
  ├── wix_first_lote/
  ├── wix_manutencao/
  ├── linktree_first_lote/
  ├── linktree_sem_ticketing/
  ├── sympla_match_rodape/   # clássico falso-positivo
  ├── bilheteria_evento_passado/
  └── ddg_zero_results/
```

Mínimo 8 goldens antes da fase CRITICAL. Step separado no CI com `continue-on-error: true` — quebra não bloqueia monitor, mas falha visível no PR.

### #4 — Retry por tipo de erro

| Erro | Retry | Backoff | Observação |
|---|---|---|---|
| `timeout`, `connection_error`, `5xx` | 1x | 3s | Padrão |
| `429` | 1x | 30s | Auto-disable mais agressivo: 3 erros, não 5 |
| `403` | 0 | — | Marca `suspected_block=true` no state da source |
| `404` | 0 | — | URL mudou, log e segue |
| `401` | 0 | — | `BREAK` imediato (não deveria acontecer) |

### #10 — Versionamento do analyzer

`ANALYZER_VERSION = "1.0.0"` em `src/analyzer.py`. Incluído em:
- Cada evidência do snapshot (artifact)
- Campo novo no `state.json`: `last_analyzer_version`
- Corpo da mensagem Telegram (rodapé pequeno)

Bump obrigatório em qualquer mudança de pesos/termos/regras. Permite bisect histórico contra goldens.

### #7 — Healthcheck sintético diário (dois tipos)

**Pipeline check**: fixture local → analyzer → Telegram `sendMessage` com `disable_notification: true` → validar response 200. Cron 06h BRT.

**Network check**: HEAD em `api.telegram.org` + `html.duckduckgo.com`. Detecta quebra de egress do Actions. Mesmo cron.

Falha → `BREAK` categoria `synthetic_fail`, rate-limit 24h. Na fase CRITICAL, healthcheck roda 4x/dia (00h, 06h, 12h, 18h BRT).

### #9 — Circuit breaker global

Se 6 runs consecutivos retornarem 0 sources com conteúdo útil (todas `skipped`/`error`/`timeout`):
- Pausa monitor por 4h (`global_pause_until` no state)
- Envia 1 `BREAK` categoria `circuit_open`
- Reset automático ao expirar

Protege contra outage do GitHub Actions e bloqueio em massa.

### #5 — Métricas semanais

Workflow separado `.github/workflows/metrics.yml`, roda domingo 09h BRT.

`metrics_weekly.md` commitado no repo contendo:
- Total de runs na semana
- Uptime % por source
- Count de `INITIAL`, `UPDATE`, `BREAK`, `HEARTBEAT` enviados
- Count de `new_link` dedupados (antes e depois do dedup)
- Avg e P95 de latência por source
- Fase atual

Anotações manuais "útil vs ruído" ficam em seção livre no final do md, editada à mão após cada semana.

### #2 reformulado — Silêncio noturno via `disable_notification`

Nada de fila. Entre 00h-07h BRT:
- `HEARTBEAT` → `disable_notification: true`
- `new_link` isolado sem score alto → `disable_notification: true`
- `INITIAL` com score ≥ 50 → **sempre** toca
- Na fase CRITICAL → desligado, tudo toca

### #1 reformulado — Baseline como contexto informativo

Não é gate. Captura hash de texto normalizado por source a cada run bem-sucedido. Guarda últimos 10 no state por source.

Na mensagem de alerta, adiciona linha: "📊 Texto mudou 40% vs média das últimas 10 capturas". Puramente informativo, não afeta score nem decisão de envio.

---

## Ordem de implementação (calendário apertado)

**Bloco urgente — antes de 17/04 (entrada em PRE_EVENT):**
1. **#3 Dedup canônica** — 1 dia
2. **#8 Modo evento próximo** (pelo menos detecção de fase + ajustes de cron/pesos) — 2-3 dias

**Bloco crítico — antes de 30/04 (entrada em CRITICAL):**
3. **#6 Goldens** — 1-2 dias
4. **#4 Retry por tipo de erro** + **#10 Versionamento** — 1 dia
5. **#7 Healthcheck sintético** — 1 dia
6. **#9 Circuit breaker** — meio dia

**Bloco pós-festival (após 10/05):**
7. **#5 Métricas semanais** — 1 dia
8. **#2 reformulado** — meio dia
9. **#1 reformulado** — opcional

Orçamento total até 30/04: ~7-9 dias de trabalho espalhados em 20 dias de calendário. Viável conciliando com o Poker Agents System.

---

## Checklist de deploy antes da fase CRITICAL

- [ ] Dedup canônica com testes passando
- [ ] `EVENT_DATES` configurado e testado com datas mockadas
- [ ] Transição automática NORMAL → PRE_EVENT validada (já deveria ter disparado em 07/04)
- [ ] Pelo menos 8 goldens versionados
- [ ] Retry diferenciado por status code
- [ ] `ANALYZER_VERSION` presente em todas as evidências
- [ ] Healthcheck sintético rodando e entregando no Telegram
- [ ] Circuit breaker testado manualmente (forçar 6 falhas)
- [ ] Secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` e var `LINKTREE_URL` confirmados
- [ ] Run manual via `workflow_dispatch` bem-sucedido 24h antes de 30/04

## Não fazer

- Não usar `repository_dispatch` nem PAT adicional
- Não filar notificações noturnas (só silenciar via flag do Telegram)
- Não usar baseline como gate de decisão
- Não mexer no analyzer durante a fase CRITICAL sem rodar goldens antes
- Não commitar `state.json` com `seen_ticket_links` > 90 dias (TTL obrigatório no load)
