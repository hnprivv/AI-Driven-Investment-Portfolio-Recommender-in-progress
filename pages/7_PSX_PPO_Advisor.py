import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os, sys, json
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import modules.utils as utils
from modules.ai.feature_eng import (
    compute_features, compute_raw_log_returns,
    FeatureNormalizer, encode_user_profile,
)
from modules.ai.ppo_agent import PPOAgent, ACTION_LABELS

PSX_BASE       = "https://psxterminal.com"
MODEL_DIR      = os.path.join(ROOT, "modules", "model", "ppo_psx")
ACTOR_PATH     = os.path.join(MODEL_DIR, "ppo_actor.pt")
NORM_PATH      = os.path.join(MODEL_DIR, "normalizer.pkl")
CONFIG_PATH    = os.path.join(MODEL_DIR, "ppo_config.json")
TRAIN_LOG_PATH = os.path.join(MODEL_DIR, "training_log.json")

ACTION_COLORS = {"BUY": "#00C853", "HOLD": "#F59E0B", "SELL": "#EF4444"}
ACTION_BG     = {"BUY": "rgba(0,200,83,0.10)", "HOLD": "rgba(245,158,11,0.10)", "SELL": "rgba(239,68,68,0.10)"}
ACTION_ICONS  = {"BUY": "▲", "HOLD": "◆", "SELL": "▼"}

_EXCLUDE_SUFFIXES = (
    "-MAY", "-MAYB", "-MAYC", "-MAYD", "-MAYE", "-JUN", "-SEP", "-DEC",
    "ETF", "R1", "R2", "R3", "CPS", "PS", "NV",
)
_EXCLUDE_EXACT = {
    "KSE100", "KSE30", "KMI30", "ALLSHR", "KSE100PR",
    "KMIALLSHR", "MII30", "PSXDIV20",
}

def _is_equity(symbol: str) -> bool:
    s = symbol.upper()
    if s in _EXCLUDE_EXACT:
        return False
    for suffix in _EXCLUDE_SUFFIXES:
        if suffix in s:
            return False
    return True

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="PSX PPO Advisor", page_icon="assets/aiprs.png", layout="wide")
utils.load_css()

# ── Auth ──────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    utils.set_sidebar_header("Guest")
    st.markdown("<div class='custom-title-box'><h1>PSX PPO Advisory Dashboard</h1></div>",
                unsafe_allow_html=True)
    utils.show_auth_wall("our PSX PPO agent's recommendations")
    st.stop()

name = st.session_state.username
utils.set_sidebar_header(name)

# ── Model check ───────────────────────────────────────────────────────────────
actor_ok  = os.path.exists(ACTOR_PATH)
norm_ok   = os.path.exists(NORM_PATH)
config_ok = os.path.exists(CONFIG_PATH)

