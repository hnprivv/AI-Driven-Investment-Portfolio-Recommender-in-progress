import { useState } from "react";
import { submitFeedback, submitSurvey } from "../api";
import Select from "../components/Select";
import "./Feedback.css";

const PAGES = ["General System", "Home", "User Form", "Overview", "AI Recommendations", "Other"];

const FEEDBACK_TYPES = [
  { key: "Suggestion / Feature Request", label: "🟢 Suggestion" },
  { key: "Bug Report / Issue", label: "🔴 Bug Report" },
  { key: "General Comment", label: "🔵 General" },
];

function QuickFeedbackForm() {
  const [feedbackType, setFeedbackType] = useState(FEEDBACK_TYPES[0].key);
  const [page, setPage] = useState(PAGES[0]);
  const [text, setText] = useState("");
  const [contact, setContact] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!text.trim()) {
      setError("Please provide text feedback before submitting.");
      return;
    }
    setSubmitting(true);
    try {
      await submitFeedback({
        feedback_type: feedbackType,
        related_page: page,
        feedback_text: text,
        contact_info: contact,
      });
      setDone(true);
      setText("");
      setContact("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="success-card">
        <div className="success-icon">✅</div>
        <div className="success-title">Response Recorded</div>
        <div className="success-body">
          Thank you! Your <b>{feedbackType}</b> has been recorded. We'll review it shortly.
        </div>
        <button style={{ marginTop: 14 }} onClick={() => setDone(false)}>
          Send Another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="feedback-form-card">
      <label className="field-label">What kind of feedback is this?</label>
      <div className="type-pills">
        {FEEDBACK_TYPES.map((ft) => (
          <button
            key={ft.key}
            type="button"
            className={`pill-btn ${feedbackType === ft.key ? "active" : ""}`}
            onClick={() => setFeedbackType(ft.key)}
          >
            {ft.label}
          </button>
        ))}
      </div>

      <div className="field-row">
        <div>
          <label className="field-label">Related page (optional)</label>
          <Select value={page} onChange={setPage} options={PAGES} />
        </div>
        <div>
          <label className="field-label" htmlFor="fb-contact">Email / contact (optional)</label>
          <input
            id="fb-contact"
            type="text"
            placeholder="For a follow-up response"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
          />
        </div>
      </div>

      <label className="field-label" htmlFor="fb-text" style={{ marginTop: 14 }}>
        Your feedback
      </label>
      <textarea
        id="fb-text"
        rows={4}
        placeholder="Please be specific — e.g. 'The chart on the Performance Tracker page doesn't load when I click Refresh.'"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}

      <button type="submit" disabled={submitting} style={{ width: "100%", marginTop: 16 }}>
        {submitting ? "Sending…" : "Send Feedback"}
      </button>
    </form>
  );
}

function SurveyForm() {
  const [q1, setQ1] = useState(3);
  const [q2, setQ2] = useState(3);
  const [q3, setQ3] = useState(4);
  const [lacking, setLacking] = useState("");
  const [openText, setOpenText] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const signals = [q1 !== 3, q2 !== 3, q3 !== 4, lacking.trim().length > 0, openText.trim().length > 0];
  const pct = Math.round((signals.filter(Boolean).length / signals.length) * 100);

  async function handleSubmit() {
    setError("");
    setSubmitting(true);
    try {
      await submitSurvey({
        q1_intuitive: q1,
        q2_useful: q2,
        q3_satisfied: q3,
        lacking_features: lacking,
        open_text: openText,
      });
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="success-card">
        <div className="success-icon">✅</div>
        <div className="success-title">Response Recorded</div>
        <div className="success-body">
          Thank you! Your detailed survey response has been recorded. Your input directly shapes the
          future of AIPRS.
        </div>
        <button
          style={{ marginTop: 14 }}
          onClick={() => {
            setDone(false);
            setQ1(3); setQ2(3); setQ3(4); setLacking(""); setOpenText("");
          }}
        >
          Submit Another Response
        </button>
      </div>
    );
  }

  return (
    <div className="feedback-form-card">
      <div className="survey-question">
        <label className="field-label">How intuitive did you find the AIPRS navigation?</label>
        <input type="range" min={1} max={5} value={q1} onChange={(e) => setQ1(Number(e.target.value))} />
        <div className="slider-labels"><span>Not at all intuitive</span><span>Extremely intuitive</span></div>
      </div>

      <div className="survey-question">
        <label className="field-label">How useful are the AI Recommendations for your decisions?</label>
        <input type="range" min={1} max={5} value={q2} onChange={(e) => setQ2(Number(e.target.value))} />
        <div className="slider-labels"><span>Not useful at all</span><span>Extremely useful</span></div>
      </div>

      <div className="survey-question">
        <label className="field-label">How satisfied are you with the visual design and aesthetics?</label>
        <input type="range" min={1} max={5} value={q3} onChange={(e) => setQ3(Number(e.target.value))} />
        <div className="slider-labels"><span>Very unsatisfied</span><span>Very satisfied</span></div>
      </div>

      <label className="field-label" htmlFor="lacking">What key features do you feel are currently lacking?</label>
      <textarea
        id="lacking"
        rows={3}
        placeholder="E.g., 'I would like to see a dedicated crypto portfolio section.'"
        value={lacking}
        onChange={(e) => setLacking(e.target.value)}
      />

      <label className="field-label" htmlFor="open-text" style={{ marginTop: 14 }}>
        Any other comments or suggestions for improvement?
      </label>
      <textarea
        id="open-text"
        rows={3}
        placeholder="E.g., 'The performance tracker needs better filtering options.'"
        value={openText}
        onChange={(e) => setOpenText(e.target.value)}
      />

      <div className="completeness-row">
        <span>Response completeness</span>
        <span className="completeness-pct">{pct}%</span>
      </div>
      <div className="completeness-track">
        <div className="completeness-fill" style={{ width: `${pct}%` }} />
      </div>

      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}

      <button style={{ width: "100%", marginTop: 18 }} disabled={submitting} onClick={handleSubmit}>
        {submitting ? "Submitting…" : "Submit Survey"}
      </button>
    </div>
  );
}

export default function Feedback() {
  const [surveyOpen, setSurveyOpen] = useState(false);

  return (
    <div className="page-shell">
      <div className="page-shell-inner">
        <h1>Share Your Feedback</h1>
        <p className="subtitle">
          Help us improve AIPRS by sharing your thoughts, suggestions, and reporting any issues.
        </p>

        <section className="dash-section" style={{ marginTop: 24 }}>
          <QuickFeedbackForm />
        </section>

        <div className="dash-divider"><span>◆</span></div>

        <section className="dash-section">
          <button className="survey-toggle" onClick={() => setSurveyOpen((v) => !v)}>
            <span>📋 Take the Optional System Survey</span>
            <span className="survey-toggle-hint">
              {surveyOpen ? "Hide" : "2 min · anonymous"} {surveyOpen ? "▲" : "▼"}
            </span>
          </button>
          {surveyOpen && (
            <div style={{ marginTop: 16 }}>
              <SurveyForm />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
