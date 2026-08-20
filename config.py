import os
from dotenv import load_dotenv

load_dotenv()

# ── KITE ──────────────────────────────────────────────
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

# ── TELEGRAM ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── CAPITAL ───────────────────────────────────────────
INITIAL_CAPITAL = 500000
MAX_RISK_PER_TRADE_PCT = 10
MAX_DAILY_LOSS_PCT = 2
MAX_TRADES_PER_DAY = 10
MAX_OPEN_POSITIONS = 5

# ── OPTION RISK ───────────────────────────────────────
STOP_LOSS_PCT = 15
TARGET_PCT = 30
TRAILING_ACTIVATE_PCT = 12
TRAILING_STOP_PCT = 8
ENTRY_SLIPPAGE_PCT = 0.5
EXIT_SLIPPAGE_PCT = 0.5
BROKERAGE_PER_ORDER = 60

# ── TIMING ────────────────────────────────────────────
SCAN_START = "09:25"
SCAN_INTERVAL_SEC = 60
NO_NEW_TRADES_AFTER = "14:15"
AUTO_EXIT_TIME = "15:00"
DEAD_ZONE_START = "13:00"
DEAD_ZONE_END = "13:30"

# ── SCANNER ───────────────────────────────────────────
MIN_GAP_PCT = 0.8              # Was 1.5 — relaxed for real market
MIN_MOMENTUM_PCT = 1.5         # Was 3.0 — most moves are 1.5-3%
VOL_MULTIPLIER = 1.5           # Was 2.0 — 2x is too strict for many stocks
RSI_OVERSOLD = 35              # Was 30 — wider oversold zone
RSI_OVERBOUGHT = 65            # Was 70 — wider overbought zone
COOLDOWN_MINUTES = 20          # Was 30 — allow re-entry sooner

# ── OPTION DELTA DEFAULTS ─────────────────────────────
ATM_DELTA = 0.50
DAILY_THETA_PCT = 3.0

# ── DB ────────────────────────────────────────────────
DB_PATH = "paper_trades.db"

# ── WEBSOCKET ─────────────────────────────────────────
WS_MODE = "full"
RECONNECT_DELAY = 5

# ── SECTOR MAPPING ────────────────────────────────────
SECTORS = {
    "RELIANCE": "Energy", "TCS": "IT", "HDFCBANK": "Banking",
    "INFY": "IT", "ICICIBANK": "Banking", "HINDUNILVR": "FMCG",
    "ITC": "FMCG", "SBIN": "Banking", "BHARTIARTL": "Telecom",
    "KOTAKBANK": "Banking", "LT": "Infra", "AXISBANK": "Banking",
    "BAJFINANCE": "Finance", "MARUTI": "Auto", "TITAN": "Consumer",
    "SUNPHARMA": "Pharma", "ASIANPAINT": "Paint", "ULTRACEMCO": "Cement",
    "WIPRO": "IT", "HCLTECH": "IT", "BAJAJFINSV": "Finance",
    "DRREDDY": "Pharma", "TATAMOTORS": "Auto", "POWERGRID": "Power",
    "NTPC": "Power", "ONGC": "Energy", "JSWSTEEL": "Metal",
    "TATASTEEL": "Metal", "ADANIENT": "Conglomerate",
    "ADANIPORTS": "Infra", "TECHM": "IT", "HDFCLIFE": "Insurance",
    "SBILIFE": "Insurance", "DIVISLAB": "Pharma", "CIPLA": "Pharma",
    "BPCL": "Energy", "COALINDIA": "Mining", "GRASIM": "Cement",
    "HINDALCO": "Metal", "INDUSINDBK": "Banking",
    "HEROMOTOCO": "Auto", "EICHERMOT": "Auto", "BRITANNIA": "FMCG",
    "APOLLOHOSP": "Healthcare", "TATACONSUM": "FMCG", "M&M": "Auto",
    "TRENT": "Retail", "HAL": "Defence", "BEL": "Defence",
    "ZOMATO": "Tech", "POLYCAB": "Electrical", "DABUR": "FMCG",
    "PIDILITIND": "Chemicals", "HAVELLS": "Electrical",
    "GODREJCP": "FMCG", "MARICO": "FMCG", "NESTLEIND": "FMCG",
    "UPL": "Chemicals", "BAJAJ-AUTO": "Auto", "TATAPOWER": "Power",
    "VEDL": "Metal", "NMDC": "Mining", "SAIL": "Metal",
    "COFORGE": "IT", "PERSISTENT": "IT", "LTIM": "IT",
    "MPHASIS": "IT", "ACC": "Cement", "BALKRISIND": "Auto",
    "CHOLAFIN": "Finance", "CROMPTON": "Electrical",
    "SIEMENS": "Industrial", "LICI": "Insurance",
    "MUTHOOTFIN": "Finance", "SRF": "Chemicals",
    "TORNTPOWER": "Power", "VOLTAS": "Consumer",
    "ABFRL": "Retail", "PAGEIND": "Consumer",
    "PEL": "Finance", "HONAUT": "Industrial",
}


def get_sector(symbol):
    return SECTORS.get(symbol, f"_{symbol}")  # Each unknown stock gets unique "sector"
