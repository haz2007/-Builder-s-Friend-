import { useEffect, useRef, useState, type FormEvent } from "react";

import {

  loginUser,

  getCurrentUser,

  getCategories,

  getAdminProducts,

  createProduct,

  updateProduct,

  deactivateProduct,

  deleteProduct,

  restoreProduct,

  createCategory,

  updateCategory,

  deleteCategory,

  uploadProductImage,

  getImageUrl,

  getNewOrdersCount,

  getAdminOrders,

  updateOrderStatus,
  getAdminAnalytics,

} from "./api";

import type { ApiCategory, ApiOrder, ApiProduct, AuthUser, AdminAnalytics, AdminAnalyticsPeriod } from "./api";

import "./Admin.css";

const TOKEN_KEY = "wood_admin_token";

type ProductForm = {

  name: string;

  description: string;

  price: string;

  stock_quantity: string;

  unit: string;

  category_id: string;

};

const emptyForm: ProductForm = {

  name: "",

  description: "",

  price: "",

  stock_quantity: "0",

  unit: "шт.",

  category_id: "",

};

const orderStatuses = [

  { value: "NEW", label: "Новый" },

  { value: "CONFIRMED", label: "Подтверждён" },

  { value: "PREPARING", label: "Готовится" },

  { value: "READY_FOR_DELIVERY", label: "Готов к доставке" },

  { value: "ASSIGNED_TO_DRIVER", label: "Назначен курьер" },

  { value: "ON_THE_WAY", label: "В пути" },

  { value: "DELIVERED", label: "Доставлен" },

  { value: "CANCELLED", label: "Отменён" },

];

function orderStatusLabel(status: string) {

  return orderStatuses.find((item) => item.value === status)?.label ?? status;

}

