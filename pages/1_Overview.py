import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os, datetime, requests
import joblib
from dotenv import load_dotenv
from fpdf import FPDF
import io as _io
import modules.utils

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

st.set_page_config(page_title="Overview", page_icon="assets/aiprs.png", layout="wide")
modules.utils.load_css()

# ---- Auth guard ----
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    modules.utils.set_sidebar_header("Guest")
    st.markdown("<div class='custom-title-box'><h1>Portfolio Overview</h1></div>", unsafe_allow_html=True)
    modules.utils.show_auth_wall("your portfolio overview and investment snapshot")

name = st.session_state.username
modules.utils.set_sidebar_header(name)

st.markdown("<div class='custom-title-box'><h1>Portfolio Overview</h1></div>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#A1A1AA;'>Your personalized investment snapshot powered by AIPRS</p>", unsafe_allow_html=True)
st.write("")

# ---- Load user from MongoDB ----
user = modules.utils.get_user_by_name(name)
if user is None:
    st.error(f"⚠️ No profile data found for user: {name}. Please update your profile.")
    st.stop()

# ---- Cluster / allocation config ----
CLUSTER_LABELS = {0: "Conservative", 1: "Moderate", 2: "Aggressive", 3: "Very Aggressive"}
BADGE_COLORS   = {"Conservative": "#16a34a", "Moderate": "#FFE600", "Aggressive": "#ff8400", "Very Aggressive": "#b71212"}

CLUSTER_ALLOCATIONS = {
    0: {"Equities": 30, "Fixed Income": 50, "Commodities": 10, "Cash": 10},
    1: {"Equities": 60, "Fixed Income": 25, "Commodities": 10, "Cash":  5},
    2: {"Equities": 85, "Fixed Income":  5, "Commodities":  8, "Cash":  2},
    3: {"Equities": 90, "Fixed Income":  5, "Commodities":  3, "Cash":  2},
}

ASSET_TICKERS = {"Equities": "SPY", "Fixed Income": "AGG", "Commodities": "GLD", "Cash": "BIL"}

user_cluster = int(user.get("cluster", 1))
risk_profile = CLUSTER_LABELS.get(user_cluster, "Moderate")
allocation   = CLUSTER_ALLOCATIONS.get(user_cluster, CLUSTER_ALLOCATIONS[1])
badge_color  = BADGE_COLORS.get(risk_profile, "#F59E0B")

saved_holdings = user.get("holdings", [])

# ---- Alpaca helpers ----
ALPACA_DATA_URL = "https://data.alpaca.markets/v2"

def _alpaca_headers():
    key    = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None
    return {
        "APCA-API-KEY-ID":     key,
        "APCA-API-SECRET-KEY": secret,
        "accept": "application/json",
    }

