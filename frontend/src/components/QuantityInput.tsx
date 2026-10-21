import { Minus, Plus } from "lucide-react";
import { useState } from "react";

/**
 * Количество: кнопки − / + и поле, в которое можно вписать число вручную
 * (50 досок кнопкой не нащёлкаешь). Больше, чем есть на складе, не даёт.
 */
export default function QuantityInput({
  value,
  max,
  onChange,
  allowRemove = false,
  large = false,
  iconSize = 15,
}: {
  value: number;
  /** Сколько всего можно взять */
  max: number;
  onChange: (value: number) => void;
  /** «−» на единице убирает товар из корзины */
  allowRemove?: boolean;
  large?: boolean;
  iconSize?: number;
}) {
  // Пока поле в фокусе, показываем то, что ввёл покупатель, даже пустую строку
  const [draft, setDraft] = useState<string | null>(null);

  function commit() {
    if (draft === null) return;
    const typed = Number.parseInt(draft, 10);
    setDraft(null);
    if (!Number.isFinite(typed) || typed < 1) return;
    const next = Math.min(typed, Math.max(max, 1));
    if (next !== value) onChange(next);
  }

  return (
    <div className={large ? "quantity-control quantity-control-large" : "quantity-control"}>
      <button
        type="button"
        onClick={() => onChange(value - 1)}
        disabled={value <= 1 && !allowRemove}
        aria-label="Уменьшить количество"
      >
        <Minus size={iconSize} />
      </button>
      <input
        className="quantity-input"
        type="text"
        inputMode="numeric"
        aria-label="Количество"
        value={draft ?? String(value)}
        onFocus={(event) => {
          setDraft(String(value));
          event.target.select();
        }}
        onChange={(event) => setDraft(event.target.value.replace(/\D/g, "").slice(0, 5))}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
          if (event.key === "Escape") {
            setDraft(null);
            event.currentTarget.blur();
          }
        }}
        title={`Можно взять до ${max}`}
      />
      <button
        type="button"
        onClick={() => onChange(value + 1)}
        disabled={value >= max}
        aria-label="Увеличить количество"
      >
        <Plus size={iconSize} />
      </button>
    </div>
  );
}
