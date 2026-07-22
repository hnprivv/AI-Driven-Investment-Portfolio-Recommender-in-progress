export default function DashboardPreview() {
  return (
    <div className="dash-preview">
      <div className="dash-preview-card dash-preview-main">
        <div className="dash-preview-header">
          <span className="dash-preview-dot" />
          Your Portfolio
        </div>
        <span className="dash-preview-badge">● Moderate Risk</span>

        <div className="dash-preview-body">
          <div className="dash-preview-donut">
            <div className="dash-preview-donut-hole">
              <span>60%</span>
              <small>Equities</small>
            </div>
          </div>
          <div className="dash-preview-legend">
            <div><span className="sw sw-1" />Equities <b>60%</b></div>
            <div><span className="sw sw-2" />Fixed Income <b>25%</b></div>
            <div><span className="sw sw-3" />Commodities <b>10%</b></div>
            <div><span className="sw sw-4" />Cash <b>5%</b></div>
          </div>
        </div>

        <div className="dash-preview-stats">
          <div>
            <span className="stat-label">Return (1Y)</span>
            <span className="stat-value up">+18.4%</span>
          </div>
          <div>
            <span className="stat-label">Sharpe Ratio</span>
            <span className="stat-value">1.42</span>
          </div>
        </div>
      </div>

      <div className="dash-preview-card dash-preview-mini">
        <div className="mini-icon">⚡</div>
        <div>
          <div className="mini-title">PPO Signal</div>
          <div className="mini-sub">BUY · 82% confidence</div>
        </div>
      </div>
    </div>
  );
}
