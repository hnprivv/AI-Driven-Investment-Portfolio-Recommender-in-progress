import streamlit as st
import modules.utils

st.set_page_config(page_title="AIPRS – Home", page_icon="assets/aiprs.png", layout="wide")

modules.utils.load_css()

# ---- Logo glow — scoped to this page via stImage selector ----
st.markdown("""
<style>
[data-testid="stImage"] img {
    border-radius: 16px;
    animation: logoPulse 3s ease-in-out infinite;
}
</style>
""", unsafe_allow_html=True)

# ---- Auth ----
if 'authenticated' in st.session_state and st.session_state.authenticated and 'username' in st.session_state:
    name = st.session_state.username
else:
    name = 'Guest'

modules.utils.set_sidebar_header(name)

# ---- Helper: custom section divider ----
def section_divider():
    st.markdown("""
    <div style='display:flex; align-items:center; gap:14px; margin:28px 0;'>
        <div style='flex:1; height:1px; background:linear-gradient(90deg,transparent,#D97706);'></div>
        <div style='color:#F59E0B; font-size:13px; text-shadow:0 0 8px rgba(217,119,6,0.6);'>◆</div>
        <div style='flex:1; height:1px; background:linear-gradient(90deg,#F59E0B,transparent);'></div>
    </div>
    """, unsafe_allow_html=True)

# ---- HEADER ----
st.markdown("""
<div class='custom-title-box'>
    <h1>AI-Driven Investment Portfolio Recommender</h1>
</div>
<p style='text-align:center; color:#A1A1AA;'>Empowering investors with data-driven, adaptive portfolio recommendations.</p>
<br>
""", unsafe_allow_html=True)

