import { useState } from "react";
import { Link } from "react-router-dom";
import { me, signup } from "../api";
import Select from "../components/Select";
import NumberInput from "../components/NumberInput";

const INCOME_RANGES = ["< 25,000", "25,000 - 50,000", "50,000 - 100,000", "100,000+"];
const HORIZONS = ["1 Year", "3-5 Years", "5-10 Years", "10+ Years"];
const EXPERIENCES = ["Beginner", "Intermediate", "Advanced"];
const GOALS = ["Stable income", "Long-term stability", "Short-term trading", "Retirement"];
const PREFERENCES = ["Stocks", "Bonds", "Real Estate", "Crypto", "ETFs", "Commodities"];

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function validatePassword(pw) {
  if (!pw.trim()) return "Password must not consist of only whitespace.";
  if (pw.length < 8) return "Password must be at least 8 characters long.";
  if (pw.length > 128) return "Password must not exceed 128 characters.";
  if (!/[A-Z]/.test(pw)) return "Password must contain at least one uppercase letter.";
  if (!/[a-z]/.test(pw)) return "Password must contain at least one lowercase letter.";
  if (!/\d/.test(pw)) return "Password must contain at least one number.";
  if (!/[^A-Za-z0-9]/.test(pw))
    return "Password must contain at least one special character (e.g. @, #, !).";
  return null;
}

export default function Signup({ onLogin }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [age, setAge] = useState(25);
  const [incomeRange, setIncomeRange] = useState(INCOME_RANGES[0]);
  const [horizon, setHorizon] = useState(HORIZONS[0]);
  const [experience, setExperience] = useState(EXPERIENCES[0]);
  const [goals, setGoals] = useState(GOALS[0]);
  const [preferences, setPreferences] = useState([]);
  const [riskTolerance, setRiskTolerance] = useState(5);
  const [agreed, setAgreed] = useState(false);

  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function togglePreference(pref) {
    setPreferences((prev) =>
      prev.includes(pref) ? prev.filter((p) => p !== pref) : [...prev, pref]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (!agreed) {
      setError("You must agree to the Privacy Policy and Terms & Conditions to create an account.");
      return;
    }
    if (!name.trim() || !email.trim() || !password) {
      setError("Please fill out all Account Details (Name, Email, Password).");
      return;
    }
    if (!EMAIL_RE.test(email.trim())) {
      setError("Please enter a valid email address (e.g. name@example.com).");
      return;
    }
    const pwError = validatePassword(password);
    if (pwError) {
      setError(pwError);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match!");
      return;
    }

    setSubmitting(true);
    try {
      await signup({
        name: name.trim(),
        email: email.trim(),
        password,
        age: Number(age),
        income_range: incomeRange,
        investment_horizon: horizon,
        experience,
        goals,
        preferences,
        risk_tolerance: Number(riskTolerance),
      });
      const fullProfile = await me();
      onLogin(fullProfile);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card signup-card" onSubmit={handleSubmit}>
        <h1>Create Your Profile</h1>
        <p className="subtitle">
          Create your account and let our AI analyze your financial profile in one step.
        </p>

        <div className="signup-columns">
          <div className="signup-col">
            <h3>1. Account Details</h3>
            <label>Full Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. John Doe" />
            <label>Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
            />
            <label>Create Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <label>Confirm Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />

            <h3>2. Financial Profile</h3>
            <label>Age</label>
            <NumberInput value={age} onChange={setAge} min={18} max={100} />
            <label>Annual Income Range</label>
            <Select value={incomeRange} onChange={setIncomeRange} options={INCOME_RANGES} />
            <label>Investment Horizon</label>
            <Select value={horizon} onChange={setHorizon} options={HORIZONS} />
            <label>Investment Experience</label>
            <Select value={experience} onChange={setExperience} options={EXPERIENCES} />
          </div>

          <div className="signup-col">
            <h3>3. Goals & Preferences</h3>
            <label>Primary Goal</label>
            <Select value={goals} onChange={setGoals} options={GOALS} />
            <label>Preferred Assets (Optional)</label>
            <div className="checkbox-grid">
              {PREFERENCES.map((p) => (
                <label key={p} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={preferences.includes(p)}
                    onChange={() => togglePreference(p)}
                  />
                  {p}
                </label>
              ))}
            </div>

            <h3>4. Risk Assessment</h3>
            <label>Risk Tolerance: {riskTolerance} / 10</label>
            <input
              type="range"
              min={1}
              max={10}
              value={riskTolerance}
              onChange={(e) => setRiskTolerance(e.target.value)}
            />

            <label className="checkbox-label agree-label">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
              />
              I have read and agree to the Privacy Policy and Terms & Conditions
            </label>
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Creating account…" : "Create Account & Analyze Profile"}
        </button>

        <div className="auth-divider"><span>◆</span></div>
        <p className="subtitle switch-auth">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
