import { useEffect, useState } from "react";
import "./Toast.css";

// Module-scoped pub/sub rather than context, so any component can call
// showToast(...) directly (e.g. from an onClick handler) without needing
// a provider wired through the tree — ToastContainer just needs to be
// rendered once, anywhere, for the notifications to show up.
let listeners = [];
let idCounter = 0;

export function showToast(message, { type = "info", duration = 4000 } = {}) {
  const id = ++idCounter;
  listeners.forEach((fn) => fn({ id, message, type, duration }));
  return id;
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    function handle(toast) {
      setToasts((prev) => [...prev, toast]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id));
      }, toast.duration);
    }
    listeners.push(handle);
    return () => {
      listeners = listeners.filter((fn) => fn !== handle);
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