# ---- HERO SECTION ----
col1, col2 = st.columns([1.3, 0.7], gap="large")
with col1:
    st.markdown("""
    <h2>What is AIPRS?</h2>
    <p style='color:#E4E4E7; font-size:16px; line-height:1.7;'>
    AIPRS is your intelligent investment companion, built to simplify complex portfolio management decisions
    using artificial intelligence. It analyzes market trends, assesses your unique risk profile, and
    constructs optimized portfolios that evolve with market behavior.
    </p>
    <p style='color:#A1A1AA; line-height:1.7;'>
    Whether you're new to investing or a seasoned trader, AIPRS tailors strategies to your comfort level,
    leveraging reinforcement learning and modern portfolio theory to find the ideal balance between risk and reward.
    </p>
    <div style='display:flex; gap:14px; margin-top:22px; flex-wrap:wrap;'>
        <div class='stat-pill'><span class='stat-num'>4</span> Risk Profiles</div>
        <div class='stat-pill'><span class='stat-num'>AI</span> Powered Engine</div>
        <div class='stat-pill'>Stocks · ETFs · Bonds & more</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.image("assets/aiprs_home.png", width="stretch")

section_divider()

# ---- WHY AIPRS ----
st.markdown("<h2>Why Choose AIPRS?</h2>", unsafe_allow_html=True)
st.write("")

cards = [
    ("✨", "Personalized Insights",
     "AIPRS evaluates your risk tolerance, goals, and time horizon to craft a portfolio that fits <b>you</b>."),
    ("◈", "AI-Driven Decisions",
     "Our reinforcement learning engine continuously adapts recommendations based on live market data."),
    ("👁", "Guaranteed Transparency",
     "Visualize portfolio performance, compare strategies, and track your financial progress in real time."),
]

cols = st.columns(3)
for col, (icon, title, desc) in zip(cols, cards):
    with col:
        st.markdown(f"""
        <div class='metric-card'>
            <div style='
                width:52px; height:52px;
                background:linear-gradient(135deg,#D97706,#FCD34D);
                border-radius:50%;
                display:flex; align-items:center; justify-content:center;
                font-size:24px; margin-bottom:14px;
                box-shadow:0 0 18px rgba(217,119,6,0.45);
                flex-shrink:0;
            '><span style='filter:grayscale(1) brightness(0);'>{icon}</span></div>
            <h3 style='margin:0 0 8px; font-size:16px;'>{title}</h3>
            <p style='color:#A1A1AA; margin:0; font-size:14px; text-align:center; line-height:1.6;'>{desc}</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
section_divider()

# ---- HOW IT WORKS — Step Timeline ----
st.markdown("<h2>How It Works</h2>", unsafe_allow_html=True)
st.write("")

steps = [
    ("Create Your Profile",
     "Sign up and complete your investor profile including your age, goals, risk tolerance, and investment horizon. This data is the foundation for everything the AI does."),
    ("Get Your AI Risk Classification",
     "Our K-Means model analyses your profile and assigns you to an investor cluster, generating a personalised portfolio allocation that reflects your financial goals and risk appetite."),
    ("Explore AI Recommendations",
     "View optimised asset allocations produced by the reinforcement learning engine, tailored specifically to your risk cluster and investment preferences."),
    ("Monitor the Markets",
     "Track US and PSX market data, price movements, and sector performance. US equity prices are delayed by 15 minutes via Alpaca Markets. PSX prices refresh every 60 seconds from psxterminal.com during market hours."),
    ("Analyse News Sentiment",
     "Read AI-analysed financial news headlines. Our NLP model scores market sentiment to help you understand how current events may be influencing your portfolio."),
    ("Run the PPO Advisors",
     "Get BUY, HOLD, and SELL signals from two dedicated reinforcement learning models: one trained on US equities and one trained on Pakistan Stock Exchange equities. Each signal comes with a confidence score and probability breakdown."),
]

_vline = "position:absolute;left:17px;top:18px;bottom:18px;width:2px;background:linear-gradient(180deg,#D97706,#FCD34D,rgba(217,119,6,0.08));"
_circle = "position:absolute;left:-46px;top:10px;width:36px;height:36px;background:linear-gradient(135deg,#D97706,#FCD34D);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:14px;box-shadow:0 0 16px rgba(217,119,6,0.55);z-index:1;"
_card   = "background:linear-gradient(135deg,rgba(217,119,6,0.09),rgba(255,255,255,0.02));border:1px solid rgba(217,119,6,0.25);border-radius:12px;padding:16px 20px;"
_stitle = "font-weight:700;color:#FCD34D;font-size:15px;margin-bottom:6px;"
_sdesc  = "color:#A1A1AA;margin:0;font-size:14px;line-height:1.65;text-align:left;"

timeline_html = f"<div style='position:relative;padding-left:56px;margin-top:8px;'><div style='{_vline}'></div>"
for i, (title, desc) in enumerate(steps):
    mb = "0" if i == len(steps) - 1 else "22px"
    timeline_html += (
        f"<div style='position:relative;margin-bottom:{mb};'>"
        f"<div style='{_circle}'>{i + 1}</div>"
        f"<div style='{_card}'>"
        f"<div style='{_stitle}'>Step {i + 1} — {title}</div>"
        f"<p style='{_sdesc}'>{desc}</p>"
        f"</div></div>"
    )
timeline_html += "</div>"
st.markdown(timeline_html, unsafe_allow_html=True)

section_divider()

# ---- OUR MISSION ----
st.markdown("<h2>Our Mission</h2>", unsafe_allow_html=True)
st.markdown("""
<div style='
    background: linear-gradient(135deg, rgba(217,119,6,0.08), rgba(255,255,255,0.02));
    border: 1px solid rgba(217,119,6,0.25);
    border-left: 4px solid #D97706;
    border-radius: 14px;
    padding: 24px 28px;
    box-shadow: 0 0 22px rgba(217,119,6,0.10);
    margin-top: 12px;
'>
    <p style='color:#A1A1AA; margin:0 0 12px; font-size:15px; line-height:1.75; text-align:left;'>
        Investing shouldn't be overwhelming. AIPRS combines cutting-edge machine learning with intuitive design
        to make intelligent investing accessible, transparent, and adaptive. No jargon, no guesswork.
    </p>
    <p style='color:#E4E4E7; margin:0; font-size:15px; line-height:1.75; text-align:left;'>
        Your financial decisions should evolve as the markets do. Let AIPRS handle the complexity,
        so you can focus on what matters — your goals.
    </p>
</div>
""", unsafe_allow_html=True)

section_divider()

# ---- CTA ----
st.markdown("""
<div style='text-align:center; background:linear-gradient(135deg,rgba(217,119,6,0.08),rgba(252,211,77,0.04)); border:1px solid rgba(217,119,6,0.22); border-radius:20px; padding:36px 24px 32px; box-shadow:0 0 32px rgba(217,119,6,0.10);'>
    <h3 style='margin:0 0 14px;'>Ready to Begin?</h3>
    <p style='color:#A1A1AA; font-size:15px; margin:0 0 6px; text-align:center;'>
        Click <a href='/User_Form' target='_self' style='color:#FCD34D; font-weight:700; text-decoration:underline; text-shadow:0 0 8px rgba(252,211,77,0.4);'>here</a>
        to get started with AIPRS today!
    </p>
    <p style='color:#A1A1AA; font-size:13px; margin:0; text-align:center;'>No commitment. Get your AI risk profile in under 2 minutes.</p>
</div>
""", unsafe_allow_html=True)

modules.utils.render_footer()
