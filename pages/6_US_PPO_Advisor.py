import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os, sys, json, datetime
import requests
from dotenv import load_dotenv

# ── Path / imports ────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

import modules.utils as utils
from modules.ai.feature_eng import (
    compute_features, compute_raw_log_returns,
    FeatureNormalizer, encode_user_profile,
    FEATURE_NAMES, N_MARKET_FEATURES,
)
from modules.ai.ppo_agent import PPOAgent, ACTION_LABELS

ALPACA_DATA_URL = "https://data.alpaca.markets/v2"

ACTION_COLORS = {"BUY": "#22C55E", "HOLD": "#F59E0B", "SELL": "#EF4444"}
ACTION_BG     = {"BUY": "rgba(34,197,94,0.12)", "HOLD": "rgba(245,158,11,0.12)", "SELL": "rgba(239,68,68,0.12)"}
ACTION_ICONS  = {"BUY": "▲", "HOLD": "◆", "SELL": "▼"}

US_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "JPM",   "SPY",  "QQQ",  "GLD",
]

def _alpaca_headers() -> dict | None:
    key    = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None
    return {
        "APCA-API-KEY-ID":     key,
        "APCA-API-SECRET-KEY": secret,
        "accept": "application/json",
    }

st.set_page_config(page_title="US PPO Advisor", page_icon="assets/aiprs.png", layout="wide")
utils.load_css()

# ── Auth ──────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    utils.set_sidebar_header("Guest")
    st.markdown("<div class='custom-title-box'><h1>US PPO Advisory Agent</h1></div>", unsafe_allow_html=True)
    utils.show_auth_wall("our PPO agent's recommendations")

name = st.session_state.username
utils.set_sidebar_header(name)

