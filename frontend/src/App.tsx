import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Clock3,
  Menu,
  Minus,
  Plus,
  Search,
  ShoppingCart,
  UserRound,
  X,
  RefreshCw,
  LogOut,
  ClipboardList,
  MapPin,
  Bell,
  Truck,
  Warehouse,
  Phone,
  Star,
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
  getNotifications,
  getUnreadNotificationsCount,
  markNotificationAsRead,
  markAllNotificationsAsRead,
} from "./api";
import type { ApiProduct, ApiCategory, ApiOrder, ApiNotification } from "./api";
import "./App.css";
import Logo from "./components/Logo";
import CatalogPage from "./pages/CatalogPage";
import HomePage from "./pages/HomePage";
import ConsentPage from "./pages/ConsentPage";
import PrivacyPage from "./pages/PrivacyPage";
import ProductPage from "./pages/ProductPage";
import { PHONES, SELLER, WORKING_HOURS, YANDEX_REVIEW_URL, YEARS_ON_MARKET } from "./shop/contacts";
import { formatPrice, pluralize } from "./shop/format";
import { ShopContext } from "./shop/ShopContext";
import type {
  CartEntry,
  Product,
  ProductVariant,
  ShopContextValue,
} from "./shop/types";
import { showFallbackImage } from "./shop/images";
import { orderStatusLabel } from "./shop/orderStatus";
import ConsentCheckbox from "./components/ConsentCheckbox";

type Customer = {
  id: number;
  phone: string;
  role: string;
};

const TOKEN_KEY = "wood_commerce_token";
// Как на сервере (schemas.PASSWORD_MIN_LENGTH); для входа старых аккаунтов не проверяется
const PASSWORD_MIN_LENGTH = 8;

const productImages = [
  "https://images.unsplash.com/photo-1513467655676-561b7d489a88?auto=format&fit=crop&w=900&q=85",
  "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=900&q=85",
  "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=85",
  "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=900&q=85",
];

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


