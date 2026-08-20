# ═══════════════════════════════════════════════════════
#  FILE: options_intraday_v2.py
#  Real-time paper trading engine
#  FIXED: volume, prev_close, REAL premiums, actual strikes, tick rounding
#  NEW: Profit lock, fast real-premium SL checks, 30min market settle
# ═══════════════════════════════════════════════════════

"""
Options Intraday Paper Trader V2

Usage:
    python3 options_intraday_v2.py
"""

import sys
import os
import time as time_mod
import logging
import json
import numpy as np
from datetime import datetime, timedelta, date, time as dt_time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from kiteconnect import KiteConnect, KiteTicker
import config

# ══════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "paper_trades_v2.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ],
)
logger = logging.getLogger("paper_v2")

G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
M = "\033[95m"
B = "\033[1m"
D = "\033[0m"

KITE_SLEEP = 0.35

# ══════════════════════════════════════════════════════
#  CAPITAL & RISK
# ══════════════════════════════════════════════════════
CAPITAL = config.INITIAL_CAPITAL
MAX_RISK_PCT = config.MAX_RISK_PER_TRADE_PCT
SL_PCT = config.STOP_LOSS_PCT
TARGET_PCT = config.TARGET_PCT
TRAIL_ACTIVATE = config.TRAILING_ACTIVATE_PCT
TRAIL_STOP = config.TRAILING_STOP_PCT
MAX_TRADES = config.MAX_TRADES_PER_DAY
MAX_OPEN = config.MAX_OPEN_POSITIONS
MAX_DAILY_LOSS_PCT = config.MAX_DAILY_LOSS_PCT
PREMIUM_CAP = 300
BROKERAGE = config.BROKERAGE_PER_ORDER * 2
ENTRY_SLIP = config.ENTRY_SLIPPAGE_PCT / 100
EXIT_SLIP = config.EXIT_SLIPPAGE_PCT / 100
DAILY_THETA_PCT = config.DAILY_THETA_PCT / 100

# ══════════════════════════════════════════════════════
#  V4 FILTERS
# ══════════════════════════════════════════════════════
MIN_PREMIUM = 8.0
MIN_STOCK_PRICE = 250
GAP_GO_MIN_GAP_PCT = 2.0
GAP_GO_MIN_VOL = 3.0
GAP_GO_MAX_SAME_DAY = 4
MARKET_REGIME_ENABLED = True
MARKET_CE_BLOCK = -0.3
MARKET_PE_BLOCK = 0.3

MIN_GAP_PCT = config.MIN_GAP_PCT
MIN_MOMENTUM_PCT = config.MIN_MOMENTUM_PCT
VOL_MULTIPLIER = config.VOL_MULTIPLIER
RSI_OVERSOLD = config.RSI_OVERSOLD
RSI_OVERBOUGHT = config.RSI_OVERBOUGHT
COOLDOWN_MINUTES = config.COOLDOWN_MINUTES

VOL_NORMAL = 1.5
VOL_HIGH = 2.5
VOL_EXTREME = 4.0

HOT_LIST = {
    "GVT&D", "COFORGE", "DIXON", "FORCEMOT", "KALYANKJIL",
    "KPITTECH", "ADANIPOWER", "ETERNAL", "GMRAIRPORT", "HINDPETRO",
    "INOXWIND", "MANAPPURAM", "MOTILALOFS", "NAM-INDIA", "SUZLON",
    "ADANIPORTS", "AMBER", "ANGELONE", "BHEL", "BLUESTARCO",
    "PGEL", "BANKINDIA", "COCHINSHIP", "HINDZINC", "LTF",
    "NATIONALUM", "RVNL", "ADANIGREEN", "BAJFINANCE", "BPCL",
    "HCLTECH", "INDUSINDBK", "IREDA", "IRFC",
}

DAY_BONUS = {
    "Monday": 0.03, "Tuesday": -0.02, "Wednesday": 0.03,
    "Thursday": 0.0, "Friday": 0.01,
}

MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)
SCAN_START = dt_time(10, 00)       # CHANGED: was 9:25, now 9:45 (30min settle)
SCAN_END = dt_time(15, 15)
DEAD_ZONE_START = dt_time(13, 0)
DEAD_ZONE_END = dt_time(13, 30)
NO_NEW_AFTER = dt_time(14, 15)
EOD_EXIT = dt_time(15, 0)
DASHBOARD_INTERVAL = 60

# ── NEW: Profit Lock & Fast Recalibrate ──
PROFIT_LOCK_TRIGGER = 0.75   # activate when 75% of target distance reached
PROFIT_LOCK_FLOOR = 0.40     # lock SL at 40% of target distance above entry
FAST_RECAL_INTERVAL = 15     # fetch real option premiums every 15 seconds

PATTERN_FILTER = {
    "Gap & Go":                 True,
    "Gap & Fall":               True,
    "Volume Spike (Bull)":      False,
    "Volume Spike (Bear)":      False,
    "Early Momentum (Up)":      False,
    "Early Momentum (Down)":    False,
    "Rel Strength (Bull)":      False,
    "Rel Weakness (Bear)":      True,
    "Oversold Bounce":          True,
    "Overbought Reversal":      True,
    "Green Building":           True,
    "Red Building":             False,
    "Hot Continuation (Bull)":  True,
    "Hot Continuation (Bear)":  False,
}


# ══════════════════════════════════════════════════════
#  INDICATORS
# ══════════════════════════════════════════════════════

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def volume_ratio_fn(current_volume, avg_daily_volume, minutes_elapsed):
    minutes_elapsed = max(minutes_elapsed, 1)
    expected_fraction = minutes_elapsed / 375.0
    expected_volume = avg_daily_volume * expected_fraction
    if expected_volume == 0:
        return 0
    return current_volume / expected_volume


def price_position_fn(high, low, current):
    if high == low:
        return 0.5
    return (current - low) / (high - low)


# ══════════════════════════════════════════════════════
#  OPTION STRIKE, PREMIUM, TICK ROUNDING
# ══════════════════════════════════════════════════════

NSE_TICK = 0.05


def round_to_tick(price, tick=NSE_TICK):
    """Round to NSE F&O tick size (0.05)."""
    return round(round(price / tick) * tick, 2)


def find_atm_strike(price, symbol=None, actual_strikes=None):
    """Find ATM strike. Uses actual NFO strikes if available,
    falls back to hardcoded steps."""
    if actual_strikes and symbol and symbol in actual_strikes:
        strikes = actual_strikes[symbol]
        if strikes:
            return min(strikes, key=lambda s: abs(s - price))

    if price < 500:
        step = 10
    elif price < 1000:
        step = 25
    elif price < 2000:
        step = 50
    else:
        step = 100
    return int(round(price / step) * step)


def estimate_entry_premium(stock_price):
    """Fallback estimation when Kite LTP is unavailable."""
    premium = stock_price * 0.015
    premium = min(premium, PREMIUM_CAP)
    premium = max(premium, 1.0)
    premium *= (1 + ENTRY_SLIP)
    return round_to_tick(premium)


def estimate_exit_premium(premium):
    return round_to_tick(premium * (1 - EXIT_SLIP))


# ══════════════════════════════════════════════════════
#  POSITION
# ══════════════════════════════════════════════════════

