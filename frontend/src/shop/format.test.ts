import { describe, expect, it } from "vitest";

import { pluralize } from "./format";
import { stockLabel } from "./stock";
import type { Product, ProductVariant } from "./types";

describe("pluralize", () => {
  const forms: [string, string, string] = ["товар", "товара", "товаров"];

  it.each([
    [1, "товар"],
    [3, "товара"],
    [5, "товаров"],
    [11, "товаров"],
    [21, "товар"],
    [112, "товаров"],
    [124, "товара"],
  ])("%i → %s", (count, expected) => {
    expect(pluralize(count, forms)).toBe(expected);
  });
});

describe("stockLabel", () => {
  const variant = (fields: Partial<ProductVariant>): ProductVariant => ({
    id: 1, name: "Штука", unit: "шт", price: 620, baseQuantity: 1, stockQuantity: 10, ...fields,
  });
  const product = { stockQuantity: 300, unit: "шт" } as Product;

  it("для кубов показывает и штуки", () => {
    const label = stockLabel(product, variant({ unit: "м3", baseQuantity: 27, stockQuantity: 11 }));
    expect(label).toBe("В наличии: 11 м3 (300 шт)");
  });

  it("нет остатка — нет в наличии", () => {
    expect(stockLabel(product, variant({ stockQuantity: 0 }))).toBe("Под заказ — срок уточним по телефону");
    expect(stockLabel(product, undefined)).toBe("Под заказ — срок уточним по телефону");
  });
});
