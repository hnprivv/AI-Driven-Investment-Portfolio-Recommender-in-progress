import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { clearToken, me } from "./api";
import Layout from "./components/Layout";
import ScrollToTop from "./components/ScrollToTop";
import ToastContainer from "./components/Toast";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import EditProfile from "./pages/EditProfile";
import Feedback from "./pages/Feedback";
import MarketOverview from "./pages/MarketOverview";
import NewsSentiment from "./pages/NewsSentiment";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import Recommendations from "./pages/Recommendations";
import Settings from "./pages/Settings";
import TermsConditions from "./pages/TermsConditions";
import Updates from "./pages/Updates";

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;

  const handleLogout = () => {
    clearToken();
    setUser(null);
  };

  return (
    <>
      <ScrollToTop />
      <ToastContainer />
      <Routes>
        <Route path="/" element={<Home user={user} onLogout={handleLogout} />} />
        <Route path="/updates" element={<Updates user={user} onLogout={handleLogout} />} />
        <Route path="/privacy" element={<PrivacyPolicy user={user} onLogout={handleLogout} />} />
        <Route path="/terms" element={<TermsConditions user={user} onLogout={handleLogout} />} />
        <Route
          path="/login"
          element={user ? <Navigate to="/dashboard" /> : <Login onLogin={setUser} />}
        />
        <Route
          path="/signup"
          element={user ? <Navigate to="/dashboard" /> : <Signup onLogin={setUser} />}
        />
        <Route
          element={
            <Layout
              user={user}
              onLogout={handleLogout}
              onUserUpdate={(updates) => setUser((u) => ({ ...u, ...updates }))}
              requireAuth={false}
            />
          }
        >
          <Route path="/market" element={<MarketOverview />} />
          <Route path="/news" element={<NewsSentiment />} />
        </Route>
        <Route
          element={
            <Layout
              user={user}
              onLogout={handleLogout}
              onUserUpdate={(updates) => setUser((u) => ({ ...u, ...updates }))}
            />
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="/profile" element={<EditProfile />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </>
  );
}
