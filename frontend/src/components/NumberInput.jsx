export default function NumberInput({ value, onChange, min, max }) {
  function clamp(n) {
    if (min !== undefined && n < min) return min;
    if (max !== undefined && n > max) return max;
    return n;
  }

  function step(delta) {
    const current = Number(value) || 0;
    onChange(clamp(current + delta));
  }

  return (
    <div className="number-input">
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="number-input-steppers">
        <button type="button" aria-label="Increment" onClick={() => step(1)}>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
            <path d="M1 5L5 1L9 5" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
        <button type="button" aria-label="Decrement" onClick={() => step(-1)}>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
            <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
      </div>
    </div>
  );
}
