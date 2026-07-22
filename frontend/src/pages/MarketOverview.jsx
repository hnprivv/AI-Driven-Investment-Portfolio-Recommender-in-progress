import { useEffect, useState } from "react";
import { getMarketStatus } from "../api";
import PsxMarketPanel from "./PsxMarketPanel";
import UsMarketPanel from "./UsMarketPanel";
import "./MarketOverview.css";

export default function MarketOverview() {
  const [tab, setTab] = useState("US");
  const [status, setStatus] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    getMarketStatus(tab).then(setStatus).catch(() => setStatus(null));
  }, [tab, refreshKey]);

  function handleRefresh() {
    setRefreshing(true);
    setRefreshKey((k) => k + 1);
    setTimeout(() => setRefreshing(false), 500);
  }

  return (
    <div className="page-shell">
      <div className="page-shell-inner">
        <h1>Market Overview</h1>
        <p className="subtitle">
          Live candlestick charts powered by Alpaca Market Data. Advisory view only.
        </p>

        <div className="market-header-row">
          {status && (
            <div>
              <span className="market-status-badge" style={{ "--status-color": status.color }}>
                <span className="market-status-dot">●</span> {status.label}
              </span>
              {tab === "US" && !status.is_open && status.last_open && (
                <span className="market-last-session">
                  Last trading session: <b>{status.last_open}</b>
                </span>
              )}
              {tab === "PSX" && (
                <span className="market-last-session">Regular hours: Mon–Fri, 09:30–15:30 PKT</span>
              )}
            </div>
          )}
          <button className="market-refresh-btn" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "⟳ Refresh"}
          </button>
        </div>

        <div className="market-tabs">
          <button
            className={`market-tab ${tab === "US" ? "active" : ""}`}
            onClick={() => setTab("US")}
          >
            US Market
          </button>
          <button
            className={`market-tab ${tab === "PSX" ? "active" : ""}`}
            onClick={() => setTab("PSX")}
          >
            PSX Market
          </button>
        </div>

        {tab === "US" ? (
          <UsMarketPanel refreshKey={refreshKey} />
        ) : (
          <PsxMarketPanel refreshKey={refreshKey} />
        )}
      </div>
    </div>
  );
}
