"""Market Overview page data layer — candlestick bars, ticker quotes, market
status, and PSX helpers. Mirrors pages/3_Market_Overview.py function-for-function
so the numbers/behavior stay identical to the Streamlit app.
"""
import datetime
import os
import time

import numpy as np
import pandas as pd
import requests

ALPACA_DATA_URL = "https://data.alpaca.markets/v2"
CACHE_TTL_SECONDS = 900  # matches the 15-min IEX delay — no point refreshing faster
PSX_SNAPSHOT_TTL_SECONDS = 60
PSX_OHLCV_TTL_SECONDS = 86400

_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str, ttl: int = CACHE_TTL_SECONDS):
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > ttl:
        return None
    return value


def _cache_set(key: str, value):
    _cache[key] = (time.time(), value)


# ==============================================================================
# MARKET STATUS
# ==============================================================================

_NYSE_HOLIDAYS_2026 = {
    datetime.date(2026, 1, 1), datetime.date(2026, 1, 19), datetime.date(2026, 2, 16),
    datetime.date(2026, 4, 3), datetime.date(2026, 5, 25), datetime.date(2026, 6, 19),
    datetime.date(2026, 7, 3), datetime.date(2026, 9, 7), datetime.date(2026, 11, 26),
    datetime.date(2026, 12, 25),
}
_NYSE_HOLIDAYS_2025 = {
    datetime.date(2025, 1, 1), datetime.date(2025, 1, 20), datetime.date(2025, 2, 17),
    datetime.date(2025, 4, 18), datetime.date(2025, 5, 26), datetime.date(2025, 6, 19),
    datetime.date(2025, 7, 4), datetime.date(2025, 9, 1), datetime.date(2025, 11, 27),
    datetime.date(2025, 12, 25),
}
NYSE_HOLIDAYS = _NYSE_HOLIDAYS_2025 | _NYSE_HOLIDAYS_2026


def market_status() -> dict:
    import pytz
    et = pytz.timezone("America/New_York")
    now_et = datetime.datetime.now(et)
    today = now_et.date()

    def is_trading_day(d: datetime.date) -> bool:
        return d.weekday() < 5 and d not in NYSE_HOLIDAYS

    last_open = today
    while not is_trading_day(last_open):
        last_open -= datetime.timedelta(days=1)

    open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    if is_trading_day(today) and open_time <= now_et < close_time:
        return dict(is_open=True, label="Market Open", color="#00C853", last_open=str(last_open))
    elif is_trading_day(today) and now_et < open_time:
        return dict(is_open=False, label="Pre-Market", color="#FFB300", last_open=str(last_open))
    elif is_trading_day(today) and now_et >= close_time:
        return dict(is_open=False, label="After Hours", color="#FFB300", last_open=str(last_open))
    else:
        return dict(is_open=False, label="Market Closed", color="#FF3D00", last_open=str(last_open))


def psx_market_status() -> dict:
    import pytz
    pkt = pytz.timezone("Asia/Karachi")
    now_pkt = datetime.datetime.now(pkt)
    today = now_pkt.date()

    open_time = now_pkt.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now_pkt.replace(hour=15, minute=30, second=0, microsecond=0)
    is_weekday = today.weekday() < 5

    if is_weekday and open_time <= now_pkt < close_time:
        return dict(is_open=True, label="PSX Open", color="#00C853")
    elif is_weekday and now_pkt < open_time:
        return dict(is_open=False, label="Pre-Market", color="#FFB300")
    elif is_weekday and now_pkt >= close_time:
        return dict(is_open=False, label="After Hours", color="#FFB300")
    else:
        return dict(is_open=False, label="PSX Closed", color="#FF3D00")


# ==============================================================================
# US DATA FETCHING (Alpaca -> fallback to synthetic)
# ==============================================================================

def _alpaca_headers():
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret, "accept": "application/json"}


