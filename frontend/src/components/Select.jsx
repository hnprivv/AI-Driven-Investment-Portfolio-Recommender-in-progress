import { useEffect, useRef, useState } from "react";

// options may be an array of strings, or an array of { value, label } objects
// for cases where the displayed text differs from the underlying value.
export default function Select({ value, onChange, options, placeholder }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const normalized = options.map((o) =>
    typeof o === "object" ? o : { value: o, label: o }
  );
  const current = normalized.find((o) => o.value === value);

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
    onChange(option.value);
    setOpen(false);
  }

  return (
    <div className="custom-select" ref={ref}>
      <button
        type="button"
        className={`custom-select-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={!current && placeholder ? "custom-select-placeholder" : ""}>
          {current ? current.label : placeholder || value}
        </span>
        <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
          <path d="M1 1.5L6 6.5L11 1.5" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>

      {open && (
        <ul className="custom-select-menu">
          {normalized.map((option) => (
            <li
              key={option.value}
              className={`custom-select-option ${option.value === value ? "selected" : ""}`}
              onClick={() => handleSelect(option)}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
