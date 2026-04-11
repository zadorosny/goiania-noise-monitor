"""Constants, search terms, and URLs for the monitor."""

# --- URLs ---
WIX_URLS = [
    "https://www.goianianoisefestival.com.br",
    "https://www.goianianoisefestival.com.br/order-online",
    "https://www.goianianoisefestival.com.br/experiences",
]

INSTAGRAM_URL = "https://www.instagram.com/goianianoisefestival/"

SYMPLA_SEARCH_URL = "https://www.sympla.com.br/eventos?s=goiania+noise+festival"

BILHETERIA_SEARCH_URL = "https://www.bilheteriadigital.com/pesquisa?q=goiania+noise"

EVENTIM_SEARCH_URL = "https://www.eventim.com.br/search/?affiliate=BDG&searchterm=goiania+noise"

DUCKDUCKGO_URL = (
    "https://html.duckduckgo.com/html/"
    "?q=site%3Abilheteriadigital.com+OR+site%3Asympla.com.br+%22goi%C3%A2nia+noise%22+2026"
)

# --- Ticketing domains ---
TICKETING_DOMAINS = [
    "bilheteriadigital.com",
    "sympla.com.br",
    "eventim.com.br",
    "eventbrite.com.br",
    "uhuu.com",
    "ingresse.com",
    "lets.events",
]

# --- Scoring terms ---
HIGH_CONFIDENCE_TERMS = [
    "comprar ingresso",
    "compre seu ingresso",
    "garanta seu ingresso",
    "garanta já",
    "1º lote",
    "1o lote",
    "2º lote",
    "2o lote",
    "primeiro lote",
    "segundo lote",
    "lote promocional",
    "meia-entrada",
    "meia entrada",
    "inteira",
    "ponto de venda",
    "pontos de venda",
    "ingressos disponíveis",
    "ingressos à venda",
    "vendas abertas",
    "pré-venda",
    "pre-venda",
    "comprar agora",
    "compre agora",
]

SUPPORT_TERMS = [
    "ingresso",
    "ingressos",
    "lote",
    "valor",
    "preço",
    "comprar",
    "venda",
    "vendas",
    "ticket",
    "tickets",
    "acesse",
    "link na bio",
    "saiba mais",
    "data",
    "edição 2026",
    "goiânia noise 2026",
]

SOLD_OUT_TERMS = [
    "esgotado",
    "esgotados",
    "sold out",
    "vendas encerradas",
    "lotado",
    "indisponível",
    "indisponiveis",
    "encerrado",
]

# --- Scoring parameters ---
HIGH_TERM_SCORE = 15
HIGH_TERM_MAX_CONTRIBUTIONS = 4
SUPPORT_TERM_SCORE = 3
SUPPORT_TERM_MAX_CONTRIBUTIONS = 5
TICKET_LINK_SCORE = 20
TICKET_LINK_MAX_CONTRIBUTIONS = 2
SOLD_OUT_PENALTY = 30
SOLD_OUT_MIN_TERMS = 2

# --- Confidence thresholds ---
CONFIDENCE_HIGH = 50
CONFIDENCE_MEDIUM = 25

# --- Heartbeat interval (seconds) ---
HEARTBEAT_INTERVAL_SECONDS = 12 * 60 * 60  # 12 hours

# --- User agent ---
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# --- Timeouts ---
PLAYWRIGHT_TIMEOUT_MS = 25_000
HTTPX_TIMEOUT_SECONDS = 15
