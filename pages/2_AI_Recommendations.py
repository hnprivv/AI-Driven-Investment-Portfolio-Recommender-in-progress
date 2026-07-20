import streamlit as st
from collections import Counter
import time
import os, datetime
import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import modules.utils

st.set_page_config(page_title="AIPRS – Recommendations", page_icon="assets/aiprs.png", layout="wide")

modules.utils.load_css()

# ---- Auth guard ----
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    modules.utils.set_sidebar_header("Guest")
    st.markdown("<div class='custom-title-box'><h1>AI Recommendations</h1></div>", unsafe_allow_html=True)
    modules.utils.show_auth_wall("your AI-powered portfolio recommendations")

name = st.session_state.username
modules.utils.set_sidebar_header(name)

user = modules.utils.get_user_by_name(name)
if user is None:
    st.error(f"⚠️ No profile data found for user: {name}. Please update your profile.")
    st.stop()

user_cluster    = int(user.get("cluster", 1))
risk_tolerance  = int(user.get("risk_tolerance", 5))

CLUSTER_LABELS = {0: "Conservative", 1: "Moderate", 2: "Aggressive", 3: "Very Aggressive"}
risk_profile   = CLUSTER_LABELS.get(user_cluster, "Moderate")

# Static fallback used only if live price data can't be fetched — mirrors
# the same cluster-based table used on the Overview page.
CLUSTER_ALLOCATIONS_FALLBACK = {
    0: {"Equities": 30, "Fixed Income": 50, "Commodities": 10, "Cash": 10},
    1: {"Equities": 60, "Fixed Income": 25, "Commodities": 10, "Cash":  5},
    2: {"Equities": 85, "Fixed Income":  5, "Commodities":  8, "Cash":  2},
    3: {"Equities": 90, "Fixed Income":  5, "Commodities":  3, "Cash":  2},
}

ASSET_TICKERS  = {"Equities": "SPY", "Fixed Income": "AGG", "Commodities": "GLD", "Cash": "BIL"}
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
def compute_mpt_allocation(risk_tolerance: int) -> dict | None:
    """
    Mean-variance (Markowitz) optimisation over the same 4-asset universe
    used on the Overview page. Maximises return minus a risk-aversion-weighted
    penalty on variance, long-only, weights summing to 1. Risk aversion is
    interpolated from the user's risk_tolerance score (1-10): lower tolerance
    -> higher aversion -> allocation skews toward Fixed Income/Cash.
    Returns None if live price history isn't available for all 4 assets.
    """
    price_series = {}
    for label, ticker in ASSET_TICKERS.items():
        df = fetch_bars(ticker)
        if df is not None and len(df) >= 30:
            price_series[label] = df.set_index("date")["close"]

    if len(price_series) < len(ASSET_TICKERS):
        return None

    prices_df = pd.DataFrame(price_series).dropna()
    if len(prices_df) < 30:
        return None

    returns  = prices_df.pct_change().dropna()
    ann_returns = returns.mean().values * 252
    ann_cov     = returns.cov().values * 252

    n = len(ASSET_TICKERS)
    risk_free     = 0.045
    risk_aversion = float(np.interp(risk_tolerance, [1, 10], [8.0, 1.0]))

    def objective(w):
        port_return = w @ ann_returns
        port_var    = w @ ann_cov @ w
        return -(port_return - 0.5 * risk_aversion * port_var)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds      = [(0, 1)] * n
    w0          = np.array([1 / n] * n)

    result  = minimize(objective, w0, method="SLSQP", bounds=bounds, constraints=constraints)
    weights = result.x if result.success else w0
    weights = np.clip(weights, 0, None)
    weights = weights / weights.sum()

    port_return = float(weights @ ann_returns)
    port_vol    = float(np.sqrt(weights @ ann_cov @ weights))
    sharpe      = (port_return - risk_free) / port_vol if port_vol > 0 else 0.0

    return {
        "weights":    dict(zip(ASSET_TICKERS.keys(), weights)),
        "exp_return": port_return,
        "exp_vol":    port_vol,
        "sharpe":     sharpe,
    }


# ---- COLLABORATIVE FILTERING ----
def get_collaborative_recs(current_user_name: str):
    """
    Finds assets preferred by other users in the same cluster using MongoDB.
    Returns (recommendations list, cluster id) or (None, error message).
    """
    all_users = modules.utils.get_all_users()
    if not all_users:
        return None, "No user data available."

    # Find the current user
    current_user = next((u for u in all_users if u.get("name") == current_user_name), None)
    if current_user is None:
        return None, "User profile not found."

    user_cluster   = current_user.get("cluster")
    current_prefs  = current_user.get("preferences", [])

    # Handle legacy comma-string preferences
    if isinstance(current_prefs, str):
        current_prefs = [p.strip() for p in current_prefs.split(",")]

    # Neighbors: same cluster, different user
    neighbors = [
        u for u in all_users
        if u.get("cluster") == user_cluster and u.get("name") != current_user_name
    ]

    if not neighbors:
        return None, "No data available for peer comparison yet."

    # Aggregate neighbor preferences
    all_neighbor_prefs = []
    for u in neighbors:
        prefs = u.get("preferences", [])
        if isinstance(prefs, str):
            prefs = [p.strip() for p in prefs.split(",")]
        all_neighbor_prefs.extend(prefs)

    pref_counts     = Counter(all_neighbor_prefs)
    recommendations = [
        (asset, count)
        for asset, count in pref_counts.most_common(5)
        if asset not in current_prefs
    ]

    return recommendations, user_cluster


