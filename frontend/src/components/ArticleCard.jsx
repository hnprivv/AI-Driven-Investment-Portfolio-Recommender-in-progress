function fmtDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
  } catch {
    return "";
  }
}

export default function ArticleCard({ article }) {
  const s = article.sentiment;
  const summary = article.summary || "";
  const truncated = summary.length > 220 ? summary.slice(0, 220) + "..." : summary;
  const published = fmtDate(article.published_at);
  const sourceLine = article.source ? `${article.source.toUpperCase()}${published ? "  ·  " + published : ""}` : published;

  return (
    <div className="article-card">
      <div className="article-card-header">
        <span className="impact-badge" style={{ "--impact-color": s.impact_color }}>
          {s.impact_label}
        </span>
        <span className="article-source">{sourceLine}</span>
      </div>
      <p className="article-headline">{article.headline || "No headline"}</p>
      {summary && <p className="article-summary">{truncated}</p>}
      <div className="article-card-footer">
        <div className="article-tags">
          {(article.symbols || []).slice(0, 5).map((sym) => (
            <span key={sym} className="article-tag">{sym}</span>
          ))}
        </div>
        <div className="article-footer-right">
          {s.inconclusive ? (
            <span className="article-confidence muted">Confidence: —</span>
          ) : (
            <span className="article-confidence" style={{ color: s.impact_color }}>
              Confidence: {(s.confidence * 100).toFixed(0)}%
            </span>
          )}
          {article.url && (
            <a className="article-read-more" href={article.url} target="_blank" rel="noreferrer">
              Read Full Article →
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