function Admin() {

  const [token, setToken] = useState(

    () => sessionStorage.getItem(TOKEN_KEY) ?? "",

  );

  const [user, setUser] = useState<AuthUser | null>(null);

  const [products, setProducts] = useState<ApiProduct[]>([]);

  const [categories, setCategories] = useState<ApiCategory[]>([]);

  const [orders, setOrders] = useState<ApiOrder[]>([]);

  const [login, setLogin] = useState("");

  const [password, setPassword] = useState("");

  const [form, setForm] = useState<ProductForm>(emptyForm);

  const [editingId, setEditingId] = useState<number | null>(null);

  const [search, setSearch] = useState("");
  const [productCategoryFilter, setProductCategoryFilter] = useState("ALL");
  const [productStockFilter, setProductStockFilter] = useState("ALL");

  const [loading, setLoading] = useState(false);

  const [ordersLoading, setOrdersLoading] = useState(false);

  const [updatingOrderId, setUpdatingOrderId] = useState<number | null>(null);

  const [orderFilter, setOrderFilter] = useState("ALL");

  const [error, setError] = useState("");

  const [notice, setNotice] = useState("");

  const [newOrdersCount, setNewOrdersCount] = useState(0);

  const [categoryName, setCategoryName] = useState("");

  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(

    null,

  );

  const [uploadingProductId, setUploadingProductId] = useState<number | null>(

    null,

  );

  const [selectedFiles, setSelectedFiles] = useState<

    Record<number, File | null>

  >({});

  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});

  const productFormRef = useRef<HTMLElement | null>(null);
  const [analyticsPeriod, setAnalyticsPeriod] = useState<AdminAnalyticsPeriod>("30d");
  const [analyticsFrom, setAnalyticsFrom] = useState("");
  const [analyticsTo, setAnalyticsTo] = useState("");
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState("");

  async function loadOrders(currentToken = token) {

    if (!currentToken) return;

    setOrdersLoading(true);

    try {

      const loadedOrders = await getAdminOrders(currentToken);

      setOrders(loadedOrders);

    } catch (err) {

      setError(

        err instanceof Error ? err.message : "Не удалось загрузить заказы.",

      );

    } finally {

      setOrdersLoading(false);

    }

  }

  async function loadData(currentToken: string) {

    const currentUser = await getCurrentUser(currentToken);

    if (currentUser.role !== "ADMIN") {

      throw new Error("У этого аккаунта нет прав администратора.");

    }

    const [loadedProducts, loadedCategories, loadedOrders] =

      await Promise.all([

        getAdminProducts(currentToken),

        getCategories(),

        getAdminOrders(currentToken),

      ]);

    setUser(currentUser);

    setProducts(loadedProducts);

    setCategories(loadedCategories);

    setOrders(loadedOrders);

  }

  useEffect(() => {

    if (!token) {

      setUser(null);

      return;

    }

    let cancelled = false;

    async function verifySession() {

      try {

        await loadData(token);

      } catch (err) {

        if (!cancelled) {

          sessionStorage.removeItem(TOKEN_KEY);

          setToken("");

          setUser(null);

          setError(

            err instanceof Error

              ? err.message

              : "Не удалось проверить доступ.",

          );

        }

      }

    }

    void verifySession();

    return () => {

      cancelled = true;

    };

  }, [token]);

  useEffect(() => {

    if (!token || !user) return;

    let cancelled = false;

    async function refreshData() {

      try {

        const count = await getNewOrdersCount(token);

        if (!cancelled) setNewOrdersCount(count);

      } catch (err) {

        if (!cancelled) {

          console.error("Не удалось обновить счётчик заказов:", err);

        }

      }

      try {

        const loadedOrders = await getAdminOrders(token);

        if (!cancelled) setOrders(loadedOrders);

      } catch (err) {

        if (!cancelled) {

          console.error("Не удалось обновить список заказов:", err);

        }

      }

    }

    void refreshData();

    const intervalId = window.setInterval(() => {

      void refreshData();

    }, 15000);

    return () => {

      cancelled = true;

      window.clearInterval(intervalId);

    };

  }, [token, user]);

  useEffect(() => {
    if (!token || !user) return;
    if (analyticsPeriod === "custom" && (!analyticsFrom || !analyticsTo)) {
      setAnalytics(null);
      setAnalyticsError("Выбери обе даты для произвольного периода.");
      return;
    }
    if (analyticsPeriod === "custom" && analyticsFrom > analyticsTo) {
      setAnalytics(null);
      setAnalyticsError("Дата начала не может быть позже даты окончания.");
      return;
    }
    let cancelled = false;
    setAnalyticsLoading(true);
    setAnalyticsError("");
    getAdminAnalytics(token, analyticsPeriod, analyticsFrom, analyticsTo)
      .then((data) => { if (!cancelled) setAnalytics(data); })
      .catch((err) => {
        if (!cancelled) setAnalyticsError(err instanceof Error ? err.message : "Не удалось загрузить аналитику.");
      })
      .finally(() => { if (!cancelled) setAnalyticsLoading(false); });
    return () => { cancelled = true; };
  }, [token, user, analyticsPeriod, analyticsFrom, analyticsTo]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    setLoading(true);

    setError("");

    setNotice("");

    try {

      const identifier = login.trim();
      const auth = await loginUser({
        ...(identifier.includes("@")
          ? { email: identifier }
          : { phone: identifier }),
        password,
      });

      await loadData(auth.access_token);

      sessionStorage.setItem(TOKEN_KEY, auth.access_token);

      setToken(auth.access_token);

      setPassword("");

    } catch (err) {

      setError(

        err instanceof Error ? err.message : "Не удалось войти в панель.",

      );

    } finally {

      setLoading(false);

    }

  }

  function logout() {

    sessionStorage.removeItem(TOKEN_KEY);

    setToken("");

    setUser(null);

    setProducts([]);

    setCategories([]);

    setOrders([]);

    setNewOrdersCount(0);

    setError("");

    setNotice("");

  }

  function resetForm() {

    setForm(emptyForm);

    setEditingId(null);

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

    };

    try {

      if (editingId === null) {

        await createProduct(data, token);

        setNotice("Товар добавлен.");

      } else {

        await updateProduct(editingId, data, token);

        setNotice("Изменения сохранены.");

      }

      resetForm();

      await loadData(token);

    } catch (err) {

      setError(

        err instanceof Error ? err.message : "Не удалось сохранить товар.",

      );

    } finally {

      setLoading(false);

    }

  }

  async function handleUploadImage(productId: number) {

    if (!token) return;

    const file = selectedFiles[productId];

    if (!file) {

      setError("Сначала выбери фотографию.");

      return;

    }

    if (file.size > 5 * 1024 * 1024) {

      setError("Размер фотографии не должен превышать 5 МБ.");

      return;

    }

    setUploadingProductId(productId);

    setError("");

    setNotice("");

    try {

      await uploadProductImage(productId, file, token);

      setSelectedFiles((previous) => ({

        ...previous,

        [productId]: null,

      }));

      const input = fileInputRefs.current[productId];

      if (input) input.value = "";

      await loadData(token);

      setNotice("Фотография загружена.");

    } catch (err) {

      setError(

        err instanceof Error

          ? err.message

          : "Не удалось загрузить фотографию.",

      );

    } finally {

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

      await loadData(token);

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
      await loadData(token);
      setNotice(`Товар «${product.name}» удалён.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить товар.");
    } finally {
      setLoading(false);
    }
  }

  function startEditingCategory(category: ApiCategory) {

    setEditingCategoryId(category.id);

    setCategoryName(category.name);

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
      await loadData(token);
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

        await createCategory({ name }, token);

        setNotice("Категория добавлена.");

      } else {

        await updateCategory(editingCategoryId, { name }, token);

        setNotice("Название категории изменено.");

      }

      resetCategoryForm();

      await loadData(token);

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

  async function handleOrderStatusChange(

    orderId: number,

    status: string,

  ) {

    if (!token) return;

    setUpdatingOrderId(orderId);

    setError("");

    setNotice("");

    try {

      await updateOrderStatus(orderId, status, token);

      await loadOrders(token);

      const count = await getNewOrdersCount(token);

      setNewOrdersCount(count);

      setNotice(`Статус заказа №${orderId} обновлён.`);

    } catch (err) {

      setError(

        err instanceof Error

          ? err.message

          : "Не удалось изменить статус заказа.",

      );

    } finally {

      setUpdatingOrderId(null);

    }

  }


  const visibleOrders = orders.filter(

    (order) => orderFilter === "ALL" || order.status === orderFilter,

  );

  const visibleProducts = products.filter((product) => {
    const matchesSearch = `${product.name} ${product.description ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase().trim());
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

  if (!user) {

    return (

      <main className="admin-page">

        <form className="admin-login" onSubmit={handleLogin}>

          <a className="admin-back" href="/">

            ← Вернуться в магазин

          </a>

          <span className="admin-eyebrow">ДРУГ СТРОИТЕЛЯ</span>

          <h1>Вход для администратора</h1>

          <p>Войди с аккаунтом, которому назначена роль ADMIN.</p>

          <label>

            Почта или номер телефона

            <input

              type="text"

              value={login}

              onChange={(event) => setLogin(event.target.value)}

              autoComplete="username"

              placeholder="admin@example.com или +79991234567"

              required

            />

          </label>

          <label>

            Пароль

            <input

              type="password"

              value={password}

              onChange={(event) => setPassword(event.target.value)}

              autoComplete="current-password"

              required

            />

          </label>

          {error && <p className="admin-error">{error}</p>}

          <button className="admin-primary" disabled={loading}>

            {loading ? "Проверяем доступ..." : "Войти"}

          </button>

        </form>

      </main>

    );

  }

  return (

    <main className="admin-page">

      <div className="admin-container">

        <header className="admin-header">

          <div className="admin-header-main">

            <a className="admin-back" href="/">

              ← Открыть магазин

            </a>

            <span className="admin-eyebrow">ПАНЕЛЬ УПРАВЛЕНИЯ</span>

            <h1>Управление магазином</h1>

            <p>Вы вошли как {user.phone ?? user.email ?? "Администратор"}</p>

          </div>

          <aside className="admin-header-summary">

            <span className="admin-eyebrow">СВОДКА</span>

            <strong>Новые заказы: {newOrdersCount}</strong>

            <p>Счётчик и список заказов обновляются каждые 15 секунд.</p>

          </aside>

          <button className="admin-secondary admin-logout" onClick={logout}>

            Выйти

          </button>

        </header>

        {error && <p className="admin-error">{error}</p>}

        {notice && <p className="admin-notice">{notice}</p>}
                
                
        <section className="admin-card admin-statistics">
          <div className="admin-section-heading">
            <div>
              <span className="admin-eyebrow">АНАЛИТИКА</span>
              <h2>Статистика магазина</h2>
              <p>Данные рассчитываются на сервере по всем заказам за выбранный период.</p>
            </div>
            {analyticsLoading && <span>Обновляем статистику...</span>}
          </div>
          <div className="admin-analytics-controls">
            <label>Период
              <select value={analyticsPeriod} onChange={(event) => setAnalyticsPeriod(event.target.value as AdminAnalyticsPeriod)}>
                <option value="7d">Последние 7 дней</option>
                <option value="30d">Последние 30 дней</option>
                <option value="90d">Последние 90 дней</option>
                <option value="all">За всё время</option>
                <option value="custom">Выбрать даты</option>
              </select>
            </label>
            {analyticsPeriod === "custom" && <>
              <label>С даты<input type="date" value={analyticsFrom} onChange={(event) => setAnalyticsFrom(event.target.value)} /></label>
              <label>По дату<input type="date" value={analyticsTo} onChange={(event) => setAnalyticsTo(event.target.value)} /></label>
            </>}
          </div>
          {analyticsError && <p className="admin-error">{analyticsError}</p>}
          {analytics && <>
            <div className="admin-stats-grid">
              <article className="admin-stat-card admin-stat-primary"><span>Сумма неотменённых заказов</span><strong>{analytics.revenue.not_cancelled.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</strong><small>Включая ещё не доставленные</small></article>
              <article className="admin-stat-card"><span>Фактическая выручка</span><strong>{analytics.revenue.delivered.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</strong><small>Только доставленные заказы</small></article>
              <article className="admin-stat-card"><span>Всего заказов</span><strong>{analytics.orders.total}</strong><small>Отменено: {analytics.orders.cancelled}</small></article>
              <article className="admin-stat-card"><span>Средний чек</span><strong>{analytics.average_order_value.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</strong><small>Без отменённых заказов</small></article>
              <article className="admin-stat-card"><span>Доставлено</span><strong>{analytics.orders.delivered}</strong><small>Конверсия: {analytics.delivery_conversion_rate.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%</small></article>
            </div>
            <div className="admin-statistics-columns">
              <div className="admin-stat-panel">
                <h3>Динамика заказов и выручки</h3>
                {analytics.trend.length === 0 ? <p className="admin-empty">За выбранный период заказов нет.</p> : <div className="admin-analytics-trend">
                  {analytics.trend.map((day) => {
                    const maxRevenue = Math.max(1, ...analytics.trend.map((item) => item.revenue));
                    const maxOrders = Math.max(1, ...analytics.trend.map((item) => item.orders));
                    return <div className="admin-analytics-day" key={day.date} title={`${day.date}: ${day.orders} заказов, ${day.revenue.toLocaleString("ru-RU")} ₽`}>
                      <span className="admin-analytics-bars">
                        <span className="admin-analytics-revenue-bar" style={{ height: `${Math.max(day.revenue > 0 ? 3 : 0, day.revenue / maxRevenue * 100)}%` }} />
                        <span className="admin-analytics-orders-bar" style={{ height: `${Math.max(day.orders > 0 ? 3 : 0, day.orders / maxOrders * 100)}%` }} />
                      </span><small>{day.date.slice(5)}</small>
                    </div>;
                  })}
                </div>}
                <p className="admin-analytics-legend"><span className="admin-analytics-legend-revenue" /> Выручка (без отмен) <span className="admin-analytics-legend-orders" /> Количество заказов</p>
              </div>
              <div className="admin-stat-panel">
                <h3>Популярные товары</h3>
                {analytics.top_products.length === 0 ? <p className="admin-empty">Нет продаж за выбранный период.</p> : <div className="admin-popular-products">
                  {analytics.top_products.map((product, index) => <div className="admin-popular-product" key={product.product_id}>
                    <span className="admin-popular-rank">{index + 1}</span><div className="admin-popular-product-info"><strong>{product.name}</strong><span>Продано: {product.quantity} · {product.revenue.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</span></div>
                  </div>)}
                </div>}
              </div>
            </div>
            <div className="admin-stat-panel admin-low-stock-panel">
              <h3>Низкий остаток (10 или меньше)</h3>
              {analytics.low_stock_products.length === 0 ? <p className="admin-empty">Нет товаров с низким остатком.</p> : <div className="admin-low-stock-list">
                {analytics.low_stock_products.map((product) => <div className="admin-low-stock-item" key={product.id}><strong>{product.name}</strong><span>{product.stock_quantity} {product.unit}</span></div>)}
              </div>}
            </div>
          </>}
        </section>


        <section className="admin-card">

          <div className="admin-list-heading">

            <div>

              <h2>Заказы покупателей</h2>

              <p>Всего заказов: {orders.length}</p>

            </div>

            <div className="admin-row-actions">

              <select

                value={orderFilter}

                onChange={(event) => setOrderFilter(event.target.value)}

                aria-label="Фильтр заказов по статусу"

              >

                <option value="ALL">Все заказы</option>

                {orderStatuses.map((status) => (

                  <option key={status.value} value={status.value}>

                    {status.label}

                  </option>

                ))}

              </select>

              <button

                type="button"

                className="admin-secondary"

                disabled={ordersLoading}

                onClick={() => void loadOrders()}

              >

                {ordersLoading ? "Обновляем..." : "Обновить"}

              </button>

            </div>

          </div>

          {ordersLoading && orders.length === 0 ? (

            <p>Загружаем заказы...</p>

          ) : visibleOrders.length === 0 ? (

            <p>Заказов с таким статусом пока нет.</p>

          ) : (

            <div className="admin-order-list">

              {visibleOrders.map((order) => (

                <article className="admin-order-card" key={order.id}>

                  <div className="admin-order-heading">

                    <div>

                      <h3>Заказ №{order.id}</h3>

                      <span className={`admin-status admin-status-${order.status.toLowerCase()}`}>

                        {orderStatusLabel(order.status)}

                      </span>

                      {order.status === "CANCELLED" ? (
                        <div className="admin-order-cancelled-track">
                          <span className="admin-order-cancelled-dot" />
                          <span>Заказ отменён</span>
                        </div>
                      ) : (
                        <div className="admin-order-progress" aria-label={`Этап заказа: ${orderStatusLabel(order.status)}`}>
                          <div className="admin-order-progress-line">
                            <span
                              className="admin-order-progress-line-fill"
                              style={{
                                width: `${(Math.max(0, orderStatuses.filter((item) => item.value !== "CANCELLED").findIndex((item) => item.value === order.status)) / (orderStatuses.filter((item) => item.value !== "CANCELLED").length - 1)) * 100}%`,
                              }}
                            />
                          </div>
                          {orderStatuses
                            .filter((item) => item.value !== "CANCELLED")
                            .map((status, index, stages) => {
                              const currentIndex = stages.findIndex((item) => item.value === order.status);
                              const state = index < currentIndex ? "done" : index === currentIndex ? "current" : "upcoming";
                              return (
                                <div className={`admin-order-progress-step ${state}`} key={status.value}>
                                  <span className="admin-order-progress-dot">{index < currentIndex ? "✓" : ""}</span>
                                  <span className="admin-order-progress-label">{status.label}</span>
                                </div>
                              );
                            })}
                        </div>
                      )}

                    </div>

                    <strong>

                      {Number(order.total_price).toLocaleString("ru-RU")} ₽

                    </strong>

                  </div>

                  <p>
                    <strong>Покупатель:</strong>{" "}
                    {order.customer_name || "Имя не указано"}
                    {" · "}
                    {order.customer_phone || "Телефон не указан"}
                  </p>

                  <p>
                    <strong>Адрес доставки:</strong>{" "}
                    {order.delivery_address || "Не указан"}
                  </p>

                  <div>

                    <strong>Состав заказа</strong>

                    <div className="admin-order-items">

                      {order.items.map((item) => {

                        const product = products.find(

                          (entry) => entry.id === item.product_id,

                        );

                        return (

                          <div className="admin-order-item" key={item.id}>

                            <span>

                              {product?.name ?? `Товар №${item.product_id}`} ×{" "}

                              {item.quantity}

                            </span>

                            <span>

                              {(

                                Number(item.price) * item.quantity

                              ).toLocaleString("ru-RU")}{" "}

                              ₽

                            </span>

                          </div>

                        );

                      })}

                    </div>

                  </div>

                  <div className="admin-order-status-control">

                    <label>

                      Изменить статус

                      <select

                        value={order.status}

                        disabled={updatingOrderId === order.id}

                        onChange={(event) =>

                          void handleOrderStatusChange(

                            order.id,

                            event.target.value,

                          )

                        }

                      >

                        {orderStatuses.map((status) => (

                          <option key={status.value} value={status.value}>

                            {status.label}

                          </option>

                        ))}

                      </select>

                    </label>

                    {updatingOrderId === order.id && (

                      <span>Сохраняем статус...</span>

                    )}

                  </div>

                  {order.status_history?.length > 0 && (

                    <details className="admin-order-history">

                      <summary>История статусов</summary>

                      <ul>

                        {order.status_history.map((history) => (

                          <li key={history.id}>

                            <strong>

                              {orderStatusLabel(history.status)}

                            </strong>

                            <span>

                              {new Date(history.created_at).toLocaleString(

                                "ru-RU",

                              )}

                            </span>

                          </li>

                        ))}

                      </ul>

                    </details>

                  )}

                </article>

              ))}

            </div>

          )}

        </section>

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

            <div className="admin-form-actions admin-full">

              <button className="admin-primary" disabled={loading}>

                {loading

                  ? "Сохраняем..."

                  : editingCategoryId === null

                    ? "Добавить категорию"

                    : "Сохранить название"}

              </button>

              {editingCategoryId !== null && (

                <button

                  type="button"

                  className="admin-secondary"

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

              categories.map((category) => (

                <div className="admin-category-row" key={category.id}>

                  <div>

                    <strong>{category.name}</strong>

                    <small>ID: {category.id}</small>

                  </div>

                  <div className="admin-category-actions" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="admin-secondary"
                      disabled={loading}
                      onClick={() => startEditingCategory(category)}
                    >
                      Переименовать
                    </button>
                    <button
                      type="button"
                      className="admin-secondary"
                      disabled={loading}
                      onClick={() => handleDeleteCategory(category)}
                      style={{
                        background: "#dc2626",
                        borderColor: "#dc2626",
                        color: "#ffffff",
                      }}
                    >
                      Удалить
                    </button>
                  </div>

                </div>

              ))

            )}

          </div>

        </section>

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

                {categories.map((category) => (

                  <option key={category.id} value={category.id}>

                    {category.name}

                  </option>

                ))}

              </select>

            </label>

            <label>

              Цена, ₽

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

              Остаток

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

              <button className="admin-primary" disabled={loading}>

                {loading

                  ? "Сохраняем..."

                  : editingId === null

                    ? "Добавить товар"

                    : "Сохранить изменения"}

              </button>

              {editingId !== null && (

                <button

                  type="button"

                  className="admin-secondary"

                  onClick={resetForm}

                >

                  Отмена

                </button>

              )}

            </div>

          </form>

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
                placeholder="Поиск по названию..."
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

                    <th>Цена</th>

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

                        {product.image_url && (

                          <img

                            src={getImageUrl(product.image_url) ?? undefined}

                            alt={product.name}

                            style={{

                              display: "block",

                              width: 90,

                              height: 70,

                              objectFit: "cover",

                              borderRadius: 8,

                              marginTop: 8,

                            }}

                          />

                        )}

                        <div style={{ marginTop: 8 }}>

                          <input

                            ref={(element) => {

                              fileInputRefs.current[product.id] = element;

                            }}

                            type="file"

                            accept="image/jpeg,image/png,image/webp"

                            onChange={(event) => {

                              const file = event.target.files?.[0] ?? null;

                              if (file && file.size > 5 * 1024 * 1024) {

                                setError(

                                  "Размер фотографии не должен превышать 5 МБ.",

                                );

                                event.target.value = "";

                                return;

                              }

                              setError("");

                              setSelectedFiles((previous) => ({

                                ...previous,

                                [product.id]: file,

                              }));

                            }}

                          />

                          <button

                            type="button"

                            className="admin-secondary"

                            disabled={

                              uploadingProductId === product.id ||

                              !selectedFiles[product.id]

                            }

                            onClick={() => handleUploadImage(product.id)}

                            style={{ marginTop: 6 }}

                          >

                            {uploadingProductId === product.id

                              ? "Загружаем..."

                              : "Загрузить фото"}

                          </button>

                        </div>

                      </td>

                      <td>

                        {product.price.toLocaleString("ru-RU")} ₽ /{" "}

                        {product.unit}

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

                        <div className="admin-row-actions">

                          <button

                            className="admin-secondary"

                            onClick={() => startEditing(product)}

                          >

                            Изменить

                          </button>

                          <button

                            className="admin-secondary"

                            disabled={loading}

                            onClick={() => handleProductStatus(product)}

                          >

                            {product.is_active === 1 ? "Скрыть" : "Вернуть"}

                          </button>
                          <button
                            type="button"
                            className="admin-secondary"
                            disabled={loading}
                            onClick={() => void handleDeleteProduct(product)}
                            style={{
                              backgroundColor: "#dc2626",
                              borderColor: "#dc2626",
                              color: "#ffffff",
                            }}
                          >
                            Удалить
                          </button>

                        </div>

                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          )}

        </section>

      </div>

    </main>

  );

}

export default Admin;