# ---- HEADER ----
st.markdown("""
<div class='custom-title-box'>
    <h1>AI Recommendations</h1>
</div>
""", unsafe_allow_html=True)

# ---- SECTION 1: CORE AI PORTFOLIO ----
st.markdown("### Your Optimized Portfolio")
st.write("Based on your risk profile and Modern Portfolio Theory, our engine suggests this allocation:")

import plotly.express as px

STRATEGY_INFO = {
    "Conservative":    ("Capital Preservation", "This portfolio prioritises stability, weighting toward Fixed Income and Cash to minimise volatility."),
    "Moderate":        ("Balanced Growth", "This portfolio balances growth and stability across Equities, Fixed Income, and Commodities."),
    "Aggressive":      ("Growth-Focused", "This portfolio prioritises growth, weighting toward Equities and Commodities to maximise expected return."),
    "Very Aggressive": ("Maximum Growth", "This portfolio is heavily weighted toward Equities and Commodities for maximum expected return, accepting higher volatility."),
}

with st.spinner("Optimizing portfolio allocation..."):
    mpt_result = compute_mpt_allocation(risk_tolerance)

if mpt_result:
    weights_map = mpt_result["weights"]
    exp_return  = mpt_result["exp_return"]
    exp_vol     = mpt_result["exp_vol"]
else:
    weights_map = {k: v / 100 for k, v in CLUSTER_ALLOCATIONS_FALLBACK.get(user_cluster, CLUSTER_ALLOCATIONS_FALLBACK[1]).items()}
    exp_return  = None
    exp_vol     = None

if exp_vol is not None:
    vol_label = "Low" if exp_vol < 0.08 else "Medium" if exp_vol < 0.15 else "High"
else:
    vol_label = {"Conservative": "Low", "Moderate": "Medium", "Aggressive": "High", "Very Aggressive": "High"}.get(risk_profile, "Medium")
strategy_title, strategy_desc = STRATEGY_INFO.get(risk_profile, STRATEGY_INFO["Moderate"])

col1, col2 = st.columns([2, 1])
with col1:
    allocation_data = pd.DataFrame({
        'Asset':      list(weights_map.keys()),
        'Percentage': [round(w * 100, 1) for w in weights_map.values()],
    })
    fig_alloc_bar = px.bar(
        allocation_data, x='Asset', y='Percentage',
        template='plotly_dark',
        color='Asset',
        color_discrete_sequence=["#B45309", "#D97706", "#F59E0B", "#FCD34D"]
    )
    fig_alloc_bar.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        height=300,
        font=dict(family="Inter", size=12, color="#E4E4E7"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
    )
    fig_alloc_bar.update_traces(marker_line_width=0)
    st.plotly_chart(fig_alloc_bar, use_container_width=True, config=modules.utils.PLOTLY_MODEBAR_CONFIG)
    if not mpt_result:
        st.caption("⚠️ Live data unavailable — showing illustrative allocation for your risk profile.")
with col2:
    st.info(f"""
    **Strategy: {strategy_title}**

    {strategy_desc}
    """)
    if exp_return is not None:
        st.metric(label="Expected Annual Return", value=f"{exp_return:.1%}")
        st.metric(label="Volatility Risk", value=vol_label, delta=f"{exp_vol:.1%} annualised", delta_color="off")
    else:
        st.metric(label="Expected Annual Return", value="N/A")
        st.metric(label="Volatility Risk", value=vol_label, delta_color="off")

st.caption(
    "This is an *optimized* allocation computed with Modern Portfolio Theory for your risk profile — "
    "it may differ from the realized performance shown on the Overview page, which reflects your actual "
    "holdings (or the static cluster benchmark) rather than this optimized mix."
)

st.markdown("---")

# ---- SECTION 2: COMMUNITY INSIGHTS ----
st.markdown("### 💡 Trending with Investors Like You")
st.write("These assets are popular among other investors who share your risk profile and financial goals.")

recs, status_or_cluster = get_collaborative_recs(name)

if recs:
    max_count = max(count for _, count in recs) if recs else 1
    rec_cols = st.columns(3)
    for i, (asset, count) in enumerate(recs[:3]):
        pct = int((count / max_count) * 100) if max_count > 0 else 0
        with rec_cols[i]:
            st.markdown(f"""
            <div class='metric-card' style='height: 200px; text-align: center;'>
                <h3 style='background:linear-gradient(90deg,#F59E0B,#FCD34D);
                           -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                           background-clip:text; display:inline-block;'>{asset}</h3>
                <p style='color: #A1A1AA; font-size: 13px; margin: 4px 0 8px;'>
                    Held by <b style='color:#E4E4E7;'>{count}</b> of your peers
                </p>
                <div style='width:80%; background:rgba(255,255,255,0.07); border-radius:6px;
                            height:6px; margin: 0 auto 10px;'>
                    <div style='width:{pct}%; background:linear-gradient(90deg,#D97706,#F59E0B);
                                border-radius:6px; height:6px;'></div>
                </div>
                <span style='font-size:11px; color:#A1A1AA;'>{pct}% of peer popularity</span>
            </div>
            """, unsafe_allow_html=True)
elif recs == []:
    st.success("You are already invested in all the top assets for your profile! You are following the trend.")
else:
    st.warning(f"Could not generate insights: {status_or_cluster}")
    st.info("Start adding preferences to your profile to unlock community insights!")

st.write("")
st.write("")

modules.utils.render_footer()