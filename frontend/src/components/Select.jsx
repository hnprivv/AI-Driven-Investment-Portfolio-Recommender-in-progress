import { useEffect, useRef, useState } from "react";

export default function Select({ value, onChange, options }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(option) {
    onChange(option);
    setOpen(false);
  }

  return (
    <div className="custom-select" ref={ref}>
      <button
        type="button"
        className={`custom-select-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{value}</span>
        <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
          <path d="M1 1.5L6 6.5L11 1.5" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>

      {open && (
        <ul className="custom-select-menu">
          {options.map((option) => (
            <li
              key={option}
              className={`custom-select-option ${option === value ? "selected" : ""}`}
              onClick={() => handleSelect(option)}
            >
              {option}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
