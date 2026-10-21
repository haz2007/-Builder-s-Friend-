import { useEffect, useState } from "react";
import { Navigate, NavLink, useNavigate, useParams } from "react-router-dom";

import { getAdminOrders, getAdminProducts, getCategories, getCurrentUser, getNewOrdersCount } from "./api";
import type { ApiCategory, ApiOrder, ApiProduct, AuthUser } from "./api";

import "./Admin.css";
import ActivitySection from "./ActivitySection";
import AdminsSection from "./AdminsSection";
import { Icon } from "./AdminIcons";
import AnalyticsSection from "./AnalyticsSection";
import CategoriesSection from "./CategoriesSection";
import { LogoMark } from "./components/Logo";
import OrdersSection from "./OrdersSection";
import ProductsSection from "./ProductsSection";

// Тот же токен, что у сайта: отдельного входа в админку нет — админ входит
// на сайте, и «Личный кабинет» ведёт его сюда
const TOKEN_KEY = "wood_commerce_token";

const ADMIN_SECTIONS = [
  // short — подпись в нижней панели на телефоне
  { key: "analytics", label: "Обзор", short: "Обзор", icon: "📊" },
  { key: "orders", label: "Заказы", short: "Заказы", icon: "📦" },
  { key: "products", label: "Товары", short: "Товары", icon: "🪵" },
  { key: "categories", label: "Категории", short: "Разделы", icon: "🗂" },
  { key: "activity", label: "Журнал", short: "Журнал", icon: "🕓" },
  { key: "admins", label: "Администраторы", short: "Админы", icon: "👥" },
];

function Admin() {
  // Раздел берётся из адреса: /admin/orders, /admin/products …
  const params = useParams();
  const section = ADMIN_SECTIONS.some((item) => item.key === params["*"])
    ? (params["*"] as string)
    : "analytics";

  const navigate = useNavigate();
  const [token] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");

  const [user, setUser] = useState<AuthUser | null>(null);

  const [products, setProducts] = useState<ApiProduct[]>([]);

  const [categories, setCategories] = useState<ApiCategory[]>([]);

  const [orders, setOrders] = useState<ApiOrder[]>([]);

  const [orderFilter, setOrderFilter] = useState("ALL");

  const [error, setError] = useState("");

  const [notice, setNotice] = useState("");

  const [newOrdersCount, setNewOrdersCount] = useState(0);

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
        // Не админ или сессия истекла — обратно на сайт, там и войти
        if (!cancelled) {
          console.error("Нет доступа к панели:", err);
          navigate("/", { replace: true, state: { openLogin: true } });
        }
      }
    }

    void verifySession();

    return () => {
      cancelled = true;
    };
  }, [token, navigate]);

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

  function logout() {
    // Выход общий с сайтом: токен один. Страница уходит на главную целиком,
    // поэтому состояние панели чистить не нужно
    localStorage.removeItem(TOKEN_KEY);
    window.location.assign("/");
  }

  if (!token) {
    // Не вошли — на главную, где сразу откроется окно входа
    return <Navigate to="/" replace state={{ openLogin: true }} />;
  }

  if (!user) {
    return (
      // Пока проверяем вход — только спокойный экран загрузки, без формы
      <main className="admin-page admin-page-loading" aria-busy="true">
        <LogoMark size={44} />
        <p>Открываем панель управления…</p>
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
            <LogoMark size={40} />
            <span className="admin-eyebrow">ПАНЕЛЬ УПРАВЛЕНИЯ</span>
            <h1>Управление магазином</h1>
            <p>Вы вошли как {user.phone ?? user.email ?? "Администратор"}</p>
          </div>
          <aside className="admin-header-summary">
            <span className="admin-eyebrow">СВОДКА</span>
            <strong>Новые заказы: {newOrdersCount}</strong>
            <p>Счётчик и список заказов обновляются каждые 15 секунд.</p>
          </aside>
          <button className="admin-btn admin-btn-ghost admin-logout" onClick={logout}>
            <Icon name="logout" />
            Выйти
          </button>
        </header>
        <div className="admin-layout">
        <nav className="admin-sidebar" aria-label="Разделы админки">
          {ADMIN_SECTIONS.map((item) => (
            <NavLink
              key={item.key}
              to={`/admin/${item.key}`}
              className={({ isActive }) =>
                isActive || (item.key === "analytics" && section === "analytics")
                  ? "admin-nav-link active"
                  : "admin-nav-link"
              }
            >
              <span className="admin-nav-icon">{item.icon}</span>
              <span className="admin-nav-label">{item.label}</span>
              <span className="admin-nav-short">{item.short}</span>
              {item.key === "orders" && newOrdersCount > 0 && (
                <em className="admin-nav-badge">{newOrdersCount}</em>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="admin-content">
        {error && <p className="admin-error">{error}</p>}

        {notice && <p className="admin-notice">{notice}</p>}
                
        {section === "analytics" && (
          <AnalyticsSection token={token} onSelectStatus={setOrderFilter} />
        )}

        {section === "orders" && (
          <OrdersSection
            token={token}
            onError={setError}
            onNotice={setNotice}
            orders={orders}
            products={products}
            onOrdersChange={setOrders}
            onNewOrdersCount={setNewOrdersCount}
            orderFilter={orderFilter}
            onOrderFilterChange={setOrderFilter}
          />
        )}

        {section === "categories" && (
          <CategoriesSection
            token={token}
            onError={setError}
            onNotice={setNotice}
            categories={categories}
            products={products}
            onReload={() => loadData(token)}
          />
        )}

        {section === "products" && (
          <ProductsSection
            token={token}
            onError={setError}
            onNotice={setNotice}
            categories={categories}
            products={products}
            onProductsChange={setProducts}
            onReload={() => loadData(token)}
          />
        )}

        {section === "activity" && <ActivitySection token={token} onError={setError} />}

        {section === "admins" && (
          <AdminsSection
            token={token}
            user={user}
            onError={setError}
            onNotice={setNotice}
          />
        )}
        </div>
        </div>
      </div>
    </main>
  );
}

export default Admin;
