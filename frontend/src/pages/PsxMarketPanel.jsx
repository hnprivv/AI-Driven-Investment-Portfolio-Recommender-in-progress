import { useEffect, useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import Select from "../components/Select";
import { getPsxCandles, getPsxQuotes } from "../api";

const PSX_BLUE_CHIPS = ["HBL", "ENGRO", "LUCK", "MCB", "PPL", "OGDC"];

const PSX_STOCKS = {
  HBL: "Habib Bank Limited", ENGRO: "Engro Corporation", LUCK: "Lucky Cement",
  MCB: "MCB Bank", UBL: "United Bank Limited", PPL: "Pakistan Petroleum",
  OGDC: "Oil & Gas Dev. Company", PSO: "Pakistan State Oil", NESTLE: "Nestle Pakistan",
  SYS: "Systems Limited", TRG: "TRG Pakistan", HUBC: "Hub Power Company",
  ATRL: "Attock Refinery", MEBL: "Meezan Bank", NBP: "National Bank of Pakistan",
  FFC: "Fauji Fertilizer Company", EFERT: "Engro Fertilizers", DGKC: "D.G. Khan Cement",
  COLG: "Colgate-Palmolive Pakistan", GLAXO: "GlaxoSmithKline Pakistan",
};

export default function PsxMarketPanel({ refreshKey }) {
  const [quotes, setQuotes] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState("HBL");
  const [limit, setLimit] = useState(120);
  const [candles, setCandles] = useState(null);
  const [candlesLoading, setCandlesLoading] = useState(true);

  useEffect(() => {
    getPsxQuotes(PSX_BLUE_CHIPS).then(setQuotes).catch(() => setQuotes({}));
  }, [refreshKey]);

  useEffect(() => {
    setCandlesLoading(true);
    getPsxCandles(selectedSymbol, limit)
      .then(setCandles)
      .catch(() => setCandles(null))
      .finally(() => setCandlesLoading(false));
  }, [selectedSymbol, limit, refreshKey]);

  const lastBar = candles?.bars?.length ? candles.bars[candles.bars.length - 1] : null;

  return (
    <>
      <h2 className="dash-section-title" style={{ marginTop: 24 }}>Price Overview</h2>
      <div className="ticker-strip">
        {PSX_BLUE_CHIPS.map((sym) => {
          const q = quotes[sym];
          const color = q && q.chg_pct >= 0 ? "#22C55E" : "#EF4444";
          const arrow = q && q.chg_pct >= 0 ? "▲" : "▼";
          return (
            <div key={sym} className="ticker-pill">
              <div className="ticker-label">{sym}</div>
              <div className="ticker-price">{q ? `PKR ${q.price.toLocaleString(undefined, { maximumFractionDigits: 1 })}` : "…"}</div>
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
      <p className="dash-caption" style={{ margin: "0 0 12px" }}>
        Historical data sourced from Yahoo Finance (.KA). Daily bars only.
      </p>

      <div className="market-controls">
        <div className="market-control">
          <label>Select PSX Stock</label>
          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            options={Object.keys(PSX_STOCKS).map((sym) => ({ value: sym, label: `${sym} – ${PSX_STOCKS[sym]}` }))}
          />
        </div>
        <div className="market-control">
          <label htmlFor="psx-bars-range">Bars: {limit}</label>
          <input
            id="psx-bars-range"
            type="range"
            min={30}
            max={500}
            step={30}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </div>
      </div>

      {candlesLoading ? (
        <p className="dash-caption">Loading chart…</p>
      ) : candles?.bars?.length ? (
        <>
          {candles.live_price != null && (
            <p style={{ margin: "0 0 8px" }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: "#E4E4E7" }}>
                PKR {candles.live_price.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </span>
              <span
                style={{
                  fontSize: 14, marginLeft: 10, fontWeight: 600,
                  color: candles.live_chg_pct >= 0 ? "#22C55E" : "#EF4444",
                }}
              >
                {candles.live_chg_pct >= 0 ? "▲" : "▼"} {Math.abs(candles.live_chg_pct).toFixed(2)}% today
              </span>
              <span style={{ fontSize: 11, marginLeft: 8, color: "#6B7280" }}>Live via psxterminal.com</span>
            </p>
          )}
          <div className="chart-card">
            <CandlestickChart
              bars={candles.bars}
              symbol={selectedSymbol}
              isLive
              currencyPrefix="PKR "
              badgeText=""
            />
          </div>
        </>
      ) : (
        <div className="info-box">
          Could not load data for <b>{selectedSymbol}</b> from Yahoo Finance. The symbol may not be
          available. Try another stock.
        </div>
      )}

      {lastBar && (
        <div className="ohlc-grid">
          <div className="metric-card">
            <span className="metric-label">Open</span>
            <span className="metric-value">PKR {lastBar.open.toFixed(1)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">High</span>
            <span className="metric-value">PKR {lastBar.high.toFixed(1)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Low</span>
            <span className="metric-value">PKR {lastBar.low.toFixed(1)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Close</span>
            <span className="metric-value">PKR {lastBar.close.toFixed(1)}</span>
            <span className="metric-sub" style={{ color: lastBar.close - lastBar.open >= 0 ? "#22C55E" : "#EF4444" }}>
              {lastBar.close - lastBar.open >= 0 ? "+" : ""}{(lastBar.close - lastBar.open).toFixed(1)}
            </span>
          </div>
        </div>
      )}
    </>
  );
}
