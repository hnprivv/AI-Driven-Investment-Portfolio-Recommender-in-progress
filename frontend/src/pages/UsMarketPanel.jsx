import { useEffect, useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import Select from "../components/Select";
import { getMarketCandles, getMarketQuotes } from "../api";

const TIMEFRAME_OPTIONS_FULL = [
  { label: "1 Min", value: "1Min" },
  { label: "5 Min", value: "5Min" },
  { label: "15 Min", value: "15Min" },
  { label: "1 Hour", value: "1Hour" },
  { label: "1 Day", value: "1Day" },
];

const TIMEFRAME_OPTIONS_SHORT = [
  { label: "5 Min", value: "5Min" },
  { label: "15 Min", value: "15Min" },
  { label: "1 Hour", value: "1Hour" },
  { label: "1 Day", value: "1Day" },
];

const CATEGORIES = {
  Stocks: {
    symbols: {
      AAPL: "Apple", MSFT: "Microsoft", GOOGL: "Google", AMZN: "Amazon",
      TSLA: "Tesla", NVDA: "NVIDIA", META: "Meta", JPM: "JPMorgan",
    },
    tickerCount: 6,
    crypto: false,
    timeframes: TIMEFRAME_OPTIONS_FULL,
    defaultTfIndex: 2,
    currencyPrefix: "$",
  },
  Cryptocurrency: {
    symbols: {
      "BTC/USD": "Bitcoin", "ETH/USD": "Ethereum", "SOL/USD": "Solana",
      "DOGE/USD": "Dogecoin", "AVAX/USD": "Avalanche", "LINK/USD": "Chainlink",
    },
    tickerCount: 4,
    crypto: true,
    timeframes: TIMEFRAME_OPTIONS_FULL,
    defaultTfIndex: 2,
    currencyPrefix: "$",
  },
  "Global Indices": {
    symbols: {
      SPY: "S&P 500 · SPY ETF", QQQ: "NASDAQ-100 · QQQ ETF",
      DIA: "Dow Jones · DIA ETF", IWM: "Russell 2000 · IWM ETF",
      EFA: "MSCI EAFE · EFA ETF", EEM: "Emerging Markets · EEM ETF",
    },
    tickerCount: 4,
    crypto: false,
    timeframes: TIMEFRAME_OPTIONS_SHORT,
    defaultTfIndex: 2,
    currencyPrefix: "$",
    note: "Prices shown are ETF share prices, not index point values. SPY tracks the S&P 500 at ~1/10th its value, DIA tracks the Dow at ~1/100th, etc. Price movements and % changes are accurate — only the absolute number differs from the raw index.",
  },
  Commodities: {
    symbols: {
      GLD: "Gold · GLD ETF (~1/10 oz/share)", SLV: "Silver · SLV ETF (~1 oz/share)",
      USO: "Crude Oil · USO ETF", UNG: "Natural Gas · UNG ETF",
      PDBC: "Diversified · PDBC ETF", CORN: "Corn · CORN ETF",
    },
    tickerCount: 4,
    crypto: false,
    timeframes: TIMEFRAME_OPTIONS_SHORT,
    defaultTfIndex: 2,
    currencyPrefix: "$",
    note: "Prices shown are ETF share prices, not commodity spot prices. GLD (~$240/share) tracks gold at roughly 1/10 oz per share — spot gold is ~$2,400/oz. SLV tracks silver at ~1 oz per share. % changes accurately reflect commodity price movements.",
  },
};

export default function UsMarketPanel({ refreshKey }) {
  const [category, setCategory] = useState("Stocks");
  const cfg = CATEGORIES[category];
  const symbolKeys = Object.keys(cfg.symbols);

  const [selectedSymbol, setSelectedSymbol] = useState(symbolKeys[0]);
  const [timeframe, setTimeframe] = useState(cfg.timeframes[cfg.defaultTfIndex].value);
  const [limit, setLimit] = useState(120);
  const [quotes, setQuotes] = useState({});
  const [candles, setCandles] = useState(null);
  const [candlesLoading, setCandlesLoading] = useState(true);

  function handleCategoryChange(nextCategory) {
    const nextCfg = CATEGORIES[nextCategory];
    setCategory(nextCategory);
    setSelectedSymbol(Object.keys(nextCfg.symbols)[0]);
    setTimeframe(nextCfg.timeframes[nextCfg.defaultTfIndex].value);
  }

  useEffect(() => {
    getMarketQuotes(symbolKeys.slice(0, cfg.tickerCount), cfg.crypto)
      .then(setQuotes)
      .catch(() => setQuotes({}));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, refreshKey]);

  useEffect(() => {
    setCandlesLoading(true);
    getMarketCandles(selectedSymbol, timeframe, limit, cfg.crypto)
      .then((d) => setCandles(d))
      .catch(() => setCandles(null))
      .finally(() => setCandlesLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSymbol, timeframe, limit, refreshKey]);

  const lastBar = candles?.bars?.length ? candles.bars[candles.bars.length - 1] : null;

  return (
    <>
      <h2 className="dash-section-title" style={{ marginTop: 24 }}>
        {category === "Cryptocurrency" ? "Crypto Price Overview" : `${category === "Global Indices" ? "Global Index ETF" : category === "Commodities" ? "Commodity ETF" : "Price"} Overview`}
      </h2>

      <div className="market-category-row">
        {Object.keys(CATEGORIES).map((cat) => (
          <button
            key={cat}
            className={`market-category-pill ${category === cat ? "active" : ""}`}
            onClick={() => handleCategoryChange(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {cfg.note && <div className="info-box" style={{ marginTop: 12 }}>{cfg.note}</div>}

      <div className="ticker-strip">
        {symbolKeys.slice(0, cfg.tickerCount).map((sym) => {
          const q = quotes[sym];
          const color = q && q.chg_pct >= 0 ? "#22C55E" : "#EF4444";
          const arrow = q && q.chg_pct >= 0 ? "▲" : "▼";
          return (
            <div key={sym} className="ticker-pill">
              <div className="ticker-label">{cfg.symbols[sym]}</div>
              <div className="ticker-price">{q ? `$${q.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "…"}</div>
              {q && (
                <div className="ticker-change" style={{ color }}>
                  {arrow} {q.chg_pct >= 0 ? "+" : ""}{q.chg_pct.toFixed(2)}%
                </div>
              )}
            </div>
          );
        })}
      </div>

      <h2 className="dash-section-title" style={{ marginTop: 28 }}>Candlestick Chart</h2>

      <div className="market-controls">
        <div className="market-control">
          <label>Select {category === "Cryptocurrency" ? "Pair" : "Ticker"}</label>
          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            options={symbolKeys.map((sym) => ({ value: sym, label: `${sym} – ${cfg.symbols[sym]}` }))}
          />
        </div>
        <div className="market-control">
          <label>Timeframe</label>
          <Select value={timeframe} onChange={setTimeframe} options={cfg.timeframes} />
        </div>
        <div className="market-control">
          <label htmlFor="bars-range">Bars: {limit}</label>
          <input
            id="bars-range"
            type="range"
            min={30}
            max={300}
            step={30}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="chart-card">
        {candlesLoading ? (
          <p className="dash-caption">Loading chart…</p>
        ) : candles?.bars?.length ? (
          <CandlestickChart
            bars={candles.bars}
            symbol={selectedSymbol}
            isLive={candles.is_live}
            currencyPrefix={cfg.currencyPrefix}
          />
        ) : (
          <p className="dash-caption">⚠️ Chart unavailable — data could not be fetched.</p>
        )}
      </div>

      {lastBar && (
        <div className="ohlc-grid">
          <div className="metric-card">
            <span className="metric-label">Open</span>
            <span className="metric-value">${lastBar.open.toFixed(2)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">High</span>
            <span className="metric-value">${lastBar.high.toFixed(2)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Low</span>
            <span className="metric-value">${lastBar.low.toFixed(2)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Close</span>
            <span className="metric-value">${lastBar.close.toFixed(2)}</span>
            <span className="metric-sub" style={{ color: lastBar.close - lastBar.open >= 0 ? "#22C55E" : "#EF4444" }}>
              {lastBar.close - lastBar.open >= 0 ? "+" : ""}{(lastBar.close - lastBar.open).toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </>
  );
}
