interface Props {
  onHome: () => void;
}

export function Header({ onHome }: Props) {
  return (
    <header className="header container">
      <button className="brand" onClick={onHome} aria-label="Ir al inicio">
        <span className="brand-mark" aria-hidden>
          <svg width="14" height="14" viewBox="0 0 14 14">
            <path d="M3 1.5l9 5.5-9 5.5z" fill="#fff" />
          </svg>
        </span>
        ClipMaker
      </button>
    </header>
  );
}
