export default function SentimentSummary({ articles }) {
  if (!articles || articles.length === 0) return null;

  const counts = { positive: 0, negative: 0, neutral: 0, inconclusive: 0 };
  for (const a of articles) {
    const s = a.sentiment;
    if (s.inconclusive) counts.inconclusive += 1;
    else counts[s.label] = (counts[s.label] || 0) + 1;
  }

  const total = articles.length;
  const posPct = (counts.positive / total) * 100;
  const negPct = (counts.negative / total) * 100;
  const neuPct = (counts.neutral / total) * 100;
  const incPct = (counts.inconclusive / total) * 100;

  let moodLabel = "Mixed / Neutral";
  let moodColor = "#A1A1AA";
  if (counts.positive > counts.negative) {
    moodLabel = "Broadly Positive";
    moodColor = "#22C55E";
  } else if (counts.negative > counts.positive) {
    moodLabel = "Broadly Negative";
    moodColor = "#EF4444";
  }

  return (
    <div className="sentiment-summary">
      <div className="sentiment-summary-header">
        <span className="sentiment-summary-title">Sentiment Summary</span>
        <span className="mood-badge" style={{ "--mood-color": moodColor }}>{moodLabel}</span>
      </div>
      <div className="sentiment-legend">
        <span style={{ color: "#22C55E" }}>● Positive: {counts.positive}</span>
        <span style={{ color: "#EF4444" }}>● Negative: {counts.negative}</span>
        <span style={{ color: "#A1A1AA" }}>● Neutral: {counts.neutral}</span>
        <span style={{ color: "#64748b" }}>● Inconclusive: {counts.inconclusive}</span>
      </div>
      <div className="sentiment-bar">
        <div style={{ width: `${posPct}%`, background: "#22C55E" }} />
        <div style={{ width: `${negPct}%`, background: "#EF4444" }} />
        <div style={{ width: `${neuPct}%`, background: "#A1A1AA" }} />
        <div style={{ width: `${incPct}%`, background: "#64748b" }} />
      </div>
    </div>
  );
}
