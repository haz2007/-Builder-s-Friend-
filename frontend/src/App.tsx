import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Clock3,
  Heart,
  Menu,
  Minus,
  Package,
  Plus,
  Search,
  ShieldCheck,
  ShoppingCart,
  Truck,
  UserRound,
  X,
  RefreshCw,
  LogOut,
  ClipboardList,
  MapPin,
} from "lucide-react";
import {
  getProducts,
  getCategories,
  registerUser,
  loginUser,
  createOrder,
  getImageUrl,
  getCurrentUser,
  getMyOrders,
  cancelOrder,
} from "./api";
import type { ApiProduct, ApiCategory, ApiOrder } from "./api";
import "./App.css";

type Product = {
  id: number;
  name: string;
  category: string;
  categoryId: number;
  description: string;
  price: number;
  unit: string;
  stockQuantity: number;
  image: string;
  badge?: string;
};

type Customer = {
  id: number;
  phone: string;
  role: string;
};

const TOKEN_KEY = "wood_commerce_token";

const productImages = [
  "https://images.unsplash.com/photo-1513467655676-561b7d489a88?auto=format&fit=crop&w=900&q=85",
  "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=900&q=85",
  "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=85",
  "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=900&q=85",
];

const orderStatusLabels: Record<string, string> = {
  NEW: "Новый",
  CONFIRMED: "Подтверждён",
  PREPARING: "Готовится к выдаче",
  READY_FOR_DELIVERY: "Готов к доставке",
  ASSIGNED_TO_DRIVER: "Назначен водитель",
  ON_THE_WAY: "В пути",
  DELIVERED: "Доставлен",
  CANCELLED: "Отменён",
};

function formatPrice(price: number) {
  return new Intl.NumberFormat("ru-RU").format(price) + " ₽";
}

function formatDate(date: string) {
  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return date;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsedDate);
}

function getStatusLabel(status: string) {
  return orderStatusLabels[status] ?? status;
}

function mapProducts(
  apiProducts: ApiProduct[],
  apiCategories: ApiCategory[],
): Product[] {
  return apiProducts.map((product, index) => {
    const category = apiCategories.find(
      (item) => item.id === product.category_id,
    );

    return {
      id: product.id,
      name: product.name,
      category: category?.name ?? "Без категории",
      categoryId: product.category_id,
      description: product.description || "Описание пока не добавлено",
      price: product.price,
      unit: product.unit,
      stockQuantity: product.stock_quantity,
      image:
        getImageUrl(product.image_url) ??
        productImages[index % productImages.length],
    };
  });
}

