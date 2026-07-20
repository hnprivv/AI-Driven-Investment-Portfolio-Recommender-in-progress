import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()  # loads variables from .env into os.environ

import modules.utils

st.set_page_config(page_title="Market Overview", page_icon="assets/aiprs.png", layout="wide")

# ---- Load CSS ----
modules.utils.load_css()

# ---- Load User Data ----
if 'authenticated' in st.session_state and st.session_state.authenticated and 'username' in st.session_state:
    name = st.session_state.username
else:
    name = 'Guest'

modules.utils.set_sidebar_header(name)

ALPACA_DATA_URL = "https://data.alpaca.markets/v2"

# US stock market holidays (NYSE) — update annually
_NYSE_HOLIDAYS_2026 = {
    datetime.date(2026, 1,  1),   # New Year's Day
    datetime.date(2026, 1, 19),   # MLK Day
    datetime.date(2026, 2, 16),   # Presidents' Day
    datetime.date(2026, 4,  3),   # Good Friday
    datetime.date(2026, 5, 25),   # Memorial Day
    datetime.date(2026, 6, 19),   # Juneteenth
    datetime.date(2026, 7,  3),   # Independence Day (observed)
    datetime.date(2026, 9,  7),   # Labor Day
    datetime.date(2026, 11, 26),  # Thanksgiving
    datetime.date(2026, 12, 25),  # Christmas
}
_NYSE_HOLIDAYS_2025 = {
    datetime.date(2025, 1,  1),
    datetime.date(2025, 1, 20),
    datetime.date(2025, 2, 17),
    datetime.date(2025, 4, 18),   # Good Friday
    datetime.date(2025, 5, 26),
    datetime.date(2025, 6, 19),
    datetime.date(2025, 7,  4),
    datetime.date(2025, 9,  1),
    datetime.date(2025, 11, 27),
    datetime.date(2025, 12, 25),
}
NYSE_HOLIDAYS = _NYSE_HOLIDAYS_2025 | _NYSE_HOLIDAYS_2026


def market_status() -> dict:
    """
    Return a dict with keys:
      is_open   – bool: True if NYSE is currently in regular session
      label     – str: human-readable status badge text
      color     – str: hex colour for the badge
      last_open – datetime.date: most recent trading day (for info display)
    """
    import pytz
    et = pytz.timezone("America/New_York")
    now_et = datetime.datetime.now(et)
    today  = now_et.date()

    def is_trading_day(d: datetime.date) -> bool:
        return d.weekday() < 5 and d not in NYSE_HOLIDAYS

    # Walk back to find the last trading day
    last_open = today
    while not is_trading_day(last_open):
        last_open -= datetime.timedelta(days=1)

    open_time  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_time = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)

    if is_trading_day(today) and open_time <= now_et < close_time:
        return dict(is_open=True,  label="Market Open",
                    color="#00C853", last_open=last_open)
    elif is_trading_day(today) and now_et < open_time:
        return dict(is_open=False, label="Pre-Market",
                    color="#FFB300", last_open=last_open)
    elif is_trading_day(today) and now_et >= close_time:
        return dict(is_open=False, label="After Hours",
                    color="#FFB300", last_open=last_open)
    else:
        return dict(is_open=False, label="Market Closed",
                    color="#FF3D00", last_open=last_open)


def get_alpaca_headers():
    """Pull Alpaca credentials from .env via os.environ."""
    api_key    = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return None
    return {
        "APCA-API-KEY-ID":     api_key,
        "APCA-API-SECRET-KEY": secret_key,
        "accept": "application/json"
    }


# ==============================================================================
# DATA FETCHING  (Alpaca  →  fallback to synthetic)
# ==============================================================================

@st.cache_data(ttl=900, show_spinner=False)  # 15-min cache matches IEX delay — no point refreshing faster
def fetch_bars_alpaca(symbol: str, timeframe: str = "1Min", limit: int = 120) -> pd.DataFrame | None:
    """
    Fetch OHLCV bars from Alpaca for *symbol*.
    timeframe examples: "1Min", "5Min", "15Min", "1Hour", "1Day"
    Returns a DataFrame with columns [timestamp, open, high, low, close, volume]
    or None on failure.
    """
    headers = get_alpaca_headers()
    if headers is None:
        return None

    # Use a generous lookback so holidays/weekends never starve the bar count.
    # Rule of thumb: ~26 bars per trading day at 15-Min; 14 calendar days ≈ 10
    # trading days, which is comfortably more than the 120-bar default.
    end   = datetime.datetime.utcnow()
    start = end - datetime.timedelta(days=14)   # 14 calendar days ≥ 10 trading days

    params = {
        "timeframe": timeframe,
        "start":     start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end":       end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit":     limit,
        "feed":      "iex",          # free tier; change to "sip" on paid plan
        "sort":      "desc",         # newest bars first so limit anchors to NOW
    }

    try:
        url  = f"{ALPACA_DATA_URL}/stocks/{symbol}/bars"
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        bars = data.get("bars", [])
        if not bars:
            return None

        df = pd.DataFrame(bars)
        df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                            "l": "low",  "c": "close", "v": "volume"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # Reverse so the chart is displayed oldest → newest (desc fetch = newest first)
        df = df.iloc[::-1].reset_index(drop=True)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)  # 15-min cache matches IEX delay — no point refreshing faster
