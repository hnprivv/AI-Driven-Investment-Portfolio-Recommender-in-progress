import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import Plot from "react-plotly.js";
import {
  clearHoldings,
  downloadReportPdf,
  getClusterPlacement,
  getPortfolioOverview,
  saveHoldings,
} from "../api";
import { showToast } from "../components/Toast";
import "./Dashboard.css";

const BEHAVIORS = {
  Conservative: {
    desc: "Prefers stability and consistent returns. Comfortable with low to moderate volatility.",
    portfolio: "Bonds, dividend-yielding stocks, and stable ETFs.",
  },
  Moderate: {
    desc: "Balanced risk and reward approach. Comfortable with standard market fluctuations.",
    portfolio: "60% equities, 40% bonds and alternative assets.",
  },
  Aggressive: {
    desc: "Seeks high returns and prioritises growth. Can tolerate short-term losses and high volatility.",
    portfolio: "80-90% equities, crypto, and 10-20% fixed income.",
  },
};

const CATEGORY_COLORS = {
  "Equities": "#F59E0B",
  "Fixed Income": "#FCD34D",
  "Commodities": "#B45309",
  "Cash": "#78350F",
};

const PROFILE_COLORS = {
  Conservative: "#FDE68A",
  Moderate: "#F59E0B",
  Aggressive: "#B45309",
  "Very Aggressive": "#7C2D12",
};

const PLOTLY_MODEBAR_CONFIG = {
  displaylogo: false,
  modeBarButtonsToRemove: [
    "lasso2d", "select2d", "toggleSpikelines",
    "hoverCompareCartesian", "hoverClosestCartesian",
  ],
};

