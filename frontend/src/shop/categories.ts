import type { ApiCategory } from "../api";

export function topLevelCategories(categories: ApiCategory[]) {
  return categories.filter((category) => category.parent_id === null);
}

export function childCategories(categories: ApiCategory[], parentId: number) {
  return categories.filter((category) => category.parent_id === parentId);
}

/** Категория и все её подкатегории — для фильтра товаров. */
export function categoryWithChildrenIds(categories: ApiCategory[], categoryId: number) {
  return [
    categoryId,
    ...childCategories(categories, categoryId).map((category) => category.id),
  ];
}

export function parentCategory(categories: ApiCategory[], category: ApiCategory) {
  return category.parent_id === null
    ? undefined
    : categories.find((item) => item.id === category.parent_id);
}

/** Только разделы, где есть товары (сами или в подразделах): пустые не показываем. */
export function categoriesWithProducts(
  categories: ApiCategory[],
  products: { categoryIds: number[] }[],
) {
  const used = new Set(products.flatMap((product) => product.categoryIds));
  return categories.filter((category) =>
    categoryWithChildrenIds(categories, category.id).some((id) => used.has(id)),
  );
}

/**
 * Порядок «как в магазине»: разделы по приоритету из API (доски первыми),
 * внутри раздела — по названию с учётом чисел (25×100 раньше 50×150).
 */
export function sortByCategoryPriority<T extends { categoryId: number; name: string }>(
  products: T[],
  categories: ApiCategory[],
) {
  const rank = new Map<number, number>();
  topLevelCategories(categories).forEach((top, i) => {
    rank.set(top.id, i * 1000);
    childCategories(categories, top.id).forEach((child, j) => rank.set(child.id, i * 1000 + j + 1));
  });
  const unknown = Number.MAX_SAFE_INTEGER;
  return [...products].sort(
    (a, b) =>
      (rank.get(a.categoryId) ?? unknown) - (rank.get(b.categoryId) ?? unknown) ||
      a.name.localeCompare(b.name, "ru", { numeric: true }),
  );
}