function mapProducts(
  apiProducts: ApiProduct[],
  apiCategories: ApiCategory[],
): Product[] {
  return apiProducts.map((product, index) => {
    const category = apiCategories.find(
      (item) => item.id === product.category_id,
    );

    const categoryNames = apiCategories
      .filter((item) =>
        (product.category_ids ?? [product.category_id]).includes(item.id),
      )
      .map((item) => item.name);

    const variants = (product.variants ?? [])
      .filter((variant) => variant.is_active === 1)
      .map((variant) => ({
        id: variant.id,
        name: variant.name,
        unit: variant.unit,
        price: variant.price,
        baseQuantity: variant.base_quantity ?? 1,
        stockQuantity: variant.stock_quantity,
      }));

    return {
      id: product.id,
      name: product.name,
      category: category?.name ?? "Без категории",
      categoryId: product.category_id,
      categoryIds: product.category_ids ?? [product.category_id],
      categoryNames,
      piecesPerCube: product.pieces_per_cubic_meter ?? null,
      dimensions:
        product.thickness_mm && product.width_mm && product.length_mm
          ? {
              thickness: product.thickness_mm,
              width: product.width_mm,
              length: product.length_mm,
            }
          : null,
      variants,
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

/** При переходе между страницами — наверх; ссылки вида /#delivery — к блоку. */
function ScrollManager() {
  const { pathname, hash, key } = useLocation();
  // Повторный клик по той же ссылке /#delivery — тоже прокрутка к блоку
  const hashVisit = hash ? key : "";

  useEffect(() => {
    // Обновление страницы открывает её сверху, а не там, где её листали
    window.history.scrollRestoration = "manual";
  }, []);

  useEffect(() => {
    if (hash) {
      // Ждём, пока страница отрисует нужный блок
      const timer = window.setTimeout(() => {
        document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth" });
        // Убираем #блок из адреса, чтобы при следующем заходе сайт не листался вниз
        window.history.replaceState(window.history.state, "", pathname + window.location.search);
      }, 50);
      return () => window.clearTimeout(timer);
    }
    window.scrollTo({ top: 0 });
  }, [pathname, hash, hashVisit]);

  return null;
}

/**
 * Шапка закрепляется через position: fixed, когда её пролистали.
 * Не sticky: Chrome при наборе в поле поиска внутри sticky-шапки
 * «показывает курсор» и сам листает страницу вверх.
 */
function usePinnedHeader() {
  const slotRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLElement>(null);
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    const slot = slotRef.current;
    const header = headerRef.current;
    if (!slot || !header) return;

    // Место под шапкой остаётся, даже когда она закреплена — контент не прыгает
    const keepHeight = () => {
      slot.style.height = `${header.offsetHeight}px`;
    };
    const update = () => setPinned(slot.getBoundingClientRect().top < 0);
    const resize = new ResizeObserver(keepHeight);

    keepHeight();
    update();
    resize.observe(header);
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      resize.disconnect();
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  return { slotRef, headerRef, pinned };
}

function App() {
  const { slotRef: headerSlotRef, headerRef, pinned: headerPinned } = usePinnedHeader();
  const [products, setProducts] = useState<Product[]>([]);
  const [apiCategories, setApiCategories] = useState<ApiCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Корзина: id варианта → количество
  const [cart, setCart] = useState<Record<number, number>>({});
  // Выбранный в карточке вариант: id товара → id варианта
  const [selectedVariants, setSelectedVariants] = useState<
    Record<number, number>
  >({});
  const [favorites, setFavorites] = useState<number[]>([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerSearch, setHeaderSearch] = useState("");
  const navigate = useNavigate();

  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [deliveryMethod, setDeliveryMethod] = useState<"DELIVERY" | "PICKUP">(
    "DELIVERY",
  );
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
  // «Войти» в шапке: вход или регистрация нового покупателя
  const [accountAuthMode, setAccountAuthMode] = useState<"login" | "register">("login");
  const [accountPrivacyAccepted, setAccountPrivacyAccepted] = useState(false);
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState("");
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState("");
  const [cancelLoadingId, setCancelLoadingId] = useState<number | null>(null);
  const [accountNotice, setAccountNotice] = useState("");
  const [notifications, setNotifications] = useState<ApiNotification[]>([]);
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState(0);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState("");
  const [notificationActionLoading, setNotificationActionLoading] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

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

  // Обновляем счётчик непрочитанных уведомлений в фоне.
  useEffect(() => {
    if (!customer) return;

    let cancelled = false;

    async function refreshUnreadCount() {
      const token = localStorage.getItem(TOKEN_KEY);

      if (!token) {
        setUnreadNotificationsCount(0);
        return;
      }

      try {
        const result = await getUnreadNotificationsCount(token);
        if (!cancelled) {
          setUnreadNotificationsCount(result.count);
        }
      } catch {
        // Не показываем ошибку при временном сбое фонового обновления.
      }
    }

    void refreshUnreadCount();
    const intervalId = window.setInterval(() => {
      void refreshUnreadCount();
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [customer]);

  const cartCount = Object.values(cart).reduce(
    (total, quantity) => total + quantity,
    0,
  );

  const variantIndex = useMemo(() => {
    const index = new Map<
      number,
      { product: Product; variant: ProductVariant }
    >();

    for (const product of products) {
      for (const variant of product.variants) {
        index.set(variant.id, { product, variant });
      }
    }

    return index;
  }, [products]);

  const cartEntries = useMemo(() => {
    const entries: CartEntry[] = [];

    for (const [variantId, quantity] of Object.entries(cart)) {
      const found = variantIndex.get(Number(variantId));
      if (found && quantity > 0) {
        entries.push({ ...found, quantity });
      }
    }

    return entries;
  }, [cart, variantIndex]);

  const cartTotal = cartEntries.reduce(
    (total, entry) => total + entry.variant.price * entry.quantity,
    0,
  );

  function getSelectedVariant(product: Product): ProductVariant | undefined {
    return (
      product.variants.find(
        (variant) => variant.id === selectedVariants[product.id],
      ) ?? product.variants[0]
    );
  }

  function selectVariant(productId: number, variantId: number) {
    setSelectedVariants((current) => ({ ...current, [productId]: variantId }));
  }

  // Склад у товара общий: штуки и кубы в корзине тратят один остаток
  function usedBaseUnits(
    product: Product,
    currentCart: Record<number, number>,
  ) {
    return product.variants.reduce(
      (total, variant) =>
        total + (currentCart[variant.id] || 0) * variant.baseQuantity,
      0,
    );
  }

  function canAddVariant(product: Product, variant: ProductVariant) {
    return (
      usedBaseUnits(product, cart) + variant.baseQuantity <=
      product.stockQuantity
    );
  }

  function maxAddable(product: Product, variant: ProductVariant) {
    const free = product.stockQuantity - usedBaseUnits(product, cart);
    return Math.max(0, Math.floor(free / variant.baseQuantity + 1e-9));
  }

  function changeQuantity(variantId: number, amount: number) {
    const found = variantIndex.get(variantId);

    if (!found) return;

    setCart((current) => {
      const next = { ...current };
      const quantity = (next[variantId] || 0) + amount;
      const used =
        usedBaseUnits(found.product, current) +
        amount * found.variant.baseQuantity;

      if (quantity <= 0) {
        delete next[variantId];
      } else if (amount < 0 || used <= found.product.stockQuantity) {
        next[variantId] = quantity;
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

  async function refreshNotifications(token?: string) {
    const activeToken = token ?? localStorage.getItem(TOKEN_KEY);

    if (!activeToken) {
      setNotifications([]);
      setUnreadNotificationsCount(0);
      return;
    }

    setNotificationsLoading(true);
    setNotificationsError("");

    try {
      const [loadedNotifications, unreadResult] = await Promise.all([
        getNotifications(activeToken),
        getUnreadNotificationsCount(activeToken),
      ]);
      setNotifications(loadedNotifications);
      setUnreadNotificationsCount(unreadResult.count);
    } catch (error) {
      setNotificationsError(
        error instanceof Error ? error.message : "Не удалось загрузить уведомления.",
      );
    } finally {
      setNotificationsLoading(false);
    }
  }

  async function handleMarkNotificationAsRead(notificationId: number) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;

    setNotificationActionLoading(true);
    setNotificationsError("");
    try {
      await markNotificationAsRead(notificationId, token);
      await refreshNotifications(token);
    } catch (error) {
      setNotificationsError(
        error instanceof Error ? error.message : "Не удалось отметить уведомление прочитанным.",
      );
    } finally {
      setNotificationActionLoading(false);
    }
  }

  async function handleMarkAllNotificationsAsRead() {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;

    setNotificationActionLoading(true);
    setNotificationsError("");
    try {
      await markAllNotificationsAsRead(token);
      await refreshNotifications(token);
    } catch (error) {
      setNotificationsError(
        error instanceof Error ? error.message : "Не удалось отметить уведомления прочитанными.",
      );
    } finally {
      setNotificationActionLoading(false);
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
    const registering = accountAuthMode === "register";
    if (registering && accountPassword.length < PASSWORD_MIN_LENGTH) {
      setAccountError(`Пароль — не короче ${PASSWORD_MIN_LENGTH} символов.`);
      return;
    }
    if (registering && !accountPrivacyAccepted) {
      setAccountError("Чтобы зарегистрироваться, подтвердите согласие на обработку данных.");
      return;
    }

    setAccountLoading(true);

    try {
      if (registering) {
        await registerUser({
          phone: accountPhone.trim(),
          password: accountPassword,
          privacy_accepted: true,
        });
      }

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

      await Promise.all([refreshOrders(auth.access_token), refreshNotifications(auth.access_token)]);
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
      await Promise.all([refreshOrders(token), refreshNotifications(token)]);
    } else {
      setAccountMode("login");
    }
  }

  function logoutCustomer() {
    localStorage.removeItem(TOKEN_KEY);
    setCustomer(null);
    setOrders([]);
    setNotifications([]);
    setUnreadNotificationsCount(0);
    setNotificationsError("");
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

    if (deliveryMethod === "DELIVERY" && deliveryAddress.trim().length < 5) {
      setCheckoutError("Укажи адрес доставки — не менее 5 символов.");
      return;
    }

    // Если покупатель уже вошёл через «Личный кабинет», используем его токен
    const storedToken = customer ? localStorage.getItem(TOKEN_KEY) : null;

    if (!storedToken && (!phone.trim() || !password)) {
      setCheckoutError("Заполни номер телефона и пароль.");
      return;
    }

    if (!storedToken && authMode === "register" && password.length < PASSWORD_MIN_LENGTH) {
      setCheckoutError(`Пароль — не короче ${PASSWORD_MIN_LENGTH} символов.`);
      return;
    }

    if (!storedToken && authMode === "register" && !privacyAccepted) {
      setCheckoutError("Чтобы зарегистрироваться, подтвердите согласие на обработку данных.");
      return;
    }

    setCheckoutLoading(true);

    try {
      let accessToken: string;

      if (storedToken) {
        accessToken = storedToken;
      } else {
        if (authMode === "register") {
          await registerUser({
            phone: phone.trim(),
            password,
            privacy_accepted: true,
          });
        }

        const auth = await loginUser({
          phone: phone.trim(),
          password,
        });
        accessToken = auth.access_token;
      }

      let user;
      try {
        user = await getCurrentUser(accessToken);
      } catch (error) {
        if (storedToken) {
          // Токен истёк — просим войти заново, корзину не трогаем
          localStorage.removeItem(TOKEN_KEY);
          setCustomer(null);
          throw new Error("Сессия истекла. Войди в аккаунт ещё раз.");
        }
        throw error;
      }

      if (user.role !== "CUSTOMER") {
        throw new Error("Оформить заказ можно только с аккаунта покупателя.");
      }

      const order = await createOrder(
        {
          customer_name: customerName.trim(),
          items: cartEntries.map((entry) => ({
            product_id: entry.product.id,
            variant_id: entry.variant.id,
            quantity: entry.quantity,
          })),
          delivery_method: deliveryMethod,
          delivery_address: deliveryMethod === "DELIVERY" ? deliveryAddress.trim() : "",
        },
        accessToken,
      );

      localStorage.setItem(TOKEN_KEY, accessToken);

      setCustomer({
        id: user.id,
        phone: user.phone ?? phone.trim(),
        role: user.role,
      });

      setAccountPhone(user.phone ?? phone.trim());
      setCheckoutSuccess(order.id);
      setCart({});

      // Остатки пересчитывает сервер (штуки ↔ кубы), просто перечитываем каталог
      getProducts()
        .then((loadedProducts) =>
          setProducts(mapProducts(loadedProducts, apiCategories)),
        )
        .catch(() => {
          // Каталог обновится при следующей загрузке страницы
        });

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

  const shop: ShopContextValue = {
    products,
    categories: apiCategories,
    loading,
    loadError,
    cart,
    cartCount,
    favorites,
    toggleFavorite,
    getSelectedVariant,
    selectVariant,
    changeQuantity,
    canAddVariant,
    maxAddable,
    openCart: () => setCartOpen(true),
    openCheckout,
  };

  return (
    <ShopContext.Provider value={shop}>
    <ScrollManager />
    <div className="site-shell">
      <div className="topbar">
        <div className="container topbar-inner">
          <span>
            <span className="status-dot" />
            {WORKING_HOURS}
          </span>

          <div className="topbar-right">
            <span>{YEARS_ON_MARKET} лет на рынке пиломатериалов</span>
            {PHONES.map((phone) => (
              <a key={phone.href} href={phone.href} className="topbar-phone">
                <Phone size={13} />
                {phone.display}
              </a>
            ))}
          </div>
        </div>
      </div>

      <div className="header-slot" ref={headerSlotRef}>
      <header
        className={`header ${headerPinned ? "is-pinned" : ""}`}
        ref={headerRef}
      >
        <div className="container header-inner">
          <Link to="/" className="brand" aria-label="Друг Строителя — на главную">
            <Logo />
          </Link>

          <nav className={`main-nav ${mobileMenuOpen ? "nav-open" : ""}`}>
            <NavLink to="/catalog" onClick={() => setMobileMenuOpen(false)}>
              Каталог
            </NavLink>
            <Link to="/#delivery" onClick={() => setMobileMenuOpen(false)}>
              Доставка
            </Link>
            <Link to="/#contacts" onClick={() => setMobileMenuOpen(false)}>
              Контакты
            </Link>
          </nav>

          <form
            className="header-search"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              const query = headerSearch.trim();
              navigate(query ? `/catalog?q=${encodeURIComponent(query)}` : "/catalog");
              setMobileMenuOpen(false);
            }}
          >
            <Search size={17} />
            <input
              type="search"
              placeholder="Поиск: доска, брус, саморезы…"
              value={headerSearch}
              onChange={(event) => setHeaderSearch(event.target.value)}
              aria-label="Поиск по каталогу"
            />
          </form>

          <div className="header-actions">
            <button
              className="header-icon mobile-menu-button"
              aria-label="Открыть меню"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X size={21} /> : <Menu size={21} />}
            </button>

            {customer && (
              <button
                type="button"
                className="notification-bell-button header-notification-bell"
                onClick={() => {
                  setNotificationsOpen(true);
                  void refreshNotifications();
                }}
                aria-label={`Открыть уведомления${unreadNotificationsCount ? `, непрочитанных: ${unreadNotificationsCount}` : ""}`}
                title="Уведомления"
              >
                <Bell size={21} />
                {unreadNotificationsCount > 0 && (
                  <span className="notification-bell-count">
                    {unreadNotificationsCount > 99 ? "99+" : unreadNotificationsCount}
                  </span>
                )}
              </button>
            )}

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
      </div>

      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/catalog/:categoryId" element={<CatalogPage />} />
          <Route path="/product/:productId" element={<ProductPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/consent" element={<ConsentPage />} />
          <Route path="*" element={<CatalogPage />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="container footer-inner">
          <Link to="/" className="brand footer-brand" aria-label="Друг Строителя — на главную">
            <Logo inverted />
          </Link>

          <span className="footer-note footer-phones">
            {PHONES.map((phone) => (
              <a key={phone.href} href={phone.href}>
                {phone.display}
              </a>
            ))}
          </span>
          <span className="copyright">© 2026 Друг Строителя</span>
        </div>
        {/* Реквизиты продавца — обязательны для дистанционной продажи */}
        <div className="container footer-legal">
          <span>
            {SELLER.name} · ОГРНИП {SELLER.ogrnip} · ИНН {SELLER.inn}
          </span>
          <span className="footer-legal-links">
            <Link to="/privacy">Политика конфиденциальности</Link>
            <Link to="/consent">Согласие на обработку данных</Link>
          </span>
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
                {cartCount} {pluralize(cartCount, ["товар", "товара", "товаров"])}
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
                  {cartEntries.map(({ product, variant, quantity }) => (
                    <div className="cart-item" key={variant.id}>
                      <img src={product.image} alt={product.name} onError={showFallbackImage} />

                      <div className="cart-item-info">
                        <strong>{product.name}</strong>
                        <small>
                          {product.variants.length > 1 &&
                            `${variant.name} · `}
                          {formatPrice(variant.price)} / {variant.unit}
                        </small>

                        <div className="quantity-control">
                          <button
                            onClick={() => changeQuantity(variant.id, -1)}
                            aria-label="Уменьшить количество"
                          >
                            <Minus size={14} />
                          </button>
                          <span>{quantity}</span>
                          <button
                            onClick={() => changeQuantity(variant.id, 1)}
                            disabled={!canAddVariant(product, variant)}
                            aria-label="Увеличить количество"
                          >
                            <Plus size={14} />
                          </button>
                        </div>
                      </div>

                      <strong className="cart-item-total">
                        {formatPrice(variant.price * quantity)}
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
                {customer ? (
                  <div className="checkout-account">
                    <span>
                      Заказ будет оформлен на аккаунт{" "}
                      <strong>{customer.phone}</strong>
                    </span>
                    <button
                      type="button"
                      className="checkout-account-switch"
                      onClick={logoutCustomer}
                    >
                      Сменить аккаунт
                    </button>
                  </div>
                ) : (
                  <>
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
                        placeholder={
                          authMode === "register"
                            ? `Не короче ${PASSWORD_MIN_LENGTH} символов`
                            : "Введите пароль"
                        }
                        autoComplete={
                          authMode === "register"
                            ? "new-password"
                            : "current-password"
                        }
                        minLength={authMode === "register" ? PASSWORD_MIN_LENGTH : 1}
                        required
                      />
                    </label>

                    {authMode === "register" && (
                      <ConsentCheckbox checked={privacyAccepted} onChange={setPrivacyAccepted} />
                    )}
                  </>
                )}

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

                <div className="checkout-field">
                  <span>Как получить заказ</span>
                  <div className="delivery-options" role="radiogroup">
                    {(
                      [
                        ["DELIVERY", "Доставка", "Привезём на объект своим транспортом"],
                        ["PICKUP", "Самовывоз", "Заберёте сами — на своей или нанятой машине"],
                      ] as const
                    ).map(([value, title, hint]) => (
                      <button
                        key={value}
                        type="button"
                        role="radio"
                        aria-checked={deliveryMethod === value}
                        className={`delivery-option ${deliveryMethod === value ? "is-selected" : ""}`}
                        onClick={() => setDeliveryMethod(value)}
                      >
                        {value === "DELIVERY" ? <Truck size={18} /> : <Warehouse size={18} />}
                        <strong>{title}</strong>
                        <small>{hint}</small>
                      </button>
                    ))}
                  </div>
                </div>

                {deliveryMethod === "DELIVERY" ? (
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
                ) : (
                  <p className="checkout-pickup-note">
                    После подтверждения заказа мы позвоним и скажем, когда
                    подъехать. Телефоны: {PHONES.map((phone) => phone.display).join(", ")}.
                  </p>
                )}

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
                    : customer
                      ? "Оформить заказ"
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
                  {accountAuthMode === "login"
                    ? "Войди, чтобы смотреть историю заказов и отслеживать их статус."
                    : "Создай аккаунт по номеру телефона — заказы и их статусы будут здесь и в Telegram-боте."}
                </p>

                <div className="auth-tabs">
                  <button
                    type="button"
                    className={accountAuthMode === "login" ? "auth-tab active" : "auth-tab"}
                    onClick={() => {
                      setAccountAuthMode("login");
                      setAccountError("");
                    }}
                  >
                    Войти
                  </button>
                  <button
                    type="button"
                    className={accountAuthMode === "register" ? "auth-tab active" : "auth-tab"}
                    onClick={() => {
                      setAccountAuthMode("register");
                      setAccountError("");
                    }}
                  >
                    Регистрация
                  </button>
                </div>

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
                    placeholder={
                      accountAuthMode === "register"
                        ? `Не короче ${PASSWORD_MIN_LENGTH} символов`
                        : "Введите пароль"
                    }
                    autoComplete={accountAuthMode === "register" ? "new-password" : "current-password"}
                    minLength={accountAuthMode === "register" ? PASSWORD_MIN_LENGTH : 1}
                    required
                  />
                </label>

                {accountAuthMode === "register" && (
                  <ConsentCheckbox checked={accountPrivacyAccepted} onChange={setAccountPrivacyAccepted} />
                )}

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
                  {accountLoading
                    ? accountAuthMode === "register" ? "Создаём аккаунт..." : "Входим..."
                    : accountAuthMode === "register" ? "Зарегистрироваться" : "Войти в аккаунт"}
                  {!accountLoading && <ArrowRight size={18} />}
                </button>

                {accountAuthMode === "login" && (
                  <p className="checkout-footnote">
                    Ещё нет аккаунта?{" "}
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => {
                        setAccountAuthMode("register");
                        setAccountError("");
                      }}
                    >
                      Зарегистрируйся
                    </button>
                  </p>
                )}
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
                              {orderStatusLabel(order.status, order.delivery_method)}
                            </span>
                          </div>
                          <strong>{formatPrice(order.total_price)}</strong>
                        </div>

                        <div className="account-order-address">
                          <MapPin size={15} />
                          <span>
                            {order.delivery_method === "PICKUP"
                              ? "Самовывоз со склада"
                              : order.delivery_address}
                          </span>
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
                                  {item.product_name ??
                                    product?.name ??
                                    `Товар №${item.product_id}`}
                                  {item.variant_name &&
                                    item.variant_name !== item.unit &&
                                    ` (${item.variant_name})`}
                                  {" × "}
                                  {item.quantity} {item.unit}
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
                                      {orderStatusLabel(history.status, order.delivery_method)}
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

                        {order.status === "DELIVERED" && (
                          <a
                            className="review-order-link"
                            href={YANDEX_REVIEW_URL}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <Star size={16} /> Оставить отзыв на Яндекс Картах
                          </a>
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

      {notificationsOpen && customer && (

                  <div className="notifications-modal-backdrop" onClick={() => setNotificationsOpen(false)}>
                    <section
                      className="notifications-modal"
                      role="dialog"
                      aria-modal="true"
                      aria-label="Уведомления"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <div className="notifications-modal-header">
                        <div>
                          <h3>Уведомления</h3>
                          <p>{unreadNotificationsCount ? `Непрочитанных: ${unreadNotificationsCount}` : "Все сообщения о заказах"}</p>
                        </div>
                        <button type="button" className="notifications-modal-close" onClick={() => setNotificationsOpen(false)} aria-label="Закрыть уведомления">
                          <X size={20} />
                        </button>
                      </div>

                      {notificationsError && <p className="checkout-error" role="alert">{notificationsError}</p>}
                      {notificationsLoading && notifications.length === 0 ? (
                        <p className="account-notifications-empty">Загружаем уведомления...</p>
                      ) : notifications.length === 0 ? (
                        <p className="account-notifications-empty">Пока уведомлений нет.</p>
                      ) : (
                        <>
                          {unreadNotificationsCount > 0 && (
                            <button
                              className="notification-read-all"
                              onClick={() => void handleMarkAllNotificationsAsRead()}
                              disabled={notificationActionLoading}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: 8,
                                padding: "10px 15px",
                                border: "1px solid #d8e3d5",
                                borderRadius: 12,
                                background: notificationActionLoading ? "#f1f3f0" : "#edf5e9",
                                color: "#315c35",
                                fontSize: 13,
                                fontWeight: 650,
                                lineHeight: 1.2,
                                cursor: notificationActionLoading ? "wait" : "pointer",
                                transition: "background 160ms ease, border-color 160ms ease, transform 160ms ease",
                                opacity: notificationActionLoading ? 0.7 : 1,
                              }}
                            >
                              <Check size={16} />
                              {notificationActionLoading ? "Обновляем..." : "Прочитать все"}
                            </button>
                          )}
                          <div className="notification-list">
                            {notifications.map((notification) => (
                              <article
                                className={`notification-card ${notification.is_read ? "is-read" : "is-unread"}`}
                                key={notification.id}
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  alignItems: "center",
                                  textAlign: "center",
                                  gap: 14,
                                  padding: "20px 18px",
                                }}
                              >
                                <div className="notification-card-content" style={{ width: "100%" }}>
                                  <strong>Заказ №{notification.order_id}</strong>
                                  <p>{notification.message}</p>
                                  <small>{formatDate(notification.created_at)}</small>
                                </div>
                                {notification.is_read ? (
                                  <span
                                    className="notification-read-status"
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      gap: 7,
                                      padding: "7px 13px",
                                      borderRadius: 999,
                                      background: "#edf7ee",
                                      color: "#367447",
                                      fontSize: 12,
                                      fontWeight: 700,
                                      lineHeight: 1.2,
                                    }}
                                  >
                                    <Check size={14} />
                                    Прочитано
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    className="notification-read-button"
                                    onClick={() => void handleMarkNotificationAsRead(notification.id)}
                                    disabled={notificationActionLoading}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      gap: 8,
                                      padding: "11px 18px",
                                      border: "1px solid #24372b",
                                      borderRadius: 10,
                                      background: notificationActionLoading ? "#68776c" : "#24372b",
                                      color: "#ffffff",
                                      fontSize: 13,
                                      fontWeight: 650,
                                      lineHeight: 1.2,
                                      cursor: notificationActionLoading ? "wait" : "pointer",
                                      transition: "background 160ms ease, transform 160ms ease",
                                      opacity: notificationActionLoading ? 0.7 : 1,
                                    }}
                                  >
                                    <Check size={15} />
                                    Отметить как прочитанное
                                  </button>
                                )}
                              </article>
                            ))}
                          </div>
                        </>
                      )}
                    </section>
                  </div>
                      )}
    </div>
    </ShopContext.Provider>
  );
}

export default App;