def fetch_latest_price(symbol: str, is_crypto: bool = False) -> float | None:
    """
    Fetch the most recent trade price for *symbol* from Alpaca.
    Uses /trades/latest for stocks (IEX feed) and crypto equivalent.
    Returns a float price or None on failure.
    """
    headers = get_alpaca_headers()
    if headers is None:
        return None
    try:
        if is_crypto:
            url    = "https://data.alpaca.markets/v1beta3/crypto/us/latest/trades"
            params = {"symbols": symbol}
            resp   = requests.get(url, headers=headers, params=params, timeout=5)
            resp.raise_for_status()
            trade  = resp.json().get("trades", {}).get(symbol, {})
            return float(trade.get("p", 0)) or None
        else:
            url  = f"{ALPACA_DATA_URL}/stocks/{symbol}/trades/latest"
            resp = requests.get(url, headers=headers, params={"feed": "iex"}, timeout=5)
            resp.raise_for_status()
            trade = resp.json().get("trade", {})
            return float(trade.get("p", 0)) or None
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_prev_close(symbol: str, is_crypto: bool = False) -> float | None:
    """
    Returns the previous session's closing price for day-over-day change calculation.
    Fetches the last 2 daily bars and returns the second-to-last close.
    """
    if is_crypto:
        headers = get_alpaca_headers()
        if headers is None:
            return None
        end   = datetime.datetime.utcnow()
        start = end - datetime.timedelta(days=14)
        params = {
            "symbols": symbol, "timeframe": "1Day",
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 2, "sort": "asc",
        }
        try:
            resp = requests.get("https://data.alpaca.markets/v1beta3/crypto/us/bars",
                                headers=headers, params=params, timeout=5)
            resp.raise_for_status()
            bars = resp.json().get("bars", {}).get(symbol, [])
            if len(bars) >= 2:
                return float(bars[-2]["c"])
        except Exception:
            pass
        return None
    else:
        df = fetch_bars_alpaca(symbol, "1Day", 2)
        if df is not None and len(df) >= 2:
            return float(df["close"].iloc[-2])
        return None


# ==============================================================================
# SYNTHETIC FALLBACK  (shown when API keys are not configured)
# ==============================================================================

def make_synthetic_bars(base_price: float, n: int = 120, seed: int = 42) -> pd.DataFrame:
    """Generate realistic-looking OHLCV bars for demo purposes."""
    rng = np.random.default_rng(seed)
    now = datetime.datetime.utcnow().replace(second=0, microsecond=0)
    timestamps = [now - datetime.timedelta(minutes=n - i) for i in range(n)]

    closes = base_price + np.cumsum(rng.normal(0, base_price * 0.002, n))
    opens  = np.roll(closes, 1); opens[0] = base_price
    highs  = np.maximum(opens, closes) + rng.uniform(0, base_price * 0.003, n)
    lows   = np.minimum(opens, closes) - rng.uniform(0, base_price * 0.003, n)
    vols   = rng.integers(100_000, 2_000_000, n)

    return pd.DataFrame({
        "timestamp": timestamps, "open": opens, "high": highs,
        "low": lows, "close": closes, "volume": vols
    })


SYNTHETIC_BASES = {
    # Approximate prices as of April 2026 — only used in demo mode (no API keys)
    "AAPL": 195.0,  "MSFT": 390.0,  "GOOGL": 160.0, "AMZN": 185.0,
    "TSLA": 250.0,  "NVDA": 880.0,  "META":  560.0,  "JPM":  230.0,
    # ETF proxies
    "SPY":  530.0,  "QQQ":  450.0,  "DIA":   395.0,  "IWM":  200.0,
    "EFA":  80.0,   "EEM":  42.0,
    # Commodity ETFs
    "GLD":  240.0,  "SLV":  28.0,   "USO":   75.0,   "UNG":  14.0,
    "PDBC": 14.0,   "CORN": 22.0,
    # Crypto pairs
    "BTC/USD": 83000.0, "ETH/USD": 1800.0, "SOL/USD":  130.0,
    "DOGE/USD": 0.17,   "AVAX/USD": 22.0,  "LINK/USD": 13.0,
}


