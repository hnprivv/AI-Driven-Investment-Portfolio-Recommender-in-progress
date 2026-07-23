import { Navigate, Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Footer from "./Footer";

export default function Layout({ user, onLogout, onUserUpdate, requireAuth = true }) {
  if (requireAuth && !user) return <Navigate to="/login" />;

  return (
    <>
      <Navbar user={user} onLogout={onLogout} />
      <main className="page-content">
        <Outlet context={{ user, onLogout, onUserUpdate }} />
      </main>
      <Footer />
    </>
  );
}
