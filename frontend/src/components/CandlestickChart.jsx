import Plot from "react-plotly.js";

const PLOTLY_MODEBAR_CONFIG = {
  displaylogo: false,
  modeBarButtonsToRemove: [
    "lasso2d", "select2d", "toggleSpikelines",
    "hoverCompareCartesian", "hoverClosestCartesian",
  ],
};

const COLOR_UP = "#22C55E";
const COLOR_DOWN = "#EF4444";

/** Candlestick + volume + SMA-20 chart, mirroring build_candlestick_chart()
 * from pages/3_Market_Overview.py — categorical x-axis so overnight/weekend
 * gaps are eliminated, matching TradingView-style packed candles.
 */
export default function CandlestickChart({ bars, symbol, isLive, currencyPrefix = "$", badgeText }) {
  if (!bars || bars.length === 0) return null;

  const n = bars.length;
  const closes = bars.map((b) => b.close);
  const opens = bars.map((b) => b.open);
  const highs = bars.map((b) => b.high);
  const lows = bars.map((b) => b.low);
  const volumes = bars.map((b) => b.volume);
  const barColors = bars.map((b) => (b.close >= b.open ? COLOR_UP : COLOR_DOWN));
  const xIdx = bars.map((_, i) => i);

  const step = Math.max(1, Math.floor(n / 8));
  const tickIndices = [];
  for (let i = 0; i < n; i += step) tickIndices.push(i);
  const tickLabels = tickIndices.map((i) => {
    const d = new Date(bars[i].timestamp);
    return d.toLocaleString("en-US", { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  });
  const hoverTimes = bars.map((b) =>
    new Date(b.timestamp).toLocaleString("en-US", {
      month: "short", day: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
    })
  );

  const lastClose = closes[n - 1];
  const firstClose = closes[0];
  const pctChange = ((lastClose - firstClose) / firstClose) * 100;
  const changeColor = pctChange >= 0 ? COLOR_UP : COLOR_DOWN;
  const liveBadge = badgeText !== undefined ? badgeText : isLive ? "🟠 15-MIN DELAYED" : "🟡 DEMO DATA";

  const traces = [
    {
      type: "candlestick",
      x: xIdx,
      open: opens, high: highs, low: lows, close: closes,
      text: hoverTimes,
      hovertext: hoverTimes,
      name: symbol,
      increasing: { line: { color: COLOR_UP, width: 1 }, fillcolor: COLOR_UP },
      decreasing: { line: { color: COLOR_DOWN, width: 1 }, fillcolor: COLOR_DOWN },
      whiskerwidth: 1,
      yaxis: "y1",
    },
    {
      type: "bar",
      x: xIdx,
      y: volumes,
      text: hoverTimes,
      hovertemplate: "%{text}<br>Volume: %{y:,.0f}<extra></extra>",
      name: "Volume",
      marker: { color: barColors },
      opacity: 0.4,
      yaxis: "y2",
      showlegend: false,
    },
  ];

  if (n >= 20) {
    const sma = closes.map((_, i) => {
      if (i < 19) return null;
      const window = closes.slice(i - 19, i + 1);
      return window.reduce((a, b) => a + b, 0) / 20;
    });
    traces.push({
      type: "scatter",
      x: xIdx,
      y: sma,
      mode: "lines",
      line: { color: "#F59E0B", width: 1.5, dash: "dot" },
      name: "SMA 20",
      yaxis: "y1",
    });
  }

  return (
    <Plot
      data={traces}
      layout={{
        autosize: true,
        height: 520,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        title: {
          text:
            `<b>${symbol}</b>   <span style='color:${changeColor}'>${pctChange >= 0 ? "+" : ""}${pctChange.toFixed(2)}%</span>` +
            `   <span style='font-size:12px; color:#A1A1AA'>${liveBadge}</span>`,
          font: { size: 18, color: "#E4E4E7" },
          x: 0.01,
        },
        xaxis: {
          tickmode: "array",
          tickvals: tickIndices,
          ticktext: tickLabels,
          tickfont: { size: 10, color: "#A1A1AA" },
          rangeslider: { visible: false },
          gridcolor: "rgba(255,255,255,0.04)",
          color: "#A1A1AA",
          showspikes: true,
          spikecolor: "#F59E0B",
          spikethickness: 1,
          spikedash: "dot",
          type: "category",
        },
        yaxis: {
          domain: [0.25, 1.0],
          gridcolor: "rgba(255,255,255,0.06)",
          color: "#A1A1AA",
          tickprefix: currencyPrefix,
          showspikes: true,
          spikecolor: "#F59E0B",
          automargin: true,
        },
        yaxis2: {
          domain: [0.0, 0.22],
          gridcolor: "rgba(255,255,255,0.03)",
          color: "#A1A1AA",
          title: { text: "Volume", font: { size: 10, color: "#A1A1AA" } },
          automargin: true,
        },
        legend: {
          orientation: "h", yanchor: "top", y: 1.02, xanchor: "right", x: 1,
          font: { color: "#A1A1AA" },
        },
        hovermode: "x unified",
        hoverlabel: { bgcolor: "#1a1a2e", font: { color: "#E4E4E7" } },
        margin: { l: 10, r: 10, t: 55, b: 10 },
        font: { family: "Inter, system-ui, sans-serif", color: "#E4E4E7" },
        dragmode: "pan",
        bargap: 0,
        bargroupgap: 0,
        transition: { duration: 400, easing: "cubic-in-out" },
      }}
      config={{ ...PLOTLY_MODEBAR_CONFIG, scrollZoom: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