def get_bars(symbol: str, timeframe: str, limit: int) -> tuple[pd.DataFrame, bool]:
    """
    Try Alpaca first; fall back to synthetic data.
    Returns (df, is_live).
    """
    df = fetch_bars_alpaca(symbol, timeframe, limit)
    if df is not None and not df.empty:
        return df, True

    seed = abs(hash(symbol)) % 10000
    base = SYNTHETIC_BASES.get(symbol, 100.0)
    return make_synthetic_bars(base, n=limit, seed=seed), False


# ==============================================================================
# CHART BUILDER
# ==============================================================================

def build_candlestick_chart(df: pd.DataFrame, symbol: str, is_live: bool, currency_prefix: str = "$", badge_text: str | None = None) -> go.Figure:
    """
    Build a professional candlestick chart with volume bars.
    Green candle = close >= open.  Red candle = close < open.

    Uses a categorical x-axis (bar index) so overnight/weekend gaps are
    eliminated — candles pack together just like TradingView or Bloomberg.
    Tick labels are formatted timestamps for readability.
    """
    colors_up   = "#22C55E"
    colors_down = "#EF4444"

    is_up      = df["close"] >= df["open"]
    bar_colors = [colors_up if u else colors_down for u in is_up]

    # ── Build readable tick labels ────────────────────────────────────────────
    # Show fewer labels so they don't crowd. Pick ~8 evenly spaced indices.
    n      = len(df)
    step   = max(1, n // 8)
    tick_indices = list(range(0, n, step))
    tick_labels  = [
        df["timestamp"].iloc[i].strftime("%b %d\n%H:%M") for i in tick_indices
    ]

    # Hover text: full timestamp for each bar
    hover_times = df["timestamp"].dt.strftime("%b %d, %Y  %H:%M").tolist()

    # Use integer index as x so Plotly treats it as categorical (no time gaps)
    x_idx = list(range(n))

    fig = go.Figure()

    # ── Candlestick ──────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=x_idx,
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        text=hover_times,
        hovertext=hover_times,
        name=symbol,
        increasing=dict(line=dict(color=colors_up,   width=1), fillcolor=colors_up),
        decreasing=dict(line=dict(color=colors_down, width=1), fillcolor=colors_down),
        whiskerwidth=1,   # 1.0 = wick fills full candle slot width, eliminating gap illusion
        yaxis="y1",
    ))

    # ── Volume bars (secondary y-axis) ───────────────────────────────────────
    fig.add_trace(go.Bar(
        x=x_idx,
        y=df["volume"],
        text=hover_times,
        hovertemplate="%{text}<br>Volume: %{y:,.0f}<extra></extra>",
        name="Volume",
        marker_color=bar_colors,
        opacity=0.4,
        yaxis="y2",
        showlegend=False,
    ))

    # ── 20-period Simple Moving Average ──────────────────────────────────────
    if len(df) >= 20:
        sma = df["close"].rolling(20).mean()
        fig.add_trace(go.Scatter(
            x=x_idx, y=sma,
            mode="lines",
            line=dict(color="#F59E0B", width=1.5, dash="dot"),
            name="SMA 20",
            yaxis="y1",
        ))

    # ── Layout ───────────────────────────────────────────────────────────────
    last_close  = df["close"].iloc[-1]
    first_close = df["close"].iloc[0]
    pct_change  = ((last_close - first_close) / first_close) * 100
    change_color = "#22C55E" if pct_change >= 0 else "#EF4444"
    live_badge   = badge_text if badge_text is not None else ("🟠 15-MIN DELAYED" if is_live else "🟡 DEMO DATA")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(11,11,15,0)",
        plot_bgcolor="rgba(11,11,15,0)",
        title=dict(
            text=f"<b>{symbol}</b>   "
                 f"<span style='color:{change_color}'>{pct_change:+.2f}%</span>   "
                 f"<span style='font-size:12px; color:#A1A1AA'>{live_badge}</span>",
            font=dict(size=18, color="#E4E4E7"),
            x=0.01,
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=tick_indices,
            ticktext=tick_labels,
            tickfont=dict(size=10, color="#A1A1AA"),
            rangeslider=dict(visible=False),
            gridcolor="rgba(255,255,255,0.04)",
            color="#A1A1AA",
            showspikes=True,
            spikecolor="#F59E0B",
            spikethickness=1,
            spikedash="dot",
            # Categorical axis: no gaps for missing time periods
            type="category",
        ),
        yaxis=dict(
            domain=[0.25, 1.0],
            gridcolor="rgba(255,255,255,0.06)",
            color="#A1A1AA",
            tickprefix=currency_prefix,
            showspikes=True,
            spikecolor="#F59E0B",
        ),
        yaxis2=dict(
            domain=[0.0, 0.22],
            gridcolor="rgba(255,255,255,0.03)",
            color="#A1A1AA",
            title=dict(text="Volume", font=dict(size=10, color="#A1A1AA")),
        ),
        legend=dict(
            orientation="h", yanchor="top", y=1.02,
            xanchor="right", x=1,
            font=dict(color="#A1A1AA"),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1a1a2e", font_color="#E4E4E7"),
        margin=dict(l=10, r=10, t=55, b=10),
        height=520,
        font=dict(family="Inter", color="#E4E4E7"),
        dragmode="pan",
        bargap=0,       # no gap between candle slots
        bargroupgap=0,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1)
    fig.update_yaxes(showgrid=True, gridwidth=1)

    return fig