# ── Model artefact paths ──────────────────────────────────────────────────────
MODEL_DIR      = os.path.join(ROOT, "modules", "model", "ppo")
ACTOR_PATH     = os.path.join(MODEL_DIR, "ppo_actor.pt")
NORM_PATH      = os.path.join(MODEL_DIR, "normalizer.pkl")
CONFIG_PATH    = os.path.join(MODEL_DIR, "ppo_config.json")
TRAIN_LOG_PATH = os.path.join(MODEL_DIR, "training_log.json")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("<div class='custom-title-box'><h1>US PPO Advisory Agent</h1></div>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:#A1A1AA;'>"
    "Reinforcement-learning recommendations based on market signals and your personal risk profile. "
    "<b>Advisory only, no trades are executed on this platform.</b></p>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

# ── Model readiness check ─────────────────────────────────────────────────────
actor_ok  = os.path.exists(ACTOR_PATH)
norm_ok   = os.path.exists(NORM_PATH)
config_ok = os.path.exists(CONFIG_PATH)
model_ready = actor_ok and norm_ok and config_ok

if not model_ready:
    st.warning(
        "**PPO model has not been trained yet.**  "
        "Run the training script from the project root to get started:",
        icon="⚠️",
    )
    st.code("pip install torch\npython train_ppo.py", language="bash")
    with st.expander("Model file status", expanded=True):
        for label, ok in [
            ("ppo_actor.pt (model weights)", actor_ok),
            ("normalizer.pkl (feature scaler)", norm_ok),
            ("ppo_config.json (architecture config)", config_ok),
        ]:
            icon = "✅" if ok else "❌"
            st.markdown(f"{icon} &nbsp; `modules/model/ppo/{label}`", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(
        "**Estimated training time:** ~2-4 hours on CPU · ~30-60 min on GPU.  \n"
        "Training fetches 5 years of daily bars from **Alpaca** for 14 tickers (AAPL, MSFT, SPY ...) "
        "using the API keys already configured in your `.env` file, "
        "then runs 3 million environment steps of PPO across random tickers and user profiles.",
    )
    st.stop()


# ── Load model (cached) ───────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_agent():
    return PPOAgent.load(MODEL_DIR)

@st.cache_resource(show_spinner=False)
def load_normalizer():
    return FeatureNormalizer.load(NORM_PATH)

agent = load_agent()
norm  = load_normalizer()


# ── Load user profile from MongoDB ───────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_profile(username: str) -> dict | None:
    if username == "Guest":
        return None
    user = utils.get_user_by_name(username)
    return dict(user) if user else None

profile = _fetch_profile(name)

if profile is None:
    st.error("Could not load your profile. Please log in again.")
    st.stop()

user_vec = encode_user_profile(profile)


# ── Market data loader ────────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker_data(ticker: str, period_days: int = 400) -> pd.DataFrame | None:
    headers = _alpaca_headers()
    if headers is None:
        return None
    end   = datetime.datetime.utcnow()
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
        url  = f"{ALPACA_DATA_URL}/stocks/{ticker}/bars"
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        bars = resp.json().get("bars", [])
        if not bars:
            return None
        df = pd.DataFrame(bars)
        df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                            "l": "low", "c": "close", "v": "volume"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.iloc[::-1].reset_index(drop=True)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None


# ── Batch inference helper ────────────────────────────────────────────────────
def run_us_ppo(ticker: str) -> dict | None:
    df = fetch_ticker_data(ticker, period_days=400)
    if df is None or len(df) < 60:
        return None
    try:
        feat_df   = compute_features(df)
        feat_norm = norm.transform(feat_df)
        rec = agent.advise(feat_norm[-1], user_vec)
        rec["last_close"] = float(df["close"].iloc[-1])
        rec["ret_1d"] = float(
            (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100
            if len(df) >= 2 else 0.0
        )
        return rec
    except Exception:
        return None


# ── Helper: run inference over a window ──────────────────────────────────────
def run_inference_window(feat_norm: np.ndarray, user_vec: np.ndarray,
                         raw_rets: np.ndarray, risk_scaled: float,
                         window: int = 60) -> list[dict]:
    results = []
    start   = max(0, len(feat_norm) - window)
    for i in range(start, len(feat_norm)):
        obs = np.concatenate([feat_norm[i], user_vec]).astype(np.float32)
        rec = agent.ac.recommend(obs, risk_scaled)
        rec["actual_ret"] = float(raw_rets[i]) if i < len(raw_rets) else 0.0
        results.append(rec)
    return results


# ── Risk profile display helpers ──────────────────────────────────────────────
_CLUSTER_LABELS = {
    0: ("Conservative",    "#4CAF50", "76,175,80",   "Prefers stability and capital preservation over high returns."),
    1: ("Moderate",        "#F59E0B", "245,158,11",  "Balances growth and security with moderate risk exposure."),
    2: ("Aggressive",      "#FF9800", "255,152,0",   "Pursues above-average returns; accepts moderate volatility."),
    3: ("Very Aggressive", "#FF3D00", "255,61,0",    "Seeks maximum returns; comfortable with high volatility."),
}

def _risk_bar_html(risk: int) -> str:
    pips = ""
    for i in range(1, 11):
        if i <= risk:
            pip_color = "#4CAF50" if i <= 3 else "#FF9800" if i <= 6 else "#FF3D00"
        else:
            pip_color = "rgba(255,255,255,0.1)"
        pips += (
            f"<div style='width:16px; height:8px; border-radius:3px; "
            f"background:{pip_color}; margin-right:3px; display:inline-block;'></div>"
        )
    return (
        f"<div style='display:flex; align-items:center; flex-wrap:nowrap; margin:4px 0;'>{pips}</div>"
        f"<div style='color:#A1A1AA; font-size:11px; margin-top:2px;'>{risk} / 10</div>"
    )

def _value_pill(text: str, color: str = "#A1A1AA") -> str:
    return (
        f"<span style='background:rgba(255,255,255,0.07); color:{color}; "
        f"border:1px solid rgba(255,255,255,0.1); border-radius:20px; "
        f"padding:2px 10px; font-size:12px; font-weight:600;'>{text}</span>"
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

left_col, right_col = st.columns([1, 1.6], gap="large")

# ── LEFT COLUMN ───────────────────────────────────────────────────────────────
with left_col:

    # Detailed single-ticker input
    st.markdown("<h3 style='color:#F59E0B;'>📈 Detailed View</h3>", unsafe_allow_html=True)
    detail_ticker = st.text_input(
        "Enter a US ticker for detailed analysis:",
        placeholder="e.g. AAPL, TSLA, NVDA",
    ).strip().upper()

    st.markdown("<br>", unsafe_allow_html=True)

    # Batch dashboard filters
    st.markdown("<h3 style='color:#F59E0B;'>🔍 Filters</h3>", unsafe_allow_html=True)
    search_query = st.text_input("Search ticker", placeholder="e.g. AAPL, SPY")
    selected_actions = st.multiselect(
        "Show only", options=["BUY", "HOLD", "SELL"],
        default=[], placeholder="All signals",
    )
    max_display = st.slider(
        "Stocks to display", min_value=5, max_value=len(US_TICKERS),
        value=len(US_TICKERS), step=1,
        help="Reduce to limit API calls",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    analyse_btn = st.button("📊 Analyse", use_container_width=True, type="primary")
    refresh_btn = st.button("⟳ Refresh Data", use_container_width=True,
                            help="Clear cache and re-fetch latest prices")
    if refresh_btn:
        st.cache_data.clear()
        st.session_state.pop("us_ppo_batch",  None)
        st.session_state.pop("us_detail_res", None)
        st.session_state.pop("us_detail_tkr", None)
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Risk profile card
    st.markdown("<h3 style='color:#F59E0B;'>👤 Your Risk Profile</h3>", unsafe_allow_html=True)

    risk_val = int(profile.get("risk_tolerance", 5))
    cluster  = int(profile["cluster"]) if profile.get("cluster") is not None else 1
    cl_label, cl_color, cl_rgb, cl_desc = _CLUSTER_LABELS.get(
        cluster, ("Unknown", "#A1A1AA", "161,161,170", "No profile description available.")
    )
    row_style = "border-bottom:1px solid rgba(255,255,255,0.05); padding:8px 0;"

    st.markdown(
        f"""
        <div style='
            background: rgba({cl_rgb}, 0.07);
            border-radius: 14px;
            border: 1px solid rgba({cl_rgb}, 0.25);
            border-top: 4px solid {cl_color};
            padding: 16px 18px;
            box-shadow: 0 0 18px rgba({cl_rgb}, 0.15);
        '>
          <div style='margin-bottom:12px;'>
            <span style='
                background:{cl_color}22; color:{cl_color};
                border:1px solid {cl_color}55; border-radius:20px;
                padding:3px 12px; font-size:12px; font-weight:700; letter-spacing:0.5px;
            '>● {cl_label}</span>
            <div style='color:#A1A1AA; font-size:11px; margin-top:6px; line-height:1.5;'>
                {cl_desc}
            </div>
          </div>
          <table style='width:100%; font-size:13px; color:#E4E4E7; border-collapse:collapse;'>
            <tr style='{row_style}'>
                <td style='color:#A1A1AA; width:45%; vertical-align:top; padding-top:10px;'>⚡ Risk tolerance</td>
                <td style='padding-top:6px;'>{_risk_bar_html(risk_val)}</td>
            </tr>
            <tr style='{row_style}'>
                <td style='color:#A1A1AA;'>⏳ Horizon</td>
                <td>{_value_pill(str(profile.get("investment_horizon","N/A")))}</td>
            </tr>
            <tr style='{row_style}'>
                <td style='color:#A1A1AA;'>🎓 Experience</td>
                <td>{_value_pill(str(profile.get("experience","N/A")))}</td>
            </tr>
            <tr style='padding:8px 0;'>
                <td style='color:#A1A1AA;'>🎂 Age</td>
                <td>{_value_pill(str(profile.get("age","N/A")))}</td>
            </tr>
          </table>
          <div style='margin-top:10px; font-size:11px; color:#6B7280;'>
            Profile sourced from your User Form submission.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── RIGHT COLUMN ──────────────────────────────────────────────────────────────
with right_col:

    # ── Detailed single-ticker view ───────────────────────────────────────────
    if detail_ticker:
        # Only re-run inference when the ticker actually changes
        if (
            "us_detail_res" not in st.session_state
            or st.session_state.get("us_detail_tkr") != detail_ticker
        ):
            with st.spinner(f"Fetching data for {detail_ticker} …"):
                df_detail = fetch_ticker_data(detail_ticker, period_days=400)

            if df_detail is None or len(df_detail) < 60:
                st.warning(
                    f"**{detail_ticker}** — could not fetch sufficient data. "
                    "Check the ticker symbol and try again.",
                    icon="⚠️",
                )
            else:
                with st.spinner(f"Running PPO inference for {detail_ticker} …"):
                    try:
                        feat_df_d   = compute_features(df_detail)
                        raw_rets_d  = compute_raw_log_returns(df_detail).reindex(feat_df_d.index).fillna(0.0).values
                        feat_norm_d = norm.transform(feat_df_d)
                        rec_d       = agent.advise(feat_norm_d[-1], user_vec)
                        history_d   = run_inference_window(feat_norm_d, user_vec, raw_rets_d,
                                                           risk_scaled=user_vec[0])
                        st.session_state["us_detail_res"] = {
                            "rec": rec_d, "history": history_d,
                            "df": df_detail, "feat_df": feat_df_d,
                        }
                        st.session_state["us_detail_tkr"] = detail_ticker
                    except Exception as e:
                        st.error(f"Inference error: {e}", icon="❌")

        if st.session_state.get("us_detail_tkr") == detail_ticker and "us_detail_res" in st.session_state:
            _d       = st.session_state["us_detail_res"]
            rec_d    = _d["rec"]
            history_d = _d["history"]
            df_detail = _d["df"]
            feat_df_d = _d["feat_df"]

            action_d  = rec_d["action"]
            conf_d    = rec_d["confidence"]
            probs_d   = rec_d["probabilities"]
            price_d   = float(df_detail["close"].iloc[-1])
            ret_1d    = float(
                (df_detail["close"].iloc[-1] / df_detail["close"].iloc[-2] - 1) * 100
                if len(df_detail) >= 2 else 0.0
            )
            acolor    = ACTION_COLORS[action_d]
            abg       = ACTION_BG[action_d]
            aicon     = ACTION_ICONS[action_d]
            risk_note = (
                "Your conservative risk profile raises the confidence bar for directional actions."
                if user_vec[0] < 0.4
                else "Your aggressive risk profile allows lower-confidence directional calls."
                if user_vec[0] > 0.7
                else ""
            )

            # Recommendation banner
            st.markdown(
                f"""<div style='background:{abg};border:1px solid {acolor}44;border-radius:14px;
                            padding:20px 24px;margin-bottom:16px;
                            display:flex;justify-content:space-between;align-items:center;'>
                  <div>
                    <div style='font-size:13px;color:#A1A1AA;'>
                      Advisory Recommendation for <b>{detail_ticker}</b>
                    </div>
                    <div style='font-size:44px;font-weight:800;color:{acolor};line-height:1.1;'>
                      {aicon} {action_d}
                    </div>
                    <div style='font-size:20px;font-weight:700;color:#E4E4E7;margin-top:4px;'>
                      ${price_d:,.2f}
                      <span style='font-size:13px;color:{"#22C55E" if ret_1d>=0 else "#EF4444"};margin-left:8px;'>
                        {"▲" if ret_1d>=0 else "▼"} {abs(ret_1d):.2f}%
                      </span>
                    </div>
                    <div style='font-size:12px;color:#A1A1AA;margin-top:6px;'>{risk_note}</div>
                  </div>
                  <div style='text-align:right;'>
                    <div style='font-size:11px;color:#A1A1AA;'>Confidence</div>
                    <div style='font-size:40px;font-weight:800;color:{acolor};'>{conf_d*100:.1f}%</div>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

            # Probability bars
            st.markdown(
                "<div style='font-size:13px; color:#A1A1AA; margin-bottom:4px;'>Action probability distribution</div>",
                unsafe_allow_html=True,
            )
            prob_fig = go.Figure()
            for a in ["SELL", "HOLD", "BUY"]:
                prob_fig.add_trace(go.Bar(
                    x=[probs_d[a]], y=[a], orientation="h",
                    marker_color=ACTION_COLORS[a],
                    text=f"{probs_d[a]*100:.1f}%", textposition="inside", name=a,
                ))
            prob_fig.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", height=130,
                margin=dict(l=10, r=10, t=5, b=5),
                xaxis=dict(range=[0, 1], tickformat=".0%", color="#A1A1AA"),
                yaxis=dict(color="#A1A1AA"),
                showlegend=False, barmode="stack",
            )
            st.plotly_chart(prob_fig, use_container_width=True, config={"displayModeBar": False})

            # Key indicators table
            st.markdown("<h4 style='color:#F59E0B; margin-top:10px;'>📊 Key Market Signals</h4>",
                        unsafe_allow_html=True)
            lf = feat_df_d.iloc[-1]
            indicator_rows = [
                ("RSI (14)",           f"{lf['rsi_14']*100:.1f}",
                 "🟢 Oversold" if lf["rsi_14"] < 0.3 else "🔴 Overbought" if lf["rsi_14"] > 0.7 else "🟡 Neutral"),
                ("Bollinger Position", f"{lf['bb_pos']:.2f}",
                 "🟢 Near Lower Band" if lf["bb_pos"] < 0.3 else "🔴 Near Upper Band" if lf["bb_pos"] > 0.7 else "🟡 Mid-Range"),
                ("Stochastic %K",      f"{lf['stoch_k']*100:.1f}",
                 "🟢 Oversold" if lf["stoch_k"] < 0.2 else "🔴 Overbought" if lf["stoch_k"] > 0.8 else "🟡 Neutral"),
                ("EMA Trend (9/21)",   f"{lf['ema_ratio_short']*100:+.2f}%",
                 "🟢 Bullish" if lf["ema_ratio_short"] > 0 else "🔴 Bearish"),
                ("EMA Trend (21/50)",  f"{lf['ema_ratio_long']*100:+.2f}%",
                 "🟢 Bullish" if lf["ema_ratio_long"] > 0 else "🔴 Bearish"),
                ("Volatility (20d)",   f"{lf['vol_20']*100:.2f}%",
                 "🔴 High" if lf["vol_20"] > 0.02 else "🟢 Low"),
                ("Volume Ratio",       f"{lf['volume_ratio']+1:.2f}x",
                 "🔴 Unusual" if abs(lf["volume_ratio"]) > 1.5 else "🟡 Normal"),
            ]
            ind_df = pd.DataFrame(indicator_rows, columns=["Indicator", "Value", "Signal"])
            st.dataframe(ind_df, use_container_width=True, hide_index=True,
                         column_config={
                             "Indicator": st.column_config.TextColumn(width="medium"),
                             "Value":     st.column_config.TextColumn(width="small"),
                             "Signal":    st.column_config.TextColumn(width="medium"),
                         })

            # Price chart with recommendation markers
            hist_len   = len(history_d)
            price_tail = df_detail.tail(hist_len).reset_index(drop=True)
            if len(price_tail) == hist_len:
                dates   = pd.to_datetime(price_tail["timestamp"])
                closes  = price_tail["close"].values
                actions = [h["action"] for h in history_d]

                chart_fig = go.Figure()
                chart_fig.add_trace(go.Scatter(
                    x=dates, y=closes, mode="lines",
                    line=dict(color="#F59E0B", width=2),
                    name="Close Price",
                ))

                def _add_markers(pts, color, symbol, label):
                    if pts:
                        xs, ys = zip(*pts)
                        chart_fig.add_trace(go.Scatter(
                            x=list(xs), y=list(ys), mode="markers",
                            marker=dict(color=color, size=8, symbol=symbol,
                                        line=dict(color="white", width=1)),
                            name=label,
                        ))

                _add_markers(
                    [(dates.iloc[i], closes[i]) for i, a in enumerate(actions) if a == "BUY"],
                    "#22C55E", "triangle-up", "BUY signal",
                )
                _add_markers(
                    [(dates.iloc[i], closes[i]) for i, a in enumerate(actions) if a == "SELL"],
                    "#EF4444", "triangle-down", "SELL signal",
                )
                _add_markers(
                    [(dates.iloc[i], closes[i]) for i, a in enumerate(actions) if a == "HOLD"],
                    "#F59E0B", "circle", "HOLD signal",
                )

                chart_fig.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", height=350,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis=dict(color="#A1A1AA", gridcolor="rgba(255,255,255,0.04)"),
                    yaxis=dict(color="#A1A1AA", gridcolor="rgba(255,255,255,0.06)", tickprefix="$"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(color="#A1A1AA")),
                    hovermode="x unified",
                )
                st.plotly_chart(chart_fig, use_container_width=True, config={**utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})

            # Hit-rate summary
            directional = [h for h in history_d if h["action"] != "HOLD"]
            if directional:
                correct = sum(
                    1 for h in directional
                    if (h["action"] == "BUY"  and h["actual_ret"] > 0)
                    or (h["action"] == "SELL" and h["actual_ret"] < 0)
                )
                hit_rate = correct / len(directional) * 100
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Directional Signals", len(directional))
                c2.metric("Correct Direction",   correct)
                c3.metric("Hit Rate",            f"{hit_rate:.1f}%",
                          delta="above 50%" if hit_rate > 50 else "below 50%",
                          delta_color="normal")
                n_buy  = sum(1 for h in history_d if h["action"] == "BUY")
                n_sell = sum(1 for h in history_d if h["action"] == "SELL")
                n_hold = sum(1 for h in history_d if h["action"] == "HOLD")
                c4.metric("BUY / SELL / HOLD", f"{n_buy} / {n_sell} / {n_hold}")

            # Explainer
            with st.expander("How this recommendation was generated", expanded=False):
                st.markdown("""
**Agent type:** Proximal Policy Optimisation (PPO) Actor-Critic

**State vector (24 features)**
- **Market signals (16):** log returns (1d, 5d, 20d), RSI(14), MACD histogram/ATR,
  Bollinger Band position, EMA ratios (9/21, 21/50), realised volatility (10d, 20d),
  price vs SMA20, volume ratio, ATR ratio, Stochastic %%K, day-of-week (sin/cos).
- **User profile (8):** risk tolerance, cluster (one-hot), investment horizon,
  experience, age.

**Training**
The agent was trained over 3 million environment steps across 14 US equities/ETFs
(AAPL, MSFT, GOOGL, TSLA, SPY, QQQ ...) using 5 years of daily data sourced from
the **Alpaca Market Data API**. Each episode randomly sampled a ticker and a
synthetic user profile to make the agent risk-aware for all profile types.

**Reward design**
BUY  → reward = +next_bar_log_return · risk_scale
SELL → reward = -next_bar_log_return · risk_scale
HOLD → 0 (no directional bet)
Conservative users have higher loss-aversion built into the reward.

**Confidence threshold**
`threshold = 0.50 + 0.10 x (1 - risk_tolerance/10)`

> **Disclaimer:** This is an AI-generated advisory recommendation for educational
> and research purposes only. It does not constitute financial advice.
> AIPRS does **not** execute any real trades.
                """)

            st.markdown("---")

    # ── Batch dashboard ───────────────────────────────────────────────────────
    if not detail_ticker and analyse_btn:
        display_tickers = (
            [t for t in US_TICKERS if search_query.upper() in t]
            if search_query
            else US_TICKERS[:max_display]
        )

        with st.spinner(f"Analysing {len(display_tickers)} US stocks …"):
            results  = []
            progress = st.progress(0, text="Loading …")
            for i, ticker in enumerate(display_tickers):
                rec = run_us_ppo(ticker)
                if rec:
                    results.append({"symbol": ticker, **rec})
                progress.progress(
                    (i + 1) / max(len(display_tickers), 1),
                    text=f"Analysing {ticker} …",
                )
            progress.empty()
        st.session_state["us_ppo_batch"] = results

    if not detail_ticker and "us_ppo_batch" in st.session_state:
        results = st.session_state["us_ppo_batch"]

        if selected_actions:
            results = [r for r in results if r["action"] in selected_actions]

        if not results:
            st.info("No results match the current filters.")
        else:
            # Summary metrics
            n_buy  = sum(1 for r in results if r["action"] == "BUY")
            n_hold = sum(1 for r in results if r["action"] == "HOLD")
            n_sell = sum(1 for r in results if r["action"] == "SELL")
            total  = len(results)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Stocks Analysed", total)
            c2.metric("🟢 BUY",  n_buy,  delta=f"{n_buy/total*100:.0f}%"  if total else None)
            c3.metric("◆ HOLD", n_hold, delta=f"{n_hold/total*100:.0f}%" if total else None, delta_color="off")
            c4.metric("🔴 SELL", n_sell, delta=f"{n_sell/total*100:.0f}%" if total else None, delta_color="inverse")

            buy_pct  = n_buy  / total * 100
            hold_pct = n_hold / total * 100
            sell_pct = n_sell / total * 100
            st.markdown(
                f"""<div style='margin:8px 0 16px 0;'>
                  <div style='font-size:12px;color:#A1A1AA;margin-bottom:5px;'>Overall Market Sentiment</div>
                  <div style='display:flex;height:10px;border-radius:5px;overflow:hidden;'>
                    <div style='width:{buy_pct}%;background:#22C55E;'></div>
                    <div style='width:{hold_pct}%;background:#F59E0B;'></div>
                    <div style='width:{sell_pct}%;background:#EF4444;'></div>
                  </div>
                  <div style='display:flex;gap:16px;margin-top:4px;font-size:11px;color:#A1A1AA;'>
                    <span>🟢 BUY {buy_pct:.0f}%</span>
                    <span>◆ HOLD {hold_pct:.0f}%</span>
                    <span>🔴 SELL {sell_pct:.0f}%</span>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

            # Stock cards — 3 per row, BUY first then HOLD then SELL, by confidence
            order = {"BUY": 0, "HOLD": 1, "SELL": 2}
            results_sorted = sorted(results, key=lambda r: (order[r["action"]], -r["confidence"]))

            cols = st.columns(3)
            for i, r in enumerate(results_sorted):
                action = r["action"]
                acolor = ACTION_COLORS[action]
                abg    = ACTION_BG[action]
                aicon  = ACTION_ICONS[action]
                conf   = r["confidence"] * 100
                probs  = r["probabilities"]
                price  = r.get("last_close", 0)
                chg    = r.get("ret_1d", 0)
                ccolor = "#22C55E" if chg >= 0 else "#EF4444"
                carrow = "▲" if chg >= 0 else "▼"
                buy_w  = int(probs["BUY"]  * 100)
                hold_w = int(probs["HOLD"] * 100)
                sell_w = int(probs["SELL"] * 100)

                with cols[i % 3]:
                    st.markdown(
                        f"""<div style='background:{abg};border:1px solid {acolor}33;
                                    border-left:4px solid {acolor};border-radius:12px;
                                    padding:14px 16px;margin-bottom:14px;'>
                          <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                            <div style='font-size:18px;font-weight:800;color:#E4E4E7;'>{r["symbol"]}</div>
                            <div style='background:{acolor}22;color:{acolor};border:1px solid {acolor}55;
                                        border-radius:20px;padding:4px 12px;font-size:13px;font-weight:800;'>
                              {aicon} {action}
                            </div>
                          </div>
                          <div style='margin-top:10px;display:flex;justify-content:space-between;align-items:baseline;'>
                            <div>
                              <div style='font-size:18px;font-weight:700;color:#E4E4E7;'>${price:,.2f}</div>
                              <div style='font-size:11px;color:{ccolor};'>
                                {carrow} {abs(chg):.2f}%
                              </div>
                            </div>
                            <div style='text-align:right;'>
                              <div style='font-size:11px;color:#A1A1AA;'>Confidence</div>
                              <div style='font-size:18px;font-weight:700;color:{acolor};'>{conf:.1f}%</div>
                            </div>
                          </div>
                          <div style='margin-top:8px;'>
                            <div style='display:flex;height:5px;border-radius:3px;overflow:hidden;'>
                              <div style='width:{buy_w}%;background:#22C55E;'></div>
                              <div style='width:{hold_w}%;background:#F59E0B;'></div>
                              <div style='width:{sell_w}%;background:#EF4444;'></div>
                            </div>
                            <div style='display:flex;justify-content:space-between;font-size:10px;color:#6B7280;margin-top:2px;'>
                              <span>B {buy_w}%</span><span>H {hold_w}%</span><span>S {sell_w}%</span>
                            </div>
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

    elif not detail_ticker and "us_ppo_batch" not in st.session_state:
        st.markdown(
            "<div style='text-align:center; color:#6B7280; padding:60px 20px;'>"
            "Enter a ticker above for a detailed view, or click <b>Analyse</b> to scan all US tickers."
            "</div>",
            unsafe_allow_html=True,
        )


# ── Training log (full width) ─────────────────────────────────────────────────
if os.path.exists(TRAIN_LOG_PATH):
    with st.expander("Training performance log", expanded=False):
        with open(TRAIN_LOG_PATH) as f:
            log_entries = json.load(f)
        if log_entries:
            log_df = pd.DataFrame(log_entries)
            log_fig = go.Figure()
            if "train_return" in log_df:
                log_fig.add_trace(go.Scatter(
                    x=log_df["step"], y=log_df["train_return"],
                    mode="lines+markers", name="Train Return",
                    line=dict(color="#F59E0B"),
                ))
            if "eval_return" in log_df:
                log_fig.add_trace(go.Scatter(
                    x=log_df["step"], y=log_df["eval_return"],
                    mode="lines+markers", name="Eval Return",
                    line=dict(color="#22C55E"),
                ))
            log_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=280,
                xaxis=dict(title="Training Steps", color="#A1A1AA"),
                yaxis=dict(title="Mean Episode Return", color="#A1A1AA"),
                legend=dict(font=dict(color="#A1A1AA")),
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(log_fig, use_container_width=True,
                            config={"displayModeBar": False})

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#A1A1AA; font-size:12px;'>"
    "PPO agent trained on historical data sourced via the <b>Alpaca Market Data API</b> (IEX feed, 15-min delayed).  "
    "Market features are refreshed each session.  "
    "This tool is for <b>advisory purposes only</b> and does not constitute financial advice."
    "</p>",
    unsafe_allow_html=True,
)

utils.render_footer()
