import { PHONES } from "./contacts";
import { formatQuantity } from "./format";
import type { Product, ProductVariant } from "./types";

/** Остатка нет — товар можно заказать по телефону, привезём под заказ */
export function isOnOrder(variant: ProductVariant | undefined) {
  return !variant || variant.stockQuantity <= 0;
}

/**
 * «Заказать» у товара под заказ: с телефона сразу звоним в магазин,
 * на компьютере открываем окно с номерами и «Перезвоните мне».
 */
export function orderByPhone(product: string, openCallUs: (options: { product: string }) => void) {
  if (window.matchMedia("(pointer: coarse)").matches) {
    window.location.href = PHONES[0].href;
  } else {
    openCallUs({ product });
  }
}

/** «В наличии: 11 м3 (300 шт)» — для кубов показываем и штуки. */
export function stockLabel(product: Product, variant: ProductVariant | undefined) {
  if (!variant || isOnOrder(variant)) return "Под заказ — срок уточним по телефону";

  const main = `В наличии: ${formatQuantity(variant.stockQuantity)} ${variant.unit}`;

  return variant.baseQuantity !== 1
    ? `${main} (${formatQuantity(product.stockQuantity)} ${product.unit})`
    : main;
}
