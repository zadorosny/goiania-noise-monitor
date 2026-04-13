"""Constants, search terms, and URLs for the monitor."""

# --- URLs ---
WIX_URLS = [
    "https://www.goianianoisefestival.com.br",
    "https://www.goianianoisefestival.com.br/order-online",
]

SYMPLA_SEARCH_URL = "https://www.sympla.com.br/eventos?s=goiania+noise+festival"

BILHETERIA_SEARCH_URL = "https://www.bilheteriadigital.com/busca/goiania%20noise/as/1"

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
    "shotgun.live",
    "queroingresso.com.br",
    "megabilheteria.com",
    "ingressos.com.br",
]

# Sources whose text is already festival-specific by domain — skip the
# target-event guard in analyze(). Everything else must mention the festival
# name to be scored, or a news article about a past edition or a
# similarly-named event can build up a score from stray terms.
TRUSTED_SOURCE_PREFIXES = ("wix_site", "instagram")
TARGET_EVENT_TERMS = ("goiânia noise", "goiania noise")

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
    "ingressos liberados",
    "ingressos já disponíveis",
    "ingressos ja disponiveis",
    "garanta o seu",
    "compre o seu",
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
TICKET_LINK_MAX_CONTRIBUTIONS = 2  # scoring cap — distinct domains
MAX_LINKS_PER_DOMAIN = 2  # display cap — URLs shown per domain
MAX_TOTAL_TICKET_LINKS = 6  # display cap — total URLs returned per detection
SOLD_OUT_PENALTY = 30
SOLD_OUT_MIN_TERMS = 2

# --- Confidence thresholds ---
CONFIDENCE_HIGH = 50
CONFIDENCE_MEDIUM = 25

# --- Heartbeat schedule (Brasília/UTC-3 hours) ---
HEARTBEAT_HOURS_BRT = [9, 14, 18, 21]

# --- User agent ---
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# --- Timeouts ---
PLAYWRIGHT_TIMEOUT_MS = 15_000
PLAYWRIGHT_HYDRATION_TIMEOUT_MS = 8_000  # max wait for networkidle after DOM load
PLAYWRIGHT_MIN_HYDRATION_MS = 1_500  # floor — always wait at least this for late scripts
HTTPX_TIMEOUT_SECONDS = 30

# --- Retry / resilience ---
TELEGRAM_RETRY_ATTEMPTS = 4
TELEGRAM_RETRY_BASE_DELAY = 1.5  # seconds, exponential

HTTPX_RETRY_ATTEMPTS = 3
HTTPX_RETRY_BASE_DELAY = 1.0  # seconds, quadratic (1s, 4s, 9s)

# --- Instagram source ---
INSTAGRAM_HANDLE = "goianianoisefestival"
INSTAGRAM_POSTS_LIMIT = 12  # last N posts to fetch
INSTAGRAM_POST_MAX_AGE_DAYS = 14  # drop anything older
APIFY_INSTAGRAM_ACTOR = "apify~instagram-scraper"
APIFY_SYNC_TIMEOUT_SECONDS = 180.0  # run-sync-get-dataset-items can take ~60-90s

# --- Observability ---
CHECK_LOG_PATH_NAME = "check_log.jsonl"
CHECK_LOG_MAX_LINES = 2000  # rotate oldest entries past this

# Consecutive empty cycles before resetting last_alert_fingerprint.
# Prevents re-alerting on transient scraper hiccups but still realerts
# if tickets reopen after a real dry spell.
EMPTY_CYCLES_RESET_THRESHOLD = 4
