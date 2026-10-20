type MarkProps = {
  size?: number;
  /** "dark" — знак на тёмной плашке (по умолчанию), "light" — без плашки */
  tone?: "dark" | "light";
};

/** Знак «Дом из досок»: крыша над тремя досками. */
export function LogoMark({ size = 44, tone = "dark" }: MarkProps) {
  const roof = tone === "dark" ? "#e3a85b" : "#3a2a1f";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      className="logo-mark"
    >
      {tone === "dark" && <rect width="48" height="48" rx="12" fill="#3a2a1f" />}
      <path
        d="M9 22.5 24 11l15 11.5"
        stroke={roof}
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="13" y="25" width="22" height="4.2" rx="1.2" fill="#e8b46c" />
      <rect x="13" y="31" width="22" height="4.2" rx="1.2" fill="#c8873a" />
      <rect x="13" y="37" width="22" height="4.2" rx="1.2" fill="#a8692b" />
    </svg>
  );
}

type LogoProps = {
  inverted?: boolean;
};

/** Полный логотип для шапки и подвала. */
export default function Logo({ inverted = false }: LogoProps) {
  return (
    <span className={`logo ${inverted ? "logo-inverted" : ""}`}>
      <LogoMark size={42} />
      <span className="logo-text">
        <strong>Друг Строителя</strong>
        <small>пиломатериалы · крепёж · доставка</small>
      </span>
    </span>
  );
}
