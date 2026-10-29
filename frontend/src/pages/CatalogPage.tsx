import {
  ChevronDown,
  ChevronRight,
  Package,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useParams, useSearchParams } from "react-router-dom";

import ProductCard from "../components/ProductCard";
import SearchSuggestions from "../components/SearchSuggestions";
import {
  categoryWithChildrenIds,
  childCategories,
  parentCategory,
  topLevelCategories,
} from "../shop/categories";
import { pluralize } from "../shop/format";
import { useShop } from "../shop/ShopContext";
import type { Product } from "../shop/types";
import { matchScore, searchTokens } from "../shop/search";
import { usePageTitle } from "../shop/usePageTitle";

const PAGE_SIZE = 12;
const CUBIC_UNITS = ["м3", "м³", "куб"];

/** Ключи фильтров в адресе страницы: ?q=&min=&max=&stock=1&cube=1&t=&w=&l= */
const FILTER_KEYS = ["min", "max", "stock", "cube", "t", "w", "l"];

function sellsByCube(product: Product) {
  return product.variants.some((variant) =>
    CUBIC_UNITS.includes(variant.unit.trim().toLowerCase()),
  );
}

function uniqueSorted(values: (number | undefined)[]) {
  return [...new Set(values.filter((value): value is number => !!value))].sort(
    (a, b) => a - b,
  );
}

