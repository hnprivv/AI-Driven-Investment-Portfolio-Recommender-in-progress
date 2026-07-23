---
title: AIPRS Backend
emoji: 📈
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
---

<!--
  The block above is Hugging Face Spaces' required config header — it's read
  from README.md at the repo root when this repo is pushed as a Space's git
  remote, and tells HF to build the Dockerfile at the repo root and expose
  port 7860. Harmless to any other viewer (GitHub just renders it as-is).
-->

# AIPRS – AI-Powered Portfolio Recommendation System

**AIPRS** is an intelligent investment companion built as a Final Year Project. It profiles investors using machine learning, recommends optimised portfolio allocations, delivers live and delayed market data across two exchanges, analyses financial news sentiment, and provides reinforcement learning-based trading signals — all through a Streamlit dashboard.

---

## System Architecture

The system operates across four layers:

1. **User Interface** — Streamlit multi-page dashboard with custom CSS theming.
2. **ML / AI Layer**
   - **K-Means Clustering** — segments users into three risk profiles: Conservative, Moderate, and Aggressive.
   - **Modern Portfolio Theory** — generates cluster-specific asset allocations (Equities, Fixed Income, Commodities, Cash).
   - **PPO Reinforcement Learning** — two trained PPO agents produce BUY / HOLD / SELL signals with confidence scores: one for US equities and one for Pakistan Stock Exchange (PSX) equities.
   - **NLP Sentiment Analysis** — a Hugging Face Transformers pipeline scores financial news headlines as Positive, Neutral, or Negative.
3. **Data Layer**
   - US equity prices: Alpaca Markets API (IEX feed, 15-minute delay).
   - PSX historical prices: Yahoo Finance via `yfinance` (`.KA` suffix tickers).
   - PSX live prices: psxterminal.com (60-second refresh during market hours).
4. **Storage Layer** — MongoDB Atlas. User documents store name, email, bcrypt-hashed password, profile answers, cluster assignment, and saved holdings.

---

## Prerequisites

- Python 3.10 or higher
- A MongoDB Atlas cluster with a database user and connection URI
- An Alpaca Markets account (paper or live) with API key and secret

---

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/hnprivv/AIPRS
cd AIPRS
```

### 2. Create a Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root with the following keys:

```
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2
MONGODB_URI=your_mongodb_atlas_connection_string
TRANSFORMERS_VERBOSITY=error
```

### 5. Train the Models (first run only)

**K-Means clustering model:**
```bash
python train_model.py
```
Outputs `modules/model/kmeans_model.pkl` and `modules/model/scaler.pkl`.

**PPO advisor — US equities:**
```bash
python train_ppo.py
```
Outputs model files under `modules/model/ppo/`.

**PPO advisor — PSX equities:**
```bash
python train_ppo_psx.py
```
Outputs model files under `modules/model/ppo_psx/`.

> Pre-trained model files are included in the repository. Re-training is only required if the underlying data or architecture changes.

### 6. Run the Application

```bash
streamlit run Home.py
```

The dashboard opens automatically in the default browser.

---

## Deployment (Hugging Face Spaces)

1. Create a new Space at huggingface.co/new-space with SDK **Streamlit**.
2. Add it as a git remote and push this repo's contents:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
   git push space main
   ```
3. In the Space's **Settings -> Repository secrets**, add: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`, `MONGODB_URI`, `TRANSFORMERS_VERBOSITY`. Never commit `.env` -- it stays git-ignored.
4. In MongoDB Atlas -> Network Access, allow access from `0.0.0.0/0`, since Spaces containers don't have a static IP.
5. The Space rebuilds automatically on push and serves `Home.py` per the `app_file` key in the frontmatter at the top of this file.

---

## Project Structure

