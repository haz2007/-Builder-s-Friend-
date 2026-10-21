import { useRef, useState, type FormEvent } from "react";

import {
  createProduct,
  deactivateProduct,
  deleteProduct,
  getAdminProducts,
  getImageUrl,
  restoreProduct,
  updateProduct,
  uploadProductImage,
} from "./api";
import type { ApiCategory, ApiProduct } from "./api";
import { Icon } from "./AdminIcons";
import ProductVariantsEditor from "./ProductVariantsEditor";
import { showFallbackImage } from "./shop/images";
import { matchScore, searchTokens } from "./shop/search";

type ProductForm = {

  name: string;

  description: string;

  price: string;

  stock_quantity: string;

  unit: string;

  category_id: string;
  thickness_mm: string;
  width_mm: string;
  length_mm: string;

};

const emptyForm: ProductForm = {

  name: "",

  description: "",

  price: "",

  stock_quantity: "0",

  unit: "шт.",

  category_id: "",
  thickness_mm: "",
  width_mm: "",
  length_mm: "",

};

type Props = {
  token: string;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  categories: ApiCategory[];
  products: ApiProduct[];
  onProductsChange: (products: ApiProduct[]) => void;
  /** Перезагрузить товары и категории после изменения */
  onReload: () => Promise<void>;
};