@dataclass
class Position:
    id: int
    symbol: str
    direction: str
    pattern: str
    strike: int
    option_type: str
    option_symbol: str
    entry_premium: float
    entry_stock_price: float
    entry_time: datetime
    quantity: int
    lot_size: int
    stop_loss: float
    target: float
    delta: float
    theta_per_min: float
    confidence: float
    reason: str
    premium_source: str = "estimated"
    status: str = "OPEN"
    current_premium: float = 0.0
    current_stock: float = 0.0
    exit_premium: float = 0.0
    exit_reason: str = ""
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    trailing_active: bool = False
    trailing_sl: float = 0.0
    # NEW: Profit lock
    profit_lock_active: bool = False
    profit_lock_sl: float = 0.0
    # NEW: Track when real premium was last fetched
    _real_premium_time: float = 0.0

    @property
    def unrealized(self):
        return (self.current_premium - self.entry_premium) * self.quantity * self.lot_size

    @property
    def pnl_pct(self):
        if self.entry_premium == 0:
            return 0
        return ((self.current_premium - self.entry_premium) / self.entry_premium) * 100

    @property
    def hold_min(self):
        end = self.exit_time or datetime.now()
        return (end - self.entry_time).total_seconds() / 60


# ══════════════════════════════════════════════════════
#  5-MIN CANDLE BUILDER
# ══════════════════════════════════════════════════════

