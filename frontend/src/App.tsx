import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Clock3,
  Menu,
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
  Heart,
  Settings,
  Trash2,
} from "lucide-react";
import {
  getProducts,
  getCategories,
  registerUser,
  requestPasswordReset,
  changePassword,
  confirmPasswordReset,
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
import ProductCard from "./components/ProductCard";
import HomePage from "./pages/HomePage";
import ConsentPage from "./pages/ConsentPage";
import DeliveryReturnsPage from "./pages/DeliveryReturnsPage";
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
import CallbackForm from "./components/CallbackForm";
import DeleteAccount from "./components/DeleteAccount";
import PhoneInput from "./components/PhoneInput";
import QuantityInput from "./components/QuantityInput";
import ConsentCheckbox from "./components/ConsentCheckbox";

type Customer = {
  id: number;
  phone: string;
  role: string;
};

const TOKEN_KEY = "wood_commerce_token";
const CART_KEY = "wood_commerce_cart";
// Тот же ключ, что в Admin.tsx: вход админа через сайт открывает панель без второго входа
const ADMIN_TOKEN_KEY = "wood_admin_token";
const FAVORITES_KEY = "wood_commerce_favorites";

function loadFavorites(): number[] {
  try {
    const saved = JSON.parse(localStorage.getItem(FAVORITES_KEY) ?? "[]") as unknown;
    return Array.isArray(saved) ? saved.filter((id) => Number.isInteger(id) && id > 0) : [];
  } catch {
    return [];
  }
}

function loadCart(): Record<number, number> {
  try {
    const saved = JSON.parse(localStorage.getItem(CART_KEY) ?? "{}") as unknown;
    if (!saved || typeof saved !== "object") return {};
    return Object.fromEntries(
      Object.entries(saved).filter(
        ([id, quantity]) => Number(id) > 0 && Number.isInteger(quantity) && (quantity as number) > 0,
      ),
    ) as Record<number, number>;
  } catch {
    return {};
  }
}
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
  const [cart, setCart] = useState<Record<number, number>>(loadCart);

  // Корзина переживает обновление страницы; только в этом браузере
  useEffect(() => {
    try {
      localStorage.setItem(CART_KEY, JSON.stringify(cart));
    } catch {
      // Приватный режим или запрет хранилища — корзина просто не сохранится
    }
  }, [cart]);
  // Выбранный в карточке вариант: id товара → id варианта
  const [selectedVariants, setSelectedVariants] = useState<
    Record<number, number>
  >({});
  const [favorites, setFavorites] = useState<number[]>(loadFavorites);

  useEffect(() => {
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    } catch {
      // Хранилище недоступно — избранное просто не сохранится
    }
  }, [favorites]);
  const [cartOpen, setCartOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerSearch, setHeaderSearch] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [orderComment, setOrderComment] = useState("");
  const [deliveryMethod, setDeliveryMethod] = useState<"DELIVERY" | "PICKUP">(
    "DELIVERY",
  );
  const [customerName, setCustomerName] = useState("");
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");
  const [checkoutSuccess, setCheckoutSuccess] = useState<number | null>(null);
  // «Перезвоните мне» вместо регистрации
  const [callbackMode, setCallbackMode] = useState(false);
  const [callbackSuccess, setCallbackSuccess] = useState<number | null>(null);

  // Личный кабинет покупателя
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountMode, setAccountMode] = useState<"login" | "orders">("login");
  // Смена пароля в кабинете (например, после временного пароля от магазина)
  const [accountTab, setAccountTab] = useState<"orders" | "favorites" | "notifications" | "settings">("orders");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [accountPhone, setAccountPhone] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  // «Войти» в шапке: вход или регистрация нового покупателя
  const [accountAuthMode, setAccountAuthMode] = useState<"login" | "register" | "reset">("login");
  // Сброс пароля: код из Telegram-бота
  const [resetCodeSent, setResetCodeSent] = useState(false);
  const [resetCode, setResetCode] = useState("");
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

  // По найденным товарам: снятый с продажи товар из сохранённой корзины не считается
  const cartCount = cartEntries.reduce((total, entry) => total + entry.quantity, 0);

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
    if (location.pathname !== "/account" || !customer) {
      return;
    }

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;

    // Открыли /account по ссылке или после обновления страницы — сразу подгружаем
    void refreshOrders(token);
    void refreshNotifications(token);
    const intervalId = window.setInterval(() => {
      void refreshOrders(token);
    }, 15000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [location.pathname, customer]);

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

    const resetting = accountAuthMode === "reset";
    if (resetting && resetCodeSent && accountPassword.length < PASSWORD_MIN_LENGTH) {
      setAccountError(`Новый пароль — не короче ${PASSWORD_MIN_LENGTH} символов.`);
      return;
    }

    setAccountLoading(true);

    try {
      if (resetting && !resetCodeSent) {
        const answer = await requestPasswordReset(accountPhone.trim());
        setAccountNotice(answer.detail);
        setResetCodeSent(true);
        return;
      }

      if (registering) {
        await registerUser({
          phone: accountPhone.trim(),
          password: accountPassword,
          privacy_accepted: true,
        });
      }

      const auth = resetting
        ? await confirmPasswordReset({
            phone: accountPhone.trim(),
            code: resetCode.trim(),
            new_password: accountPassword,
          })
        : await loginUser({
            phone: accountPhone.trim(),
            password: accountPassword,
          });

      const user = await getCurrentUser(auth.access_token);

      if (user.role === "ADMIN") {
        // Админ вошёл через обычную форму сайта — сразу в панель управления.
        // Токен админки живёт в sessionStorage, как при входе на /admin
        sessionStorage.setItem(ADMIN_TOKEN_KEY, auth.access_token);
        setAccountPassword("");
        setAccountOpen(false);
        navigate("/admin");
        return;
      }

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
      setResetCode("");
      setResetCodeSent(false);
      setAccountAuthMode("login");
      setAccountMode("orders");
      setAccountOpen(false);
      setAccountTab("orders");
      navigate("/account");

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

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    if (newPassword.length < PASSWORD_MIN_LENGTH) {
      setPasswordMessage({ ok: false, text: `Новый пароль — не короче ${PASSWORD_MIN_LENGTH} символов.` });
      return;
    }
    setPasswordSaving(true);
    setPasswordMessage(null);
    try {
      await changePassword(token, { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordMessage({ ok: true, text: "Пароль изменён. В следующий раз входите с новым паролем." });
    } catch (error) {
      setPasswordMessage({
        ok: false,
        text: error instanceof Error ? error.message : "Не удалось сменить пароль.",
      });
    } finally {
      setPasswordSaving(false);
    }
  }

  async function openAccount() {
    setCartOpen(false);
    setCheckoutOpen(false);
    setAccountError("");
    setOrdersError("");
    setAccountNotice("");

    const token = localStorage.getItem(TOKEN_KEY);

    if (token && customer) {
      // Вошедший покупатель — на страницу кабинета, а не во всплывающую панель
      setAccountMode("orders");
      setAccountOpen(false);
      navigate("/account");
      await Promise.all([refreshOrders(token), refreshNotifications(token)]);
    } else {
      setAccountMode("login");
      setAccountOpen(true);
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
          comment: orderComment.trim(),
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
      setOrderComment("");

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
    setCallbackSuccess(null);
    setCallbackMode(false);
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


  const favoriteProducts = products.filter((product) => favorites.includes(product.id));
  const ACCOUNT_TABS = [
    { key: "orders", label: "Заказы", icon: <ClipboardList size={17} /> },
    { key: "favorites", label: "Избранное", icon: <Heart size={17} /> },
    { key: "notifications", label: "Уведомления", icon: <Bell size={17} /> },
    { key: "settings", label: "Настройки", icon: <Settings size={17} /> },
  ] as const;

  const accountPage = customer ? (
    <section className="page-section account-page">
      <div className="container">
        <h1>Личный кабинет</h1>
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


          <nav className="account-tabs" aria-label="Разделы личного кабинета">
            {ACCOUNT_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={accountTab === tab.key ? "is-active" : ""}
                onClick={() => setAccountTab(tab.key)}
              >
                {tab.icon}
                {tab.label}
                {tab.key === "notifications" && unreadNotificationsCount > 0 && (
                  <em>{unreadNotificationsCount}</em>
                )}
                {tab.key === "favorites" && favoriteProducts.length > 0 && <em>{favoriteProducts.length}</em>}
              </button>
            ))}
          </nav>

          {accountTab === "orders" && (
            <>
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
                      onClick={() => navigate("/catalog")}
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

                        {order.comment && (
                          <p className="account-order-comment">«{order.comment}»</p>
                        )}

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
            </>
          )}

          {accountTab === "favorites" &&
            (favoriteProducts.length === 0 ? (
              <div className="account-empty">
                <Heart size={34} />
                <h3>В избранном пусто</h3>
                <p>Нажимайте на сердечко у товара, чтобы вернуться к нему позже.</p>
                <button className="button button-primary checkout-button" onClick={() => navigate("/catalog")}>
                  Перейти в каталог
                </button>
              </div>
            ) : (
              <div className="product-grid account-favorites">
                {favoriteProducts.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
            ))}

          {accountTab === "notifications" &&
            (notifications.length === 0 ? (
              <div className="account-empty">
                <Bell size={34} />
                <h3>Уведомлений нет</h3>
                <p>Здесь появятся сообщения о смене статуса ваших заказов.</p>
              </div>
            ) : (
              <div className="account-notification-list">
                {unreadNotificationsCount > 0 && (
                  <button
                    type="button"
                    className="button button-dark"
                    onClick={() => void handleMarkAllNotificationsAsRead()}
                    disabled={notificationActionLoading}
                  >
                    <Check size={16} /> Прочитать все
                  </button>
                )}
                {notifications.map((notification) => (
                  <article
                    key={notification.id}
                    className={`account-notification ${notification.is_read ? "" : "is-unread"}`}
                  >
                    <strong>Заказ №{notification.order_id}</strong>
                    <p>{notification.message}</p>
                    <small>{formatDate(notification.created_at)}</small>
                    {!notification.is_read && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => void handleMarkNotificationAsRead(notification.id)}
                        disabled={notificationActionLoading}
                      >
                        Отметить прочитанным
                      </button>
                    )}
                  </article>
                ))}
              </div>
            ))}

          {accountTab === "settings" && (
            <div className="account-settings">
              <h3>Сменить пароль</h3>
                {(
                  <form className="account-password-form" onSubmit={handleChangePassword}>
                    <label className="checkout-field">
                      <span>Текущий пароль</span>
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(event) => setCurrentPassword(event.target.value)}
                        placeholder="Или временный пароль от магазина"
                        autoComplete="current-password"
                        required
                      />
                    </label>
                    <label className="checkout-field">
                      <span>Новый пароль</span>
                      <input
                        type="password"
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        placeholder={`Не короче ${PASSWORD_MIN_LENGTH} символов`}
                        autoComplete="new-password"
                        minLength={PASSWORD_MIN_LENGTH}
                        required
                      />
                    </label>
                    {passwordMessage && (
                      <p className={passwordMessage.ok ? "account-notice" : "checkout-error"} role="status">
                        {passwordMessage.text}
                      </p>
                    )}
                    <button className="button button-primary checkout-button" type="submit" disabled={passwordSaving}>
                      {passwordSaving ? "Сохраняем..." : "Сменить пароль"}
                    </button>
                  </form>
                )}
                <h3 className="account-settings-danger">Удаление аккаунта</h3>
                {(
                  <DeleteAccount
                    token={localStorage.getItem(TOKEN_KEY) ?? ""}
                    onDeleted={() => {
                      logoutCustomer();
                      setAccountTab("orders");
                      setAccountNotice("Аккаунт удалён. Спасибо, что были с нами.");
                    }}
                  />
                )}


            </div>
          )}
        </div>
      </div>
    </section>
  ) : (
    <section className="page-section">
      <div className="container empty-results">
        <UserRound size={30} />
        <h3>Личный кабинет</h3>
        <p>Войдите, чтобы видеть заказы, избранное и уведомления.</p>
        <button className="button button-dark" onClick={() => void openAccount()}>
          Войти или зарегистрироваться
        </button>
      </div>
    </section>
  );

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
            <NavLink to="/delivery" onClick={() => setMobileMenuOpen(false)}>
              Доставка
            </NavLink>
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
              <span>{customer ? "Кабинет" : "Войти"}</span>
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
          <Route path="/delivery" element={<DeliveryReturnsPage />} />
          <Route path="/account" element={accountPage} />
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
            <Link to="/delivery">Доставка и возврат</Link>
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

                        <QuantityInput
                          value={quantity}
                          max={quantity + maxAddable(product, variant)}
                          onChange={(next) => changeQuantity(variant.id, next - quantity)}
                          allowRemove
                          iconSize={14}
                        />
                      </div>

                      <div className="cart-item-side">
                        <strong className="cart-item-total">
                          {formatPrice(variant.price * quantity)}
                        </strong>
                        <button
                          type="button"
                          className="cart-item-remove"
                          onClick={() => changeQuantity(variant.id, -quantity)}
                          aria-label={`Удалить ${product.name} из корзины`}
                          title="Удалить из корзины"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
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
                    : callbackSuccess !== null
                      ? "Заявка принята"
                      : callbackMode
                        ? "Перезвоните мне"
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
            ) : callbackSuccess !== null ? (
              <div className="checkout-success">
                <span className="checkout-success-icon">
                  <Check size={32} />
                </span>
                <h3>Перезвоним!</h3>
                <p>
                  Заявка <strong>№{callbackSuccess}</strong> уже у менеджера. Позвоним в рабочее
                  время — {WORKING_HOURS.toLowerCase()}.
                </p>
                <button
                  className="button button-dark checkout-button"
                  onClick={() => setCheckoutOpen(false)}
                >
                  Продолжить покупки
                </button>
              </div>
            ) : callbackMode ? (
              <CallbackForm
                cart={cartEntries}
                initialName={customerName}
                initialComment={orderComment}
                onDone={(requestId) => {
                  setCallbackSuccess(requestId);
                  setCallbackMode(false);
                  setCart({});
                  setOrderComment("");
                }}
                onCancel={() => setCallbackMode(false)}
              />
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
                    <button
                      type="button"
                      className="checkout-callback-offer"
                      onClick={() => setCallbackMode(true)}
                    >
                      <Phone size={16} />
                      Не хочу регистрироваться — перезвоните мне
                    </button>

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
                      <PhoneInput value={phone} onChange={setPhone} required />
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
                        ["DELIVERY", "Доставка", "Привезём на объект, стоимость обсудим по телефону"],
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

                <label className="checkout-field">
                  <span>
                    Комментарий к заказу <small className="checkout-optional">— необязательно</small>
                  </span>
                  <textarea
                    value={orderComment}
                    onChange={(event) => setOrderComment(event.target.value)}
                    placeholder="Например: распилить по 3 м, привезти после 14:00"
                    maxLength={500}
                    rows={2}
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
                    : accountAuthMode === "register"
                      ? "Создай аккаунт по номеру телефона — заказы и их статусы будут здесь и в Telegram-боте."
                      : "Если аккаунт подключён к нашему Telegram-боту, код для смены пароля придёт туда."}
                </p>

                {accountAuthMode !== "reset" && <div className="auth-tabs">
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
                </div>}

                <label className="checkout-field">
                  <span>Номер телефона</span>
                  <PhoneInput value={accountPhone} onChange={setAccountPhone} required />
                </label>

                {accountAuthMode === "reset" && resetCodeSent && (
                  <label className="checkout-field">
                    <span>Код из Telegram</span>
                    <input
                      inputMode="numeric"
                      value={resetCode}
                      onChange={(event) => setResetCode(event.target.value)}
                      placeholder="6 цифр"
                      autoComplete="one-time-code"
                      maxLength={12}
                      required
                    />
                  </label>
                )}

                {(accountAuthMode !== "reset" || resetCodeSent) && (
                  <label className="checkout-field">
                    <span>{accountAuthMode === "reset" ? "Новый пароль" : "Пароль"}</span>
                    <input
                      type="password"
                      value={accountPassword}
                      onChange={(event) => setAccountPassword(event.target.value)}
                      placeholder={
                        accountAuthMode === "login"
                          ? "Введите пароль"
                          : `Не короче ${PASSWORD_MIN_LENGTH} символов`
                      }
                      autoComplete={accountAuthMode === "login" ? "current-password" : "new-password"}
                      minLength={accountAuthMode === "login" ? 1 : PASSWORD_MIN_LENGTH}
                      required
                    />
                  </label>
                )}

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
                    ? "Подождите..."
                    : accountAuthMode === "register"
                      ? "Зарегистрироваться"
                      : accountAuthMode === "reset"
                        ? resetCodeSent ? "Сменить пароль и войти" : "Получить код"
                        : "Войти в аккаунт"}
                  {!accountLoading && <ArrowRight size={18} />}
                </button>

                {accountAuthMode === "login" && (
                  <p className="checkout-footnote">
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => {
                        setAccountAuthMode("reset");
                        setResetCodeSent(false);
                        setAccountError("");
                        setAccountNotice("");
                      }}
                    >
                      Забыли пароль?
                    </button>
                    {" · "}Ещё нет аккаунта?{" "}
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

                {accountAuthMode === "reset" && (
                  <p className="checkout-footnote">
                    Бот не подключён? Позвоните в магазин — вам сбросят пароль.{" "}
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => {
                        setAccountAuthMode("login");
                        setResetCodeSent(false);
                        setAccountError("");
                        setAccountNotice("");
                      }}
                    >
                      Вернуться ко входу
                    </button>
                  </p>
                )}
              </form>
            ) : null}
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