export default function Dashboard() {
  const { user } = useOutletContext();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const [holdingsInput, setHoldingsInput] = useState("");
  const [holdingsError, setHoldingsError] = useState("");
  const [holdingsSuccess, setHoldingsSuccess] = useState("");
  const [savingHoldings, setSavingHoldings] = useState(false);
  const [clearingHoldings, setClearingHoldings] = useState(false);

  const [clusterData, setClusterData] = useState(null);
  const [clusterError, setClusterError] = useState("");

  function loadOverview() {
    return getPortfolioOverview()
      .then((d) => {
        setData(d);
        const text = d.holdings
          .map((h) => `${h.ticker}:${h.weight.toFixed(1)}`)
          .join(", ");
        setHoldingsInput(text);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    loadOverview();
    getClusterPlacement()
      .then(setClusterData)
      .catch((e) => setClusterError(e.message));
  }, []);

  function flashSuccess(message) {
    setHoldingsSuccess(message);
    setTimeout(() => setHoldingsSuccess(""), 5000);
  }

  async function handleSaveHoldings(e) {
    e.preventDefault();
    setHoldingsError("");
    setHoldingsSuccess("");
    if (!holdingsInput.trim()) {
      setHoldingsError("Please enter at least one ticker.");
      return;
    }
    setSavingHoldings(true);
    try {
      await saveHoldings(holdingsInput);
      setHoldingsSuccess("Holdings saved. Recalculating your metrics…");
      await loadOverview();
      flashSuccess("Metrics updated successfully!");
    } catch (err) {
      setHoldingsError(err.message);
    } finally {
      setSavingHoldings(false);
    }
  }

  async function handleClearHoldings() {
    setHoldingsError("");
    setHoldingsSuccess("");
    setClearingHoldings(true);
    try {
      await clearHoldings();
      await loadOverview();
      flashSuccess("Holdings cleared. Now using the cluster benchmark.");
    } catch (err) {
      setHoldingsError(err.message);
    } finally {
      setClearingHoldings(false);
    }
  }

  async function handleDownloadReport() {
    showToast("Generating your PDF report — it'll download automatically.", { type: "info" });
    try {
      await downloadReportPdf();
    } catch (err) {
      showToast(err.message, { type: "error" });
    }
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-inner">
          <p className="error">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="dashboard">
        <div className="dashboard-inner">
          <p className="subtitle">Loading your portfolio…</p>
        </div>
      </div>
    );
  }

  const behavior = BEHAVIORS[data.risk_profile];
  const curveDates = data.curve.map((p) => p.date);
  const curveValues = data.curve.map((p) => p.value);
  const preferences = data.profile.preferences?.length
    ? data.profile.preferences.join(", ")
    : "N/A";

  return (
    <div className="dashboard">
      <div className="dashboard-inner">
      <h1>Welcome back, {user.name}</h1>
      <p className="subtitle">Your personalized investment snapshot powered by AIPRS</p>

      {/* ── Portfolio Metrics ─────────────────────────────────────────── */}
      <section className="dash-section">
        <h2 className="dash-section-title">
          Portfolio Metrics
          <span className="dash-section-sub"> — {data.metrics_source}</span>
        </h2>
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-label">Total Return (1Y)</span>
            <span className="metric-value">{(data.total_return * 100).toFixed(1)}%</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Annualised Volatility</span>
            <span className="metric-value">{(data.ann_vol * 100).toFixed(1)}%</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Sharpe Ratio</span>
            <span className="metric-value">{data.sharpe.toFixed(2)}</span>
          </div>
          <div className="metric-card metric-card-report">
            <span className="metric-label">Portfolio Report</span>
            <button
              type="button"
              className="pdf-download-btn"
              onClick={handleDownloadReport}
            >
              ⬇ Download PDF
            </button>
          </div>
        </div>
        <p className="dash-caption">
          These figures reflect realized 1-year performance of{" "}
          {data.metrics_available ? "your entered holdings" : "the static cluster benchmark"}.
          They may differ from the <i>optimized</i> allocation and expected return/volatility
          shown on the AI Recommendations page, which uses Modern Portfolio Theory rather than
          fixed cluster weights.
        </p>
      </section>

      <div className="dash-divider"><span>◆</span></div>

      {/* ── Portfolio Performance ─────────────────────────────────────── */}
      <section className="dash-section">
        <h2 className="dash-section-title">Portfolio Performance</h2>
        <div className="chart-card">
          {data.curve.length > 0 ? (
            <Plot
              data={[
                {
                  x: curveDates,
                  y: curveValues,
                  type: "scatter",
                  mode: "lines",
                  line: { color: "#F59E0B" },
                },
              ]}
              layout={{
                autosize: true,
                height: 400,
                margin: { l: 40, r: 20, t: 20, b: 40 },
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: { family: "Inter, system-ui, sans-serif", size: 12, color: "#E4E4E7" },
                xaxis: { type: "date", gridcolor: "rgba(255,255,255,0.04)" },
                yaxis: { tickformat: ".3f", gridcolor: "rgba(255,255,255,0.05)" },
                shapes: [
                  {
                    type: "line", xref: "paper", x0: 0, x1: 1, y0: 1, y1: 1,
                    line: { color: "rgba(255,255,255,0.18)", dash: "dot" },
                  },
                ],
                transition: { duration: 500, easing: "cubic-in-out" },
              }}
              config={{ ...PLOTLY_MODEBAR_CONFIG, scrollZoom: true }}
              style={{ width: "100%" }}
              useResizeHandler
            />
          ) : (
            <p className="dash-caption">⚠️ Chart unavailable — market data could not be fetched.</p>
          )}
        </div>
      </section>

      <div className="dash-divider"><span>◆</span></div>

      {/* ── Holdings Input ────────────────────────────────────────────── */}
      <section className="dash-section">
        <h2 className="dash-section-title">Invested in More Assets? Let Us Know!</h2>
        <p className="dash-caption">
          Enter the assets you hold and AIPRS will calculate your actual portfolio metrics.
          Use <code>TICKER:WEIGHT%</code> format (e.g. <code>AAPL:50, MSFT:30, OGDC.KA:20</code>),
          or just ticker names for equal weighting (e.g. <code>AAPL, MSFT, OGDC.KA</code>).
          PSX tickers must end with <code>.KA</code>.
        </p>

        {data.holdings.length > 0 && (
          <div className="holdings-pills">
            {data.holdings.map((h) => (
              <span key={h.ticker} className="holdings-pill">
                {h.ticker} {h.weight.toFixed(1)}%
              </span>
            ))}
          </div>
        )}

        <form onSubmit={handleSaveHoldings} className="holdings-form">
          <input
            type="text"
            value={holdingsInput}
            onChange={(e) => setHoldingsInput(e.target.value)}
            placeholder="e.g. AAPL:50, MSFT:30, OGDC.KA:20  or  AAPL, MSFT, OGDC.KA"
          />
          {holdingsError && <div className="error">{holdingsError}</div>}
          {holdingsSuccess && <div className="success">{holdingsSuccess}</div>}
          <div className="holdings-actions">
            <button type="submit" disabled={savingHoldings}>
              {savingHoldings ? "Saving…" : "Save & Recalculate"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClearHoldings}
              disabled={clearingHoldings}
            >
              {clearingHoldings ? "Clearing…" : "Clear Holdings"}
            </button>
          </div>
        </form>
      </section>

      <div className="dash-divider"><span>◆</span></div>

      {/* ── Profile Summary ───────────────────────────────────────────── */}
      <section className="dash-section">
        <h2 className="dash-section-title">Profile Summary</h2>
        <div className="chart-card profile-card">
          <div className="profile-grid">
            <div className="profile-col">
              <p><b>Name:</b> {data.profile.name}</p>
              <p><b>Age:</b> {data.profile.age}</p>
              <p><b>Income Range:</b> {data.profile.income_range}</p>
              <p><b>Risk Tolerance:</b> {data.profile.risk_tolerance}</p>
              <p><b>Investment Horizon:</b> {data.profile.investment_horizon}</p>
            </div>
            <div className="profile-col">
              <p><b>Experience Level:</b> {data.profile.experience}</p>
              <p><b>Primary Goals:</b> {data.profile.goals}</p>
              <p><b>Preferred Assets:</b> {preferences}</p>
              <div className="risk-badge-row">
                <span className="risk-badge-label">Risk Cluster</span>
                <span className="risk-badge" style={{ "--badge-color": data.badge_color }}>
                  ● {data.risk_profile}
                </span>
              </div>
            </div>
          </div>
          {behavior && (
            <div className="behavior-box">
              <span className="behavior-label">Investor Behaviour</span>
              <p>{behavior.desc}</p>
              <span className="behavior-label">Ideal Portfolio</span>
              <p>{behavior.portfolio}</p>
            </div>
          )}
        </div>
      </section>

      <div className="dash-divider"><span>◆</span></div>

      {/* ── Asset Allocation ──────────────────────────────────────────── */}
      <section className="dash-section">
        <h2 className="dash-section-title">Your Asset Allocation</h2>
        {data.holdings_by_category ? (
          <>
            <div className="chart-card">
              <Plot
                data={[
                  {
                    type: "pie",
                    values: Object.values(data.holdings_by_category),
                    labels: Object.keys(data.holdings_by_category),
                    marker: {
                      colors: Object.keys(data.holdings_by_category).map(
                        (cat) => CATEGORY_COLORS[cat] || "#F59E0B"
                      ),
                    },
                    textinfo: "percent",
                    textposition: "inside",
                    insidetextfont: { color: "#0B0B0F", size: 13, family: "Inter, system-ui, sans-serif" },
                    automargin: true,
                  },
                ]}
                layout={{
                  autosize: true,
                  height: 380,
                  paper_bgcolor: "rgba(0,0,0,0)",
                  plot_bgcolor: "rgba(0,0,0,0)",
                  font: { color: "#E4E4E7" },
                  showlegend: true,
                  legend: {
                    orientation: "v",
                    font: { color: "#E4E4E7", size: 13 },
                    bgcolor: "rgba(15,10,0,0.85)",
                    bordercolor: "rgba(217,119,6,0.3)",
                    borderwidth: 1,
                    x: 0.02, y: 0.98, xanchor: "left", yanchor: "top",
                  },
                  margin: { l: 20, r: 20, t: 20, b: 20 },
                  transition: { duration: 500, easing: "cubic-in-out" },
                }}
                config={PLOTLY_MODEBAR_CONFIG}
                style={{ width: "100%" }}
                useResizeHandler
              />
            </div>
            <p className="dash-caption">
              Breakdown of your entered holdings by asset class. For a personalized{" "}
              <i>recommended</i> allocation, see AI Recommendations.
            </p>
          </>
        ) : (
          <div className="info-box">
            Add your holdings above to see your actual allocation breakdown here — or visit{" "}
            <b>AI Recommendations</b> for a personalized suggested allocation.
          </div>
        )}
      </section>

      <div className="dash-divider"><span>◆</span></div>

      {/* ── AI Cluster Placement ──────────────────────────────────────── */}
      <section className="dash-section">
        <h2 className="dash-section-title">Your AI Cluster Placement</h2>
        <p className="dash-caption" style={{ margin: "0 0 16px" }}>
          Where you sit among all investor profiles in the K-Means model's decision space.
        </p>
        {clusterData ? (
          <>
            <div className="chart-card">
            <Plot
              data={[
                ...Object.entries(
                  clusterData.background.reduce((acc, p) => {
                    (acc[p.profile] ||= []).push(p);
                    return acc;
                  }, {})
                ).map(([profile, points]) => ({
                  type: "scatter3d",
                  mode: "markers",
                  name: profile,
                  x: points.map((p) => p.age),
                  y: points.map((p) => p.risk_score),
                  z: points.map((p) => p.exp_score),
                  marker: {
                    size: 4,
                    opacity: 0.6,
                    color: PROFILE_COLORS[profile] || "#F59E0B",
                  },
                })),
                {
                  type: "scatter3d",
                  mode: "markers+text",
                  name: "Your Profile",
                  x: [clusterData.user_point.age],
                  y: [clusterData.user_point.risk_score],
                  z: [clusterData.user_point.exp_score],
                  text: ["📍 YOU"],
                  textposition: "top center",
                  textfont: { color: "#FFFFFF", size: 14 },
                  marker: {
                    size: 12,
                    color: "#16a34a",
                    symbol: "diamond",
                    line: { color: "#FFFFFF", width: 2 },
                  },
                },
              ]}
              layout={{
                autosize: true,
                height: 500,
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: { family: "Inter, system-ui, sans-serif", color: "#E4E4E7" },
                scene: {
                  xaxis: { title: "Age", gridcolor: "rgba(255,255,255,0.08)", backgroundcolor: "rgba(0,0,0,0)" },
                  yaxis: { title: "Risk Score", gridcolor: "rgba(255,255,255,0.08)", backgroundcolor: "rgba(0,0,0,0)" },
                  zaxis: { title: "Experience Score", gridcolor: "rgba(255,255,255,0.08)", backgroundcolor: "rgba(0,0,0,0)" },
                },
                margin: { l: 0, r: 0, b: 0, t: 20 },
                legend: {
                  title: { text: "Investor Segment", font: { family: "Inter, system-ui, sans-serif", color: "#E4E4E7" } },
                  x: 0.02, y: 0.98, xanchor: "left", yanchor: "top",
                  bgcolor: "rgba(15,10,0,0.85)",
                  bordercolor: "rgba(217,119,6,0.3)",
                  borderwidth: 1,
                  font: { family: "Inter, system-ui, sans-serif", color: "#E4E4E7" },
                },
              }}
              config={PLOTLY_MODEBAR_CONFIG}
              style={{ width: "100%" }}
              useResizeHandler
            />
            </div>
            <p className="dash-caption">
              Classification based on Age, Risk Score, and Experience Score. Your position (📍)
              is computed by the trained K-Means model.
            </p>
          </>
        ) : clusterError ? (
          <p className="dash-caption">⚠️ {clusterError}</p>
        ) : (
          <p className="dash-caption">Loading cluster visualisation…</p>
        )}
      </section>
      </div>
    </div>
  );
}
