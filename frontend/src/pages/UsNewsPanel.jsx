import { useEffect, useState } from "react";
import ArticleCard from "../components/ArticleCard";
import SentimentSummary from "../components/SentimentSummary";
import { getMarketNews, getTickerNews } from "../api";

export default function UsNewsPanel({ refreshKey }) {
  const [innerTab, setInnerTab] = useState("market");

  const [marketLimit, setMarketLimit] = useState(20);
  const [marketArticles, setMarketArticles] = useState(null);
  const [marketLoading, setMarketLoading] = useState(true);

  const [tickerInput, setTickerInput] = useState("");
  const [tickerQuery, setTickerQuery] = useState("");
  const [assetLimit, setAssetLimit] = useState(15);
  const [tickerArticles, setTickerArticles] = useState(null);
  const [tickerLoading, setTickerLoading] = useState(false);

  useEffect(() => {
    if (innerTab !== "market") return;
    setMarketLoading(true);
    getMarketNews(marketLimit)
      .then((d) => setMarketArticles(d.articles))
      .catch(() => setMarketArticles([]))
      .finally(() => setMarketLoading(false));
  }, [innerTab, marketLimit, refreshKey]);

  useEffect(() => {
    if (innerTab !== "asset" || !tickerQuery) return;
    setTickerLoading(true);
    getTickerNews(tickerQuery, assetLimit)
      .then((d) => setTickerArticles(d.articles))
      .catch(() => setTickerArticles([]))
      .finally(() => setTickerLoading(false));
  }, [innerTab, tickerQuery, assetLimit, refreshKey]);

  function handleTickerSubmit(e) {
    e.preventDefault();
    setTickerQuery(tickerInput.trim().toUpperCase());
  }

  return (
    <>
      <div className="page-tabs sub">
        <button className={`page-tab sub ${innerTab === "market" ? "active" : ""}`} onClick={() => setInnerTab("market")}>
          Global Market News
        </button>
        <button className={`page-tab sub ${innerTab === "asset" ? "active" : ""}`} onClick={() => setInnerTab("asset")}>
          Asset-Specific News
        </button>
      </div>

      {innerTab === "market" ? (
        <div style={{ marginTop: 20 }}>
          <p className="dash-caption" style={{ margin: "0 0 12px" }}>
            Latest financial headlines from global markets, analyzed for potential market impact.
          </p>
          <div className="market-control" style={{ maxWidth: 260 }}>
            <label htmlFor="market-limit">Number of articles: {marketLimit}</label>
            <input
              id="market-limit"
              type="range"
              min={5}
              max={50}
              step={5}
              value={marketLimit}
              onChange={(e) => setMarketLimit(Number(e.target.value))}
            />
          </div>

          {marketLoading ? (
            <p className="dash-caption">Fetching and analyzing market news…</p>
          ) : !marketArticles || marketArticles.length === 0 ? (
            <div className="info-box" style={{ marginTop: 12 }}>
              No market news available. Check your Alpaca API credentials.
            </div>
          ) : (
            <>
              <p className="dash-caption">Showing {marketArticles.length} articles</p>
              <div className="article-grid">
                {marketArticles.map((a) => (
                  <ArticleCard key={a.id || a.url} article={a} />
                ))}
              </div>
              <SentimentSummary articles={marketArticles} />
            </>
          )}
        </div>
      ) : (
        <div style={{ marginTop: 20 }}>
          <p className="dash-caption" style={{ margin: "0 0 12px" }}>
            Enter a ticker to see recent news and its predicted impact on that asset.
          </p>
          <form onSubmit={handleTickerSubmit} className="market-controls">
            <div className="market-control">
              <label htmlFor="ticker-input">Ticker Symbol</label>
              <input
                id="ticker-input"
                type="text"
                placeholder="e.g. AAPL"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value)}
              />
            </div>
            <div className="market-control">
              <label htmlFor="asset-limit">Number of articles: {assetLimit}</label>
              <input
                id="asset-limit"
                type="range"
                min={5}
                max={50}
                step={5}
                value={assetLimit}
                onChange={(e) => setAssetLimit(Number(e.target.value))}
              />
            </div>
            <button type="submit" style={{ marginTop: 0 }}>Search</button>
          </form>

          {!tickerQuery ? (
            <div className="news-placeholder">
              Enter a ticker symbol above to load asset-specific news and sentiment analysis.
            </div>
          ) : tickerLoading ? (
            <p className="dash-caption">Fetching and analyzing news for {tickerQuery}…</p>
          ) : !tickerArticles || tickerArticles.length === 0 ? (
            <div className="info-box" style={{ marginTop: 12 }}>
              No news found for <b>{tickerQuery}</b>. Check the ticker is valid, or try a more actively
              covered symbol.
            </div>
          ) : (
            <>
              <p className="dash-caption">
                Showing {tickerArticles.length} articles for <b style={{ color: "var(--text)" }}>{tickerQuery}</b>
              </p>
              <div className="article-grid">
                {tickerArticles.map((a) => (
                  <ArticleCard key={a.id || a.url} article={a} />
                ))}
              </div>
              <SentimentSummary articles={tickerArticles} />
            </>
          )}
        </div>
      )}
    </>
  );
}
