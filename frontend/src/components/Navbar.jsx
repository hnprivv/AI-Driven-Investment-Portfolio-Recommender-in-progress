import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { logout } from "../api";
import aiprsLogo from "../assets/aiprs-logo.png";
import { LATEST_UPDATE_ID } from "../updatesLog";

// One-line addition per future page — Overview, Recommendations, Market,
// PPO Advisors, News, etc. just get appended here as they're built.
// guestOk links stay visible (and reachable) for logged-out visitors too —
// their routes don't require auth, unlike the rest.
const NAV_LINKS = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "AI Recommendations", path: "/recommendations" },
  { label: "Market", path: "/market", guestOk: true },
  { label: "News", path: "/news", guestOk: true },
  { label: "Update Log", path: "/updates" },
  { label: "Feedback", path: "/feedback" },
];

const UPDATES_SEEN_KEY = "aiprs_updates_seen";

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

function UserMenu({ user, onLogout }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleLogout() {
    setOpen(false);
    await logout();
    onLogout();
    navigate("/login");
  }

  return (
    <div className="navbar-user-menu" ref={ref}>
      <button
        type="button"
        className={`navbar-user-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="navbar-avatar">{initials(user.name)}</span>
        <span className="navbar-username">{user.name}</span>
        <svg width="10" height="6" viewBox="0 0 12 8" fill="none">
          <path d="M1 1.5L6 6.5L11 1.5" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>

      {open && (
        <div className="navbar-user-dropdown">
          <Link to="/profile" className="navbar-user-dropdown-item" onClick={() => setOpen(false)}>
            Edit Profile
          </Link>
          <Link to="/settings" className="navbar-user-dropdown-item" onClick={() => setOpen(false)}>
            Settings
          </Link>
          <div className="navbar-user-dropdown-divider" />
          <button type="button" className="navbar-user-dropdown-item danger" onClick={handleLogout}>
            Log Out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Navbar({ user, onLogout, minimal = false }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const [hasNewUpdate, setHasNewUpdate] = useState(
    () => localStorage.getItem(UPDATES_SEEN_KEY) !== LATEST_UPDATE_ID
  );

  useEffect(() => {
    if (location.pathname === "/updates") {
      localStorage.setItem(UPDATES_SEEN_KEY, LATEST_UPDATE_ID);
      setHasNewUpdate(false);
    }
  }, [location.pathname]);

  if (minimal) {
    return (
      <header className="navbar">
        <div className="navbar-inner navbar-inner-minimal">
          <Link to="/" className="navbar-brand">
            <img src={aiprsLogo} alt="" width="28" height="28" className="navbar-logo" />
            AIPRS
          </Link>
        </div>
      </header>
    );
  }

  if (!user) {
    return (
      <header className="navbar">
        <div className="navbar-inner navbar-inner-guest">
          <Link to="/" className="navbar-brand">
            <img src={aiprsLogo} alt="" width="28" height="28" className="navbar-logo" />
            AIPRS
          </Link>
          <nav className="navbar-links">
            {NAV_LINKS.filter((link) => link.guestOk).map((link) => (
              <NavLink
                key={link.path}
                to={link.path}
                className={({ isActive }) =>
                  "navbar-link" + (isActive ? " active" : "")
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
    );
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          <img src={aiprsLogo} alt="" width="28" height="28" className="navbar-logo" />
          AIPRS
        </Link>

        <div className={`navbar-menu ${menuOpen ? "open" : ""}`}>
          <nav className="navbar-links">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.path}
                to={link.path}
                className={({ isActive }) =>
                  "navbar-link" + (isActive ? " active" : "")
                }
                onClick={() => setMenuOpen(false)}
              >
                {link.label}
                {link.path === "/updates" && hasNewUpdate && (
                  <span className="navbar-link-dot" aria-label="New update" />
                )}
              </NavLink>
            ))}
          </nav>

          <div className="navbar-user">
            <UserMenu user={user} onLogout={onLogout} />
          </div>
        </div>

        <button
          className="navbar-hamburger"
          aria-label="Toggle menu"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>
      </div>
    </header>
  );
}