st.markdown("<div class='custom-title-box'><h1>PSX PPO Advisory Dashboard</h1></div>",
            unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:#A1A1AA;'>"
    "Reinforcement-learning recommendations for <b>Pakistan Stock Exchange</b> — "
    "powered by <b>psxterminal.com</b>. Advisory only, no trades executed.</p>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

if not (actor_ok and norm_ok and config_ok):
    st.warning("**PSX PPO model has not been trained yet.** Run the training script first:", icon="⚠️")
    st.code("python train_ppo_psx.py", language="bash")
    for label, ok in [
        ("ppo_actor.pt", actor_ok), ("normalizer.pkl", norm_ok), ("ppo_config.json", config_ok)
    ]:
        st.markdown(f"{'✅' if ok else '❌'} &nbsp; `modules/model/ppo_psx/{label}`",
                    unsafe_allow_html=True)
    st.stop()


# ── Load model ────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_agent():
    return PPOAgent.load(MODEL_DIR)

@st.cache_resource(show_spinner=False)
def load_normalizer():
    return FeatureNormalizer.load(NORM_PATH)

agent = load_agent()
norm  = load_normalizer()

# ── User profile ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_profile(username):
    user = utils.get_user_by_name(username)
    return dict(user) if user else None

profile = _fetch_profile(name)
if not profile:
    st.error("Could not load your profile. Please log in again.")
    st.stop()

user_vec = encode_user_profile(profile)

# ── Data helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_psx_symbols() -> list[str]:
    try:
        r = requests.get(f"{PSX_BASE}/api/symbols", timeout=8)
        data = r.json()
        if data.get("success"):
            raw = data.get("data", [])
            symbols = []
            for item in raw:
                sym = item if isinstance(item, str) else item.get("symbol", "")
                if sym and _is_equity(sym):
                    symbols.append(sym)
            if len(symbols) > 50:
                return sorted(symbols)
    except Exception:
        pass
    return sorted([
        "ACPL","AGP","AIRLINK","AKBL","ASL","ASTL","ATRL","AVN","BAHL","BATA",
        "BOK","BOP","CHCC","COLG","CSAP","DAWH","DGKC","EFERT","ENGRO","EPCL",
        "FABL","FATIMA","FCCL","FFC","FEROZ","GATM","GHNI","GLAXO","HCAR","HBL",
        "HINOON","HMB","HUBC","ICI","ISL","JVDC","KAPCO","KOHC","KTML","LOADS",
        "LOTCHEM","LUCK","MARI","MCB","MEBL","MLCF","MTL","MUGHAL","NBP","NCL",
        "NESTLE","NETSOL","NML","NRL","OGDC","PAEL","PIOC","POL","PNSC","PPL",
        "PSO","PTC","QUICE","SEARL","SNBL","SNGP","SSGC","SYS","TRG","TREET",
        "UBL","UNITY",
    ])


@st.cache_data(ttl=60, show_spinner=False)
def fetch_live_snapshot() -> dict:
    try:
        r = requests.get(f"{PSX_BASE}/api/market-data", params={"market": "REG"}, timeout=8)
        data = r.json()
        if data.get("success"):
            return data["data"].get("REG", {})
    except Exception:
        pass
    return {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_daily_ohlcv(symbol: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        end   = pd.Timestamp.today()
        start = end - pd.DateOffset(years=5)
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
            if raw is None or len(raw) < 60:
                continue
            raw.columns = [c.lower() for c in raw.columns]
            if "close" not in raw.columns:
                continue
            df = raw[["open", "high", "low", "close", "volume"]].copy()
            df.index = pd.to_datetime(df.index)
            df = df[df["volume"] > 0].dropna()
            if len(df) >= 60:
                return df
    except Exception:
        pass
    return None


def run_ppo(symbol: str) -> dict | None:
    df = fetch_daily_ohlcv(symbol)
    if df is None:
        return None
    try:
        feat_df   = compute_features(df)
        feat_norm = norm.transform(feat_df)
        rec       = agent.advise(feat_norm[-1], user_vec)
        rec["last_close"] = float(df["close"].iloc[-1])
        rec["ret_1d"]     = float(
            (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100
            if len(df) >= 2 else 0.0
        )
        return rec
    except Exception:
        return None


# ── Risk profile helpers ──────────────────────────────────────────────────────
_CLUSTER_LABELS = {
    0: ("Conservative",    "#4CAF50", "76,175,80",   "Prefers stability and capital preservation."),
    1: ("Moderate",        "#F59E0B", "245,158,11",  "Balances growth and security with moderate risk."),
    2: ("Aggressive",      "#FF9800", "255,152,0",   "Pursues above-average returns; accepts volatility."),
    3: ("Very Aggressive", "#FF3D00", "255,61,0",    "Seeks maximum returns; comfortable with high risk."),
}

def _risk_bar_html(risk: int) -> str:
    pips = ""
    for i in range(1, 11):
        if i <= risk:
            c = "#4CAF50" if i <= 3 else "#FF9800" if i <= 6 else "#FF3D00"
        else:
            c = "rgba(255,255,255,0.1)"
        pips += (f"<div style='flex:1;min-width:0;height:8px;border-radius:3px;"
                 f"background:{c};margin-right:2px;'></div>")
    return (f"<div style='display:flex;align-items:center;width:100%;margin:4px 0;'>{pips}</div>"
            f"<div style='color:#A1A1AA;font-size:11px;margin-top:2px;'>{risk} / 10</div>")

def _pill(text, color="#A1A1AA"):
    return (f"<span style='background:rgba(255,255,255,0.07);color:{color};"
            f"border:1px solid rgba(255,255,255,0.1);border-radius:20px;"
            f"padding:2px 10px;font-size:12px;font-weight:600;'>{text}</span>")


# ══════════════════════════════════════════════════════════════════════════════
# TWO-COLUMN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
left_col, right_col = st.columns([1, 2.2], gap="large")

# ── LEFT: controls + profile ──────────────────────────────────────────────────
with left_col:
    st.markdown("<h3 style='color:#F59E0B;'>🔍 Filters</h3>", unsafe_allow_html=True)

    # Symbol search
    search_query = st.text_input("Search symbol", placeholder="e.g. HBL, ENGRO, LUCK")

    # Signal filter
    selected_actions = st.multiselect(
        "Show only", options=["BUY", "HOLD", "SELL"],
        default=[], placeholder="All signals",
    )

    # How many to display
    max_display = st.slider(
        "Stocks to display", min_value=10, max_value=100, value=30, step=10,
        help="Fewer stocks = faster loading"
    )

    # Refresh + analyse button
    st.markdown("<br>", unsafe_allow_html=True)
    analyse_btn = st.button("📊 Analyse", use_container_width=True, type="primary")
    refresh_btn = st.button("⟳ Refresh Data", use_container_width=True)
    if refresh_btn:
        st.cache_data.clear()
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Detailed single stock view ────────────────────────────────────────────
    st.markdown("<h3 style='color:#F59E0B;'>📈 Detailed View</h3>", unsafe_allow_html=True)
    detail_sym = st.text_input(
        "Enter any PSX symbol:",
        placeholder="e.g. HBL, MEBL, SYS, DAWH",
        help="Any PSX Regular Market equity with data on Yahoo Finance",
    ).strip().upper()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Risk profile card (same style as 7_US_PPO_Advisor.py) ───────────────────
    st.markdown("<h3 style='color:#F59E0B;'>👤 Your Risk Profile</h3>", unsafe_allow_html=True)

    risk_val = int(profile.get("risk_tolerance", 5))
    cluster  = int(profile["cluster"]) if profile.get("cluster") is not None else 1
    cl_label, cl_color, cl_rgb, cl_desc = _CLUSTER_LABELS.get(
        cluster, ("Unknown", "#A1A1AA", "161,161,170", ""))
    row_s = "border-bottom:1px solid rgba(255,255,255,0.05);padding:8px 0;"

    st.markdown(
        f"""<div style='background:rgba({cl_rgb},0.07);border-radius:14px;
                    border:1px solid rgba({cl_rgb},0.25);border-top:4px solid {cl_color};
                    padding:16px 18px;'>
          <span style='background:{cl_color}22;color:{cl_color};border:1px solid {cl_color}55;
                       border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700;'>
            ● {cl_label}
          </span>
          <div style='color:#A1A1AA;font-size:11px;margin-top:6px;'>{cl_desc}</div>
          <table style='width:100%;font-size:13px;color:#E4E4E7;border-collapse:collapse;margin-top:10px;'>
            <tr style='{row_s}'>
              <td style='color:#A1A1AA;width:45%;vertical-align:top;padding-top:10px;'>⚡ Risk</td>
              <td style='padding-top:6px;'>{_risk_bar_html(risk_val)}</td>
            </tr>
            <tr style='{row_s}'>
              <td style='color:#A1A1AA;'>⏳ Horizon</td>
              <td>{_pill(str(profile.get("investment_horizon","N/A")))}</td>
            </tr>
            <tr style='{row_s}'>
              <td style='color:#A1A1AA;'>🎓 Experience</td>
              <td>{_pill(str(profile.get("experience","N/A")))}</td>
            </tr>
            <tr>
              <td style='color:#A1A1AA;'>🎂 Age</td>
              <td>{_pill(str(profile.get("age","N/A")))}</td>
            </tr>
          </table>
        </div>""",
        unsafe_allow_html=True,
    )


# ── RIGHT: results ────────────────────────────────────────────────────────────
with right_col:

    # ── Detailed single stock (top of right col) ──────────────────────────────
    if detail_sym:
        with st.spinner(f"Loading {detail_sym} …"):
            df_detail    = fetch_daily_ohlcv(detail_sym)
            detail_rec   = run_ppo(detail_sym)
            live_snap_d  = fetch_live_snapshot()

        if df_detail is None or detail_rec is None:
            st.warning(
                f"**{detail_sym}** — no sufficient data found on Yahoo Finance. "
                "Check the symbol is a valid PSX Regular Market equity.",
                icon="⚠️",
            )
        else:
            action = detail_rec["action"]
            acolor = ACTION_COLORS[action]
            conf   = detail_rec["confidence"] * 100
            probs  = detail_rec["probabilities"]
            tick   = live_snap_d.get(detail_sym, {})
            price  = tick.get("price") or detail_rec.get("last_close", 0)
            chg    = tick.get("changePercent", 0) * 100 or detail_rec.get("ret_1d", 0)

            # Recommendation banner
            st.markdown(
                f"""<div style='background:{ACTION_BG[action]};border:1px solid {acolor}44;
                            border-radius:14px;padding:20px 24px;margin-bottom:16px;
                            display:flex;justify-content:space-between;align-items:center;'>
                  <div>
                    <div style='font-size:13px;color:#A1A1AA;'>
                      Advisory Recommendation for <b>{detail_sym}</b>
                    </div>
                    <div style='font-size:44px;font-weight:800;color:{acolor};line-height:1.1;'>
                      {ACTION_ICONS[action]} {action}
                    </div>
                    <div style='font-size:20px;font-weight:700;color:#E4E4E7;margin-top:4px;'>
                      PKR {price:,.1f}
                      <span style='font-size:13px;color:{"#00C853" if chg>=0 else "#EF4444"};margin-left:8px;'>
                        {"▲" if chg>=0 else "▼"} {abs(chg):.2f}%
                      </span>
                    </div>
                  </div>
                  <div style='text-align:right;'>
                    <div style='font-size:11px;color:#A1A1AA;'>Confidence</div>
                    <div style='font-size:40px;font-weight:800;color:{acolor};'>{conf:.1f}%</div>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

            # Probability bars
            prob_fig = go.Figure()
            bar_colors = {"BUY": "#00C853", "SELL": "#EF4444", "HOLD": "#F59E0B"}
            for a in ["SELL", "HOLD", "BUY"]:
                prob_fig.add_trace(go.Bar(
                    x=[probs[a]], y=[a], orientation="h",
                    marker_color=bar_colors[a],
                    text=f"{probs[a]*100:.1f}%", textposition="inside", name=a,
                ))
            prob_fig.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", height=130,
                margin=dict(l=10,r=10,t=5,b=5),
                xaxis=dict(range=[0,1], tickformat=".0%", color="#A1A1AA"),
                yaxis=dict(color="#A1A1AA"),
                showlegend=False, barmode="stack",
            )
            st.plotly_chart(prob_fig, use_container_width=True,
                            config={"displayModeBar": False})
            st.caption("Figure: PPO agent's action probability distribution (Buy / Hold / Sell) for the selected ticker.")

            # Candlestick chart
            plot_df = df_detail.tail(120)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=plot_df.index,
                open=plot_df["open"], high=plot_df["high"],
                low=plot_df["low"],   close=plot_df["close"],
                increasing_line_color="#00C853",
                decreasing_line_color="#EF4444",
                name="Price",
            ))
            last_date = plot_df.index[-1]
            fig.add_shape(
                type="line", x0=last_date, x1=last_date, y0=0, y1=1, yref="paper",
                line=dict(color=acolor, dash="dash", width=2),
            )
            fig.add_annotation(
                x=last_date, y=0.95, yref="paper",
                text=f"{ACTION_ICONS[action]} {action} ({conf:.1f}%)",
                showarrow=False, font=dict(color=acolor, size=12),
                xanchor="left", bgcolor="rgba(0,0,0,0.5)", borderpad=4,
            )
            fig.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", height=320,
                margin=dict(l=10,r=10,t=10,b=10),
                xaxis=dict(color="#A1A1AA", gridcolor="rgba(255,255,255,0.04)",
                           rangeslider_visible=False),
                yaxis=dict(color="#A1A1AA", gridcolor="rgba(255,255,255,0.06)",
                           tickprefix="PKR "),
                hovermode="x unified", showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={**utils.PLOTLY_MODEBAR_CONFIG, "scrollZoom": True})
            st.caption(f"Figure: {detail_sym} candlestick price chart (last 120 sessions) with the agent's current recommendation marked.")

            # Key indicators
            feat_df = compute_features(df_detail)
            lf = feat_df.iloc[-1]
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("RSI (14)",       f"{lf['rsi_14']*100:.1f}",
                      "Oversold" if lf["rsi_14"] < 0.3 else "Overbought" if lf["rsi_14"] > 0.7 else "Neutral")
            i2.metric("Bollinger Pos.", f"{lf['bb_pos']:.2f}",
                      "Near Lower" if lf["bb_pos"] < 0.3 else "Near Upper" if lf["bb_pos"] > 0.7 else "Mid-Band")
            i3.metric("EMA Trend",      f"{lf['ema_ratio_short']*100:+.2f}%",
                      "Bullish" if lf["ema_ratio_short"] > 0 else "Bearish")
            i4.metric("Volatility 20d", f"{lf['vol_20']*100:.2f}%",
                      "High" if lf["vol_20"] > 0.02 else "Normal")

            st.markdown("---")

    # ── Dashboard: all stocks ─────────────────────────────────────────────────
    with st.spinner("Loading PSX symbols …"):
        all_symbols = fetch_psx_symbols()

    if search_query:
        display_symbols = [s for s in all_symbols if search_query.upper() in s]
    else:
        display_symbols = all_symbols[:max_display]

    st.caption(
        f"📋 **{len(all_symbols)}** PSX equity symbols available — "
        f"showing **{len(display_symbols)}**."
    )

    # Run PPO
    with st.spinner(f"Analysing {len(display_symbols)} stocks …"):
        live_snap = fetch_live_snapshot()
        results   = []
        progress  = st.progress(0, text="Loading …")
        for i, sym in enumerate(display_symbols):
            rec = run_ppo(sym)
            if rec:
                tick = live_snap.get(sym, {})
                results.append({
                    "symbol":     sym,
                    "live_price": tick.get("price"),
                    "live_pct":   tick.get("changePercent", 0) * 100,
                    **rec,
                })
            progress.progress((i+1) / max(len(display_symbols),1),
                               text=f"Analysing {sym} …")
        progress.empty()

    if selected_actions:
        results = [r for r in results if r["action"] in selected_actions]

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

    if total:
        buy_pct  = n_buy  / total * 100
        hold_pct = n_hold / total * 100
        sell_pct = n_sell / total * 100
        st.markdown(
            f"""<div style='margin:8px 0 16px 0;'>
              <div style='font-size:12px;color:#A1A1AA;margin-bottom:5px;'>Overall Market Sentiment</div>
              <div style='display:flex;height:10px;border-radius:5px;overflow:hidden;'>
                <div style='width:{buy_pct}%;background:#00C853;'></div>
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

    # Stock cards — 3 per row, BUY first
    order = {"BUY": 0, "HOLD": 1, "SELL": 2}
    results_sorted = sorted(results, key=lambda r: (order[r["action"]], -r["confidence"]))

    if not results_sorted:
        st.info("No results. Try adjusting filters or search.")
    else:
        cols = st.columns(3)
        for i, r in enumerate(results_sorted):
            action = r["action"]
            acolor = ACTION_COLORS[action]
            abg    = ACTION_BG[action]
            aicon  = ACTION_ICONS[action]
            conf   = r["confidence"] * 100
            probs  = r["probabilities"]
            price  = r.get("live_price") or r.get("last_close", 0)
            chg    = r.get("live_pct") or r.get("ret_1d", 0)
            ccolor = "#00C853" if chg >= 0 else "#EF4444"
            carrow = "▲" if chg >= 0 else "▼"
            plabel = "Live" if r.get("live_price") else "Close"
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
                          <div style='font-size:18px;font-weight:700;color:#E4E4E7;'>PKR {price:,.1f}</div>
                          <div style='font-size:11px;color:{ccolor};'>
                            {carrow} {abs(chg):.2f}% <span style='color:#6B7280;'>({plabel})</span>
                          </div>
                        </div>
                        <div style='text-align:right;'>
                          <div style='font-size:11px;color:#A1A1AA;'>Confidence</div>
                          <div style='font-size:18px;font-weight:700;color:{acolor};'>{conf:.1f}%</div>
                        </div>
                      </div>
                      <div style='margin-top:8px;'>
                        <div style='display:flex;height:5px;border-radius:3px;overflow:hidden;'>
                          <div style='width:{buy_w}%;background:#00C853;'></div>
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

    # Training log
    if os.path.exists(TRAIN_LOG_PATH):
        with st.expander("Model Training Performance", expanded=False):
            with open(TRAIN_LOG_PATH) as f:
                log_data = json.load(f)
            if log_data:
                log_df  = pd.DataFrame(log_data)
                log_fig = go.Figure()
                for col, color, label in [
                    ("train_return", "#F59E0B", "Train Return"),
                    ("eval_return",  "#00C853", "Eval Return"),
                ]:
                    if col in log_df:
                        log_fig.add_trace(go.Scatter(
                            x=log_df["step"], y=log_df[col],
                            mode="lines+markers", name=label,
                            line=dict(color=color),
                        ))
                log_fig.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", height=260,
                    xaxis=dict(title="Training Steps", color="#A1A1AA"),
                    yaxis=dict(title="Mean Episode Return", color="#A1A1AA"),
                    legend=dict(font=dict(color="#A1A1AA")),
                    margin=dict(l=10,r=10,t=10,b=10),
                )
                st.plotly_chart(log_fig, use_container_width=True,
                                config={"displayModeBar": False})
                best = max(log_data, key=lambda x: x["eval_return"])
                st.caption(
                    f"Best checkpoint: step {best['step']:,} — "
                    f"eval return {best['eval_return']:+.4f}"
                )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<p style='color:#A1A1AA;font-size:12px;'>"
    "PSX PPO agent trained on ~70 liquid PSX stocks — generalises to any PSX Regular Market equity. "
    "Historical data from Yahoo Finance (.KA). "
    "Live prices from psxterminal.com (60s refresh during market hours). "
    "<b>Advisory only — not financial advice.</b></p>",
    unsafe_allow_html=True,
)

utils.render_footer()