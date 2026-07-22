import { useEffect, useState } from "react";
import ArticleCard from "../components/ArticleCard";
import SentimentSummary from "../components/SentimentSummary";
import { getPsxCompanyNews, getPsxMarketNews } from "../api";

export default function PsxNewsPanel({ refreshKey }) {
  const [innerTab, setInnerTab] = useState("market");

  const [marketLimit, setMarketLimit] = useState(15);
  const [marketArticles, setMarketArticles] = useState(null);
  const [marketLoading, setMarketLoading] = useState(true);

  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [assetLimit, setAssetLimit] = useState(15);
  const [companyArticles, setCompanyArticles] = useState(null);
  const [displayLabel, setDisplayLabel] = useState("");
  const [companyLoading, setCompanyLoading] = useState(false);

  useEffect(() => {
    if (innerTab !== "market") return;
    setMarketLoading(true);
    getPsxMarketNews(marketLimit)
      .then((d) => setMarketArticles(d.articles))
      .catch(() => setMarketArticles([]))
      .finally(() => setMarketLoading(false));
  }, [innerTab, marketLimit, refreshKey]);

  useEffect(() => {
    if (innerTab !== "asset" || !searchQuery) return;
    setCompanyLoading(true);
    getPsxCompanyNews(searchQuery, assetLimit)
      .then((d) => {
        setCompanyArticles(d.articles);
        setDisplayLabel(d.display_label);
      })
      .catch(() => setCompanyArticles([]))
      .finally(() => setCompanyLoading(false));
  }, [innerTab, searchQuery, assetLimit, refreshKey]);

  function handleSearchSubmit(e) {
    e.preventDefault();
    setSearchQuery(searchInput.trim());
  }

  return (
    <>
      <div className="page-tabs sub">
        <button className={`page-tab sub ${innerTab === "market" ? "active" : ""}`} onClick={() => setInnerTab("market")}>
          General Market News
        </button>
        <button className={`page-tab sub ${innerTab === "asset" ? "active" : ""}`} onClick={() => setInnerTab("asset")}>
          Stock-Specific News
        </button>
      </div>

      {innerTab === "market" ? (
        <div style={{ marginTop: 20 }}>
          <p className="dash-caption" style={{ margin: "0 0 12px" }}>
            Latest Pakistan Stock Exchange and KSE-100 headlines, analyzed for market impact.
          </p>
          <div className="market-control" style={{ maxWidth: 260 }}>
            <label htmlFor="psx-market-limit">Number of articles: {marketLimit}</label>
            <input
              id="psx-market-limit"
              type="range"
              min={5}
              max={30}
              step={5}
              value={marketLimit}
              onChange={(e) => setMarketLimit(Number(e.target.value))}
            />
          </div>

          {marketLoading ? (
            <p className="dash-caption">Fetching and analyzing PSX market news…</p>
          ) : !marketArticles || marketArticles.length === 0 ? (
            <div className="info-box" style={{ marginTop: 12 }}>
              No PSX market news could be retrieved. Ensure you have internet access.
            </div>
          ) : (
            <>
              <p className="dash-caption">
                Showing {marketArticles.length} articles · Sourced via Google News RSS
              </p>
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
            Enter a PSX ticker symbol or company name to load news and sentiment analysis.
          </p>
          <form onSubmit={handleSearchSubmit} className="market-controls">
            <div className="market-control">
              <label htmlFor="psx-search-input">PSX Symbol or Company Name</label>
              <input
                id="psx-search-input"
                type="text"
                placeholder="e.g. HBL, ENGRO, Lucky Cement"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <div className="market-control">
              <label htmlFor="psx-asset-limit">Number of articles: {assetLimit}</label>
              <input
                id="psx-asset-limit"
                type="range"
                min={5}
                max={30}
                step={5}
                value={assetLimit}
                onChange={(e) => setAssetLimit(Number(e.target.value))}
              />
            </div>
            <button type="submit" style={{ marginTop: 0 }}>Search</button>
          </form>

          {!searchQuery ? (
            <div className="news-placeholder">
              Enter a PSX ticker or company name above to load stock-specific news.
            </div>
          ) : companyLoading ? (
            <p className="dash-caption">Fetching and analyzing news for {displayLabel || searchQuery}…</p>
          ) : !companyArticles || companyArticles.length === 0 ? (
            <div className="info-box" style={{ marginTop: 12 }}>
              No news found for <b>{displayLabel || searchQuery}</b>. Try a different symbol or company name.
            </div>
          ) : (
            <>
              <p className="dash-caption">
                Showing {companyArticles.length} articles for{" "}
                <b style={{ color: "var(--text)" }}>{displayLabel}</b>
              </p>
              <div className="article-grid">
                {companyArticles.map((a) => (
                  <ArticleCard key={a.id || a.url} article={a} />
                ))}
              </div>
              <SentimentSummary articles={companyArticles} />
            </>
          )}
        </div>
      )}
    </>
  );
}
