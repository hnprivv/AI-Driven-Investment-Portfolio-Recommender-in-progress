import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { me } from "./api";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import MarketOverview from "./pages/MarketOverview";
import NewsSentiment from "./pages/NewsSentiment";
import Recommendations from "./pages/Recommendations";
import Settings from "./pages/Settings";

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

  return (
    <Routes>
      <Route path="/" element={<Home user={user} onLogout={() => setUser(null)} />} />
      <Route
        path="/login"
        element={user ? <Navigate to="/dashboard" /> : <Login onLogin={setUser} />}
      />
      <Route
        path="/signup"
        element={user ? <Navigate to="/dashboard" /> : <Signup onLogin={setUser} />}
      />
      <Route element={<Layout user={user} onLogout={() => setUser(null)} />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/recommendations" element={<Recommendations />} />
        <Route path="/market" element={<MarketOverview />} />
        <Route path="/news" element={<NewsSentiment />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
