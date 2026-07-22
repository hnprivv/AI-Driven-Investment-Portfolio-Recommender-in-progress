import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import DashboardPreview from "../components/DashboardPreview";
import "./Home.css";

const ICON_PROPS = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };

const TargetIcon = () => (
  <svg {...ICON_PROPS}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
  </svg>
);

const CpuIcon = () => (
  <svg {...ICON_PROPS}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
    <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
  </svg>
);

const EyeIcon = () => (
  <svg {...ICON_PROPS}>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const FEATURES = [
  {
    icon: TargetIcon,
    title: "Personalized Insights",
    desc: "AIPRS evaluates your risk tolerance, goals, and time horizon to craft a portfolio that fits you.",
  },
  {
    icon: CpuIcon,
    title: "AI-Driven Decisions",
    desc: "Our reinforcement learning engine continuously adapts recommendations based on live market data.",
  },
  {
    icon: EyeIcon,
    title: "Guaranteed Transparency",
    desc: "Visualize portfolio performance, compare strategies, and track your financial progress in real time.",
  },
];

const STEPS = [
  {
    title: "Create Your Profile",
    desc: "Sign up and complete your investor profile — age, goals, risk tolerance, and horizon. This is the foundation for everything the AI does.",
  },
  {
    title: "Get Your AI Risk Classification",
    desc: "Our K-Means model analyses your profile and assigns you to an investor cluster, generating a personalised allocation.",
  },
  {
    title: "Explore AI Recommendations",
    desc: "View optimised asset allocations from the reinforcement learning engine, tailored to your risk cluster.",
  },
  {
    title: "Monitor the Markets",
    desc: "Track US and PSX market data in real time, with live price feeds and sector performance.",
  },
  {
    title: "Analyse News Sentiment",
    desc: "Read AI-analysed financial headlines, scored to help you understand how current events affect your portfolio.",
  },
  {
    title: "Run the PPO Advisors",
    desc: "Get BUY / HOLD / SELL signals from two dedicated RL models — one for US equities, one for PSX — each with a confidence score.",
  },
];

export default function Home({ user, onLogout }) {
  return (
    <div className="home-page">
      <Navbar user={user} onLogout={onLogout} />

      <section className="hero">
        <div className="hero-inner">
          <div className="hero-copy">
            <div className="hero-eyebrow">AI-Powered Portfolio Recommender</div>
            <h1>
              Investing, guided by <span className="gradient-text">artificial intelligence</span>.
            </h1>
            <p className="hero-sub">
              AIPRS analyzes market trends, assesses your unique risk profile, and constructs
              optimized portfolios that evolve with market behavior — combining reinforcement
              learning with Modern Portfolio Theory.
            </p>
            {!user && (
              <div className="hero-actions">
                <Link to="/signup">
                  <button className="btn-primary" type="button">Get Started Free</button>
                </Link>
                <Link to="/login">
                  <button className="btn-ghost" type="button">Log In</button>
                </Link>
              </div>
            )}
            <div className="hero-stats">
              <div className="stat-pill"><span className="stat-num">4</span> Risk Profiles</div>
              <div className="stat-pill"><span className="stat-num">AI</span> Powered Engine</div>
              <div className="stat-pill">Stocks · ETFs · Bonds & more</div>
            </div>
          </div>

          <div className="hero-visual">
            <DashboardPreview />
          </div>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Why Choose AIPRS?</h2>
        <div className="features-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="features-grid-item">
              <div className="feature-card">
                <div className="feature-icon"><f.icon /></div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">How It Works</h2>
        <div className="timeline">
          {STEPS.map((s, i) => (
            <div key={s.title} className="timeline-item">
              <div className="timeline-marker">{i + 1}</div>
              <div className="timeline-card">
                <div className="step-title">{s.title}</div>
                <p>{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Our Mission</h2>
        <blockquote className="mission-box">
          <p>
            Investing shouldn't be overwhelming. AIPRS combines cutting-edge machine learning
            with intuitive design to make intelligent investing accessible, transparent, and
            adaptive. No jargon, no guesswork.
          </p>
          <p>
            Your financial decisions should evolve as the markets do. Let AIPRS handle the
            complexity, so you can focus on what matters — your goals.
          </p>
        </blockquote>
      </section>

      {!user && (
        <section className="section">
          <div className="cta-band">
            <h3>Ready to Begin?</h3>
            <p>Get your AI risk profile in under 2 minutes. No commitment.</p>
            <Link to="/signup">
              <button className="btn-primary" type="button">Get Started Free</button>
            </Link>
          </div>
        </section>
      )}

      <footer className="home-footer">
        <p>AIPRS — Final Year Project. For research and educational demonstration only.</p>
      </footer>
    </div>
  );
}