@st.cache_data(ttl=900, show_spinner=False)
def fetch_bars(ticker: str, period_days: int = 365) -> pd.DataFrame | None:
    headers = _alpaca_headers()
    if headers is None:
        return None
    end   = datetime.datetime.now(datetime.timezone.utc)
    start = end - datetime.timedelta(days=period_days)
    params = {
        "timeframe": "1Day",
        "start":     start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end":       end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit":     10_000,
        "feed":      "iex",
        "sort":      "desc",
    }
    try:
        resp = requests.get(
            f"{ALPACA_DATA_URL}/stocks/{ticker}/bars",
            headers=headers, params=params, timeout=10,
        )
        resp.raise_for_status()
        bars = resp.json().get("bars", [])
        if not bars:
            return None
        df = pd.DataFrame(bars)
        df.rename(columns={"t": "date", "c": "close"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.iloc[::-1].reset_index(drop=True)
        return df[["date", "close"]]
    except Exception:
        return None

@st.cache_data(ttl=900, show_spinner=False)
def fetch_bars_yahoo(ticker: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if df.empty:
            return None
        close = df["Close"] if "Close" in df.columns else df.iloc[:, -1]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        result = pd.DataFrame({
            "date":  pd.to_datetime(close.index).date,
            "close": close.values,
        })
        return result.dropna()
    except Exception:
        return None

def _fetch_ticker(ticker: str, market: str) -> pd.DataFrame | None:
    if market == "PSX":
        return fetch_bars_yahoo(ticker)
    return fetch_bars(ticker)

def parse_holdings_input(text: str) -> tuple[list[dict], str | None]:
    """Parse 'AAPL:40, MSFT:30, OGDC.KA:30' or 'AAPL, MSFT' (equal weight).
    Returns (holdings_list, error_msg)."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return [], "Please enter at least one ticker."

    holdings      = []
    has_any_colon = any(":" in p for p in parts)

    for part in parts:
        if ":" in part:
            bits   = part.split(":", 1)
            ticker = bits[0].strip().upper()
            if not ticker:
                return [], "Ticker cannot be empty."
            try:
                weight = float(bits[1].strip())
            except ValueError:
                return [], f"Invalid weight for '{ticker}' — use a number."
            if weight <= 0:
                return [], f"Weight for '{ticker}' must be greater than 0."
            holdings.append({"ticker": ticker, "weight": weight})
        else:
            ticker = part.strip().upper()
            if not ticker:
                continue
            if has_any_colon:
                return [], "Please specify weights for all tickers or none."
            holdings.append({"ticker": ticker, "weight": None})

    if not holdings:
        return [], "No valid tickers found."

    if any(h["weight"] is None for h in holdings):
        equal_w = round(100 / len(holdings), 4)
        for h in holdings:
            h["weight"] = equal_w

    total = sum(h["weight"] for h in holdings)
    if abs(total - 100) > 2:
        return [], f"Weights sum to {total:.1f}% but must sum to 100%."

    for h in holdings:
        h["weight"] = round(h["weight"] / total * 100, 4)
        h["market"] = "PSX" if h["ticker"].endswith(".KA") else "US"

    return holdings, None

def compute_portfolio_metrics(
    price_series: dict, weights_map: dict
) -> tuple[float | None, float | None, float | None, pd.Series | None]:
    tickers   = list(price_series.keys())
    prices_df = pd.DataFrame({t: price_series[t] for t in tickers}).dropna()
    if len(prices_df) < 21:
        return None, None, None, None
    weights       = np.array([weights_map[t] / 100 for t in tickers])
    daily_returns = prices_df.pct_change().dropna()
    port_daily    = daily_returns.values @ weights
    equity_curve  = pd.Series((1 + port_daily).cumprod(), index=daily_returns.index)
    total_return  = float(equity_curve.iloc[-1] - 1)
    ann_vol       = float(np.std(port_daily) * np.sqrt(252))
    ann_return    = float((equity_curve.iloc[-1] ** (252 / max(len(port_daily), 1))) - 1)
    sharpe        = float((ann_return - 0.045) / ann_vol) if ann_vol > 0 else 0.0
    return total_return, ann_vol, sharpe, equity_curve

@st.cache_data(ttl=900, show_spinner=False)
def generate_pdf_report(
    username: str,
    risk_profile: str,
    user_age: int,
    income_range: str,
    investment_horizon: str,
    experience: str,
    goals: str,
    risk_tolerance: int,
    total_return: float,
    ann_vol: float,
    sharpe: float,
    metrics_source: str,
    curve_dates: list,
    curve_values: list,
    allocation_labels: list,
    allocation_values: list,
    holdings: list,
) -> bytes:

    # Equity curve chart image
    curve_img_bytes = None
    if curve_dates and curve_values:
        _curve_df = pd.DataFrame({
            "Date":            pd.to_datetime(curve_dates),
            "Portfolio Value": curve_values,
        })
        _fig_c = px.line(
            _curve_df, x="Date", y="Portfolio Value",
            template="plotly_white", color_discrete_sequence=["#F59E0B"],
        )
        _fig_c.add_hline(y=1.0, line_dash="dot", line_color="rgba(0,0,0,0.3)")
        _fig_c.update_layout(
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            font=dict(color="#111111", family="Arial"),
            margin=dict(l=40, r=20, t=20, b=40),
            xaxis=dict(gridcolor="rgba(0,0,0,0.08)", linecolor="rgba(0,0,0,0.2)"),
            yaxis=dict(gridcolor="rgba(0,0,0,0.08)", linecolor="rgba(0,0,0,0.2)"),
        )
        curve_img_bytes = _fig_c.to_image(format="png", width=900, height=350, scale=2)

    # Allocation pie chart image
    _fig_a = px.pie(
        values=allocation_values,
        names=allocation_labels,
        color_discrete_sequence=["#F59E0B", "#FCD34D", "#B45309", "#78350F"],
    )
    _fig_a.update_layout(
        paper_bgcolor="#FFFFFF",
        font=dict(color="#111111", family="Arial"),
        legend=dict(font=dict(color="#111111")),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    alloc_img_bytes = _fig_a.to_image(format="png", width=600, height=400, scale=2)

    # Build PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 12, "AIPRS Portfolio Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 96)
    pdf.cell(0, 5,
        f"Generated for {username}  |  "
        f"{datetime.datetime.now(datetime.timezone.utc).strftime('%d %B %Y, %H:%M UTC')}",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    pdf.ln(4)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Investor Profile
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Investor Profile", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    profile_rows = [
        ("Risk Profile",         risk_profile),
        ("Age",                  str(user_age)),
        ("Annual Income Range",  income_range),
        ("Investment Horizon",   investment_horizon),
        ("Experience Level",     experience),
        ("Primary Goal",         goals),
        ("Risk Tolerance Score", f"{risk_tolerance} / 10"),
    ]
    for label, value in profile_rows:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(90, 7, label)
        pdf.set_text_color(17, 17, 17)
        pdf.cell(90, 7, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Portfolio Metrics
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, f"Portfolio Metrics  ({metrics_source})", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    metric_cols = [
        ("Total Return (1Y)",     f"{total_return:.2%}"),
        ("Annualised Volatility", f"{ann_vol:.2%}"),
        ("Sharpe Ratio",          f"{sharpe:.2f}"),
    ]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(90, 90, 96)
    for label, _ in metric_cols:
        pdf.cell(63, 6, label)
    pdf.ln()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(17, 17, 17)
    for _, value in metric_cols:
        pdf.cell(63, 9, value)
    pdf.ln(12)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Equity curve
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Portfolio Performance (1Y)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    if curve_img_bytes:
        pdf.image(_io.BytesIO(curve_img_bytes), x=10, w=190)
        pdf.ln(1)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(0, 5, f"Figure: Growth of your portfolio over the past year ({metrics_source}).",
                  new_x="LMARGIN", new_y="NEXT", align="C")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(0, 8, "Chart unavailable - market data could not be fetched.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Asset Allocation
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Recommended Asset Allocation", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.image(_io.BytesIO(alloc_img_bytes), x=30, w=150)
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(90, 90, 96)
    pdf.cell(0, 5, f"Figure: Recommended asset allocation for a {risk_profile} risk profile.",
              new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # Holdings
    if holdings:
        pdf.set_draw_color(217, 119, 6)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(245, 158, 11)
        pdf.cell(0, 8, "Your Holdings", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(80, 7, "Ticker")
        pdf.cell(60, 7, "Market")
        pdf.cell(50, 7, "Weight", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for h in holdings:
            pdf.set_text_color(17, 17, 17)
            pdf.cell(80, 7, h["ticker"])
            pdf.cell(60, 7, h.get("market", "US"))
            pdf.cell(50, 7, f"{h['weight']:.1f}%", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Disclaimer page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Legal Disclaimer", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 64)
    pdf.multi_cell(0, 6,
        "AIPRS is an academic Final Year Project built for research and educational demonstration. "
        "It is not a licensed financial advisory service, investment platform, or brokerage, and is "
        "not regulated by any financial authority. All outputs in this report - including portfolio "
        "metrics, performance charts, asset allocations, and any recommendations - are produced for "
        "educational and demonstration purposes only. They do not constitute financial advice or "
        "regulated financial guidance. AIPRS and its developers accept no responsibility or liability "
        "whatsoever for any financial loss arising from actions taken based on anything contained in "
        "this report. Always consult a qualified and licensed financial advisor before making any "
        "investment decisions.\n\n"
        "AI-Powered Portfolio Recommendation System (AIPRS)  |  Academic Final Year Project  |  "
        "aiprs.support@gmail.com"
    )

    return bytes(pdf.output())

# ---- Fetch benchmark ETF data (cluster-based) ----
with st.status("Fetching benchmark market data...", expanded=False) as _bm_status:
    benchmark_series = {}
    failed_tickers   = []
    for asset, ticker in ASSET_TICKERS.items():
        _bm_status.update(label=f"Fetching {asset} ({ticker})...")
        df_raw = fetch_bars(ticker)
        if df_raw is not None and len(df_raw) > 20:
            benchmark_series[asset] = df_raw.set_index("date")["close"]
        else:
            failed_tickers.append(ticker)
    _bm_status.update(label="Benchmark data ready.", state="complete", expanded=False)

if failed_tickers:
    st.warning(
        f"Could not fetch benchmark data for: **{', '.join(failed_tickers)}**. "
        "Showing static fallback metrics. Check your Alpaca API keys in `.env`.",
        icon="⚠️",
    )

# ---- Compute benchmark metrics ----
if benchmark_series:
    assets_ordered = [a for a in ASSET_TICKERS if a in benchmark_series]
    bm_price_map   = {ASSET_TICKERS[a]: benchmark_series[a] for a in assets_ordered}
    bm_weights_map = {ASSET_TICKERS[a]: allocation[a] for a in assets_ordered}
    bm_return, bm_vol, bm_sharpe, bm_curve = compute_portfolio_metrics(bm_price_map, bm_weights_map)
    if bm_return is None:
        bm_return, bm_vol, bm_sharpe, bm_curve = 0.128, 0.082, 1.42, None
    if "Equities" in benchmark_series and bm_curve is not None:
        spy_return = float(benchmark_series["Equities"].iloc[-1] / benchmark_series["Equities"].iloc[0] - 1)
        bm_delta   = f"{bm_return - spy_return:+.1%} vs SPY"
    else:
        bm_delta = None
else:
    bm_return, bm_vol, bm_sharpe, bm_curve = 0.128, 0.082, 1.42, None
    bm_delta = "+2.3%"

# ---- Fetch and compute user holdings metrics ----
user_metrics_available = False
user_return = user_vol = user_sharpe = user_curve = None
user_failed: list[str] = []

if saved_holdings:
    with st.spinner("Fetching data for your holdings…"):
        user_price_series: dict = {}
        weights_map = {h["ticker"]: h["weight"] for h in saved_holdings}
        for h in saved_holdings:
            df_raw = _fetch_ticker(h["ticker"], h.get("market", "US"))
            if df_raw is not None and len(df_raw) > 20:
                user_price_series[h["ticker"]] = df_raw.set_index("date")["close"]
            else:
                user_failed.append(h["ticker"])

    if user_price_series:
        user_return, user_vol, user_sharpe, user_curve = compute_portfolio_metrics(
            user_price_series, weights_map
        )
        if user_return is not None:
            user_metrics_available = True

    if user_failed:
        st.warning(
            f"Could not fetch data for: **{', '.join(user_failed)}**. "
            "These holdings were excluded from your metrics.",
            icon="⚠️",
        )

# ---- Pre-compute active curve and PDF inputs ----
active_curve    = user_curve if user_metrics_available else bm_curve
metrics_source  = "your holdings" if user_metrics_available else "cluster benchmark"
display_return  = user_return  if user_metrics_available else bm_return
display_vol     = user_vol     if user_metrics_available else bm_vol
display_sharpe  = user_sharpe  if user_metrics_available else bm_sharpe

if active_curve is not None:
    _curve_dates  = [str(d) for d in active_curve.index.tolist()]
    _curve_values = active_curve.tolist()
else:
    _curve_dates  = []
    _curve_values = []

with st.spinner("Generating portfolio report..."):
    pdf_bytes = generate_pdf_report(
        username           = name,
        risk_profile       = risk_profile,
        user_age           = int(user.get("age", 0)),
        income_range       = str(user.get("income_range", "")),
        investment_horizon = str(user.get("investment_horizon", "")),
        experience         = str(user.get("experience", "")),
        goals              = str(user.get("goals", "")),
        risk_tolerance     = int(user.get("risk_tolerance", 5)),
        total_return       = display_return,
        ann_vol            = display_vol,
        sharpe             = display_sharpe,
        metrics_source     = metrics_source,
        curve_dates        = _curve_dates,
        curve_values       = _curve_values,
        allocation_labels  = list(allocation.keys()),
        allocation_values  = list(allocation.values()),
        holdings           = saved_holdings,
    )

# ══════════════════════════════════════════════════════
# PORTFOLIO METRICS
# ══════════════════════════════════════════════════════
if user_metrics_available:
    st.markdown(
        "<h3 style='color:#F59E0B;'>Portfolio Metrics "
        "<span style='font-size:13px; color:#A1A1AA; font-weight:400;'>"
        "— based on your holdings</span></h3>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<h3 style='color:#F59E0B;'>Portfolio Metrics "
        "<span style='font-size:13px; color:#A1A1AA; font-weight:400;'>"
        "— cluster benchmark</span></h3>",
        unsafe_allow_html=True,
    )

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Return (1Y)",
        f"{display_return:.1%}",
        delta=(bm_delta if not user_metrics_available else None),
    )
with c2:
    st.metric("Annualised Volatility", f"{display_vol:.1%}")
with c3:
    st.metric("Sharpe Ratio", f"{display_sharpe:.2f}")
with c4:
    st.markdown("<p style='color:#A1A1AA; font-size:14px; margin-bottom:4px;'>Portfolio Report</p>", unsafe_allow_html=True)
    st.download_button(
        label="⬇ Download PDF",
        data=pdf_bytes,
        file_name=f"aiprs_report_{name.lower().replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

st.caption(
    "These figures reflect realized 1-year performance of "
    + ("your entered holdings" if user_metrics_available else "the static cluster benchmark")
    + ". They may differ from the *optimized* allocation and expected return/volatility shown on the "
    "AI Recommendations page, which uses Modern Portfolio Theory rather than fixed cluster weights."
)

st.markdown("---")

# ══════════════════════════════════════════════════════
# PORTFOLIO PERFORMANCE
# ══════════════════════════════════════════════════════
st.markdown("<h3 style='color:#F59E0B;'>Portfolio Performance</h3>", unsafe_allow_html=True)

if active_curve is not None:
    curve_df = active_curve.reset_index()
    curve_df.columns = ["Date", "Portfolio Value"]
    curve_df["Date"] = pd.to_datetime(curve_df["Date"])

    fig = px.line(
        curve_df, x="Date", y="Portfolio Value",
        template="plotly_dark",
        color_discrete_sequence=["#F59E0B"],
    )
    fig.add_hline(
        y=1.0, line_dash="dot",
        line_color="rgba(255,255,255,0.18)",
        annotation_text="Starting value",
        annotation_font_color="#A1A1AA",
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20), height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", size=12, color="#E4E4E7"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
        yaxis=dict(tickformat=".3f", gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig, use_container_width=True, config=modules.utils.PLOTLY_MODEBAR_CONFIG)

    if user_metrics_available:
        tickers_display = " · ".join(h["ticker"] for h in saved_holdings)
        st.caption(f"Your portfolio: {tickers_display} · 1-year performance")
    else:
        st.caption(
            f"Blended {risk_profile} benchmark — SPY (Equities) · AGG (Fixed Income) · "
            f"GLD (Commodities) · BIL (Cash) · Data via Alpaca IEX feed"
        )
else:
    np.random.seed(42)
    df_growth = pd.DataFrame({
        "Date":            pd.date_range("2025-01-01", periods=60),
        "Portfolio Value": np.cumsum(np.random.randn(60)) + 100,
    })
    fig = px.line(df_growth, x="Date", y="Portfolio Value",
                  template="plotly_dark", color_discrete_sequence=["#F59E0B"])
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=400,
                      font=dict(family="Inter", size=12, color="#E4E4E7"))
    st.plotly_chart(fig, use_container_width=True, config=modules.utils.PLOTLY_MODEBAR_CONFIG)
    st.caption("⚠️ Live data unavailable — showing illustrative chart.")

st.markdown("---")

# ══════════════════════════════════════════════════════
# HOLDINGS INPUT
# ══════════════════════════════════════════════════════
st.markdown("<h3 style='color:#F59E0B;'>Invested in More Assets? Let Us Know!</h3>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#A1A1AA;'>"
    "Enter the assets you hold and AIPRS will calculate your actual portfolio metrics. "
    "Use <code>TICKER:WEIGHT%</code> format (e.g. <code>AAPL:50, MSFT:30, OGDC.KA:20</code>), "
    "or just ticker names for equal weighting (e.g. <code>AAPL, MSFT, OGDC.KA</code>). "
    "PSX tickers must end with <code>.KA</code>."
    "</p>",
    unsafe_allow_html=True,
)

if saved_holdings:
    st.markdown("<p style='color:#A1A1AA; font-size:13px; margin-bottom:6px;'>Current saved holdings:</p>", unsafe_allow_html=True)
    pills = " &nbsp; ".join(
        f"<span style='background:rgba(217,119,6,0.15);border:1px solid rgba(217,119,6,0.3);"
        f"border-radius:20px;padding:3px 12px;font-size:12px;color:#FCD34D;'>"
        f"{h['ticker']} {h['weight']:.1f}%</span>"
        for h in saved_holdings
    )
    st.markdown(pills, unsafe_allow_html=True)
    st.write("")
    current_text = ", ".join(f"{h['ticker']}:{h['weight']:.1f}" for h in saved_holdings)
else:
    current_text = ""

with st.form("holdings_form"):
    holdings_input = st.text_input(
        "Your holdings",
        value=current_text,
        placeholder="e.g. AAPL:50, MSFT:30, OGDC.KA:20  or  AAPL, MSFT, OGDC.KA",
        help="US tickers via Alpaca · PSX tickers ending in .KA via Yahoo Finance",
    )
    col_save, col_clear = st.columns(2)
    with col_save:
        save_btn  = st.form_submit_button("Save & Recalculate", use_container_width=True)
    with col_clear:
        clear_btn = st.form_submit_button("Clear Holdings", use_container_width=True)

if save_btn:
    if not holdings_input.strip():
        st.error("Please enter at least one ticker.")
    else:
        parsed, err = parse_holdings_input(holdings_input)
        if err:
            st.error(err)
        else:
            ok, msg = modules.utils.update_user(name, {"holdings": parsed})
            if ok:
                st.session_state["_overlay_notif"] = (
                    "Holdings Saved",
                    "Your portfolio metrics are being recalculated.",
                )
                st.rerun()
            else:
                st.error(f"Could not save holdings: {msg}")

if clear_btn:
    ok, msg = modules.utils.update_user(name, {"holdings": []})
    if ok:
        st.session_state["_overlay_notif"] = (
            "Holdings Cleared",
            "Your portfolio will now use the cluster benchmark.",
        )
        st.rerun()
    else:
        st.error(f"Could not clear holdings: {msg}")

st.markdown("---")

# ══════════════════════════════════════════════════════
# PROFILE SUMMARY
# ══════════════════════════════════════════════════════
st.markdown("<h3 style='color:#F59E0B;'>Profile Summary</h3>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.write(f"**Name:** {user.get('name')}")
    st.write(f"**Age:** {user.get('age')}")
    st.write(f"**Income Range:** {user.get('income_range')}")
    st.write(f"**Risk Tolerance:** {user.get('risk_tolerance')}")
    st.write(f"**Investment Horizon:** {user.get('investment_horizon')}")
with col2:
    st.write(f"**Experience Level:** {user.get('experience')}")
    st.write(f"**Primary Goals:** {user.get('goals')}")

    prefs = user.get("preferences", [])
    prefs_display = ", ".join(prefs) if isinstance(prefs, list) and prefs else (prefs or "N/A")
    st.write(f"**Preferred Assets:** {prefs_display}")

    st.markdown(f"""
    <div style='margin-top:6px;'>
        <span style='font-size:13px; color:#A1A1AA; margin-right:8px;'>Risk Cluster</span>
        <span style='
            background-color:{badge_color}22;
            color:{badge_color};
            border:1px solid {badge_color}66;
            border-radius:20px;
            padding:3px 14px;
            font-size:12px;
            font-weight:700;
            letter-spacing:1px;
        '>● {risk_profile}</span>
    </div>
    """, unsafe_allow_html=True)

_BEHAVIORS = {
    "Conservative": {
        "desc": "Prefers stability and consistent returns. Comfortable with low to moderate volatility.",
        "portfolio": "Bonds, dividend-yielding stocks, and stable ETFs.",
    },
    "Moderate": {
        "desc": "Balanced risk and reward approach. Comfortable with standard market fluctuations.",
        "portfolio": "60% equities, 40% bonds and alternative assets.",
    },
    "Aggressive": {
        "desc": "Seeks high returns and prioritises growth. Can tolerate short-term losses and high volatility.",
        "portfolio": "80–90% equities, crypto, and 10–20% fixed income.",
    },
}
_b = _BEHAVIORS.get(risk_profile, {})
if _b:
    st.markdown(f"""
    <div style='
        margin-top:14px;
        background:linear-gradient(135deg,rgba(217,119,6,0.07),rgba(255,255,255,0.01));
        border:1px solid rgba(217,119,6,0.2);
        border-radius:10px;
        padding:14px 18px;
        font-size:13px;
        color:#A1A1AA;
        line-height:1.7;
    '>
        <span style='color:#FCD34D; font-weight:600;'>Investor Behaviour</span><br>
        {_b['desc']}<br>
        <span style='color:#FCD34D; font-weight:600;'>Ideal Portfolio</span><br>
        {_b['portfolio']}
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ══════════════════════════════════════════════════════
# ASSET ALLOCATION PIE
# ══════════════════════════════════════════════════════
st.markdown("<h3 style='color:#F59E0B;'>Recommended Asset Allocation</h3>", unsafe_allow_html=True)

fig_alloc = px.pie(
    values=list(allocation.values()),
    names=list(allocation.keys()),
    color_discrete_sequence=px.colors.sequential.Oranges,
)
fig_alloc.update_traces(
    textinfo="percent",
    textposition="inside",
    pull=[0.02, 0.02, 0.05, 0],
    automargin=True,
    insidetextfont=dict(color="#0B0B0F", size=13, family="Inter"),
)
fig_alloc.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#E4E4E7"),
    showlegend=True,
    legend=dict(
        orientation="v",
        font=dict(color="#E4E4E7", size=13),
        bgcolor="rgba(15,10,0,0.85)",
        bordercolor="rgba(217,119,6,0.3)",
        borderwidth=1,
        x=0.02, y=0.98, xanchor="left", yanchor="top",
    ),
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig_alloc, use_container_width=True, config=modules.utils.PLOTLY_MODEBAR_CONFIG)

st.markdown(
    f"<p style='color:#A1A1AA;'>Allocation tailored to your <b>{risk_profile}</b> risk profile. "
    "The AI engine refines these weights based on your full risk assessment.</p>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ══════════════════════════════════════════════════════
# AI CLUSTER PLACEMENT (3D scatter)
# ══════════════════════════════════════════════════════
st.markdown("<h3 style='color:#F59E0B;'>🧩 Your AI Cluster Placement</h3>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#A1A1AA;'>Where you sit among all investor profiles in the K-Means model's decision space.</p>",
    unsafe_allow_html=True,
)

model_path  = os.path.join(modules.utils.MODEL_DIR, "kmeans_model.pkl")
scaler_path = os.path.join(modules.utils.MODEL_DIR, "scaler.pkl")

if os.path.exists(model_path) and os.path.exists(scaler_path):
    np.random.seed(42)
    _n = 150
    bg_df = pd.DataFrame({
        "Age":           np.random.randint(18, 75, _n),
        "Income_Score":  np.random.randint(1,  5,  _n),
        "Risk_Score":    np.random.randint(1,  11, _n),
        "Horizon_Score": np.random.choice([1, 3, 5, 10], _n),
        "Exp_Score":     np.random.randint(1,  4,  _n),
    })
    _model  = joblib.load(model_path)
    _scaler = joblib.load(scaler_path)
    bg_df["Cluster"] = _model.predict(_scaler.transform(bg_df))
    bg_df["Profile"] = bg_df["Cluster"].map(CLUSTER_LABELS)

    _user_exp  = modules.utils.EXPERIENCE_MAP.get(user.get("experience", "Beginner"), 1)
    _user_risk = user.get("risk_tolerance", 5)
    _user_age  = user.get("age", 30)

    fig_3d = px.scatter_3d(
        bg_df,
        x="Age", y="Risk_Score", z="Exp_Score",
        color="Profile",
        color_discrete_map={
            "Conservative": "#FDE68A",
            "Moderate":     "#F59E0B",
            "Aggressive":   "#B45309",
        },
        title="AI Model Decision Boundaries",
    )
    fig_3d.update_traces(marker=dict(size=4, opacity=0.6))
    fig_3d.add_scatter3d(
        x=[_user_age], y=[_user_risk], z=[_user_exp],
        mode="markers+text",
        text=["📍 YOU"],
        textposition="top center",
        textfont=dict(color="#FFFFFF", size=14),
        marker=dict(size=12, color="#16a34a", symbol="diamond",
                    line=dict(color="#FFFFFF", width=2)),
        name="Your Profile",
    )
    fig_3d.update_layout(
        margin=dict(l=0, r=0, b=0, t=40),
        legend=dict(
            title=dict(text="Investor Segment"),
            x=0.02, y=0.98, xanchor="left", yanchor="top",
            bgcolor="rgba(15,10,0,0.85)",
            bordercolor="rgba(217,119,6,0.3)",
            borderwidth=1,
            font=dict(color="#E4E4E7"),
        ),
    )
    st.plotly_chart(fig_3d, use_container_width=True, config=modules.utils.PLOTLY_MODEBAR_CONFIG)
    st.caption(
        "Classification based on Age, Risk Score, and Experience Score. "
        "Your position (📍) is computed by the trained K-Means model."
    )
else:
    st.warning("Pre-trained AI models not found. Unable to render cluster visualisation.")

modules.utils.render_footer()
