import { useState } from "react";
import PsxNewsPanel from "./PsxNewsPanel";
import UsNewsPanel from "./UsNewsPanel";
import "./NewsSentiment.css";

export default function NewsSentiment() {
  const [tab, setTab] = useState("US");
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  function handleRefresh() {
    setRefreshing(true);
    setRefreshKey((k) => k + 1);
    setTimeout(() => setRefreshing(false), 500);
  }

  return (
    <div className="page-shell">
      <div className="page-shell-inner">
        <h1>News & Market Sentiment</h1>
        <p className="subtitle">
          AI-powered market-impact analysis of financial headlines via FinBERT.
        </p>

        <div className="market-header-row">
          <span />
          <button className="refresh-btn" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "⟳ Refresh"}
          </button>
        </div>

        <div className="page-tabs">
          <button className={`page-tab ${tab === "US" ? "active" : ""}`} onClick={() => setTab("US")}>
            US Market
          </button>
          <button className={`page-tab ${tab === "PSX" ? "active" : ""}`} onClick={() => setTab("PSX")}>
            PSX Market
          </button>
        </div>

        {tab === "US" ? <UsNewsPanel refreshKey={refreshKey} /> : <PsxNewsPanel refreshKey={refreshKey} />}

        <p className="dash-caption" style={{ marginTop: 32 }}>
          US news sourced from Alpaca Markets (Benzinga feed, 15-min delayed). PSX news sourced from
          Google News RSS. Sentiment analysis powered by FinBERT (ProsusAI), a transformer model
          trained on financial text.
        </p>
      </div>
    </div>
  );
}
