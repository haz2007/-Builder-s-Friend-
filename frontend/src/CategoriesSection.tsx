import { useState, type FormEvent } from "react";

import { createCategory, deleteCategory, updateCategory } from "./api";
import type { ApiCategory, ApiProduct } from "./api";
import { Icon } from "./AdminIcons";

/** Разделы, а сразу под каждым — его подкатегории. */
function categoriesTree(categories: ApiCategory[]) {
  return categories
    .filter((category) => category.parent_id === null)
    .flatMap((top) => [
      top,
      ...categories.filter((category) => category.parent_id === top.id),
    ]);
}

type Props = {
  token: string;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  categories: ApiCategory[];
  products: ApiProduct[];
  /** Перезагрузить товары и категории после изменения */
  onReload: () => Promise<void>;
};

export default function CategoriesSection({
  token,
  onError: setError,
  onNotice: setNotice,
  categories,
  products,
  onReload,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [categoryName, setCategoryName] = useState("");
  // "" — категория верхнего уровня, иначе id родителя
  const [categoryParentId, setCategoryParentId] = useState("");

  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(
    null,
  );

  const sortedCategories = categoriesTree(categories);

  function categoryProductCount(categoryId: number) {
    return products.filter((product) => product.category_ids.includes(categoryId)).length;
  }

  function startEditingCategory(category: ApiCategory) {
    setEditingCategoryId(category.id);

    setCategoryName(category.name);
    setCategoryParentId(category.parent_id ? String(category.parent_id) : "");

    setError("");

    setNotice("");
  }

  async function handleDeleteCategory(category: ApiCategory) {
    if (!token) return;

    const categoryProducts = products.filter(
      (product) => product.category_id === category.id,
    );
    const warning = categoryProducts.length
      ? `В категории «${category.name}» находится товаров: ${categoryProducts.length}.\n\nЕсли продолжить, категория и все товары в ней будут удалены. Это действие нельзя отменить.\n\nУдалить категорию вместе с товарами?`
      : `Удалить категорию «${category.name}»? Это действие нельзя отменить.`;

    if (!window.confirm(warning)) return;

    setLoading(true);
    setError("");
    setNotice("");
    try {
      await deleteCategory(category.id, token);
      if (editingCategoryId === category.id) resetCategoryForm();
      await onReload();
      setNotice(
        categoryProducts.length
          ? `Категория «${category.name}» и её товары удалены.`
          : `Категория «${category.name}» удалена.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить категорию.");
    } finally {
      setLoading(false);
    }
  }

  function resetCategoryForm() {
    setEditingCategoryId(null);

    setCategoryName("");
    setCategoryParentId("");
  }

  async function handleSaveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) return;

    const name = categoryName.trim();

    if (!name) {
      setError("Введи название категории.");

      return;
    }

    setLoading(true);

    setError("");

    setNotice("");

    try {
      if (editingCategoryId === null) {
        await createCategory({ name, parent_id: categoryParentId ? Number(categoryParentId) : null }, token);

        setNotice("Категория добавлена.");
      } else {
        await updateCategory(editingCategoryId, { name, parent_id: categoryParentId ? Number(categoryParentId) : null }, token);

        setNotice("Категория сохранена.");
      }

      resetCategoryForm();

      await onReload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось сохранить категорию.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="admin-card">
      <h2>
        {editingCategoryId === null
          ? "Добавить категорию"
          : `Переименовать категорию №${editingCategoryId}`}
      </h2>
      <p>
        Категории отображаются в каталоге магазина и при добавлении товара.
      </p>
      <form className="admin-product-form" onSubmit={handleSaveCategory}>
        <label className="admin-full">
          Название категории
          <input
            value={categoryName}

            onChange={(event) => setCategoryName(event.target.value)}

            placeholder="Например, Крепёж и метизы"
            maxLength={100}

            required
          />
        </label>
        <label className="admin-full">
          Где находится
          <select
            value={categoryParentId}
            onChange={(event) => setCategoryParentId(event.target.value)}
          >
            <option value="">Отдельный раздел (верхний уровень)</option>
            {categories
              .filter(
                (category) =>
                  category.parent_id === null &&
                  category.id !== editingCategoryId,
              )
              .map((category) => (
                <option key={category.id} value={category.id}>
                  Подкатегория в «{category.name}»
                </option>
              ))}
          </select>
        </label>
        <div className="admin-form-actions admin-full">
          <button className="admin-btn admin-btn-primary" disabled={loading}>
            {loading
              ? "Сохраняем..."
              : editingCategoryId === null
                ? "Добавить категорию"
                : "Сохранить"}
          </button>
          {editingCategoryId !== null && (
            <button
              type="button"
              className="admin-btn admin-btn-outline"
              onClick={resetCategoryForm}

            >
              Отмена
            </button>
          )}
        </div>
      </form>
      <div className="admin-category-list">
        {categories.length === 0 ? (
          <p>Категорий пока нет.</p>
        ) : (
          sortedCategories.map((category) => (
            <div
              className={`admin-category-row ${category.parent_id ? "is-child" : ""}`}
              key={category.id}
            >
              <div>
                <strong>
                  {category.parent_id ? "↳ " : ""}
                  {category.name}
                </strong>
                <small>
                  {category.parent_id
                    ? `Подкатегория · товаров: ${categoryProductCount(category.id)}`
                    : `Раздел · подкатегорий: ${categories.filter((item) => item.parent_id === category.id).length}`}
                </small>
              </div>
              <div className="admin-category-actions">
                <button
                  type="button"
                  className="admin-btn admin-btn-outline admin-btn-sm"
                  disabled={loading}
                  onClick={() => startEditingCategory(category)}
                >
                  <Icon name="edit" size={15} />
                  Изменить
                </button>
                <button
                  type="button"
                  className="admin-btn admin-btn-danger admin-btn-sm admin-btn-icon"
                  disabled={loading}
                  onClick={() => handleDeleteCategory(category)}
                  title="Удалить категорию"
                  aria-label={`Удалить категорию «${category.name}»`}
                >
                  <Icon name="trash" size={15} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
