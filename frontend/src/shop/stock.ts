import { formatQuantity } from "./format";
import type { Product, ProductVariant } from "./types";

/** «В наличии: 11 м3 (300 шт)» — для кубов показываем и штуки. */
export function stockLabel(product: Product, variant: ProductVariant | undefined) {
  if (!variant || variant.stockQuantity <= 0) return "Нет в наличии";

  const main = `В наличии: ${formatQuantity(variant.stockQuantity)} ${variant.unit}`;

  return variant.baseQuantity !== 1
    ? `${main} (${formatQuantity(product.stockQuantity)} ${product.unit})`
    : main;
}