def fetch_bars_alpaca(symbol: str, timeframe: str = "1Min", limit: int = 120) -> pd.DataFrame | None:
    cache_key = f"candles:{symbol}:{timeframe}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = _alpaca_headers()
    if headers is None:
        return None

    end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(days=14)
    params = {
        "timeframe": timeframe,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": limit,
        "feed": "iex",
        "sort": "desc",
    }
    try:
        resp = requests.get(f"{ALPACA_DATA_URL}/stocks/{symbol}/bars", headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        bars = resp.json().get("bars", [])
        if not bars:
            return None
        df = pd.DataFrame(bars)
        df.rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.iloc[::-1].reset_index(drop=True)
        result = df[["timestamp", "open", "high", "low", "close", "volume"]]
        _cache_set(cache_key, result)
        return result
    except Exception:
        return None


def fetch_latest_price(symbol: str, is_crypto: bool = False) -> float | None:
    cache_key = f"latest:{symbol}:{is_crypto}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = _alpaca_headers()
    if headers is None:
        return None
    try:
        if is_crypto:
            url = "https://data.alpaca.markets/v1beta3/crypto/us/latest/trades"
            resp = requests.get(url, headers=headers, params={"symbols": symbol}, timeout=5)
            resp.raise_for_status()
            trade = resp.json().get("trades", {}).get(symbol, {})
            price = float(trade.get("p", 0)) or None
        else:
            url = f"{ALPACA_DATA_URL}/stocks/{symbol}/trades/latest"
            resp = requests.get(url, headers=headers, params={"feed": "iex"}, timeout=5)
            resp.raise_for_status()
            trade = resp.json().get("trade", {})
            price = float(trade.get("p", 0)) or None
        if price is not None:
            _cache_set(cache_key, price)
        return price
    except Exception:
        return None


def fetch_prev_close(symbol: str, is_crypto: bool = False) -> float | None:
    cache_key = f"prevclose:{symbol}:{is_crypto}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if is_crypto:
        headers = _alpaca_headers()
        if headers is None:
            return None
        end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(days=14)
        params = {
            "symbols": symbol, "timeframe": "1Day",
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 2, "sort": "asc",
        }
        try:
            resp = requests.get("https://data.alpaca.markets/v1beta3/crypto/us/bars", headers=headers, params=params, timeout=5)
            resp.raise_for_status()
            bars = resp.json().get("bars", {}).get(symbol, [])
            if len(bars) >= 2:
                result = float(bars[-2]["c"])
                _cache_set(cache_key, result)
                return result
        except Exception:
            pass
        return None
    else:
        df = fetch_bars_alpaca(symbol, "1Day", 2)
        if df is not None and len(df) >= 2:
            result = float(df["close"].iloc[-2])
            _cache_set(cache_key, result)
            return result
        return None


# ==============================================================================
# SYNTHETIC FALLBACK
# ==============================================================================

def make_synthetic_bars(base_price: float, n: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    now = datetime.datetime.utcnow().replace(second=0, microsecond=0)
    timestamps = [now - datetime.timedelta(minutes=n - i) for i in range(n)]

    closes = base_price + np.cumsum(rng.normal(0, base_price * 0.002, n))
    opens = np.roll(closes, 1)
    opens[0] = base_price
    highs = np.maximum(opens, closes) + rng.uniform(0, base_price * 0.003, n)
    lows = np.minimum(opens, closes) - rng.uniform(0, base_price * 0.003, n)
    vols = rng.integers(100_000, 2_000_000, n)

    return pd.DataFrame({
        "timestamp": timestamps, "open": opens, "high": highs,
        "low": lows, "close": closes, "volume": vols,
    })


SYNTHETIC_BASES = {
    "AAPL": 195.0, "MSFT": 390.0, "GOOGL": 160.0, "AMZN": 185.0,
    "TSLA": 250.0, "NVDA": 880.0, "META": 560.0, "JPM": 230.0,
    "SPY": 530.0, "QQQ": 450.0, "DIA": 395.0, "IWM": 200.0,
    "EFA": 80.0, "EEM": 42.0,
    "GLD": 240.0, "SLV": 28.0, "USO": 75.0, "UNG": 14.0,
    "PDBC": 14.0, "CORN": 22.0,
    "BTC/USD": 83000.0, "ETH/USD": 1800.0, "SOL/USD": 130.0,
    "DOGE/USD": 0.17, "AVAX/USD": 22.0, "LINK/USD": 13.0,
}


def get_bars(symbol: str, timeframe: str, limit: int) -> tuple[pd.DataFrame, bool]:
    df = fetch_bars_alpaca(symbol, timeframe, limit)
    if df is not None and not df.empty:
        return df, True
    seed = abs(hash(symbol)) % 10000
    base = SYNTHETIC_BASES.get(symbol, 100.0)
    return make_synthetic_bars(base, n=limit, seed=seed), False


def get_crypto_bars(symbol: str, timeframe: str, limit: int) -> tuple[pd.DataFrame, bool]:
    cache_key = f"crypto_candles:{symbol}:{timeframe}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = _alpaca_headers()
    if headers is None:
        result = (make_synthetic_bars(SYNTHETIC_BASES.get(symbol, 100.0), n=limit, seed=abs(hash(symbol)) % 10000), False)
        return result

    end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(days=14)
    params = {
        "symbols": symbol, "timeframe": timeframe,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": limit, "sort": "desc",
    }
    try:
        resp = requests.get("https://data.alpaca.markets/v1beta3/crypto/us/bars", headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        bars = resp.json().get("bars", {}).get(symbol, [])
        if not bars:
            raise ValueError("empty")
        df = pd.DataFrame(bars)
        df.rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.iloc[::-1].reset_index(drop=True)
        result = (df[["timestamp", "open", "high", "low", "close", "volume"]], True)
    except Exception:
        result = (make_synthetic_bars(SYNTHETIC_BASES.get(symbol, 100.0), n=limit, seed=abs(hash(symbol)) % 10000), False)

    _cache_set(cache_key, result)
    return result


def get_quote(symbol: str, is_crypto: bool = False) -> dict:
    """price + day-over-day % change, with synthetic fallback."""
    last_price = fetch_latest_price(symbol, is_crypto=is_crypto)
    prev_price = fetch_prev_close(symbol, is_crypto=is_crypto)

    if last_price is None:
        bars, _ = get_bars(symbol, "1Day", 2)
        last_price = float(bars["close"].iloc[-1])
        prev_price = float(bars["close"].iloc[-2]) if len(bars) >= 2 else last_price

    if prev_price is None or prev_price == 0:
        prev_price = last_price

    chg_pct = ((last_price - prev_price) / prev_price) * 100
    return {"price": last_price, "chg_pct": chg_pct}


# ==============================================================================
# PSX
# ==============================================================================

PSX_BASE = "https://psxterminal.com"

PSX_BLUE_CHIPS = ["HBL", "ENGRO", "LUCK", "MCB", "PPL", "OGDC"]

PSX_STOCKS = {
    "HBL": "Habib Bank Limited", "ENGRO": "Engro Corporation", "LUCK": "Lucky Cement",
    "MCB": "MCB Bank", "UBL": "United Bank Limited", "PPL": "Pakistan Petroleum",
    "OGDC": "Oil & Gas Dev. Company", "PSO": "Pakistan State Oil", "NESTLE": "Nestle Pakistan",
    "SYS": "Systems Limited", "TRG": "TRG Pakistan", "HUBC": "Hub Power Company",
    "ATRL": "Attock Refinery", "MEBL": "Meezan Bank", "NBP": "National Bank of Pakistan",
    "FFC": "Fauji Fertilizer Company", "EFERT": "Engro Fertilizers", "DGKC": "D.G. Khan Cement",
    "COLG": "Colgate-Palmolive Pakistan", "GLAXO": "GlaxoSmithKline Pakistan",
}


def fetch_psx_snapshot() -> dict:
    cache_key = "psx_snapshot"
    cached = _cache_get(cache_key, ttl=PSX_SNAPSHOT_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        r = requests.get(f"{PSX_BASE}/api/market-data", params={"market": "REG"}, timeout=8)
        data = r.json()
        if data.get("success"):
            result = data["data"].get("REG", {})
            _cache_set(cache_key, result)
            return result
    except Exception:
        pass
    return {}


def fetch_psx_ohlcv(symbol: str) -> pd.DataFrame | None:
    cache_key = f"psx_ohlcv:{symbol}"
    cached = _cache_get(cache_key, ttl=PSX_OHLCV_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        import yfinance as yf
        end = pd.Timestamp.today()
        start = end - pd.DateOffset(years=2)
        for ticker_str in [f"{symbol}.KA", symbol]:
            raw = yf.download(
                ticker_str, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
                interval="1d", auto_adjust=True, progress=False, multi_level_index=False,
            )
            if raw is None or len(raw) < 10:
                continue
            raw.columns = [c.lower() for c in raw.columns]
            if "close" not in raw.columns:
                continue
            df = raw[["open", "high", "low", "close", "volume"]].copy()
            df = df[df["volume"] > 0].dropna()
            if len(df) < 10:
                continue
            df = df.reset_index()
            for col in ("Date", "Datetime", "date", "datetime"):
                if col in df.columns:
                    df.rename(columns={col: "timestamp"}, inplace=True)
                    break
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            result = df[["timestamp", "open", "high", "low", "close", "volume"]]
            _cache_set(cache_key, result)
            return result
    except Exception:
        pass
    return None


def get_psx_quote(symbol: str, snapshot: dict) -> dict:
    tick = snapshot.get(symbol, {})
    price = tick.get("price")
    chg_pct = (tick.get("changePercent", 0) or 0) * 100

    if price is None:
        df_t = fetch_psx_ohlcv(symbol)
        if df_t is not None and len(df_t) >= 2:
            price = float(df_t["close"].iloc[-1])
            prev = float(df_t["close"].iloc[-2])
            chg_pct = (price - prev) / prev * 100 if prev else 0.0
        else:
            price = 0.0
            chg_pct = 0.0

    return {"price": price, "chg_pct": chg_pct}
