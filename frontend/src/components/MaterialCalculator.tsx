import { Calculator } from "lucide-react";
import { useState } from "react";

import { piecesForArea, piecesForLength, volumeOf } from "../shop/calculator";
import { formatPrice, formatQuantity } from "../shop/format";
import type { Product, ProductVariant } from "../shop/types";

type Mode = "area" | "length";

/** «Сколько нужно?» для досок, бруса и вагонки — по площади или длине. */
export default function MaterialCalculator({
  product,
  onTake,
}: {
  product: Product;
  /** Положить в поле количества нужное число штук */
  onTake: (variant: ProductVariant, pieces: number) => void;
}) {
  const [mode, setMode] = useState<Mode>("area");
  const [value, setValue] = useState("");
  const size = product.dimensions;
  const piece = product.variants.find((variant) => variant.baseQuantity === 1);
  if (!size || !piece) return null;

  const number = Number(value.replace(",", "."));
  const pieces = mode === "area" ? piecesForArea(number, size) : piecesForLength(number, size);
  const enough = pieces <= piece.stockQuantity;

  return (
    <section className="material-calculator" aria-label="Калькулятор материала">
      <h2>
        <Calculator size={18} /> Сколько нужно?
      </h2>
      <div className="material-calculator-modes" role="radiogroup">
        {(
          [
            ["area", "Площадь, м²", "пол, обшивка"],
            ["length", "Длина, м", "каркас, лаги"],
          ] as const
        ).map(([key, title, hint]) => (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={mode === key}
            className={mode === key ? "is-selected" : ""}
            onClick={() => setMode(key)}
          >
            <strong>{title}</strong>
            <small>{hint}</small>
          </button>
        ))}
      </div>
      <label className="material-calculator-input">
        <span>{mode === "area" ? "Площадь, м²" : "Общая длина, м"}</span>
        <input
          type="text"
          inputMode="decimal"
          value={value}
          onChange={(event) => setValue(event.target.value.replace(/[^\d.,]/g, "").slice(0, 8))}
          placeholder={mode === "area" ? "например, 20" : "например, 40"}
        />
      </label>
      {pieces > 0 && (
        <div className="material-calculator-result">
          <p>
            <strong>
              {pieces} {piece.unit}
            </strong>{" "}
            ≈ {formatQuantity(Number(volumeOf(pieces, size).toFixed(3)))} м³ ·{" "}
            {formatPrice(pieces * piece.price)}
          </p>
          <small>С запасом 10 % на подрезку, по размерам {size.width}×{size.length} мм.</small>
          {enough ? (
            <button type="button" className="button button-dark" onClick={() => onTake(piece, pieces)}>
              Взять {pieces} {piece.unit}
            </button>
          ) : (
            <small className="material-calculator-warning">
              На складе {formatQuantity(piece.stockQuantity)} {piece.unit} — позвоните, привезём под заказ.
            </small>
          )}
        </div>
      )}
    </section>
  );
}
