import { formatPrice } from "../shop/format";
import type { Product, ProductVariant } from "../shop/types";

type Props = {
  product: Product;
  selected: ProductVariant | undefined;
  onSelect: (variantId: number) => void;
  size?: "compact" | "large";
};

/** Как покупать товар: поштучно, кубами, пачкой и т. п. */
export default function VariantPicker({
  product,
  selected,
  onSelect,
  size = "compact",
}: Props) {
  if (product.variants.length < 2) return null;

  return (
    <div className={`variant-picker variant-picker-${size}`}>
      <span className="variant-picker-label">Как покупать</span>
      <div
        className="variant-options"
        role="radiogroup"
        aria-label={`Как покупать: ${product.name}`}
      >
        {product.variants.map((variant) => {
          const isSelected = variant.id === selected?.id;

          return (
            <button
              key={variant.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              className={`variant-option ${isSelected ? "is-selected" : ""}`}
              onClick={() => onSelect(variant.id)}
            >
              <span>{variant.name}</span>
              <small>
                {formatPrice(variant.price)} / {variant.unit}
              </small>
            </button>
          );
        })}
      </div>
    </div>
  );
}
