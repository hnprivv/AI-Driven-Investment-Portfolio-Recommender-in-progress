import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { logout } from "../api";

// One-line addition per future page — Overview, Recommendations, Market,
// PPO Advisors, News, etc. just get appended here as they're built.
const NAV_LINKS = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "AI Recommendations", path: "/recommendations" },
  { label: "Market", path: "/market" },
  { label: "Settings", path: "/settings" },
];

export default function Navbar({ user, onLogout }) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  async function handleLogout() {
    await logout();
    onLogout();
    navigate("/login");
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          AIPRS
        </Link>

        <div className={`navbar-menu ${menuOpen ? "open" : ""}`}>
          {user && (
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
                </NavLink>
              ))}
            </nav>
          )}

          <div className="navbar-user">
            {user ? (
              <>
                <span className="navbar-username">{user.name}</span>
                <button className="navbar-logout" onClick={handleLogout}>
                  Log Out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="navbar-login-link" onClick={() => setMenuOpen(false)}>
                  Log In
                </Link>
                <Link to="/signup" onClick={() => setMenuOpen(false)}>
                  <button className="navbar-signup-btn" type="button">Sign Up</button>
                </Link>
              </>
            )}
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