/** Товары: форма добавления и правки, варианты продажи, фото, фильтры списка. */
export default function ProductsSection({
  token,
  onError: setError,
  onNotice: setNotice,
  categories,
  products,
  onProductsChange: setProducts,
  onReload,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<ProductForm>(emptyForm);

  const [editingId, setEditingId] = useState<number | null>(null);

  const [search, setSearch] = useState("");
  const [productCategoryFilter, setProductCategoryFilter] = useState("ALL");
  const [productStockFilter, setProductStockFilter] = useState("ALL");
  const [uploadingProductId, setUploadingProductId] = useState<number | null>(

    null,

  );

  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});

  const productFormRef = useRef<HTMLElement | null>(null);

  // То же правило, что и на сервере: 27,333 доски в кубе → 27 шт
  const piecesPerCubePreview = (() => {
    const [t, w, l] = [form.thickness_mm, form.width_mm, form.length_mm].map(
      (value) => Number(value.replace(",", ".")),
    );
    if (!(t > 0 && w > 0 && l > 0)) return null;
    return Math.floor(1 / ((t * w * l) / 1_000_000_000) + 1e-9);
  })();

  const editingProduct =
    products.find((product) => product.id === editingId) ?? null;

  // После изменения вариантов основной вариант мог поменяться —
  // подтягиваем его цену/остаток/единицу в форму товара.
  async function reloadEditedProduct() {
    const loadedProducts = await getAdminProducts(token);
    setProducts(loadedProducts);

    const updated = loadedProducts.find((product) => product.id === editingId);
    if (updated) {
      setForm((current) => ({
        ...current,
        price: String(updated.price),
        stock_quantity: String(updated.stock_quantity),
        unit: updated.unit,
      }));
    }
  }

  function resetForm() {

    setForm(emptyForm);

    setEditingId(null);

  }

  function openVariants(product: ApiProduct) {
    startEditing(product);
    // Ждём, пока отрисуется блок вариантов, и прокручиваем к нему
    window.setTimeout(() => {
      document
        .getElementById("product-variants")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 150);
  }

  function startEditing(product: ApiProduct) {

    setEditingId(product.id);

    setForm({

      name: product.name,

      description: product.description ?? "",

      price: String(product.price),

      stock_quantity: String(product.stock_quantity),

      unit: product.unit,

      category_id: String(product.category_id),
      thickness_mm: product.thickness_mm ? String(product.thickness_mm) : "",
      width_mm: product.width_mm ? String(product.width_mm) : "",
      length_mm: product.length_mm ? String(product.length_mm) : "",

    });

    setError("");

    setNotice("");

    window.requestAnimationFrame(() => {
      productFormRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });

  }

  async function handleSaveProduct(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    if (!token) return;

    const price = Number(form.price);

    const stock = Number(form.stock_quantity);

    const categoryId = Number(form.category_id);

    if (

      !form.name.trim() ||

      !Number.isFinite(price) ||

      price <= 0 ||

      !Number.isFinite(stock) ||

      stock < 0 ||

      !Number.isInteger(categoryId) ||

      categoryId <= 0 ||

      !form.unit.trim()

    ) {

      setError("Проверь название, цену, остаток, единицу и категорию.");

      return;

    }

    const dimensionValues = [form.thickness_mm, form.width_mm, form.length_mm]
      .map((value) => value.trim());
    const filledDimensions = dimensionValues.filter(Boolean).length;

    if (filledDimensions !== 0 && filledDimensions !== 3) {
      setError("Укажи толщину, ширину и длину доски вместе — или оставь все пустыми.");
      return;
    }

    const [thickness, width, length] = dimensionValues.map((value) =>
      value ? Number(value.replace(",", ".")) : null,
    );

    setLoading(true);

    setError("");

    setNotice("");

    const data = {

      name: form.name.trim(),

      description: form.description.trim() || null,

      price,

      stock_quantity: stock,

      unit: form.unit.trim(),

      category_id: categoryId,
      thickness_mm: thickness,
      width_mm: width,
      length_mm: length,

    };

    try {

      if (editingId === null) {
        const created = await createProduct(data, token);
        await onReload();
        // Сразу открываем новый товар: ниже появится блок «Варианты продажи»
        openVariants(created);
        setNotice(
          "Товар добавлен. Ниже можно добавить варианты продажи — например, «Куб» или «Пачка».",
        );
      } else {
        await updateProduct(editingId, data, token);
        setNotice("Изменения сохранены.");
        resetForm();
        await onReload();
      }

    } catch (err) {

      setError(

        err instanceof Error ? err.message : "Не удалось сохранить товар.",

      );

    } finally {

      setLoading(false);

    }

  }

  async function handleUploadImage(productId: number, file: File) {

    if (!token) return;

    const input = fileInputRefs.current[productId];

    if (file.size > 5 * 1024 * 1024) {

      setError("Размер фотографии не должен превышать 5 МБ.");

      if (input) input.value = "";

      return;

    }

    setUploadingProductId(productId);

    setError("");

    setNotice("");

    try {

      await uploadProductImage(productId, file, token);

      await onReload();

      setNotice("Фотография загружена.");

    } catch (err) {

      setError(

        err instanceof Error

          ? err.message

          : "Не удалось загрузить фотографию.",

      );

    } finally {

      if (input) input.value = "";

      setUploadingProductId(null);

    }

  }

  async function handleProductStatus(product: ApiProduct) {

    if (!token) return;

    const action =

      product.is_active === 1 ? deactivateProduct : restoreProduct;

    const confirmation =

      product.is_active === 1

        ? `Скрыть товар «${product.name}» из каталога?`

        : `Вернуть товар «${product.name}» в каталог?`;

    if (!window.confirm(confirmation)) return;

    setLoading(true);

    setError("");

    setNotice("");

    try {

      await action(product.id, token);

      await onReload();

      setNotice(

        product.is_active === 1

          ? "Товар скрыт из каталога."

          : "Товар снова доступен в каталоге.",

      );

    } catch (err) {

      setError(

        err instanceof Error

          ? err.message

          : "Не удалось изменить статус товара.",

      );

    } finally {

      setLoading(false);

    }

  }

  async function handleDeleteProduct(product: ApiProduct) {
    if (!token) return;
    if (!window.confirm(`Удалить товар «${product.name}»? Это действие нельзя отменить.`)) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      await deleteProduct(product.id, token);
      if (editingId === product.id) resetForm();
      await onReload();
      setNotice(`Товар «${product.name}» удалён.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить товар.");
    } finally {
      setLoading(false);
    }
  }

  const visibleProducts = products.filter((product) => {
    const matchesSearch =
      matchScore(searchTokens(search), {
        title: product.name,
        extra: [
          product.description ?? "",
          categories.find((category) => category.id === product.category_id)?.name ?? "",
          ...product.variants.map((variant) => variant.name),
        ],
      }) > 0;
    const matchesCategory =
      productCategoryFilter === "ALL" ||
      String(product.category_id) === productCategoryFilter;
    const matchesStock =
      productStockFilter === "ALL" ||
      (productStockFilter === "IN_STOCK" && product.stock_quantity > 0) ||
      (productStockFilter === "OUT_OF_STOCK" && product.stock_quantity <= 0) ||
      (productStockFilter === "LOW_STOCK" && product.stock_quantity > 0 && product.stock_quantity <= 10);
    return matchesSearch && matchesCategory && matchesStock;
  });

  return (
    <>
    <section
      className="admin-card"
      ref={productFormRef}
      style={{ scrollMarginTop: "24px" }}
    >

      <h2>

        {editingId === null

          ? "Добавить товар"

          : `Редактировать товар №${editingId}`}

      </h2>

      <form className="admin-product-form" onSubmit={handleSaveProduct}>

        <label>

          Название

          <input

            value={form.name}

            onChange={(event) =>

              setForm({ ...form, name: event.target.value })

            }

            maxLength={200}

            required

          />

        </label>

        <label>

          Категория

          <select

            value={form.category_id}

            onChange={(event) =>

              setForm({ ...form, category_id: event.target.value })

            }

            required

          >

            <option value="">Выбрать категорию</option>
            {categories
              .filter((category) => category.parent_id === null)
              .map((top) => {
                const children = categories.filter(
                  (category) => category.parent_id === top.id,
                );
                return children.length ? (
                  <optgroup key={top.id} label={top.name}>
                    <option value={top.id}>{top.name} (без подкатегории)</option>
                    {children.map((child) => (
                      <option key={child.id} value={child.id}>
                        {child.name}
                      </option>
                    ))}
                  </optgroup>
                ) : (
                  <option key={top.id} value={top.id}>
                    {top.name}
                  </option>
                );
              })}

          </select>

        </label>

        <label>

          Цена основного варианта, ₽

          <input

            type="number"

            min="0.01"

            step="0.01"

            value={form.price}

            onChange={(event) =>

              setForm({ ...form, price: event.target.value })

            }

            required

          />

        </label>

        <label>

          Остаток на складе (в единице товара)

          <input

            type="number"

            min="0"

            step="0.01"

            value={form.stock_quantity}

            onChange={(event) =>

              setForm({ ...form, stock_quantity: event.target.value })

            }

            required

          />

        </label>

        <label>

          Единица измерения

          <input

            value={form.unit}

            onChange={(event) =>

              setForm({ ...form, unit: event.target.value })

            }

            placeholder="шт., м, м², м³, уп."

            maxLength={20}

            required

          />

        </label>

        <fieldset className="admin-dimensions admin-full">
          <legend>Размеры доски, мм (только для пиломатериалов)</legend>
          <p>
            Если заполнить, остаток ведётся в штуках (единица «шт»), а
            вариант «м³» сам списывает столько досок, сколько целых
            входит в куб.
          </p>
          <div className="admin-dimensions-grid">
            <label>
              Толщина
              <input
                type="number"
                min="1"
                step="0.1"
                value={form.thickness_mm}
                onChange={(event) =>
                  setForm({ ...form, thickness_mm: event.target.value })
                }
                placeholder="50"
              />
            </label>
            <label>
              Ширина
              <input
                type="number"
                min="1"
                step="0.1"
                value={form.width_mm}
                onChange={(event) =>
                  setForm({ ...form, width_mm: event.target.value })
                }
                placeholder="150"
              />
            </label>
            <label>
              Длина
              <input
                type="number"
                min="1"
                step="1"
                value={form.length_mm}
                onChange={(event) =>
                  setForm({ ...form, length_mm: event.target.value })
                }
                placeholder="6000"
              />
            </label>
          </div>
          {piecesPerCubePreview !== null && (
            <strong className="admin-dimensions-result">
              В 1 м³ — {piecesPerCubePreview} шт
            </strong>
          )}
        </fieldset>

        <label className="admin-full">

          Описание

          <textarea

            value={form.description}

            onChange={(event) =>

              setForm({ ...form, description: event.target.value })

            }

            maxLength={1000}

            rows={3}

          />

        </label>

        <div className="admin-form-actions admin-full">

          <button className="admin-btn admin-btn-primary" disabled={loading}>

            {loading

              ? "Сохраняем..."

              : editingId === null

                ? "Добавить товар"

                : "Сохранить изменения"}

          </button>

          {editingId !== null && (

            <button

              type="button"

              className="admin-btn admin-btn-outline"

              onClick={resetForm}

            >

              Отмена

            </button>

          )}

        </div>

      </form>

      {editingProduct === null && (
        <p className="admin-hint admin-variants-hint">
          💡 Продавать товар по-разному (штука, куб, пачка) можно будет
          сразу после сохранения: появится блок «Варианты продажи». Для
          досок укажи размеры — количество штук в кубе посчитается само.
        </p>
      )}

      {editingProduct && (
        <ProductVariantsEditor
          key={editingProduct.id}
          product={editingProduct}
          token={token}
          onChanged={reloadEditedProduct}
          onError={setError}
          onNotice={setNotice}
        />
      )}

    </section>

    <section className="admin-card">

      <div className="admin-list-heading">

        <div>

          <h2>Список товаров</h2>

          <p>Показано: {visibleProducts.length} из {products.length}</p>

        </div>

        <div className="admin-row-actions admin-product-filters">
          <input
            className="admin-search"
            placeholder="Поиск: доска 50х150, саморезы…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Поиск товаров по названию и описанию"
          />
          <select
            value={productCategoryFilter}
            onChange={(event) => setProductCategoryFilter(event.target.value)}
            aria-label="Фильтр товаров по категории"
          >
            <option value="ALL">Все категории</option>
            {categories.map((category) => (
              <option key={category.id} value={String(category.id)}>
                {category.name}
              </option>
            ))}
          </select>
          <select
            value={productStockFilter}
            onChange={(event) => setProductStockFilter(event.target.value)}
            aria-label="Фильтр товаров по остатку"
          >
            <option value="ALL">Любой остаток</option>
            <option value="IN_STOCK">Есть в наличии</option>
            <option value="LOW_STOCK">Мало на складе (1–10)</option>
            <option value="OUT_OF_STOCK">Нет в наличии</option>
          </select>
        </div>

      </div>

      {visibleProducts.length === 0 ? (

        <p>Товары не найдены.</p>

      ) : (

        <div className="admin-table-wrap">

          <table className="admin-table">

            <thead>

              <tr>

                <th>Товар и фото</th>

                <th>Варианты и цены</th>

                <th>Остаток</th>

                <th>Статус</th>

                <th>Действия</th>

              </tr>

            </thead>

            <tbody>

              {visibleProducts.map((product) => (

                <tr key={product.id}>

                  <td>

                    <strong>{product.name}</strong>

                    <small>

                      {categories.find(

                        (category) =>

                          category.id === product.category_id,

                      )?.name ?? "Без категории"}

                    </small>

                    <div className="admin-product-photo">
                      {product.image_url ? (
                        <img
                          src={getImageUrl(product.image_url) ?? undefined}
                          onError={showFallbackImage}
                          alt={product.name}
                        />
                      ) : (
                        <span className="admin-product-photo-empty">Нет фото</span>
                      )}
                      <label
                        className={`admin-btn admin-btn-ghost admin-btn-sm ${
                          uploadingProductId === product.id ? "is-busy" : ""
                        }`}
                      >
                        <Icon name="camera" size={15} />
                        {uploadingProductId === product.id
                          ? "Загружаем…"
                          : product.image_url
                            ? "Сменить фото"
                            : "Добавить фото"}
                        <input
                          ref={(element) => {
                            fileInputRefs.current[product.id] = element;
                          }}
                          type="file"
                          hidden
                          accept="image/jpeg,image/png,image/webp"
                          disabled={uploadingProductId === product.id}
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) void handleUploadImage(product.id, file);
                          }}
                        />
                      </label>
                    </div>

                  </td>

                  <td>
                    <div className="admin-variant-prices">
                      {product.variants
                        .filter((variant) => variant.is_active === 1)
                        .map((variant) => (
                          <div className="admin-variant-price" key={variant.id}>
                            <span>{variant.name}</span>
                            <b>
                              {variant.price.toLocaleString("ru-RU")} ₽
                              <small> / {variant.unit}</small>
                            </b>
                          </div>
                        ))}
                    </div>
                  </td>

                  <td>

                    {product.stock_quantity} {product.unit}

                  </td>

                  <td>

                    <span

                      className={

                        product.is_active === 1

                          ? "admin-status active"

                          : "admin-status inactive"

                      }

                    >

                      {product.is_active === 1

                        ? "В каталоге"

                        : "Скрыт"}

                    </span>

                  </td>

                  <td>

                    <div className="admin-product-actions">
                      <button
                        type="button"
                        className="admin-btn admin-btn-outline admin-btn-sm"
                        onClick={() => startEditing(product)}
                      >
                        <Icon name="edit" size={15} />
                        Изменить
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn-outline admin-btn-sm"
                        onClick={() => openVariants(product)}
                        title="Штука, куб, пачка — как продаётся товар"
                      >
                        <Icon name="layers" size={15} />
                        Варианты
                        <span className="admin-btn-count">{product.variants.length}</span>
                      </button>
                      <div className="admin-product-actions-row">
                        <button
                          type="button"
                          className="admin-btn admin-btn-ghost admin-btn-sm"
                          disabled={loading}
                          onClick={() => handleProductStatus(product)}
                          title={
                            product.is_active === 1
                              ? "Убрать из каталога, не удаляя"
                              : "Снова показать в каталоге"
                          }
                        >
                          <Icon name={product.is_active === 1 ? "eyeOff" : "eye"} size={15} />
                          {product.is_active === 1 ? "Скрыть" : "Вернуть"}
                        </button>
                        <button
                          type="button"
                          className="admin-btn admin-btn-danger admin-btn-sm admin-btn-icon"
                          disabled={loading}
                          onClick={() => void handleDeleteProduct(product)}
                          title="Удалить товар"
                          aria-label={`Удалить «${product.name}»`}
                        >
                          <Icon name="trash" size={15} />
                        </button>
                      </div>
                    </div>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      )}

    </section>
    </>
  );
}