class CandleBuilder:
    def __init__(self):
        self.current = {}
        self.candles = {}
        self.completed = []

    def _bucket(self, dt):
        minute = (dt.minute // 5) * 5
        return dt.replace(minute=minute, second=0, microsecond=0)

    def update(self, symbol, ltp, volume, tick_time):
        bucket = self._bucket(tick_time)
        key = symbol

        if key not in self.current:
            self.current[key] = {
                "bucket": bucket,
                "open": ltp, "high": ltp, "low": ltp, "close": ltp,
                "cum_volume": volume,
                "start_volume": volume,
            }
            return

        c = self.current[key]

        if bucket != c["bucket"]:
            candle_volume = max(c["cum_volume"] - c["start_volume"], c["cum_volume"])
            completed = {
                "dt": c["bucket"],
                "open": c["open"], "high": c["high"],
                "low": c["low"], "close": c["close"],
                "volume": candle_volume,
                "cum_volume": c["cum_volume"],
            }
            if symbol not in self.candles:
                self.candles[symbol] = []
            self.candles[symbol].append(completed)
            self.completed.append((symbol, completed))

            self.current[key] = {
                "bucket": bucket,
                "open": ltp, "high": ltp, "low": ltp, "close": ltp,
                "cum_volume": volume,
                "start_volume": volume,
            }
        else:
            c["high"] = max(c["high"], ltp)
            c["low"] = min(c["low"], ltp)
            c["close"] = ltp
            if volume > c["cum_volume"]:
                c["cum_volume"] = volume

    def get_candles(self, symbol):
        return self.candles.get(symbol, [])

    def get_today_candles(self, symbol, today):
        return [c for c in self.candles.get(symbol, []) if c["dt"].date() == today]

    def get_current(self, symbol):
        return self.current.get(symbol)

    def flush_completed(self):
        result = list(self.completed)
        self.completed = []
        return result


# ══════════════════════════════════════════════════════
#  PAPER TRADER
# ══════════════════════════════

class OptionsIntradayPaperTrader:

    def __init__(self):
        self.kite = None
        self.ticker = None
        self.fno_stocks = []
        self.lot_sizes = {}
        self.nse_tokens = {}
        self.token_to_symbol = {}
        self.avg_volumes = {}
        self.daily_candles_hist = {}
        self.active_hot = set()
        self.candle_builder = CandleBuilder()
        self.positions = []
        self.closed = []
        self.all_trades = []
        self._id = 0
        self.daily_pnl = 0.0
        self.circuit_breaker = False
        self.last_signal_time = {}
        self.trades_today = 0
        self.gap_go_today = 0
        self.last_dashboard = 0
        self.tick_count = 0
        self.running = False
        self._sample_tick = None
        self._sample_tick_logged = False
        self._tick_volume_sample = None

        # Option instrument lookup
        self.option_instruments = {}
        self.actual_strikes = {}
        self._last_fast_recalibrate = 0      # NEW: fast recalibrate timer
        self._real_premiums_fetched = 0
        self._real_premiums_failed = 0

    # ── CONNECTION ────────────────────────────────

    def connect(self):
        self.kite = KiteConnect(api_key=config.KITE_API_KEY)
        self.kite.set_access_token(config.KITE_ACCESS_TOKEN)
        profile = self.kite.profile()
        logger.info("Connected: %s", profile.get("user_name"))

    # ── INSTRUMENTS ───────────────────────────────

    def load_instruments(self):
        logger.info("Loading F&O instruments...")
        instruments = self.kite.instruments("NFO")
        time_mod.sleep(KITE_SLEEP)

        fno_set = set()
        for inst in instruments:
            if inst.get("segment") == "NFO-FUT" and inst.get("name"):
                name = inst["name"]
                ls = int(inst.get("lot_size", 0))
                if ls > 0:
                    self.lot_sizes[name] = ls
                    fno_set.add(name)

        for inst in instruments:
            if inst.get("segment") == "NFO-OPT" and inst.get("name"):
                name = inst["name"]
                ls = int(inst.get("lot_size", 0))
                if ls > 0 and name not in self.lot_sizes:
                    self.lot_sizes[name] = ls

        self.fno_stocks = sorted(fno_set)
        self.active_hot = HOT_LIST & set(self.fno_stocks)

        self._build_option_lookup(instruments, fno_set)

        try:
            nse_instruments = self.kite.instruments("NSE")
            time_mod.sleep(KITE_SLEEP)

            nse_lookup = {}
            for inst in nse_instruments:
                ts = inst.get("tradingsymbol", "")
                name = inst.get("name", "")
                token = inst.get("instrument_token", 0)
                seg = inst.get("segment", "")
                if seg == "NSE" and token:
                    if ts:
                        nse_lookup[ts] = token
                    if name:
                        nse_lookup[name] = token

            matched = 0
            for symbol in self.fno_stocks:
                token = None
                if symbol in nse_lookup:
                    token = nse_lookup[symbol]
                if not token:
                    for suffix in ["-EQ", "-BE", "-SM"]:
                        key = symbol + suffix
                        if key in nse_lookup:
                            token = nse_lookup[key]
                            break
                if not token:
                    clean = symbol.replace("-", "").replace("&", "")
                    for key, val in nse_lookup.items():
                        if key.replace("-", "").replace("&", "") == clean:
                            token = val
                            break
                if token:
                    self.nse_tokens[symbol] = token
                    self.token_to_symbol[token] = symbol
                    matched += 1

            logger.info("  NSE token matching: %d/%d", matched, len(self.fno_stocks))

        except Exception as e:
            logger.warning("Failed to load NSE instruments: %s", e)

        logger.info("  F&O stocks: %d", len(self.fno_stocks))
        logger.info("  Hot list: %d active", len(self.active_hot))
        logger.info("  NSE tokens: %d mapped", len(self.nse_tokens))
        logger.info("  Option instruments: %d mapped", len(self.option_instruments))
        logger.info("  Actual strikes: %d symbols mapped", len(self.actual_strikes))

    def _build_option_lookup(self, instruments, fno_set):
        """Build lookup table and extract actual strikes per symbol."""
        option_map = defaultdict(list)
        strikes_map = defaultdict(set)
        today = date.today()

        for inst in instruments:
            if inst.get("segment") != "NFO-OPT":
                continue
            name = inst.get("name", "")
            if name not in fno_set:
                continue

            strike = inst.get("strike", 0)
            opt_type = inst.get("instrument_type", "")
            ts = inst.get("tradingsymbol", "")
            expiry = inst.get("expiry")
            token = inst.get("instrument_token", 0)

            if not (strike and opt_type in ("CE", "PE") and expiry and ts):
                continue

            if isinstance(expiry, datetime):
                expiry = expiry.date()

            strikes_map[name].add(int(strike))
            key = (name, int(strike), opt_type)
            option_map[key].append((expiry, ts, token))

        for key, entries in option_map.items():
            future = [(e, ts, t) for e, ts, t in entries if e >= today]
            if future:
                future.sort(key=lambda x: x[0])
                best = future[0]
                self.option_instruments[key] = {
                    "tradingsymbol": best[1],
                    "token": best[2],
                    "expiry": best[0],
                }

        for symbol, strike_set in strikes_map.items():
            self.actual_strikes[symbol] = sorted(strike_set)

        logger.info("  Option lookup: %d contracts mapped", len(self.option_instruments))

    # ── REAL PREMIUM FETCHING ─────────────────────

    def _get_real_premium(self, symbol, strike, option_type):
        """Fetch real option premium from Kite API."""
        key = (symbol, strike, option_type)
        opt = self.option_instruments.get(key)

        if not opt:
            actual = self.actual_strikes.get(symbol, [])
            if actual:
                nearest = min(actual, key=lambda s: abs(s - strike))
                alt_key = (symbol, nearest, option_type)
                opt = self.option_instruments.get(alt_key)
                if opt:
                    logger.debug("  Strike %d not found for %s, using nearest: %d",
                                 strike, symbol, nearest)

        if not opt:
            return None

        ts = opt["tradingsymbol"]
        full_sym = "NFO:{}".format(ts)

        try:
            ltp_data = self.kite.ltp([full_sym])
            time_mod.sleep(KITE_SLEEP)
            if full_sym in ltp_data:
                price = ltp_data[full_sym].get("last_price", 0)
                if price > 0:
                    self._real_premiums_fetched += 1
                    return float(price)
        except Exception as e:
            logger.debug("LTP fetch failed for %s: %s", full_sym, e)
            self._real_premiums_failed += 1

        return None

    def _get_real_premiums_batch(self, requests):
        """Batch fetch real option premiums."""
        results = {}
        sym_map = {}
        instruments = []

        for symbol, strike, option_type in requests:
            key = (symbol, strike, option_type)
            opt = self.option_instruments.get(key)

            if not opt:
                actual = self.actual_strikes.get(symbol, [])
                if actual:
                    nearest = min(actual, key=lambda s: abs(s - strike))
                    alt_key = (symbol, nearest, option_type)
                    opt = self.option_instruments.get(alt_key)
                    if opt:
                        key = alt_key

            if opt:
                full_sym = "NFO:{}".format(opt["tradingsymbol"])
                instruments.append(full_sym)
                sym_map[full_sym] = key

        if not instruments:
            return results

        try:
            ltp_data = self.kite.ltp(instruments)
            time_mod.sleep(KITE_SLEEP)
            for full_sym, key in sym_map.items():
                if full_sym in ltp_data:
                    price = ltp_data[full_sym].get("last_price", 0)
                    if price > 0:
                        results[key] = float(price)
                        self._real_premiums_fetched += 1
                    else:
                        self._real_premiums_failed += 1
                else:
                    self._real_premiums_failed += 1
        except Exception as e:
            logger.debug("Batch LTP fetch failed: %s", e)
            self._real_premiums_failed += len(instruments)

        return results

    # ── FAST RECALIBRATE (NEW) ────────────────────

    def _fast_recalibrate(self):
        """Fetch real option LTPs for open positions every 15 seconds."""
        open_pos = [p for p in self.positions if p.status == "OPEN"]
        if not open_pos:
            return

        requests = [(p.symbol, p.strike, p.option_type) for p in open_pos]
        real_prices = self._get_real_premiums_batch(requests)

        now_ts = datetime.now().timestamp()
        updated = 0
        for pos in open_pos:
            key = (pos.symbol, pos.strike, pos.option_type)
            if key in real_prices:
                pos.current_premium = round_to_tick(real_prices[key])
                pos._real_premium_time = now_ts
                updated += 1

        if updated > 0:
            logger.debug("Fast recalibrate: %d/%d positions updated with real premiums",
                         updated, len(open_pos))

    # ── HISTORICAL DATA ──────────────────────────

    def fetch_historical_data(self):
        logger.info("Fetching historical daily data...")
        end = datetime.now()
        start = end - timedelta(days=40)
        fetched = 0

        for symbol in self.fno_stocks:
            token = self.nse_tokens.get(symbol)
            if not token:
                continue
            try:
                raw = self.kite.historical_data(token, start, end, "day", oi=False)
                time_mod.sleep(KITE_SLEEP)

                if raw and len(raw) > 5:
                    candles = []
                    for r in raw:
                        dt = r["date"]
                        if hasattr(dt, "tzinfo") and dt.tzinfo:
                            dt = dt.replace(tzinfo=None)
                        candles.append({
                            "date": dt.date() if hasattr(dt, "date") else dt,
                            "open": float(r["open"]),
                            "high": float(r["high"]),
                            "low": float(r["low"]),
                            "close": float(r["close"]),
                            "volume": int(r.get("volume", 0)),
                        })
                    self.daily_candles_hist[symbol] = candles
                    vols = [c["volume"] for c in candles[-20:] if c["volume"] > 0]
                    if vols:
                        self.avg_volumes[symbol] = np.mean(vols)

                fetched += 1
                if fetched % 30 == 0:
                    logger.info("  Daily: %d/%d", fetched, len(self.fno_stocks))

            except Exception as e:
                logger.debug("  Daily error %s: %s", symbol, e)
                time_mod.sleep(KITE_SLEEP)

        logger.info("  Daily data: %d stocks", len(self.daily_candles_hist))
        logger.info("  Avg volumes: %d stocks", len(self.avg_volumes))

    # ── TICKER ────────────────────────────────────

    def start_ticker(self):
        logger.info("Starting KiteTicker...")
        tokens = list(self.nse_tokens.values())
        logger.info("  Subscribing to %d tokens", len(tokens))

        self.ticker = KiteTicker(config.KITE_API_KEY, config.KITE_ACCESS_TOKEN)

        def on_connect(ws, response):
            logger.info("  Ticker connected")
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_QUOTE, tokens)
            logger.info("  Subscribed to %d tokens in QUOTE mode", len(tokens))

        def on_ticks(ws, ticks):
            self.tick_count += len(ticks)
            now = datetime.now()

            for tick in ticks:
                token = tick.get("instrument_token", 0)
                symbol = self.token_to_symbol.get(token)
                if not symbol:
                    continue

                ltp = tick.get("last_price", 0)

                # Kite QUOTE mode field names
                volume = 0
                vol1 = tick.get("volume_traded", 0)
                if vol1 and vol1 > 0:
                    volume = vol1
                if volume == 0:
                    vol2 = tick.get("volume", 0)
                    if vol2 and vol2 > 0:
                        volume = vol2
                if volume == 0:
                    ohlc = tick.get("ohlc", {})
                    if isinstance(ohlc, dict):
                        vol3 = ohlc.get("volume", 0)
                        if vol3 and vol3 > 0:
                            volume = vol3
                if volume == 0:
                    buy_qty = tick.get("total_buy_quantity", 0)
                    sell_qty = tick.get("total_sell_quantity", 0)
                    if buy_qty > 0 and sell_qty > 0:
                        volume = buy_qty + sell_qty
                if volume == 0:
                    last_qty = tick.get("last_traded_quantity", 0)
                    if last_qty > 0:
                        volume = last_qty * 100

                if not self._sample_tick and ltp > 0:
                    self._sample_tick = dict(tick)
                    self._tick_volume_sample = volume

                if ltp > 0:
                    self.candle_builder.update(symbol, ltp, volume, now)

            self._process_candles()

            # NEW: Fast recalibrate real premiums every 15s
            now_ts = now.timestamp()
            if now_ts - self._last_fast_recalibrate >= FAST_RECAL_INTERVAL:
                self._fast_recalibrate()
                self._last_fast_recalibrate = now_ts

            self._update_positions_live()
            self._check_eod_exit()

            if now_ts - self.last_dashboard > DASHBOARD_INTERVAL:
                self._print_dashboard()
                self.last_dashboard = now_ts

        def on_connect_error(ws, code, msg):
            logger.error("Ticker error: %s %s", code, msg)

        def on_close(ws, code, msg):
            logger.warning("Ticker closed: %s %s", code, msg)

        def on_reconnect(ws, attempts_count):
            logger.info("Ticker reconnecting (attempt %d)", attempts_count)

        self.ticker.on_connect = on_connect
        self.ticker.on_ticks = on_ticks
        self.ticker.on_error = on_connect_error
        self.ticker.on_close = on_close
        self.ticker.on_reconnect = on_reconnect

        self.ticker.connect(threaded=True)
        logger.info("  Ticker thread started")

    # ── CANDLE PROCESSING ─────────────────────────

    def _process_candles(self):
        completed = self.candle_builder.flush_completed()
        for symbol, candle in completed:
            now = datetime.now()
            t = now.time()

            if t < SCAN_START or t > SCAN_END:
                continue
            if DEAD_ZONE_START <= t <= DEAD_ZONE_END:
                continue
            if t >= NO_NEW_AFTER:
                continue
            if self.circuit_breaker:
                continue
            if self.trades_today >= MAX_TRADES:
                continue

            state = self._build_state(symbol, now)
            if not state:
                continue

            market_avg = self._calc_market_avg(now)

            rsi_val = None
            daily = self.daily_candles_hist.get(symbol, [])
            if len(daily) > 15:
                closes = [d["close"] for d in daily]
                rsi_val = calc_rsi(closes)

            last = self.last_signal_time.get(symbol)
            if last:
                elapsed = (now - last).total_seconds() / 60
                if elapsed < COOLDOWN_MINUTES:
                    continue

            signal = self._detect_signal(symbol, state, rsi_val, market_avg)
            if signal:
                pos = self._open_trade(signal, now)
                if pos:
                    self.trades_today += 1
                    self._log_trade_open(pos)

    def _build_state(self, symbol, now):
        today = now.date()
        today_candles = self.candle_builder.get_today_candles(symbol, today)
        current = self.candle_builder.get_current(symbol)

        if current and current["bucket"].date() == today:
            pass
        else:
            if not today_candles:
                return None

        daily = self.daily_candles_hist.get(symbol, [])
        prev_close = 0
        if daily:
            if daily[-1]["date"] == today:
                if len(daily) >= 2:
                    prev_close = daily[-2]["close"]
            else:
                prev_close = daily[-1]["close"]

        if prev_close == 0:
            return None

        if not today_candles and not current:
            return None

        all_today = list(today_candles)
        if current and current["bucket"].date() == today:
            all_today.append({
                "dt": current["bucket"],
                "open": current["open"], "high": current["high"],
                "low": current["low"], "close": current["close"],
                "volume": current.get("cum_volume", 0),
                "cum_volume": current.get("cum_volume", 0),
            })

        if not all_today:
            return None

        ltp = all_today[-1]["close"]
        day_open = all_today[0]["open"]
        day_high = max(c["high"] for c in all_today)
        day_low = min(c["low"] for c in all_today)

        cum_volume = 0
        last_candle = all_today[-1]
        if isinstance(last_candle.get("cum_volume"), (int, float)) and last_candle["cum_volume"] > 0:
            cum_volume = last_candle["cum_volume"]
        else:
            cum_volume = last_candle.get("volume", 0)
        if cum_volume == 0 and current:
            cum_volume = current.get("cum_volume", current.get("volume", 0))

        mins = max((now.hour - 9) * 60 + (now.minute - 15), 1)

        return {
            "ltp": ltp, "prev_close": prev_close,
            "open": day_open, "high": day_high, "low": day_low,
            "volume": cum_volume, "minutes_elapsed": mins,
        }

    def _calc_market_avg(self, now):
        all_pct = []
        today = now.date()
        for symbol in self.fno_stocks:
            daily = self.daily_candles_hist.get(symbol, [])
            prev_close = 0
            if daily:
                if daily[-1]["date"] == today:
                    if len(daily) >= 2:
                        prev_close = daily[-2]["close"]
                else:
                    prev_close = daily[-1]["close"]
            if prev_close == 0:
                continue
            current = self.candle_builder.get_current(symbol)
            if current and current["bucket"].date() == today:
                pct = (current["close"] - prev_close) / prev_close * 100
                all_pct.append(pct)
        return float(np.mean(all_pct)) if all_pct else 0

    # ── SIGNAL DETECTION ─────────────────────────

    def _detect_signal(self, symbol, state, rsi_val, market_avg_pct):
        ltp = state["ltp"]
        prev_close = state["prev_close"]
        open_p = state["open"]
        high = state["high"]
        low = state["low"]
        volume = state["volume"]
        mins = state["minutes_elapsed"]

        if prev_close == 0 or open_p == 0 or ltp == 0:
            return None

        avg_vol = self.avg_volumes.get(symbol, 0)
        vol_ratio = volume_ratio_fn(volume, avg_vol, mins)
        pos = price_position_fn(high, low, ltp)
        pct_from_prev = (ltp - prev_close) / prev_close * 100
        pct_from_open = (ltp - open_p) / open_p * 100
        vol_tier = self._vol_tier(vol_ratio)
        is_hot = symbol in self.active_hot
        relative_strength = pct_from_prev - market_avg_pct

        signal = None

        # PATTERN 1: Gap & Go
        if pct_from_prev > GAP_GO_MIN_GAP_PCT and vol_ratio >= GAP_GO_MIN_VOL and ltp > open_p:
            base = 0.56
            if pct_from_prev > 3.0: base += 0.05
            if pct_from_prev > 4.0: base += 0.05
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_CE")
            signal = ("BUY_CE", "Gap & Go", conf, "Gap +{:.1f}%, vol {:.1f}x".format(pct_from_prev, vol_ratio))

        # PATTERN 2: Gap & Fall
        elif pct_from_prev < -GAP_GO_MIN_GAP_PCT and vol_ratio >= GAP_GO_MIN_VOL and ltp < open_p:
            base = 0.56
            if pct_from_prev < -3.0: base += 0.05
            if pct_from_prev < -4.0: base += 0.05
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_PE")
            signal = ("BUY_PE", "Gap & Fall", conf, "Gap {:.1f}%, vol {:.1f}x".format(pct_from_prev, vol_ratio))

        # PATTERN 3: Volume Spike
        elif vol_ratio >= VOL_EXTREME:
            if pct_from_prev > 0.5 and ltp > open_p:
                conf = self._confidence(0.60, vol_ratio, rsi_val, symbol, "EXTREME", "BUY_CE")
                signal = ("BUY_CE", "Volume Spike (Bull)", conf, "EXTREME vol {:.1f}x".format(vol_ratio))
            elif pct_from_prev < -0.5 and ltp < open_p:
                conf = self._confidence(0.60, vol_ratio, rsi_val, symbol, "EXTREME", "BUY_PE")
                signal = ("BUY_PE", "Volume Spike (Bear)", conf, "EXTREME vol {:.1f}x".format(vol_ratio))

        # PATTERN 4: Early Momentum
        elif pct_from_open > MIN_MOMENTUM_PCT and pos > 0.70 and vol_ratio >= VOL_MULTIPLIER * 0.8:
            base = 0.54
            if pos > 0.85: base += 0.03
            if pct_from_open > 2.0: base += 0.03
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_CE")
            signal = ("BUY_CE", "Early Momentum (Up)", conf, "Intraday +{:.1f}%".format(pct_from_open))

        elif pct_from_open < -MIN_MOMENTUM_PCT and pos < 0.30 and vol_ratio >= VOL_MULTIPLIER * 0.8:
            base = 0.54
            if pos < 0.15: base += 0.03
            if pct_from_open < -2.0: base += 0.03
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_PE")
            signal = ("BUY_PE", "Early Momentum (Down)", conf, "Intraday {:.1f}%".format(pct_from_open))

        # PATTERN 5: Relative Strength/Weakness
        elif relative_strength > 2.5 and pct_from_prev > 0.5 and ltp > open_p and vol_ratio >= VOL_MULTIPLIER * 0.7:
            base = 0.52 + (0.05 if relative_strength > 4.0 else 0)
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_CE")
            signal = ("BUY_CE", "Rel Strength (Bull)", conf, "Outperforming {:+.1f}%".format(relative_strength))

        elif relative_strength < -2.5 and pct_from_prev < -0.5 and ltp < open_p and vol_ratio >= VOL_MULTIPLIER * 0.7:
            base = 0.52 + (0.05 if relative_strength < -4.0 else 0)
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_PE")
            signal = ("BUY_PE", "Rel Weakness (Bear)", conf, "Underperforming {:.1f}%".format(relative_strength))

        # PATTERN 6: Oversold Bounce
        elif rsi_val is not None and rsi_val < RSI_OVERSOLD and pct_from_prev > 0.2 and ltp > open_p and vol_ratio > 0.8:
            base = 0.54 + (0.06 if rsi_val < 25 else 0.03 if rsi_val < 30 else 0)
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_CE")
            signal = ("BUY_CE", "Oversold Bounce", conf, "RSI {:.0f}".format(rsi_val))

        # PATTERN 7: Overbought Reversal
        elif rsi_val is not None and rsi_val > RSI_OVERBOUGHT and pct_from_prev < -0.2 and ltp < open_p and vol_ratio > 0.8:
            base = 0.54 + (0.06 if rsi_val > 80 else 0.03 if rsi_val > 75 else 0)
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_PE")
            signal = ("BUY_PE", "Overbought Reversal", conf, "RSI {:.0f}".format(rsi_val))

        # PATTERN 8: Green/Red Building
        elif pct_from_prev > 1.0 and ltp > open_p and pos > 0.60 and vol_ratio >= VOL_MULTIPLIER:
            base = 0.52 + (0.04 if pct_from_prev > 2.0 else 0)
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_CE")
            signal = ("BUY_CE", "Green Building", conf, "Building +{:.1f}%".format(pct_from_prev))

        elif pct_from_prev < -1.0 and ltp < open_p and pos < 0.40 and vol_ratio >= VOL_MULTIPLIER:
            base = 0.52 + (0.04 if pct_from_prev < -2.0 else 0)
            conf = self._confidence(base, vol_ratio, rsi_val, symbol, vol_tier, "BUY_PE")
            signal = ("BUY_PE", "Red Building", conf, "Building {:.1f}%".format(pct_from_prev))

        # PATTERN 9: Hot List Continuation
        elif is_hot and vol_ratio >= VOL_HIGH:
            dc = self.daily_candles_hist.get(symbol, [])
            recent_3d = 0
            if len(dc) >= 4 and dc[-4]["close"] > 0:
                recent_3d = (dc[-1]["close"] - dc[-4]["close"]) / dc[-4]["close"] * 100
            if recent_3d > 1.5 and pct_from_prev > 0.3 and ltp > open_p:
                conf = self._confidence(0.52, vol_ratio, rsi_val, symbol, vol_tier, "BUY_CE")
                signal = ("BUY_CE", "Hot Continuation (Bull)", conf, "Hot stock, 3d +{:.1f}%".format(recent_3d))
            elif recent_3d < -1.5 and pct_from_prev < -0.3 and ltp < open_p:
                conf = self._confidence(0.52, vol_ratio, rsi_val, symbol, vol_tier, "BUY_PE")
                signal = ("BUY_PE", "Hot Continuation (Bear)", conf, "Hot stock, 3d {:.1f}%".format(recent_3d))

        # APPLY FILTERS
        if signal and signal[2] >= 0.52:
            pattern_name = signal[1]
            if pattern_name in PATTERN_FILTER and not PATTERN_FILTER[pattern_name]:
                return None
            if MARKET_REGIME_ENABLED:
                if signal[0] == "BUY_CE" and market_avg_pct < MARKET_CE_BLOCK:
                    return None
                if signal[0] == "BUY_PE" and market_avg_pct > MARKET_PE_BLOCK:
                    return None
            return {
                "symbol": symbol, "direction": signal[0],
                "pattern": pattern_name, "confidence": signal[2],
                "reason": signal[3], "price": ltp,
                "vol_ratio": vol_ratio, "vol_tier": vol_tier,
            }
        return None

    def _vol_tier(self, vol_ratio):
        if vol_ratio >= VOL_EXTREME: return "EXTREME"
        elif vol_ratio >= VOL_HIGH: return "HIGH"
        elif vol_ratio >= VOL_NORMAL: return "NORMAL"
        return "LOW"

    def _confidence(self, base, vol_ratio, rsi_val, symbol, vol_tier, direction):
        conf = base
        if vol_tier == "EXTREME": conf += 0.10
        elif vol_tier == "HIGH": conf += 0.05
        elif vol_tier == "NORMAL": conf += 0.02

        if rsi_val:
            if direction == "BUY_CE" and rsi_val < 35: conf += 0.05
            elif direction == "BUY_PE" and rsi_val > 65: conf += 0.05
            elif direction == "BUY_CE" and rsi_val < 45: conf += 0.02
            elif direction == "BUY_PE" and rsi_val > 55: conf += 0.02

        if symbol in self.active_hot: conf += 0.05
        conf += DAY_BONUS.get(datetime.now().strftime("%A"), 0)
        return round(min(conf, 0.95), 2)

    # ── TRADE MANAGEMENT ──────────────────────────

    def _open_trade(self, signal, current_time):
        if self.circuit_breaker:
            return None
        if self.trades_today >= MAX_TRADES:
            return None

        open_count = sum(1 for p in self.positions if p.status == "OPEN")
        if open_count >= MAX_OPEN:
            return None

        for p in self.positions:
            if p.symbol == signal["symbol"]:
                return None
        for p in self.closed:
            if p.symbol == signal["symbol"]:
                return None

        sector = config.get_sector(signal["symbol"])
        same_sector = sum(
            1 for p in self.positions
            if p.status == "OPEN" and config.get_sector(p.symbol) == sector
        )
        if same_sector >= 2:
            return None

        max_loss = CAPITAL * MAX_DAILY_LOSS_PCT / 100
        if self.daily_pnl < -max_loss:
            self.circuit_breaker = True
            return None

        stock_price = signal["price"]
        if stock_price < MIN_STOCK_PRICE:
            return None

        option_type = "CE" if signal["direction"] == "BUY_CE" else "PE"

        # Use ACTUAL NFO strikes
        strike = find_atm_strike(stock_price, signal["symbol"], self.actual_strikes)
        lot_size = self.lot_sizes.get(signal["symbol"], 1)

        # Fetch REAL premium from Kite API
        real_premium = self._get_real_premium(signal["symbol"], strike, option_type)

        if real_premium and real_premium > 0:
            premium = round_to_tick(real_premium * (1 + ENTRY_SLIP))
            premium_source = "real"
        else:
            premium = estimate_entry_premium(stock_price)
            premium_source = "estimated"

        if premium < MIN_PREMIUM:
            return None
        if premium > PREMIUM_CAP:
            return None

        if signal["pattern"] == "Gap & Go" and self.gap_go_today >= GAP_GO_MAX_SAME_DAY:
            return None

        max_capital = CAPITAL * MAX_RISK_PCT / 100
        quantity = max(1, int(max_capital / (premium * lot_size)))

        stop_loss = round_to_tick(premium * (1 - SL_PCT / 100))
        target = round_to_tick(premium * (1 + TARGET_PCT / 100))

        delta = 0.50
        daily_theta = premium * DAILY_THETA_PCT
        theta_per_min = daily_theta / 375.0

        # Use actual tradingsymbol from option lookup
        opt_info = self.option_instruments.get((signal["symbol"], strike, option_type))
        if not opt_info:
            actual = self.actual_strikes.get(signal["symbol"], [])
            if actual:
                nearest = min(actual, key=lambda s: abs(s - strike))
                opt_info = self.option_instruments.get((signal["symbol"], nearest, option_type))

        if opt_info:
            option_symbol = opt_info["tradingsymbol"]
        else:
            month_str = current_time.strftime("%b").upper()
            year_str = current_time.strftime("%y")
            option_symbol = "{}{}{}{}{}".format(
                signal["symbol"], year_str, month_str, strike, option_type)

        self._id += 1
        pos = Position(
            id=self._id,
            symbol=signal["symbol"],
            direction=signal["direction"],
            pattern=signal["pattern"],
            strike=strike,
            option_type=option_type,
            option_symbol=option_symbol,
            entry_premium=premium,
            entry_stock_price=stock_price,
            entry_time=current_time,
            quantity=quantity,
            lot_size=lot_size,
            stop_loss=stop_loss,
            target=target,
            delta=delta,
            theta_per_min=theta_per_min,
            confidence=signal["confidence"],
            reason=signal["reason"],
            premium_source=premium_source,
            current_premium=premium,
            current_stock=stock_price,
        )

        self.positions.append(pos)
        self.last_signal_time[signal["symbol"]] = current_time
        if signal["pattern"] == "Gap & Go":
            self.gap_go_today += 1

        return pos

    # ── POSITION UPDATE (REWRITTEN) ───────────────

    def _update_positions_live(self):
        """
        Position management with:
        - Real premium priority (from fast recalibrate)
        - Profit lock (75% trigger → 40% SL floor)
        - Trailing stop
        - Time-based SL tightening
        """
        now = datetime.now()

        for pos in self.positions:
            if pos.status != "OPEN":
                continue

            # ── Update stock price (always from candle builder) ──
            current = self.candle_builder.get_current(pos.symbol)
            if current:
                pos.current_stock = current["close"]

            # ── Update premium: real if fresh, otherwise model ──
            real_age = now.timestamp() - pos._real_premium_time

            if real_age <= 20:
                # Real premium is fresh (set by _fast_recalibrate)
                # Don't overwrite with model — pos.current_premium is already real
                pass
            else:
                # Real premium is stale — use delta-theta model
                ltp = pos.current_stock
                if ltp <= 0:
                    continue

                stock_move = ltp - pos.entry_stock_price
                minutes_held = (now - pos.entry_time).total_seconds() / 60

                if pos.direction == "BUY_CE":
                    delta_effect = pos.delta * stock_move
                else:
                    delta_effect = pos.delta * (-stock_move)

                if pos.entry_stock_price > 0:
                    pct_move = abs(stock_move / pos.entry_stock_price)
                    if pct_move > 0.01:
                        gamma_boost = abs(delta_effect) * 0.10
                        if (pos.direction == "BUY_CE" and stock_move > 0) or \
                           (pos.direction == "BUY_PE" and stock_move < 0):
                            delta_effect += gamma_boost

                theta_effect = pos.theta_per_min * minutes_held
                pos.current_premium = max(
                    pos.entry_premium + delta_effect - theta_effect, 0.05
                )
                pos.current_premium = round_to_tick(pos.current_premium)

            pnl_pct = pos.pnl_pct

            # ── 1. Profit lock activation (NEW) ──
            # When premium reaches 75% of target distance,
            # lock SL at 40% of target distance above entry
            if not pos.profit_lock_active:
                target_dist = pos.target - pos.entry_premium
                if target_dist > 0:
                    current_profit = pos.current_premium - pos.entry_premium
                    if current_profit >= PROFIT_LOCK_TRIGGER * target_dist:
                        lock_sl = round_to_tick(
                            pos.entry_premium + PROFIT_LOCK_FLOOR * target_dist
                        )
                        if lock_sl > pos.stop_loss:
                            pos.profit_lock_active = True
                            pos.profit_lock_sl = lock_sl
                            pos.stop_loss = lock_sl
                            print()
                            print("  {}{}PROFIT LOCK #{}{} {} | "
                                  "Premium Rs.{:.2f} ({:.0f}% of target) | "
                                  "SL locked at Rs.{:.2f}{}".format(
                                      Y, B, pos.id, D, pos.option_symbol,
                                      pos.current_premium,
                                      PROFIT_LOCK_TRIGGER * 100,
                                      lock_sl, D))
                            logger.info(
                                "PROFIT LOCK #%d %s: premium %.2f "
                                "(%.0f%% of target %.2f) -> SL locked at %.2f",
                                pos.id, pos.symbol, pos.current_premium,
                                PROFIT_LOCK_TRIGGER * 100, pos.target, lock_sl,
                            )

            # ── 2. Trailing stop update ──
            if pnl_pct >= TRAIL_ACTIVATE and not pos.trailing_active:
                pos.trailing_active = True
                pos.trailing_sl = round_to_tick(
                    pos.current_premium * (1 - TRAIL_STOP / 100)
                )

            if pos.trailing_active:
                new_trail = round_to_tick(
                    pos.current_premium * (1 - TRAIL_STOP / 100)
                )
                if new_trail > pos.trailing_sl:
                    pos.trailing_sl = new_trail

            # ── 3. Determine effective SL (highest protection) ──
            effective_sl = pos.stop_loss
            sl_reason = "Profit Lock" if pos.profit_lock_active else "Stop Loss"

            if pos.trailing_active and pos.trailing_sl > effective_sl:
                effective_sl = pos.trailing_sl
                sl_reason = "Trailing Stop"

            # ── 4. Close checks ──
            if pos.current_premium <= effective_sl:
                self._close(pos, effective_sl, sl_reason, now)
                self._log_trade_close(pos)
                continue

            if pos.current_premium >= pos.target:
                self._close(pos, pos.target, "Target Hit", now)
                self._log_trade_close(pos)
                continue

            # ── 5. Afternoon SL tightening ──
            if now.time() >= dt_time(13, 30):
                afternoon_sl = round_to_tick(pos.entry_premium * (1 - 10 / 100))
                if afternoon_sl > pos.stop_loss:
                    pos.stop_loss = afternoon_sl

    def _check_eod_exit(self):
        now = datetime.now()
        if now.time() < EOD_EXIT:
            return
        for pos in self.positions:
            if pos.status == "OPEN":
                self._close(pos, pos.current_premium, "EOD Exit", now)
                self._log_trade_close(pos)

    def _close(self, pos, exit_premium, reason, current_time):
        real_exit = self._get_real_premium(pos.symbol, pos.strike, pos.option_type)
        if real_exit and real_exit > 0:
            actual_exit = round_to_tick(real_exit * (1 - EXIT_SLIP))
        else:
            actual_exit = estimate_exit_premium(exit_premium)

        pos.status = "CLOSED"
        pos.exit_premium = actual_exit
        pos.exit_reason = reason
        pos.exit_time = current_time

        gross = (actual_exit - pos.entry_premium) * pos.quantity * pos.lot_size
        pos.pnl = gross - BROKERAGE

        self.daily_pnl += pos.pnl
        self.closed.append(pos)
        self.all_trades.append(pos)

    # ── LOGGING ───────────────────────────────────

    def _log_trade_open(self, pos):
        tag = G if pos.direction == "BUY_CE" else C
        source_tag = "(REAL)" if pos.premium_source == "real" else "(EST)"

        print()
        print("  {} {}NEW TRADE #{}{} {} {} @ Rs.{:.2f} {}{}{}".format(
            tag, B, pos.id, D, pos.option_type, pos.option_symbol,
            pos.entry_premium, Y, source_tag, D))
        print("    {} | {} | Conf: {}".format(pos.pattern, pos.reason, pos.confidence))
        print("    Entry: Rs.{:.2f} | SL: Rs.{:.2f} | Target: Rs.{:.2f}".format(
            pos.entry_premium, pos.stop_loss, pos.target))
        print("    Qty: {} ({} lots x {})".format(
            pos.quantity * pos.lot_size, pos.quantity, pos.lot_size))
        print()

        logger.info(
            "OPEN #%d %s %s %s @ %.2f %s | SL %.2f | Target %.2f | Qty %d | %s",
            pos.id, pos.option_type, pos.symbol, pos.pattern,
            pos.entry_premium, source_tag, pos.stop_loss, pos.target,
            pos.quantity * pos.lot_size, pos.reason,
        )

    def _log_trade_close(self, pos):
        tag = G if pos.pnl > 0 else R
        print()
        print("  {} {}CLOSE #{}{} {} | {} | P&L: {}Rs.{:+,.0f}{}".format(
            tag, B, pos.id, D, pos.option_symbol,
            pos.exit_reason, tag, pos.pnl, D))
        print("    Entry: Rs.{:.2f} -> Exit: Rs.{:.2f} | Held: {:.0f}m".format(
            pos.entry_premium, pos.exit_premium, pos.hold_min))
        print()

        logger.info(
            "CLOSE #%d %s %s | %s | P&L Rs.%+.0f | Entry %.2f -> Exit %.2f | %.0fm",
            pos.id, pos.option_type, pos.symbol, pos.exit_reason,
            pos.pnl, pos.entry_premium, pos.exit_premium, pos.hold_min,
        )

    # ══════════════════════════════════════════════
    #  DASHBOARD
    # ══════════════════════════════════════════════

    def _print_dashboard(self):
        now = datetime.now()
        open_pos = [p for p in self.positions if p.status == "OPEN"]
        total_unrealized = sum(p.unrealized for p in open_pos)

        print()
        print(M + "  " + "=" * 70)
        print("  DASHBOARD {} | Ticks: {} | Trades: {} | P&L: Rs.{:+,.0f}".format(
            now.strftime("%H:%M:%S"), self.tick_count,
            self.trades_today, self.daily_pnl))
        print("  " + "=" * 70 + D)

        # Real premium stats
        total_fetches = self._real_premiums_fetched + self._real_premiums_failed
        if total_fetches > 0:
            success_rate = self._real_premiums_fetched / total_fetches * 100
            print("  {}Premium source: REAL (fetches: {}, success: {:.0f}%, fallback: {}){}".format(
                G if success_rate > 80 else Y,
                self._real_premiums_fetched, success_rate,
                self._real_premiums_failed, D))

        # Tick format diagnostic (once)
        if self._sample_tick:
            st = self._sample_tick
            print("  {}TICK FORMAT (first tick):{}".format(C, D))
            print("    Keys: {}".format(sorted(st.keys())))
            vol_fields = {}
            for k in ("volume_traded", "volume", "last_traded_quantity",
                       "total_buy_quantity", "total_sell_quantity"):
                val = st.get(k)
                if val is not None:
                    vol_fields[k] = val
            print("    Volume fields: {}".format(vol_fields))
            if self._tick_volume_sample is not None:
                print("    Extracted volume: {} {}".format(
                    self._tick_volume_sample,
                    "(OK)" if self._tick_volume_sample > 0 else "(ZERO!)"))
            self._sample_tick = None

        # Top gappers
        if now.time() >= SCAN_START and now.time() <= SCAN_END:
            gappers = []
            for symbol in self.fno_stocks:
                daily = self.daily_candles_hist.get(symbol, [])
                if not daily:
                    continue
                if daily[-1]["date"] == now.date():
                    prev = daily[-2]["close"] if len(daily) >= 2 else 0
                else:
                    prev = daily[-1]["close"]
                if prev == 0:
                    continue
                current = self.candle_builder.get_current(symbol)
                if not current or current["bucket"].date() != now.date():
                    continue
                ltp = current["close"]
                gap_pct = (ltp - prev) / prev * 100
                if abs(gap_pct) > 1.0:
                    avg_vol = self.avg_volumes.get(symbol, 0)
                    mins = (now.hour - 9) * 60 + (now.minute - 15)
                    cum_vol = current.get("cum_volume", current.get("volume", 0))
                    vr = volume_ratio_fn(cum_vol, avg_vol, max(mins, 1))
                    block_reason = None
                    if vr == 0 and avg_vol == 0:
                        block_reason = "no avg vol data"
                    elif vr == 0:
                        block_reason = "no tick vol (cum={})".format(cum_vol)
                    elif abs(gap_pct) >= GAP_GO_MIN_GAP_PCT and gap_pct > 0 and ltp <= current["open"]:
                        block_reason = "price {:.1f} < open {:.1f}".format(ltp, current["open"])
                    elif abs(gap_pct) >= GAP_GO_MIN_GAP_PCT and gap_pct < 0 and ltp >= current["open"]:
                        block_reason = "price {:.1f} > open {:.1f}".format(ltp, current["open"])
                    elif abs(gap_pct) >= GAP_GO_MIN_GAP_PCT and vr < GAP_GO_MIN_VOL:
                        block_reason = "vol {:.1f}x < {:.1f}x".format(vr, GAP_GO_MIN_VOL)
                    gappers.append((symbol, gap_pct, vr, block_reason, cum_vol, avg_vol))

            if gappers:
                gappers.sort(key=lambda x: -abs(x[1]))
                print("  {}TOP GAPPERS (>1%):{}".format(C, D))
                print("  {:<14} {:>8} {:>8} {:>12} {:>12} {:<25}".format(
                    "Symbol", "Gap%", "Vol", "DayVol", "AvgVol", "Status"))
                print("  " + "-" * 80)
                for sym, gap, vr, block, cum_v, avg_v in gappers[:8]:
                    if block:
                        print("  {:<14} {:>+7.2f}% {:>6.1f}x {:>12,} {:>12,.0f} {}BLOCKED:{} {}".format(
                            sym, gap, vr, cum_v, avg_v, R, D, block))
                    else:
                        print("  {:<14} {:>+7.2f}% {:>6.1f}x {:>12,} {:>12,.0f} {}OK{}".format(
                            sym, gap, vr, cum_v, avg_v, G, D))
            else:
                print("  {}No stocks with >1% gap today{}".format(Y, D))

        # Open positions
        if open_pos:
            print("  {}OPEN ({}):{}".format(Y, len(open_pos), D))
            hdr = "  {:<4} {:<22} {:<4} {:>8} {:>8} {:>8} {:>8} {:>10} {:>8}"
            print(hdr.format("#", "Contract", "Dir", "Entry", "Now", "SL", "Target", "P&L", "Protect"))
            print("  " + "-" * 82)
            for p in open_pos:
                tag = G if p.unrealized > 0 else R
                # Show premium source: * = real (fresh), ~ = model
                real_fresh = (now.timestamp() - p._real_premium_time) < 20
                src = "*" if real_fresh else "~"
                # Show protection type
                protect = ""
                if p.profit_lock_active:
                    protect = "PLock"
                elif p.trailing_active:
                    protect = "Trail"
                else:
                    protect = "SL"
                print(hdr.format(
                    p.id, p.option_symbol + src, p.option_type,
                    "{:.2f}".format(p.entry_premium),
                    "{:.2f}".format(p.current_premium),
                    "{:.2f}".format(p.stop_loss),
                    "{:.2f}".format(p.target),
                    "{}{:+,.0f}{}".format(tag, p.unrealized, D),
                    protect,
                ))
            print("  {}  * = real premium (fresh), ~ = model estimate{}".format(Y, D))
            print("  {}  Protect: PLock=Profit Lock, Trail=Trailing, SL=Stop Loss{}".format(Y, D))
        else:
            print("  No open positions")

        if self.closed:
            print("  {}CLOSED ({}):{}".format(Y, len(self.closed), D))
            for p in self.closed:
                tag = G if p.pnl > 0 else R
                print("    {}#{} {} P&L: Rs.{:+,.0f}{} | {}->{} | {}".format(
                    tag, p.id, p.option_symbol, p.pnl, D,
                    p.entry_time.strftime("%H:%M"),
                    p.exit_time.strftime("%H:%M") if p.exit_time else "",
                    p.exit_reason))

        if self.circuit_breaker:
            print("  {}CIRCUIT BREAKER ACTIVE{}".format(R, D))

        print(M + "  " + "=" * 70 + D)
        print()

        # Save summary
        summary = {
            "time": now.isoformat(),
            "daily_pnl": self.daily_pnl,
            "trades_today": self.trades_today,
            "open_positions": len(open_pos),
            "unrealized": total_unrealized,
            "circuit_breaker": self.circuit_breaker,
            "real_premiums_fetched": self._real_premiums_fetched,
            "real_premiums_failed": self._real_premiums_failed,
        }
        try:
            with open(os.path.join(LOG_DIR, "paper_v2_status.json"), "w") as f:
                json.dump(summary, f, indent=2)
        except Exception:
            pass

    # ── DAILY RECAP ───────────────────────────────

    def _print_daily_recap(self):
        if not self.all_trades:
            return
        print()
        print(M + "=" * 80)
        print("  DAILY RECAP — {}".format(date.today()))
        print("=" * 80 + D)

        n = len(self.all_trades)
        wins = [t for t in self.all_trades if t.pnl > 0]
        losses = [t for t in self.all_trades if t.pnl <= 0]

        print("  Trades: {} | Wins: {} ({:.0f}%) | P&L: {}Rs.{:+,.0f}{}".format(
            n, len(wins), len(wins) / n * 100 if n else 0,
            G if self.daily_pnl >= 0 else R, self.daily_pnl, D))

        if wins:
            print("  Avg Win: Rs.{:+,.0f}".format(np.mean([t.pnl for t in wins])))
        if losses:
            print("  Avg Loss: Rs.{:+,.0f}".format(np.mean([t.pnl for t in losses])))

        print("  Real premiums: {} fetched, {} failed".format(
            self._real_premiums_fetched, self._real_premiums_failed))

        # Profit lock stats
        pl_count = sum(1 for t in self.all_trades if t.profit_lock_active)
        if pl_count > 0:
            pl_wins = sum(1 for t in self.all_trades if t.profit_lock_active and t.pnl > 0)
            print("  Profit lock: {} activated, {} won ({:.0f}%)".format(
                pl_count, pl_wins, pl_wins / pl_count * 100 if pl_count else 0))

        print()
        for t in self.all_trades:
            tag = G if t.pnl > 0 else R
            src = "REAL" if t.premium_source == "real" else "EST"
            protect = ""
            if t.profit_lock_active:
                protect = " [PLOCK]"
            elif t.trailing_active:
                protect = " [TRAIL]"
            print("  {}{} {} | {} | {} | {}{} | P&L: Rs.{:+,.0f}{}".format(
                tag, t.option_symbol, t.direction, t.pattern,
                t.exit_reason, src, protect, t.pnl, D))

        print(M + "=" * 80 + D)
        print()

        logger.info("DAILY RECAP: %d trades | %d wins | P&L Rs.%+.0f | Real: %d fetched | ProfitLock: %d",
                     n, len(wins), self.daily_pnl, self._real_premiums_fetched,
                     sum(1 for t in self.all_trades if t.profit_lock_active))

    # ── MAIN LOOP ─────────────────────────────────

    def run(self):
        now = datetime.now()
        print()
        print(M + "=" * 80)
        print("  OPTIONS INTRADAY PAPER TRADER V2")
        print("  Real-time paper trading with V4 backtester filters")
        print("  Date: {}".format(now.strftime("%Y-%m-%d %H:%M:%S")))
        print("  Capital: Rs.{:,} | SL: {}% | Target: {}%".format(
            CAPITAL, SL_PCT, TARGET_PCT))
        print("  Max trades/day: {} | Max open: {}".format(MAX_TRADES, MAX_OPEN))
        print("  Min premium: Rs.{} | Min stock price: Rs.{}".format(MIN_PREMIUM, MIN_STOCK_PRICE))
        print("  Gap & Go: {}% gap + {}x vol | Max {}/day".format(
            GAP_GO_MIN_GAP_PCT, GAP_GO_MIN_VOL, GAP_GO_MAX_SAME_DAY))
        print("  Market regime: ON (CE<{}% blocked, PE>{}% blocked)".format(
            MARKET_CE_BLOCK, MARKET_PE_BLOCK))
        print("  {}Premium source: Kite LTP API (real prices){}".format(G, D))
        print("  {}Strike source: Actual NFO instrument data{}".format(G, D))
        print("  {}Tick rounding: NSE 0.05{}".format(G, D))
        print("  {}Market settle: 30 min (scan starts 09:45){}".format(G, D))
        print("  {}Profit Lock: {}% trigger -> {}% SL floor{}".format(
            G, int(PROFIT_LOCK_TRIGGER * 100), int(PROFIT_LOCK_FLOOR * 100), D))
        print("  {}Fast Recalibrate: every {}s (real premium for SL checks){}".format(
            G, FAST_RECAL_INTERVAL, D))

        active_pats = [k for k, v in PATTERN_FILTER.items() if v]
        print("  Active patterns: {}".format(", ".join(active_pats)))
        print("=" * 80 + D)
        print()

        self.connect()
        self.load_instruments()
        self.fetch_historical_data()

        if not self.nse_tokens:
            logger.error("No NSE tokens found!")
            return

        self.start_ticker()

        logger.info("Waiting for market open...")
        self.running = True

        try:
            while self.running:
                time_mod.sleep(1)
                now = datetime.now()
                if now.time() > MARKET_CLOSE:
                    logger.info("Market closed")
                    self._print_daily_recap()
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self._print_daily_recap()
        finally:
            if self.ticker:
                try:
                    self.ticker.close()
                except Exception:
                    pass
            logger.info("Paper trader stopped")


# ══════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    trader = OptionsIntradayPaperTrader()
    trader.run()