function getProductWord(count: number) {
  const lastTwo = count % 100;
  const last = count % 10;

  if (lastTwo >= 11 && lastTwo <= 14) return "товаров";
  if (last === 1) return "товар";
  if (last >= 2 && last <= 4) return "товара";

  return "товаров";
}

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [apiCategories, setApiCategories] = useState<ApiCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [activeCategory, setActiveCategory] = useState("Все товары");
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<Record<number, number>>({});
  const [favorites, setFavorites] = useState<number[]>([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sort, setSort] = useState("popular");

  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");
  const [checkoutSuccess, setCheckoutSuccess] = useState<number | null>(null);

  // Личный кабинет покупателя
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountMode, setAccountMode] = useState<"login" | "orders">("login");
  const [accountPhone, setAccountPhone] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState("");
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState("");
  const [cancelLoadingId, setCancelLoadingId] = useState<number | null>(null);
  const [accountNotice, setAccountNotice] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCatalog() {
      setLoading(true);
      setLoadError("");

      try {
        const [loadedProducts, loadedCategories] = await Promise.all([
          getProducts(),
          getCategories(),
        ]);

        if (cancelled) return;

        setApiCategories(loadedCategories);
        setProducts(mapProducts(loadedProducts, loadedCategories));
      } catch (error) {
        if (cancelled) return;

        console.error("Не удалось загрузить каталог:", error);
        setLoadError(
          "Не удалось загрузить каталог. Проверь, запущен ли сервер FastAPI, и попробуй ещё раз.",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCatalog();

    return () => {
      cancelled = true;
    };
  }, []);

  // Проверяем, остался ли пользователь авторизованным после обновления страницы.
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const token = localStorage.getItem(TOKEN_KEY);

      if (!token) return;

      try {
        const user = await getCurrentUser(token);

        if (cancelled) return;

        if (user.role !== "CUSTOMER") {
          localStorage.removeItem(TOKEN_KEY);
          return;
        }

        setCustomer({
          id: user.id,
          phone: user.phone ?? "",
          role: user.role,
        });

        setAccountPhone(user.phone ?? "");
      } catch {
        if (!cancelled) {
          localStorage.removeItem(TOKEN_KEY);
          setCustomer(null);
        }
      }
    }

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  const categories = useMemo(
    () => ["Все товары", ...apiCategories.map((category) => category.name)],
    [apiCategories],
  );

  const filteredProducts = useMemo(() => {
    let result = products.filter((product) => {
      const matchesCategory =
        activeCategory === "Все товары" ||
        product.category === activeCategory;

      const matchesSearch = (
        product.name +
        " " +
        product.description +
        " " +
        product.category
      )
        .toLowerCase()
        .includes(search.toLowerCase());

      return matchesCategory && matchesSearch;
    });

    if (sort === "cheap") {
      result = [...result].sort((a, b) => a.price - b.price);
    }

    if (sort === "expensive") {
      result = [...result].sort((a, b) => b.price - a.price);
    }

    return result;
  }, [products, activeCategory, search, sort]);

  const cartCount = Object.values(cart).reduce(
    (total, quantity) => total + quantity,
    0,
  );

  const cartTotal = products.reduce(
    (total, product) => total + product.price * (cart[product.id] || 0),
    0,
  );

  function changeQuantity(id: number, amount: number) {
    const product = products.find((item) => item.id === id);

    if (!product) return;

    setCart((current) => {
      const next = { ...current };
      const quantity = (next[id] || 0) + amount;

      if (quantity <= 0) {
        delete next[id];
      } else if (quantity <= product.stockQuantity) {
        next[id] = quantity;
      }

      return next;
    });
  }

  function toggleFavorite(id: number) {
    setFavorites((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }

  async function refreshOrders(token?: string) {
    const activeToken = token ?? localStorage.getItem(TOKEN_KEY);

    if (!activeToken) {
      setOrders([]);
      return;
    }

    setOrdersLoading(true);
    setOrdersError("");

    try {
      const loadedOrders = await getMyOrders(activeToken);
      setOrders(loadedOrders);
    } catch (error) {
      setOrdersError(
        error instanceof Error
          ? error.message
          : "Не удалось загрузить заказы. Попробуй ещё раз.",
      );
    } finally {
      setOrdersLoading(false);
    }
  }

  useEffect(() => {
    if (!accountOpen || accountMode !== "orders" || !customer) {
      return;
    }

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;

    const intervalId = window.setInterval(() => {
      void refreshOrders(token);
    }, 15000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [accountOpen, accountMode, customer]);

  async function handleAccountLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAccountError("");
    setAccountNotice("");
    setAccountLoading(true);

    try {
      const auth = await loginUser({
        phone: accountPhone.trim(),
        password: accountPassword,
      });

      const user = await getCurrentUser(auth.access_token);

      if (user.role !== "CUSTOMER") {
        throw new Error(
          "Этот раздел предназначен для покупателей. Войди через аккаунт покупателя.",
        );
      }

      localStorage.setItem(TOKEN_KEY, auth.access_token);

      setCustomer({
        id: user.id,
        phone: user.phone ?? accountPhone.trim(),
        role: user.role,
      });

      setAccountPassword("");
      setAccountMode("orders");

      await refreshOrders(auth.access_token);
    } catch (error) {
      setAccountError(
        error instanceof Error
          ? error.message
          : "Не удалось войти. Проверь телефон и пароль.",
      );
    } finally {
      setAccountLoading(false);
    }
  }

  async function openAccount() {
    setCartOpen(false);
    setCheckoutOpen(false);
    setAccountOpen(true);
    setAccountError("");
    setOrdersError("");
    setAccountNotice("");

    const token = localStorage.getItem(TOKEN_KEY);

    if (token && customer) {
      setAccountMode("orders");
      await refreshOrders(token);
    } else {
      setAccountMode("login");
    }
  }

  function logoutCustomer() {
    localStorage.removeItem(TOKEN_KEY);
    setCustomer(null);
    setOrders([]);
    setAccountMode("login");
    setAccountError("");
    setAccountNotice("Ты вышел из аккаунта.");
  }

  async function handleCancelOrder(orderId: number) {
    const token = localStorage.getItem(TOKEN_KEY);

    if (!token) {
      setAccountError("Войди в аккаунт, чтобы отменить заказ.");
      return;
    }

    const confirmed = window.confirm(
      `Отменить заказ №${orderId}? Это действие нельзя будет отменить.`,
    );

    if (!confirmed) return;

    setCancelLoadingId(orderId);
    setAccountError("");
    setAccountNotice("");

    try {
      await cancelOrder(orderId, token);
      await refreshOrders(token);
      setAccountNotice(`Заказ №${orderId} отменён.`);
    } catch (error) {
      setAccountError(
        error instanceof Error
          ? error.message
          : "Не удалось отменить заказ.",
      );
    } finally {
      setCancelLoadingId(null);
    }
  }

  async function handleCheckout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCheckoutError("");
    setCheckoutSuccess(null);

    if (cartCount === 0) {
      setCheckoutError("Корзина пуста.");
      return;
    }

    if (customerName.trim().length < 2) {
      setCheckoutError("Укажи, как к тебе обращаться (не менее 2 символов).");
      return;
    }

    if (deliveryAddress.trim().length < 5) {
      setCheckoutError("Укажи адрес доставки — не менее 5 символов.");
      return;
    }

    if (!phone.trim() || !password) {
      setCheckoutError("Заполни номер телефона и пароль.");
      return;
    }

    setCheckoutLoading(true);

    try {
      if (authMode === "register") {
        await registerUser({
          phone: phone.trim(),
          password,
        });
      }

      const auth = await loginUser({
        phone: phone.trim(),
        password,
      });

      const user = await getCurrentUser(auth.access_token);

      if (user.role !== "CUSTOMER") {
        throw new Error("Оформить заказ можно только с аккаунта покупателя.");
      }

      const order = await createOrder(
        {
          customer_name: customerName.trim(),
          items: products
            .filter((product) => (cart[product.id] || 0) > 0)
            .map((product) => ({
              product_id: product.id,
              quantity: cart[product.id],
            })),
          delivery_address: deliveryAddress.trim(),
        },
        auth.access_token,
      );

      localStorage.setItem(TOKEN_KEY, auth.access_token);

      setCustomer({
        id: user.id,
        phone: user.phone ?? phone.trim(),
        role: user.role,
      });

      setAccountPhone(user.phone ?? phone.trim());
      setCheckoutSuccess(order.id);
      setCart({});

      setProducts((current) =>
        current.map((product) => {
          const orderedItem = order.items.find(
            (item) => item.product_id === product.id,
          );

          return orderedItem
            ? {
                ...product,
                stockQuantity: Math.max(
                  0,
                  product.stockQuantity - orderedItem.quantity,
                ),
              }
            : product;
        }),
      );

      setPassword("");
    } catch (error) {
      setCheckoutError(
        error instanceof Error
          ? error.message
          : "Не удалось оформить заказ. Попробуй ещё раз.",
      );
    } finally {
      setCheckoutLoading(false);
    }
  }

  function openCheckout() {
    setCartOpen(false);
    setCheckoutOpen(true);
    setCheckoutError("");
    setCheckoutSuccess(null);
  }

  return (
    <div className="site-shell">
      <div className="topbar">
        <div className="container topbar-inner">
          <span>
            <span className="status-dot" />
            Работаем ежедневно, без выходных
          </span>

          <div className="topbar-right">
            <span>30 лет на рынке пиломатериалов</span>
            <a href="#contacts">Контакты</a>
          </div>
        </div>
      </div>

      <header className="header">
        <div className="container header-inner">
          <a href="#" className="brand">
            <span className="brand-mark">
              <Package size={25} strokeWidth={1.8} />
            </span>

            <span className="brand-copy">
              <strong>ДРУГ СТРОИТЕЛЯ</strong>
              <small>МАТЕРИАЛЫ ДЛЯ СТРОИТЕЛЬСТВА</small>
            </span>
          </a>

          <nav className={`main-nav ${mobileMenuOpen ? "nav-open" : ""}`}>
            <a href="#catalog" onClick={() => setMobileMenuOpen(false)}>
              Каталог
            </a>
            <a href="#advantages" onClick={() => setMobileMenuOpen(false)}>
              О магазине
            </a>
            <a href="#delivery" onClick={() => setMobileMenuOpen(false)}>
              Доставка
            </a>
            <a href="#contacts" onClick={() => setMobileMenuOpen(false)}>
              Контакты
            </a>
          </nav>

          <div className="header-actions">
            <button
              className="header-icon mobile-menu-button"
              aria-label="Открыть меню"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X size={21} /> : <Menu size={21} />}
            </button>

            <button
              className="cart-button"
              onClick={openAccount}
              title="Личный кабинет"
            >
              <UserRound size={19} />
              <span>{customer ? "Мои заказы" : "Войти"}</span>
            </button>

            <button
              className="cart-button"
              onClick={() => setCartOpen(true)}
            >
              <ShoppingCart size={19} />
              <span>Корзина</span>
              <span className="cart-count">{cartCount}</span>
            </button>
          </div>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-photo" />
          <div className="hero-shade" />

          <div className="container hero-content">
            <div className="hero-label">
              <span />
              НАДЁЖНАЯ ОСНОВА ВАШЕГО ПРОЕКТА
            </div>

            <h1>
              Хороший материал.
              <br />
              <span>Крепкий результат.</span>
            </h1>

            <p>
              Пиломатериалы для дома, стройки и отделки.
              <br />
              Выбирайте нужное — остальное мы поможем организовать.
            </p>

            <div className="hero-actions">
              <a href="#catalog" className="button button-primary">
                Смотреть каталог <ArrowRight size={18} />
              </a>

              <a href="#advantages" className="hero-secondary">
                Почему мы <ArrowRight size={17} />
              </a>
            </div>

            <div className="hero-trust">
              <div className="trust-avatars">
                <span>Д</span>
                <span>С</span>
                <span>М</span>
              </div>

              <div>
                <strong>30 лет на рынке</strong>
                <small>Опыт, проверенный временем</small>
              </div>
            </div>
          </div>

          <div className="hero-side-note">
            <span>01 / 03</span>
            <span className="hero-side-line" />
            <span>НАТУРАЛЬНОЕ ДЕРЕВО</span>
          </div>
        </section>

        <section className="benefits-strip" id="advantages">
          <div className="container benefits-grid">
            <div className="benefit">
              <span className="benefit-icon">
                <ShieldCheck size={22} />
              </span>
              <div>
                <strong>Проверенные материалы</strong>
                <small>Внимание к качеству каждой партии</small>
              </div>
            </div>

            <div className="benefit">
              <span className="benefit-icon">
                <Truck size={22} />
              </span>
              <div>
                <strong>Доставка на объект</strong>
                <small>Согласуем удобные условия</small>
              </div>
            </div>

            <div className="benefit">
              <span className="benefit-icon">
                <Clock3 size={22} />
              </span>
              <div>
                <strong>Быстрый расчёт</strong>
                <small>Поможем подобрать объём</small>
              </div>
            </div>

            <div className="benefit">
              <span className="benefit-icon">
                <Check size={22} />
              </span>
              <div>
                <strong>Понятные цены</strong>
                <small>Стоимость указана в каталоге</small>
              </div>
            </div>
          </div>
        </section>

        <section className="catalog-section" id="catalog">
          <div className="container">
            <div className="section-heading">
              <div>
                <span className="eyebrow">ВЫБИРАЙТЕ СВОЁ</span>
                <h2>
                  Каталог материалов<span>.</span>
                </h2>
                <p>
                  Всё необходимое для строительства и отделки в одном месте.
                </p>
              </div>

              <div className="catalog-count">
                <strong>
                  {filteredProducts.length.toString().padStart(2, "0")}
                </strong>
                <span>ПОЗИЦИЙ В КАТАЛОГЕ</span>
              </div>
            </div>

            <div className="catalog-toolbar">
              <div className="category-tabs">
                {categories.map((category) => (
                  <button
                    key={category}
                    className={
                      activeCategory === category
                        ? "category-tab active"
                        : "category-tab"
                    }
                    onClick={() => setActiveCategory(category)}
                  >
                    {category}
                  </button>
                ))}
              </div>

              <div className="catalog-tools">
                <label className="search-box">
                  <Search size={18} />

                  <input
                    type="search"
                    placeholder="Найти материал..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />

                  {search && (
                    <button
                      className="clear-search"
                      onClick={() => setSearch("")}
                      aria-label="Очистить поиск"
                    >
                      <X size={15} />
                    </button>
                  )}
                </label>

                <label className="sort-box">
                  <select
                    value={sort}
                    onChange={(event) => setSort(event.target.value)}
                    aria-label="Сортировка товаров"
                  >
                    <option value="popular">По популярности</option>
                    <option value="cheap">Сначала дешевле</option>
                    <option value="expensive">Сначала дороже</option>
                  </select>
                  <ChevronDown size={15} />
                </label>
              </div>
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
            ) : filteredProducts.length > 0 ? (
              <div className="product-grid">
                {filteredProducts.map((product, index) => (
                  <article className="product-card" key={product.id}>
                    <div className="product-image-wrap">
                      <img
                        className="product-image"
                        src={product.image}
                        alt={product.name}
                        loading="lazy"
                      />

                      {product.badge && (
                        <span className="product-badge">{product.badge}</span>
                      )}

                      <button
                        className={`favorite-button ${
                          favorites.includes(product.id) ? "is-favorite" : ""
                        }`}
                        aria-label={
                          favorites.includes(product.id)
                            ? "Убрать из избранного"
                            : "Добавить в избранное"
                        }
                        onClick={() => toggleFavorite(product.id)}
                      >
                        <Heart
                          size={18}
                          fill={
                            favorites.includes(product.id)
                              ? "currentColor"
                              : "none"
                          }
                        />
                      </button>

                      <span className="product-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </div>

                    <div className="product-info">
                      <span className="product-category">
                        {product.category}
                      </span>
                      <h3>{product.name}</h3>
                      <p>{product.description}</p>

                      <div
                        className={`product-stock ${
                          product.stockQuantity > 0 ? "is-available" : "is-unavailable"
                        }`}
                      >
                        <span className="product-stock-dot" />
                        {product.stockQuantity > 0
                          ? `В наличии: ${product.stockQuantity} ${product.unit}`
                          : "Нет в наличии"}
                      </div>

                      <div className="product-bottom">
                        <div className="product-price">
                          <strong>{formatPrice(product.price)}</strong>
                          <small>/ {product.unit}</small>
                        </div>

                        {cart[product.id] ? (
                          <div className="quantity-control">
                            <button
                              onClick={() => changeQuantity(product.id, -1)}
                              aria-label="Уменьшить количество"
                            >
                              <Minus size={15} />
                            </button>
                            <span>{cart[product.id]}</span>
                            <button
                              onClick={() => changeQuantity(product.id, 1)}
                              disabled={
                                cart[product.id] >= product.stockQuantity
                              }
                              aria-label="Увеличить количество"
                            >
                              <Plus size={15} />
                            </button>
                          </div>
                        ) : (
                          <button
                            className="add-button"
                            onClick={() => changeQuantity(product.id, 1)}
                            disabled={product.stockQuantity < 1}
                            aria-label={`Добавить ${product.name} в корзину`}
                          >
                            <Plus size={19} />
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-results">
                <Search size={30} />
                <h3>Ничего не найдено</h3>
                <p>
                  Попробуйте изменить запрос или выбрать другую категорию.
                </p>
                <button
                  className="button button-dark"
                  onClick={() => {
                    setSearch("");
                    setActiveCategory("Все товары");
                  }}
                >
                  Сбросить фильтры
                </button>
              </div>
            )}

            <div className="catalog-footer">
              <span>
                Цены и наличие уточняются при оформлении заказа.
              </span>
              <a href="#contacts">
                Нужна помощь с выбором? <ArrowRight size={16} />
              </a>
            </div>
          </div>
        </section>

        <section className="delivery-section" id="delivery">
          <div className="container delivery-panel">
            <div className="delivery-copy">
              <span className="eyebrow">ОТ ЗАКАЗА ДО ОБЪЕКТА</span>
              <h2>
                Строить проще,
                <br />
                когда всё <span>под рукой.</span>
              </h2>
              <p>
                Расскажите, что нужно для вашего проекта. Поможем с подбором
                материалов, количеством и организацией доставки.
              </p>
              <button
                className="button button-primary"
                onClick={() => {
                  if (cartCount > 0) {
                    openCheckout();
                  } else {
                    document.getElementById("catalog")?.scrollIntoView({
                      behavior: "smooth",
                    });
                  }
                }}
              >
                {cartCount > 0 ? "Оформить заказ" : "Выбрать материалы"}{" "}
                <ArrowRight size={18} />
              </button>
            </div>

            <div className="delivery-visual">
              <img
                src="https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=1100&q=85"
                alt="Строительные материалы на объекте"
                loading="lazy"
              />
              <div className="delivery-stamp">
                <Truck size={24} />
                <strong>ДОСТАВКА</strong>
                <span>По договорённости</span>
              </div>
            </div>
          </div>
        </section>

        <section className="contact-section" id="contacts">
          <div className="container contact-inner">
            <div>
              <span className="eyebrow">ЕСТЬ ВОПРОСЫ?</span>
              <h2>Давайте обсудим ваш проект.</h2>
              <p>
                Свяжитесь с нами, чтобы уточнить наличие, цены и условия
                доставки.
              </p>
            </div>

            <button
              className="button button-light"
              onClick={() => {
                if (cartCount > 0) {
                  openCheckout();
                } else {
                  document.getElementById("catalog")?.scrollIntoView({
                    behavior: "smooth",
                  });
                }
              }}
            >
              {cartCount > 0 ? "Оформить заказ" : "Вернуться в каталог"}{" "}
              <ArrowRight size={18} />
            </button>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container footer-inner">
          <a href="#" className="brand footer-brand">
            <span className="brand-mark">
              <Package size={23} />
            </span>
            <span className="brand-copy">
              <strong>ДРУГ СТРОИТЕЛЯ</strong>
              <small>МАТЕРИАЛЫ ДЛЯ СТРОИТЕЛЬСТВА</small>
            </span>
          </a>

          <span className="footer-note">
            Материалы для хороших проектов.
          </span>
          <span className="copyright">© 2026 Друг Строителя</span>
        </div>
      </footer>

      {cartCount > 0 && !cartOpen && !checkoutOpen && !accountOpen && (
        <div className="sticky-cart-bar">
          <button
            className="sticky-cart-main"
            onClick={() => setCartOpen(true)}
            aria-label={`Открыть корзину, сумма ${formatPrice(cartTotal)}`}
          >
            <span className="sticky-cart-icon">
              <ShoppingCart size={21} />
              <span>{cartCount}</span>
            </span>

            <span className="sticky-cart-copy">
              <strong>
                {cartCount} {getProductWord(cartCount)}
              </strong>
              <small>Открыть корзину</small>
            </span>

            <span className="sticky-cart-action">
              <span className="sticky-cart-total">{formatPrice(cartTotal)}</span>
              <span className="sticky-cart-action-label">В корзину</span>
              <ArrowRight size={18} aria-hidden="true" />
            </span>
          </button>
        </div>
      )}

      {cartOpen && (
        <div className="cart-overlay" onClick={() => setCartOpen(false)}>
          <aside
            className="cart-drawer"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="cart-header">
              <div>
                <span className="eyebrow">ВАШ ВЫБОР</span>
                <h2>Корзина ({cartCount})</h2>
              </div>

              <button
                className="close-cart"
                onClick={() => setCartOpen(false)}
                aria-label="Закрыть корзину"
              >
                <X size={22} />
              </button>
            </div>

            {cartCount === 0 ? (
              <div className="cart-empty">
                <ShoppingCart size={36} />
                <h3>Пока здесь пусто</h3>
                <p>Добавьте товары из каталога, чтобы собрать заказ.</p>
                <button
                  className="button button-dark"
                  onClick={() => setCartOpen(false)}
                >
                  Перейти в каталог
                </button>
              </div>
            ) : (
              <>
                <div className="cart-items">
                  {products
                    .filter((product) => cart[product.id])
                    .map((product) => (
                      <div className="cart-item" key={product.id}>
                        <img src={product.image} alt={product.name} />

                        <div className="cart-item-info">
                          <strong>{product.name}</strong>
                          <small>
                            {formatPrice(product.price)} / {product.unit}
                          </small>

                          <div className="quantity-control">
                            <button
                              onClick={() => changeQuantity(product.id, -1)}
                              aria-label="Уменьшить количество"
                            >
                              <Minus size={14} />
                            </button>
                            <span>{cart[product.id]}</span>
                            <button
                              onClick={() => changeQuantity(product.id, 1)}
                              disabled={
                                cart[product.id] >= product.stockQuantity
                              }
                              aria-label="Увеличить количество"
                            >
                              <Plus size={14} />
                            </button>
                          </div>
                        </div>

                        <strong className="cart-item-total">
                          {formatPrice(product.price * cart[product.id])}
                        </strong>
                      </div>
                    ))}
                </div>

                <div className="cart-summary">
                  <div>
                    <span>Предварительная сумма</span>
                    <strong>{formatPrice(cartTotal)}</strong>
                  </div>

                  <p>
                    Итоговую стоимость и доставку подтвердим при согласовании
                    заказа.
                  </p>

                  <button
                    className="button button-primary checkout-button"
                    onClick={openCheckout}
                  >
                    Оформить заказ <ArrowRight size={18} />
                  </button>
                </div>
              </>
            )}
          </aside>
        </div>
      )}

      {checkoutOpen && (
        <div
          className="cart-overlay checkout-overlay"
          onClick={() => {
            if (!checkoutLoading) setCheckoutOpen(false);
          }}
        >
          <section
            className="checkout-panel"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="cart-header">
              <div>
                <span className="eyebrow">ДРУГ СТРОИТЕЛЯ</span>
                <h2>
                  {checkoutSuccess !== null
                    ? "Заказ оформлен"
                    : "Оформление заказа"}
                </h2>
              </div>

              <button
                className="close-cart"
                onClick={() => setCheckoutOpen(false)}
                disabled={checkoutLoading}
                aria-label="Закрыть оформление"
              >
                <X size={22} />
              </button>
            </div>

            {checkoutSuccess !== null ? (
              <div className="checkout-success">
                <span className="checkout-success-icon">
                  <Check size={32} />
                </span>
                <h3>Спасибо за заказ!</h3>
                <p>
                  Номер заказа: <strong>#{checkoutSuccess}</strong>
                </p>
                <p>
                  Заказ сохранён. Его статус можно отслеживать в разделе «Мои
                  заказы».
                </p>
                <button
                  className="button button-primary checkout-button"
                  onClick={() => {
                    setCheckoutOpen(false);
                    void openAccount();
                  }}
                >
                  Перейти к моим заказам
                </button>
                <button
                  className="button button-dark checkout-button"
                  onClick={() => setCheckoutOpen(false)}
                >
                  Продолжить покупки
                </button>
              </div>
            ) : (
              <form className="checkout-form" onSubmit={handleCheckout}>
                <p className="checkout-description">
                  Войди в аккаунт или создай новый, чтобы отправить заказ.
                </p>

                <div className="auth-tabs">
                  <button
                    type="button"
                    className={
                      authMode === "login" ? "auth-tab active" : "auth-tab"
                    }
                    onClick={() => {
                      setAuthMode("login");
                      setCheckoutError("");
                    }}
                  >
                    Войти
                  </button>
                  <button
                    type="button"
                    className={
                      authMode === "register"
                        ? "auth-tab active"
                        : "auth-tab"
                    }
                    onClick={() => {
                      setAuthMode("register");
                      setCheckoutError("");
                    }}
                  >
                    Регистрация
                  </button>
                </div>

                <label className="checkout-field">
                  <span>Номер телефона</span>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    placeholder="+7 999 123-45-67"
                    autoComplete="tel"
                    maxLength={30}
                    required
                  />
                </label>

                <label className="checkout-field">
                  <span>Пароль</span>
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Введите пароль"
                    autoComplete={
                      authMode === "register"
                        ? "new-password"
                        : "current-password"
                    }
                    minLength={1}
                    required
                  />
                </label>

                <label className="checkout-field">
                  <span>Как к вам обращаться?</span>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(event) => setCustomerName(event.target.value)}
                    placeholder="Ваше имя"
                    autoComplete="name"
                    minLength={2}
                    maxLength={100}
                    required
                  />
                </label>

                <label className="checkout-field">
                  <span>Адрес доставки</span>
                  <textarea
                    value={deliveryAddress}
                    onChange={(event) =>
                      setDeliveryAddress(event.target.value)
                    }
                    placeholder="Город, улица, дом, дополнительные ориентиры"
                    minLength={5}
                    maxLength={500}
                    rows={3}
                    required
                  />
                </label>

                <div className="checkout-order-summary">
                  <span>Товаров в заказе: {cartCount}</span>
                  <strong>{formatPrice(cartTotal)}</strong>
                </div>

                {checkoutError && (
                  <p className="checkout-error" role="alert">
                    {checkoutError}
                  </p>
                )}

                <button
                  className="button button-primary checkout-button"
                  type="submit"
                  disabled={checkoutLoading || cartCount === 0}
                >
                  {checkoutLoading
                    ? "Отправляем заказ..."
                    : authMode === "register"
                      ? "Зарегистрироваться и заказать"
                      : "Войти и оформить заказ"}
                  {!checkoutLoading && <ArrowRight size={18} />}
                </button>

                <p className="checkout-footnote">
                  Сумма будет рассчитана сервером по актуальным ценам и
                  количеству товара на складе.
                </p>
              </form>
            )}
          </section>
        </div>
      )}

      {accountOpen && (
        <div
          className="cart-overlay account-overlay"
          onClick={() => {
            if (!accountLoading && cancelLoadingId === null) {
              setAccountOpen(false);
            }
          }}
        >
          <section
            className="checkout-panel account-panel"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="cart-header">
              <div>
                <span className="eyebrow">ДРУГ СТРОИТЕЛЯ</span>
                <h2>
                  {accountMode === "orders"
                    ? "Мои заказы"
                    : "Личный кабинет"}
                </h2>
              </div>

              <button
                className="close-cart"
                onClick={() => setAccountOpen(false)}
                aria-label="Закрыть личный кабинет"
              >
                <X size={22} />
              </button>
            </div>

            {accountMode === "login" ? (
              <form className="checkout-form" onSubmit={handleAccountLogin}>
                <p className="checkout-description">
                  Войди, чтобы смотреть историю заказов и отслеживать их статус.
                </p>

                <label className="checkout-field">
                  <span>Номер телефона</span>
                  <input
                    type="tel"
                    value={accountPhone}
                    onChange={(event) => setAccountPhone(event.target.value)}
                    placeholder="+7 999 123-45-67"
                    autoComplete="tel"
                    maxLength={30}
                    required
                  />
                </label>

                <label className="checkout-field">
                  <span>Пароль</span>
                  <input
                    type="password"
                    value={accountPassword}
                    onChange={(event) => setAccountPassword(event.target.value)}
                    placeholder="Введите пароль"
                    autoComplete="current-password"
                    required
                  />
                </label>

                {accountError && (
                  <p className="checkout-error" role="alert">
                    {accountError}
                  </p>
                )}

                {accountNotice && (
                  <p className="account-notice">{accountNotice}</p>
                )}

                <button
                  className="button button-primary checkout-button"
                  type="submit"
                  disabled={accountLoading}
                >
                  {accountLoading ? "Входим..." : "Войти в аккаунт"}
                  {!accountLoading && <ArrowRight size={18} />}
                </button>

                <p className="checkout-footnote">
                  Ещё нет аккаунта? Создай его при оформлении первого заказа.
                </p>
              </form>
            ) : (
              <div className="account-orders">
                <div className="account-profile">
                  <span className="account-profile-icon">
                    <UserRound size={22} />
                  </span>
                  <div>
                    <strong>{customer?.phone || "Покупатель"}</strong>
                    <small>Аккаунт покупателя</small>
                  </div>
                  <button
                    className="account-logout"
                    onClick={logoutCustomer}
                    title="Выйти из аккаунта"
                  >
                    <LogOut size={17} />
                    <span>Выйти</span>
                  </button>
                </div>

                <div className="account-orders-heading">
                  <div>
                    <h3>История заказов</h3>
                    <p>Здесь можно проверить состояние каждого заказа.</p>
                  </div>
                  <button
                    className="account-refresh"
                    onClick={() => void refreshOrders()}
                    disabled={ordersLoading}
                    title="Обновить список заказов"
                  >
                    <RefreshCw
                      size={17}
                      className={ordersLoading ? "refresh-spinning" : ""}
                    />
                  </button>
                </div>

                {accountError && (
                  <p className="checkout-error" role="alert">
                    {accountError}
                  </p>
                )}

                {accountNotice && (
                  <p className="account-notice">{accountNotice}</p>
                )}

                {ordersError && (
                  <p className="checkout-error" role="alert">
                    {ordersError}
                  </p>
                )}

                {ordersLoading && orders.length === 0 ? (
                  <div className="account-empty">
                    <RefreshCw size={26} className="refresh-spinning" />
                    <p>Загружаем заказы...</p>
                  </div>
                ) : orders.length === 0 ? (
                  <div className="account-empty">
                    <ClipboardList size={34} />
                    <h3>Заказов пока нет</h3>
                    <p>
                      Когда ты оформишь заказ, он появится в этом разделе.
                    </p>
                    <button
                      className="button button-primary checkout-button"
                      onClick={() => {
                        setAccountOpen(false);
                        document.getElementById("catalog")?.scrollIntoView({
                          behavior: "smooth",
                        });
                      }}
                    >
                      Перейти в каталог
                    </button>
                  </div>
                ) : (
                  <div className="account-order-list">
                    {orders.map((order) => (
                      <article className="account-order-card" key={order.id}>
                        <div className="account-order-top">
                          <div>
                            <span className="account-order-number">
                              Заказ №{order.id}
                            </span>
                            <span
                              className={`order-status status-${order.status.toLowerCase()}`}
                            >
                              {getStatusLabel(order.status)}
                            </span>
                          </div>
                          <strong>{formatPrice(order.total_price)}</strong>
                        </div>

                        <div className="account-order-address">
                          <MapPin size={15} />
                          <span>{order.delivery_address}</span>
                        </div>

                        <div className="account-order-items">
                          {order.items.map((item) => {
                            const product = products.find(
                              (candidate) => candidate.id === item.product_id,
                            );

                            return (
                              <div
                                className="account-order-item"
                                key={item.id}
                              >
                                <span>
                                  {product?.name ?? `Товар №${item.product_id}`}
                                  {" × "}
                                  {item.quantity}
                                </span>
                                <strong>
                                  {formatPrice(item.price * item.quantity)}
                                </strong>
                              </div>
                            );
                          })}
                        </div>

                        <div className="order-history">
                          <strong className="order-history-title">
                            <Clock3 size={15} />
                            История статусов
                          </strong>

                          {order.status_history.length > 0 ? (
                            <ol>
                              {order.status_history.map((history) => (
                                <li key={history.id}>
                                  <span className="history-dot" />
                                  <div>
                                    <strong>
                                      {getStatusLabel(history.status)}
                                    </strong>
                                    <small>
                                      {formatDate(history.created_at)}
                                    </small>
                                  </div>
                                </li>
                              ))}
                            </ol>
                          ) : (
                            <p className="order-history-empty">
                              История пока не заполнена.
                            </p>
                          )}
                        </div>

                        {order.status === "NEW" && (
                          <button
                            className="cancel-order-button"
                            onClick={() => void handleCancelOrder(order.id)}
                            disabled={cancelLoadingId === order.id}
                          >
                            {cancelLoadingId === order.id
                              ? "Отменяем заказ..."
                              : "Отменить заказ"}
                          </button>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
