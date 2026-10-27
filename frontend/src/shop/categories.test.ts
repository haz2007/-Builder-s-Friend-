import { describe, expect, it } from "vitest";
import { categoriesWithProducts, sortByCategoryPriority } from "./categories";

// Как отдаёт API: верхний уровень по позиции, затем подразделы по позиции
const categories = [
  { id: 1, name: "Пиломатериалы", parent_id: null },
  { id: 5, name: "Крепёж", parent_id: null },
  { id: 2, name: "Доска", parent_id: 1 },
  { id: 3, name: "Брус", parent_id: 1 },
  { id: 4, name: "Вагонка", parent_id: 1 },
  { id: 6, name: "Саморезы", parent_id: 5 },
];

const product = (name: string, categoryId: number) => ({ name, categoryId, categoryIds: [categoryId] });

describe("порядок товаров", () => {
  it("сначала доски, потом брус, потом крепёж; размеры по возрастанию", () => {
    const sorted = sortByCategoryPriority(
      [
        product("Саморез 35 мм", 6),
        product("Брус 100×100×6000", 3),
        product("Доска 50×150×6000", 2),
        product("Доска 25×100×6000", 2),
      ],
      categories,
    );
    expect(sorted.map((p) => p.name)).toEqual([
      "Доска 25×100×6000",
      "Доска 50×150×6000",
      "Брус 100×100×6000",
      "Саморез 35 мм",
    ]);
  });

  it("пустые разделы не показываются", () => {
    const shown = categoriesWithProducts(categories, [product("Доска 25×100×6000", 2)]);
    expect(shown.map((c) => c.name)).toEqual(["Пиломатериалы", "Доска"]);
  });
});