```
AIPRS_Dashboard/
├── Home.py                      # Landing page
├── train_model.py               # Trains and saves the K-Means model
├── train_ppo.py                 # Trains the US equities PPO agent
├── train_ppo_psx.py             # Trains the PSX equities PPO agent
├── requirements.txt             # Python dependencies
├── styles.css                   # Global custom CSS
├── .env                         # Environment variables (not committed)
├── .streamlit/
│   └── config.toml              # Streamlit theme and server config
├── pages/
│   ├── 0_User_Form.py           # Investor profile signup
│   ├── 1_Overview.py            # Portfolio overview, metrics, holdings, PDF report
│   ├── 2_AI_Recommendations.py  # Cluster-based allocation recommendations
│   ├── 3_Market_Overview.py     # US and PSX market data and charts
│   ├── 4_News_Sentiment.py      # Financial news with NLP sentiment scores
│   ├── 5_Feedback_Changes.py    # User feedback form
│   ├── 6_US_PPO_Advisor.py      # PPO trading signals for US equities
│   ├── 7_PSX_PPO_Advisor.py     # PPO trading signals for PSX equities
│   ├── 8_Login.py               # Login and logout
│   └── 9_Settings.py            # Account settings and password change
├── modules/
│   ├── utils.py                 # MongoDB helpers, auth, CSS loader, footer, modals
│   ├── news_fetcher.py          # News API integration
│   └── ai/
│       ├── ppo_agent.py         # PPO agent inference
│       ├── market_env.py        # RL market environment
│       ├── feature_eng.py       # Feature engineering for the PPO models
│       └── sentiment.py         # Hugging Face sentiment pipeline
├── modules/model/
│   ├── kmeans_model.pkl         # Trained K-Means model
│   ├── scaler.pkl               # Feature scaler
│   ├── ppo/                     # Trained US equities PPO model
│   └── ppo_psx/                 # Trained PSX equities PPO model
├── assets/
│   ├── aiprs.png                # Browser tab icon
│   ├── aiprs_home.png           # Homepage hero image
│   └── aiprs_text.png           # Text logo variant
└── data/
    └── users_dataset.json       # Dataset used for K-Means training
```

---

## Key Features

| Feature | Detail |
|---|---|
| Investor Profiling | 7-question form covering age, income, horizon, experience, goals, and risk tolerance |
| Risk Classification | K-Means assigns users to Conservative, Moderate, or Aggressive cluster |
| Portfolio Allocation | MPT-based allocation across Equities, Fixed Income, Commodities, and Cash |
| User Holdings | Users can enter their own holdings (ticker:weight) for personalised portfolio metrics |
| Portfolio Metrics | Total Return, Annualised Volatility, and Sharpe Ratio computed from live price data |
| PDF Report | Downloadable report with investor profile, metrics, equity curve, allocation chart, and holdings |
| Market Data — US | Alpaca Markets IEX feed, 15-minute delayed, daily OHLCV bars |
| Market Data — PSX | Yahoo Finance historical data; psxterminal.com live prices (60s refresh) |
| News Sentiment | NLP-scored headlines: Positive, Neutral, or Negative with confidence |
| PPO Advisor — US | BUY / HOLD / SELL signals with probability breakdown for US equities |
| PPO Advisor — PSX | BUY / HOLD / SELL signals with probability breakdown for PSX equities |
| Authentication | Email and password login with bcrypt hashing; signup with email format, duplicate, and password strength validation |

---

## Notes

- **No real financial advice.** AIPRS is an academic project for research and educational demonstration. It is not regulated by any financial authority and does not constitute investment advice.
- **Alpaca feed.** The IEX feed used is free-tier and carries a 15-minute delay. Real-time data requires a paid Alpaca subscription.
- **Caching.** Streamlit caches market data for 15 minutes (`ttl=900`). To force a refresh, stop the server with `Ctrl+C` and restart.
- **Python version.** Union type hints (`X | Y`) require Python 3.10+. The app will not run on earlier versions.

---

## License

Developed exclusively for academic purposes as part of a Final Year Project (FYP). Not licensed for commercial use.