/** /catalog — все товары, /catalog/:categoryId — категория или подкатегория. */
export default function CatalogPage() {
  const { products, categories, loading, loadError } = useShop();
  const { categoryId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);

  const search = searchParams.get("q") ?? "";
  const sort = searchParams.get("sort") ?? "popular";
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const minPrice = Number(searchParams.get("min")) || 0;
  const maxPrice = Number(searchParams.get("max")) || 0;
  const onlyInStock = searchParams.get("stock") === "1";
  const onlyCubes = searchParams.get("cube") === "1";
  const thickness = Number(searchParams.get("t")) || 0;
  const width = Number(searchParams.get("w")) || 0;
  const length = Number(searchParams.get("l")) || 0;

  const category = categories.find((item) => String(item.id) === categoryId);
  usePageTitle(category ? category.name : "Каталог");
  const parent = category ? parentCategory(categories, category) : undefined;
  // Активная вкладка верхнего уровня и её подкатегории
  const topCategory = parent ?? category;
  const subcategories = topCategory ? childCategories(categories, topCategory.id) : [];

  function updateParams(changes: Record<string, string>) {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    next.delete("page");
    setSearchParams(next, { replace: true });
  }

  function resetFilters() {
    const next = new URLSearchParams(searchParams);
    for (const key of [...FILTER_KEYS, "q", "page"]) next.delete(key);
    setSearchParams(next, { replace: true });
  }

  // Товары текущей категории — основа и для фильтров, и для списка
  const categoryIds = category ? categoryWithChildrenIds(categories, category.id) : null;
  const inCategory = categoryIds
    ? products.filter((product) =>
        product.categoryIds.some((id) => categoryIds.includes(id)),
      )
    : products;

  const lumber = inCategory.filter((product) => product.dimensions);
  const dimensionOptions = {
    t: uniqueSorted(lumber.map((product) => product.dimensions?.thickness)),
    w: uniqueSorted(lumber.map((product) => product.dimensions?.width)),
    l: uniqueSorted(lumber.map((product) => product.dimensions?.length)),
  };
  const hasCubeProducts = inCategory.some(sellsByCube);

  const tokens = searchTokens(search);
  const scores = new Map(
    inCategory.map((product) => [
      product.id,
      matchScore(tokens, {
        title: product.name,
        extra: [
          product.description,
          ...product.categoryNames,
          ...product.variants.map((variant) => variant.name),
        ],
      }),
    ]),
  );
  let filtered = inCategory.filter((product) => {
    if (!scores.get(product.id)) return false;
    if (minPrice && product.price < minPrice) return false;
    if (maxPrice && product.price > maxPrice) return false;
    if (onlyInStock && product.stockQuantity <= 0) return false;
    if (onlyCubes && !sellsByCube(product)) return false;
    if (thickness && product.dimensions?.thickness !== thickness) return false;
    if (width && product.dimensions?.width !== width) return false;
    if (length && product.dimensions?.length !== length) return false;
    return true;
  });

  // По запросу сначала то, что совпало в названии
  if (tokens.length > 0 && sort === "popular") {
    filtered = [...filtered].sort((a, b) => (scores.get(b.id) ?? 0) - (scores.get(a.id) ?? 0));
  }
  if (sort === "cheap") filtered = [...filtered].sort((a, b) => a.price - b.price);
  if (sort === "expensive") filtered = [...filtered].sort((a, b) => b.price - a.price);
  if (sort === "name") {
    filtered = [...filtered].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }

  const activeFilters =
    FILTER_KEYS.filter((key) => searchParams.get(key)).length + (search ? 1 : 0);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  if (categoryId && !loading && !category) {
    return (
      <section className="catalog-section page-section">
        <div className="container empty-results">
          <Package size={30} />
          <h3>Такой категории нет</h3>
          <p>Возможно, её переименовали или удалили.</p>
          <Link to="/catalog" className="button button-dark">
            Весь каталог
          </Link>
        </div>
      </section>
    );
  }

  const title =
    category?.name ?? (categoryId && loading ? "Загрузка" : "Каталог материалов");
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? "category-tab active" : "category-tab";

  return (
    <section className="catalog-section page-section">
      <div className="container">
        <nav className="breadcrumbs" aria-label="Навигация">
          <Link to="/">Главная</Link>
          <ChevronRight size={14} />
          {category ? (
            <>
              <Link to="/catalog">Каталог</Link>
              {parent && (
                <>
                  <ChevronRight size={14} />
                  <Link to={`/catalog/${parent.id}`}>{parent.name}</Link>
                </>
              )}
              <ChevronRight size={14} />
              <span>{category.name}</span>
            </>
          ) : (
            <span>Каталог</span>
          )}
        </nav>

        <div className="section-heading">
          <div>
            <span className="eyebrow">
              {parent ? parent.name.toUpperCase() : category ? "КАТЕГОРИЯ" : "ВЫБИРАЙТЕ СВОЁ"}
            </span>
            <h2>
              {title}
              <span>.</span>
            </h2>
            <p>
              {loading
                ? "Загружаем товары…"
                : `${filtered.length} ${pluralize(filtered.length, ["позиция", "позиции", "позиций"])}`}
              {search && ` по запросу «${search}»`}
              {/* Рисунки, а не фото товара: упаковка условная (закон о защите прав потребителей, ст. 10) */}
              {!loading && " · изображения товаров — иллюстрации"}
            </p>
          </div>
        </div>

        <div className="category-tabs catalog-top-tabs">
          <NavLink to="/catalog" end className={tabClass}>
            Все товары
          </NavLink>
          {topLevelCategories(categories).map((item) => (
            <NavLink
              key={item.id}
              to={`/catalog/${item.id}`}
              className={() =>
                tabClass({ isActive: topCategory?.id === item.id })
              }
            >
              {item.name}
            </NavLink>
          ))}
        </div>

        {topCategory && subcategories.length > 0 && (
          <div className="subcategory-chips">
            <NavLink to={`/catalog/${topCategory.id}`} end className="subcategory-chip">
              Все {topCategory.name.toLowerCase()}
            </NavLink>
            {subcategories.map((item) => (
              <NavLink key={item.id} to={`/catalog/${item.id}`} className="subcategory-chip">
                {item.name}
              </NavLink>
            ))}
          </div>
        )}

        <div className="catalog-layout">
          <aside className={`catalog-filters ${filtersOpen ? "is-open" : ""}`}>
            <div className="catalog-filters-heading">
              <strong>Фильтры</strong>
              {activeFilters > 0 && (
                <button type="button" onClick={resetFilters}>
                  Сбросить ({activeFilters})
                </button>
              )}
            </div>

            <div className="filter-group">
              <span className="filter-label">Цена, ₽</span>
              <div className="filter-range">
                <input
                  type="number"
                  min={0}
                  placeholder="от"
                  value={searchParams.get("min") ?? ""}
                  onChange={(event) => updateParams({ min: event.target.value })}
                />
                <input
                  type="number"
                  min={0}
                  placeholder="до"
                  value={searchParams.get("max") ?? ""}
                  onChange={(event) => updateParams({ max: event.target.value })}
                />
              </div>
              <small className="filter-note">По цене основного варианта</small>
            </div>

            <div className="filter-group">
              <label className="filter-check">
                <input
                  type="checkbox"
                  checked={onlyInStock}
                  onChange={(event) => updateParams({ stock: event.target.checked ? "1" : "" })}
                />
                Только в наличии
              </label>
              {hasCubeProducts && (
                <label className="filter-check">
                  <input
                    type="checkbox"
                    checked={onlyCubes}
                    onChange={(event) => updateParams({ cube: event.target.checked ? "1" : "" })}
                  />
                  Продаётся кубами
                </label>
              )}
            </div>

            {lumber.length > 0 && (
              <div className="filter-group">
                <span className="filter-label">Размеры доски, мм</span>
                {(
                  [
                    ["t", "Толщина"],
                    ["w", "Ширина"],
                    ["l", "Длина"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="filter-select">
                    <span>{label}</span>
                    <select
                      value={searchParams.get(key) ?? ""}
                      onChange={(event) => updateParams({ [key]: event.target.value })}
                    >
                      <option value="">Любая</option>
                      {dimensionOptions[key].map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            )}
          </aside>

          <div className="catalog-results">
            <div className="catalog-tools">
              <button
                type="button"
                className="filters-toggle"
                onClick={() => setFiltersOpen(!filtersOpen)}
              >
                <SlidersHorizontal size={16} />
                Фильтры{activeFilters > 0 && ` (${activeFilters})`}
              </button>

              <label className="search-box">
                <Search size={18} />
                <input
                  type="search"
                  placeholder="Найти в этом разделе..."
                  value={search}
                  onChange={(event) => updateParams({ q: event.target.value })}
                />
                {search && (
                  <button
                    className="clear-search"
                    onClick={() => updateParams({ q: "" })}
                    aria-label="Очистить поиск"
                  >
                    <X size={15} />
                  </button>
                )}
              </label>

              <label className="sort-box">
                <select
                  value={sort}
                  onChange={(event) => updateParams({ sort: event.target.value })}
                  aria-label="Сортировка товаров"
                >
                  <option value="popular">По популярности</option>
                  <option value="cheap">Сначала дешевле</option>
                  <option value="expensive">Сначала дороже</option>
                  <option value="name">По названию</option>
                </select>
                <ChevronDown size={15} />
              </label>
            </div>

            {loading ? (
              <div className="empty-results">
                <Package size={30} />
                <h3>Загружаем каталог</h3>
                <p>Получаем товары и категории с сервера.</p>
              </div>
            ) : loadError ? (
              <div className="empty-results">
                <Package size={30} />
                <h3>Не удалось загрузить товары</h3>
                <p>{loadError}</p>
                <button
                  className="button button-dark"
                  onClick={() => window.location.reload()}
                >
                  Повторить
                </button>
              </div>
            ) : pageItems.length > 0 ? (
              <>
                <div className="product-grid">
                  {pageItems.map((product, index) => (
                    <ProductCard key={product.id} product={product} priority={index < 3} />
                  ))}
                </div>

                {pageCount > 1 && (
                  <nav className="pagination" aria-label="Страницы каталога">
                    {Array.from({ length: pageCount }, (_, index) => index + 1).map(
                      (number) => (
                        <button
                          key={number}
                          className={number === currentPage ? "active" : ""}
                          aria-current={number === currentPage ? "page" : undefined}
                          onClick={() => {
                            const next = new URLSearchParams(searchParams);
                            if (number === 1) next.delete("page");
                            else next.set("page", String(number));
                            setSearchParams(next);
                            window.scrollTo({ top: 0, behavior: "smooth" });
                          }}
                        >
                          {number}
                        </button>
                      ),
                    )}
                  </nav>
                )}
              </>
            ) : (
              <div className="empty-results">
                <Search size={30} />
                <h3>Ничего не найдено</h3>
                <p>Попробуйте изменить запрос, фильтры или выбрать другую категорию.</p>
                <SearchSuggestions query={search} />
                <button className="button button-dark" onClick={resetFilters}>
                  Сбросить фильтры
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