# ==============================================================================
# TICKER HEADER STRIP  (price + change badges)
# ==============================================================================

def render_ticker_strip(symbols: list[str], label_map: dict[str, str], is_crypto: bool = False):
    """
    Render a horizontal row of price/change pills.
    Uses the latest trade price from Alpaca's /trades/latest endpoint
    and the previous session close for accurate day-over-day % change.
    Falls back to the last bar in synthetic data when keys are absent.
    """
    cols = st.columns(len(symbols))
    for col, sym in zip(cols, symbols):
        label = label_map.get(sym, sym)

        last_price = fetch_latest_price(sym, is_crypto=is_crypto)
        prev_price = fetch_prev_close(sym,   is_crypto=is_crypto)

        # Fallback to synthetic when API is unavailable
        if last_price is None:
            bars, _ = get_bars(sym, "1Day", 2)
            last_price = float(bars["close"].iloc[-1])
            prev_price = float(bars["close"].iloc[-2]) if len(bars) >= 2 else last_price

        if prev_price is None or prev_price == 0:
            prev_price = last_price  # avoid divide-by-zero; show 0% change

        chg     = last_price - prev_price
        chg_pct = (chg / prev_price) * 100
        color   = "#22C55E" if chg_pct >= 0 else "#EF4444"
        arrow   = "▲" if chg_pct >= 0 else "▼"

        col.markdown(f"""
        <div style='
            background:rgba(255,255,255,0.04); border-radius:10px;
            padding:10px 14px; border:1px solid rgba(255,255,255,0.07);
            text-align:center;
        '>
            <div style='font-size:11px; color:#A1A1AA; margin-bottom:2px;'>{label}</div>
            <div style='font-size:17px; font-weight:700; color:#E4E4E7;'>${last_price:,.2f}</div>
            <div style='font-size:13px; color:{color}; font-weight:600;'>{arrow} {chg_pct:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)


# ==============================================================================
# PSX  –  HELPERS
# ==============================================================================

PSX_BASE = "https://psxterminal.com"

PSX_BLUE_CHIPS = ["HBL", "ENGRO", "LUCK", "MCB", "PPL", "OGDC"]

PSX_STOCKS = {
    "HBL":    "Habib Bank Limited",
    "ENGRO":  "Engro Corporation",
    "LUCK":   "Lucky Cement",
    "MCB":    "MCB Bank",
    "UBL":    "United Bank Limited",
    "PPL":    "Pakistan Petroleum",
    "OGDC":   "Oil & Gas Dev. Company",
    "PSO":    "Pakistan State Oil",
    "NESTLE": "Nestle Pakistan",
    "SYS":    "Systems Limited",
    "TRG":    "TRG Pakistan",
    "HUBC":   "Hub Power Company",
    "ATRL":   "Attock Refinery",
    "MEBL":   "Meezan Bank",
    "NBP":    "National Bank of Pakistan",
    "FFC":    "Fauji Fertilizer Company",
    "EFERT":  "Engro Fertilizers",
    "DGKC":   "D.G. Khan Cement",
    "COLG":   "Colgate-Palmolive Pakistan",
    "GLAXO":  "GlaxoSmithKline Pakistan",
}


def psx_market_status() -> dict:
    import pytz
    pkt     = pytz.timezone("Asia/Karachi")
    now_pkt = datetime.datetime.now(pkt)
    today   = now_pkt.date()

    open_time  = now_pkt.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_time = now_pkt.replace(hour=15, minute=30, second=0, microsecond=0)
    is_weekday = today.weekday() < 5

    if is_weekday and open_time <= now_pkt < close_time:
        return dict(is_open=True,  label="PSX Open",    color="#00C853")
    elif is_weekday and now_pkt < open_time:
        return dict(is_open=False, label="Pre-Market",  color="#FFB300")
    elif is_weekday and now_pkt >= close_time:
        return dict(is_open=False, label="After Hours", color="#FFB300")
    else:
        return dict(is_open=False, label="PSX Closed",  color="#FF3D00")


@st.cache_data(ttl=60, show_spinner=False)
def fetch_psx_snapshot() -> dict:
    try:
        r = requests.get(f"{PSX_BASE}/api/market-data", params={"market": "REG"}, timeout=8)
        data = r.json()
        if data.get("success"):
            return data["data"].get("REG", {})
    except Exception:
        pass
    return {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_psx_ohlcv(symbol: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        end   = pd.Timestamp.today()
        start = end - pd.DateOffset(years=2)
        for ticker_str in [f"{symbol}.KA", symbol]:
            raw = yf.download(
                ticker_str,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=True,
                progress=False,
                multi_level_index=False,
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
            # yfinance index column may be named "Date" or "Datetime"
            for col in ("Date", "Datetime", "date", "datetime"):
                if col in df.columns:
                    df.rename(columns={col: "timestamp"}, inplace=True)
                    break
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
    except Exception:
        pass
    return None


def render_psx_ticker_strip(symbols: list[str], snapshot: dict):
    cols = st.columns(len(symbols))
    for col, sym in zip(cols, symbols):
        tick    = snapshot.get(sym, {})
        price   = tick.get("price")
        chg_pct = (tick.get("changePercent", 0) or 0) * 100

        if price is None:
            df_t = fetch_psx_ohlcv(sym)
            if df_t is not None and len(df_t) >= 2:
                price   = float(df_t["close"].iloc[-1])
                prev    = float(df_t["close"].iloc[-2])
                chg_pct = (price - prev) / prev * 100 if prev else 0.0
            else:
                price   = 0.0
                chg_pct = 0.0

        color = "#22C55E" if chg_pct >= 0 else "#EF4444"
        arrow = "▲" if chg_pct >= 0 else "▼"
        col.markdown(
            f"""<div style='background:rgba(255,255,255,0.04);border-radius:10px;
                padding:10px 14px;border:1px solid rgba(255,255,255,0.07);text-align:center;'>
                <div style='font-size:11px;color:#A1A1AA;margin-bottom:2px;'>{sym}</div>
                <div style='font-size:17px;font-weight:700;color:#E4E4E7;'>PKR {price:,.1f}</div>
                <div style='font-size:13px;color:{color};font-weight:600;'>{arrow} {chg_pct:+.2f}%</div>
            </div>""",
            unsafe_allow_html=True,
        )


# ==============================================================================
# PAGE  –  HEADER
# ==============================================================================

st.markdown("<div class='custom-title-box'><h1>Market Overview</h1></div>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:#A1A1AA;'>Live candlestick charts powered by Alpaca Market Data. <b>Advisory view only.</b></p>",
    unsafe_allow_html=True
)
st.markdown("<br>", unsafe_allow_html=True)

tab_us, tab_psx = st.tabs(["US Market", "PSX Market"])

# ==============================================================================
# US MARKET TAB
# ==============================================================================
with tab_us:

    # Market status + refresh row
    mstatus = market_status()
    _hdr_left, _hdr_right = st.columns([5, 1])
    with _hdr_left:
        _closed_note = (
            f"  ·  Last trading session: **{mstatus['last_open'].strftime('%b %d, %Y')}**"
            if not mstatus["is_open"] else ""
        )
        st.markdown(
            f"<span style='background:{mstatus['color']}22; color:{mstatus['color']}; "
            f"border:1px solid {mstatus['color']}55; border-radius:6px; "
            f"padding:4px 10px; font-size:13px; font-weight:600;'>"
            f"● {mstatus['label']}</span>"
            f"<span style='color:#A1A1AA; font-size:13px;'>{_closed_note}</span>",
            unsafe_allow_html=True,
        )
    with _hdr_right:
        if st.button("⟳ Refresh", use_container_width=True,
                     help="Clear cache and reload latest data from Alpaca", key="us_refresh"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # API key status banner
    headers_check = get_alpaca_headers()
    if headers_check is None:
        st.info(
            "**Demo Mode** – Alpaca API keys not found. "
            "Add them to `.streamlit/secrets.toml` under `[alpaca]` with keys "
            "`api_key` and `secret_key` to switch to live data.",
            icon="ℹ️"
        )

    market_type = st.radio(
        "Choose a market category:",
        ["Stocks", "Cryptocurrency", "Global Indices", "Commodities"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Stocks ────────────────────────────────────────────────────────────────
    if market_type == "Stocks":

        STOCKS = {
            "AAPL": "Apple",  "MSFT": "Microsoft", "GOOGL": "Google",
            "AMZN": "Amazon", "TSLA": "Tesla",      "NVDA": "NVIDIA",
            "META": "Meta",   "JPM": "JPMorgan",
        }

        st.markdown("<h3 style='color:#F59E0B;'>Price Overview</h3>", unsafe_allow_html=True)
        with st.spinner("Fetching latest prices..."):
            render_ticker_strip(list(STOCKS.keys())[:6], STOCKS)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<h3 style='color:#F59E0B;'>Candlestick Chart</h3>", unsafe_allow_html=True)
        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
        with ctrl1:
            selected_stock = st.selectbox("Select Ticker", list(STOCKS.keys()),
                                           format_func=lambda s: f"{s} – {STOCKS[s]}")
        with ctrl2:
            tf_options = {"1 Min": "1Min", "5 Min": "5Min", "15 Min": "15Min",
                          "1 Hour": "1Hour", "1 Day": "1Day"}
            tf_label  = st.selectbox("Timeframe", list(tf_options.keys()), index=2)
            timeframe = tf_options[tf_label]
        with ctrl3:
            limit = st.slider("Bars", 30, 300, 120, step=30)

        df, is_live = get_bars(selected_stock, timeframe, limit)
        fig = build_candlestick_chart(df, selected_stock, is_live)
        st.plotly_chart(fig, use_container_width=True, config={**modules.utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})

        last = df.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open",  f"${last['open']:.2f}")
        m2.metric("High",  f"${last['high']:.2f}")
        m3.metric("Low",   f"${last['low']:.2f}")
        m4.metric("Close", f"${last['close']:.2f}",
                  delta=f"{last['close'] - last['open']:+.2f}")

    # ── Cryptocurrency ────────────────────────────────────────────────────────
    elif market_type == "Cryptocurrency":

        CRYPTO = {
            "BTC/USD":  "Bitcoin",   "ETH/USD":  "Ethereum",
            "SOL/USD":  "Solana",    "DOGE/USD": "Dogecoin",
            "AVAX/USD": "Avalanche", "LINK/USD": "Chainlink",
        }

        st.markdown("<h3 style='color:#F59E0B;'>Crypto Price Overview</h3>", unsafe_allow_html=True)
        with st.spinner("Fetching latest prices..."):
            render_ticker_strip(list(CRYPTO.keys())[:4], CRYPTO, is_crypto=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<h3 style='color:#F59E0B;'>Candlestick Chart</h3>", unsafe_allow_html=True)
        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
        with ctrl1:
            selected_crypto = st.selectbox("Select Pair", list(CRYPTO.keys()),
                                            format_func=lambda s: f"{s} – {CRYPTO[s]}")
        with ctrl2:
            tf_options = {"1 Min": "1Min", "5 Min": "5Min", "15 Min": "15Min",
                          "1 Hour": "1Hour", "1 Day": "1Day"}
            tf_label  = st.selectbox("Timeframe", list(tf_options.keys()), index=2, key="crypto_tf")
            timeframe = tf_options[tf_label]
        with ctrl3:
            limit = st.slider("Bars", 30, 300, 120, step=30, key="crypto_limit")

        @st.cache_data(ttl=900, show_spinner=False)
        def fetch_crypto_bars(symbol: str, timeframe: str, limit: int) -> tuple[pd.DataFrame, bool]:
            headers = get_alpaca_headers()
            if headers is None:
                return make_synthetic_bars(SYNTHETIC_BASES.get(symbol, 100.0), n=limit,
                                           seed=abs(hash(symbol)) % 10000), False
            end   = datetime.datetime.utcnow()
            start = end - datetime.timedelta(days=14)
            params = {
                "symbols": symbol, "timeframe": timeframe,
                "start":   start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end":     end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit":   limit, "sort": "desc",
            }
            try:
                url  = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
                resp = requests.get(url, headers=headers, params=params, timeout=8)
                resp.raise_for_status()
                bars = resp.json().get("bars", {}).get(symbol, [])
                if not bars:
                    raise ValueError("empty")
                df = pd.DataFrame(bars)
                df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                    "l": "low", "c": "close", "v": "volume"}, inplace=True)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.iloc[::-1].reset_index(drop=True)
                return df[["timestamp", "open", "high", "low", "close", "volume"]], True
            except Exception:
                return make_synthetic_bars(SYNTHETIC_BASES.get(symbol, 100.0), n=limit,
                                           seed=abs(hash(symbol)) % 10000), False

        with st.spinner(f"Loading {selected_crypto} chart..."):
            df, is_live = fetch_crypto_bars(selected_crypto, timeframe, limit)
        fig = build_candlestick_chart(df, selected_crypto, is_live)
        st.plotly_chart(fig, use_container_width=True, config={**modules.utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})

        last = df.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open",  f"${last['open']:,.2f}")
        m2.metric("High",  f"${last['high']:,.2f}")
        m3.metric("Low",   f"${last['low']:,.2f}")
        m4.metric("Close", f"${last['close']:,.2f}",
                  delta=f"{last['close'] - last['open']:+.2f}")

    # ── Global Indices ────────────────────────────────────────────────────────
    elif market_type == "Global Indices":

        INDEX_PROXIES = {
            "SPY": "S&P 500 · SPY ETF",    "QQQ": "NASDAQ-100 · QQQ ETF",
            "DIA": "Dow Jones · DIA ETF",   "IWM": "Russell 2000 · IWM ETF",
            "EFA": "MSCI EAFE · EFA ETF",   "EEM": "Emerging Markets · EEM ETF",
        }

        st.markdown("<h3 style='color:#F59E0B;'>Global Index ETF Prices</h3>", unsafe_allow_html=True)
        st.info(
            "**Note:** Prices shown are ETF share prices, not index point values. "
            "SPY tracks the S&P 500 at ~1/10th its value, DIA tracks the Dow at ~1/100th, etc. "
            "Price movements and % changes are accurate — only the absolute number differs from the raw index.",
            icon="ℹ️"
        )
        with st.spinner("Fetching latest prices..."):
            render_ticker_strip(list(INDEX_PROXIES.keys())[:4], INDEX_PROXIES)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<h3 style='color:#F59E0B;'>Candlestick Chart</h3>", unsafe_allow_html=True)
        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
        with ctrl1:
            selected_idx = st.selectbox("Select Index ETF", list(INDEX_PROXIES.keys()),
                                         format_func=lambda s: f"{s} — {INDEX_PROXIES[s]}")
        with ctrl2:
            tf_options = {"5 Min": "5Min", "15 Min": "15Min", "1 Hour": "1Hour", "1 Day": "1Day"}
            tf_label   = st.selectbox("Timeframe", list(tf_options.keys()), index=2, key="idx_tf")
            timeframe  = tf_options[tf_label]
        with ctrl3:
            limit = st.slider("Bars", 30, 300, 120, step=30, key="idx_limit")

        df, is_live = get_bars(selected_idx, timeframe, limit)
        fig = build_candlestick_chart(df, selected_idx, is_live)
        st.plotly_chart(fig, use_container_width=True, config={**modules.utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})

        last = df.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open",  f"${last['open']:.2f}")
        m2.metric("High",  f"${last['high']:.2f}")
        m3.metric("Low",   f"${last['low']:.2f}")
        m4.metric("Close", f"${last['close']:.2f}",
                  delta=f"{last['close'] - last['open']:+.2f}")

    # ── Commodities ───────────────────────────────────────────────────────────
    elif market_type == "Commodities":

        COMMODITY_PROXIES = {
            "GLD":  "Gold · GLD ETF (~1/10 oz/share)",
            "SLV":  "Silver · SLV ETF (~1 oz/share)",
            "USO":  "Crude Oil · USO ETF",
            "UNG":  "Natural Gas · UNG ETF",
            "PDBC": "Diversified · PDBC ETF",
            "CORN": "Corn · CORN ETF",
        }

        st.markdown("<h3 style='color:#F59E0B;'>Commodity ETF Prices</h3>", unsafe_allow_html=True)
        st.info(
            "**Note:** Prices shown are ETF share prices, not commodity spot prices. "
            "GLD (~$240/share) tracks gold at roughly 1/10 oz per share — spot gold is ~$2,400/oz. "
            "SLV tracks silver at ~1 oz per share. % changes accurately reflect commodity price movements.",
            icon="ℹ️"
        )
        with st.spinner("Fetching latest prices..."):
            render_ticker_strip(list(COMMODITY_PROXIES.keys())[:4], COMMODITY_PROXIES)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<h3 style='color:#F59E0B;'>Candlestick Chart</h3>", unsafe_allow_html=True)
        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
        with ctrl1:
            selected_com = st.selectbox("Select Commodity ETF", list(COMMODITY_PROXIES.keys()),
                                         format_func=lambda s: f"{s} — {COMMODITY_PROXIES[s]}")
        with ctrl2:
            tf_options = {"5 Min": "5Min", "15 Min": "15Min", "1 Hour": "1Hour", "1 Day": "1Day"}
            tf_label   = st.selectbox("Timeframe", list(tf_options.keys()), index=2, key="com_tf")
            timeframe  = tf_options[tf_label]
        with ctrl3:
            limit = st.slider("Bars", 30, 300, 120, step=30, key="com_limit")

        df, is_live = get_bars(selected_com, timeframe, limit)
        fig = build_candlestick_chart(df, selected_com, is_live)
        st.plotly_chart(fig, use_container_width=True, config={**modules.utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})

        last = df.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open",  f"${last['open']:.2f}")
        m2.metric("High",  f"${last['high']:.2f}")
        m3.metric("Low",   f"${last['low']:.2f}")
        m4.metric("Close", f"${last['close']:.2f}",
                  delta=f"{last['close'] - last['open']:+.2f}")


# ==============================================================================
# PSX MARKET TAB
# ==============================================================================
with tab_psx:

    # PSX market status + refresh row
    pstatus = psx_market_status()
    _psx_left, _psx_right = st.columns([5, 1])
    with _psx_left:
        st.markdown(
            f"<span style='background:{pstatus['color']}22; color:{pstatus['color']}; "
            f"border:1px solid {pstatus['color']}55; border-radius:6px; "
            f"padding:4px 10px; font-size:13px; font-weight:600;'>"
            f"● {pstatus['label']}</span>"
            f"<span style='color:#A1A1AA; font-size:13px;'>"
            f"  ·  Regular hours: Mon–Fri, 09:30–15:30 PKT</span>",
            unsafe_allow_html=True,
        )
    with _psx_right:
        if st.button("⟳ Refresh", use_container_width=True,
                     help="Clear cache and reload latest PSX data", key="psx_refresh"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Price strip — blue chip tickers
    st.markdown("<h3 style='color:#F59E0B;'>Price Overview</h3>", unsafe_allow_html=True)
    with st.spinner("Fetching latest PSX prices..."):
        psx_snap = fetch_psx_snapshot()
        render_psx_ticker_strip(PSX_BLUE_CHIPS, psx_snap)
    st.markdown("<br>", unsafe_allow_html=True)

    # Candlestick chart
    st.markdown("<h3 style='color:#F59E0B;'>Candlestick Chart</h3>", unsafe_allow_html=True)
    st.caption("Historical data sourced from Yahoo Finance (.KA). Daily bars only.")

    ctrl1, ctrl2 = st.columns([3, 1])
    with ctrl1:
        selected_psx = st.selectbox(
            "Select PSX Stock",
            list(PSX_STOCKS.keys()),
            format_func=lambda s: f"{s} – {PSX_STOCKS[s]}",
            key="psx_stock",
        )
    with ctrl2:
        psx_limit = st.slider("Bars", 30, 500, 120, step=30, key="psx_limit")

    with st.spinner(f"Loading {selected_psx} ..."):
        df_psx = fetch_psx_ohlcv(selected_psx)

    if df_psx is None or len(df_psx) < 10:
        st.warning(
            f"Could not load data for **{selected_psx}** from Yahoo Finance. "
            "The symbol may not be available. Try another stock.",
            icon="⚠️",
        )
    else:
        df_psx_plot = df_psx.tail(psx_limit).reset_index(drop=True)

        # Live price from psxterminal.com if available
        tick_live = psx_snap.get(selected_psx, {})
        live_price = tick_live.get("price")
        live_chg   = (tick_live.get("changePercent", 0) or 0) * 100

        if live_price:
            price_label = f"PKR {live_price:,.1f}"
            chg_color   = "#22C55E" if live_chg >= 0 else "#EF4444"
            chg_arrow   = "▲" if live_chg >= 0 else "▼"
            st.markdown(
                f"<div style='margin-bottom:8px;'>"
                f"<span style='font-size:22px;font-weight:700;color:#E4E4E7;'>{price_label}</span>"
                f"<span style='font-size:14px;color:{chg_color};margin-left:10px;font-weight:600;'>"
                f"{chg_arrow} {abs(live_chg):.2f}% today</span>"
                f"<span style='font-size:11px;color:#6B7280;margin-left:8px;'>Live via psxterminal.com</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        fig_psx = build_candlestick_chart(df_psx_plot, selected_psx, is_live=True,
                                          currency_prefix="PKR ", badge_text="")
        st.plotly_chart(fig_psx, use_container_width=True, config={**modules.utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})

        last_psx = df_psx_plot.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open",  f"PKR {last_psx['open']:,.1f}")
        m2.metric("High",  f"PKR {last_psx['high']:,.1f}")
        m3.metric("Low",   f"PKR {last_psx['low']:,.1f}")
        m4.metric("Close", f"PKR {last_psx['close']:,.1f}",
                  delta=f"{last_psx['close'] - last_psx['open']:+.1f}")


# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("""
<p style='color:#A1A1AA; font-size:13px;'>
Market data sourced from <b>Alpaca Markets</b> via the IEX feed (15-min delayed, free tier).
AIPRS provides <b>advisory insights only</b> — this platform does <b>NOT</b> facilitate live trading.
Demo mode uses synthetic data when API keys are absent.
</p>
""", unsafe_allow_html=True)

modules.utils.render_footer()