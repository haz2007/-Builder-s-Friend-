
export const API_ORIGIN = "http://127.0.0.1:8000";

export function getImageUrl(
  imageUrl: string | null | undefined,
): string | null {
  if (!imageUrl) return null;

  if (imageUrl.startsWith("http://") || imageUrl.startsWith("https://")) {
    return imageUrl;
  }

  return `${API_ORIGIN}${imageUrl.startsWith("/") ? "" : "/"}${imageUrl}`;
}

export type ApiCategory = { id: number; name: string; parent_id: number | null };

export type ApiProductVariant = {
  id: number;
  product_id: number;
  name: string;
  unit: string;
  price: number;
  /** Сколько базовых единиц товара в 1 единице варианта (м³ → 27 шт). */
  base_quantity: number;
  /** Сколько единиц варианта доступно из общего склада. */
  stock_quantity: number;
  is_active: number;
};

export type ApiProduct = {
  id: number;
  name: string;
  description: string | null;
  price: number;
  stock_quantity: number;
  unit: string;
  category_id: number;
  is_active: number;
  image_url?: string | null;
  category_ids: number[];
  thickness_mm: number | null;
  width_mm: number | null;
  length_mm: number | null;
  pieces_per_cubic_meter: number | null;
  variants: ApiProductVariant[];
};

export type RegisterData = { phone: string; password: string };
export type CustomerLoginData = { phone: string; password: string };
export type AdminLoginData = { email: string; password: string } | { phone: string; password: string };
export type LoginData = CustomerLoginData | AdminLoginData;

export type AuthUser = {
  id: number;
  email: string | null;
  phone: string | null;
  role: string;
  /** 1 — владелец магазина, может управлять администраторами */
  is_owner?: number;
};

export type ApiAdmin = AuthUser & { has_telegram: boolean };

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type CreateOrderData = {
  customer_name: string;
  items: { product_id: number; variant_id: number; quantity: number }[];
  /** DELIVERY — привозит магазин, PICKUP — самовывоз */
  delivery_method: "DELIVERY" | "PICKUP";
  delivery_address: string;
};

export type ApiOrderItem = {
  id: number;
  product_id: number;
  variant_id: number;
  quantity: number;
  price: number;
  unit: string;
  base_quantity: number;
  product_name: string | null;
  variant_name: string | null;
};

export type ApiOrderStatusHistory = {
  id: number;
  order_id: number;
  status: string;
  created_at: string;
};

export type ApiOrder = {
  id: number;
  status: string;
  total_price: number;
  delivery_address: string;
  delivery_method?: "DELIVERY" | "PICKUP";
  /** Допустимые следующие статусы: следующий этап и/или отмена */
  allowed_statuses?: string[];
  customer_name: string;
  customer_phone: string | null;
  items: ApiOrderItem[];
  status_history: ApiOrderStatusHistory[];
};

export type ProductCreateData = {
  name: string;
  description: string | null;
  price: number;
  stock_quantity: number;
  unit: string;
  category_id: number;
  thickness_mm?: number | null;
  width_mm?: number | null;
  length_mm?: number | null;
};

export type ProductUpdateData = Partial<ProductCreateData>;

export type VariantCreateData = {
  name: string;
  unit: string;
  price: number;
  base_quantity?: number;
};

export type VariantUpdateData = Partial<VariantCreateData> & {
  is_active?: number;
};
export type CategoryCreateData = { name: string; parent_id?: number | null };

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Ошибка API: ${response.status}`;

    try {
      const data = await response.json();

      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail
          .map(
            (item: { msg?: string }) =>
              item.msg ?? "Ошибка проверки данных",
          )
          .join(", ");
      }
    } catch {
      // Ответ не содержит JSON.
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

function adminHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export function getProducts(): Promise<ApiProduct[]> {
  return request<ApiProduct[]>("/api/v1/products/?limit=100");
}

export function getCategories(): Promise<ApiCategory[]> {
  return request<ApiCategory[]>("/api/v1/categories/");
}

export function registerUser(data: RegisterData): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function loginUser(data: LoginData): Promise<AuthToken> {
  return request<AuthToken>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getCurrentUser(token: string): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/me", {
    headers: adminHeaders(token),
  });
}

export function createOrder(
  data: CreateOrderData,
  token: string,
): Promise<ApiOrder> {
  return request<ApiOrder>("/api/v1/orders/", {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify(data),
  });
}

/** Получить заказы вошедшего пользователя. */
export function getMyOrders(token: string): Promise<ApiOrder[]> {
  return request<ApiOrder[]>("/api/v1/orders/?limit=100", {
    headers: adminHeaders(token),
  });
}

/** Получить подробности заказа. */
export function getOrder(
  orderId: number,
  token: string,
): Promise<ApiOrder> {
  return request<ApiOrder>(`/api/v1/orders/${orderId}`, {
    headers: adminHeaders(token),
  });
}

/** Получить историю изменения статуса. */
export function getOrderHistory(
  orderId: number,
  token: string,
): Promise<ApiOrderStatusHistory[]> {
  return request<ApiOrderStatusHistory[]>(
    `/api/v1/orders/${orderId}/history`,
    { headers: adminHeaders(token) },
  );
}

/** Отменить заказ, если сервер разрешает отмену. */
export function cancelOrder(
  orderId: number,
  token: string,
): Promise<ApiOrder> {
  return request<ApiOrder>(`/api/v1/orders/${orderId}/cancel`, {
    method: "POST",
    headers: adminHeaders(token),
  });
}

export async function getAdminProducts(token: string): Promise<ApiProduct[]> {
  const activeProducts = await request<ApiProduct[]>(
    "/api/v1/products/?is_active=1&limit=100",
    { headers: adminHeaders(token) },
  );

  const inactiveProducts = await request<ApiProduct[]>(
    "/api/v1/products/?is_active=0&limit=100",
    { headers: adminHeaders(token) },
  );

  return [...activeProducts, ...inactiveProducts];
}

export function createProduct(
  data: ProductCreateData,
  token: string,
): Promise<ApiProduct> {
  return request<ApiProduct>("/api/v1/products/", {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify(data),
  });
}

export function updateProduct(
  productId: number,
  data: ProductUpdateData,
  token: string,
): Promise<ApiProduct> {
  return request<ApiProduct>(`/api/v1/products/${productId}`, {
    method: "PATCH",
    headers: adminHeaders(token),
    body: JSON.stringify(data),
  });
}

export function deactivateProduct(
  productId: number,
  token: string,
): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/v1/products/${productId}`, {
    method: "DELETE",
    headers: adminHeaders(token),
  });
}

export function restoreProduct(
  productId: number,
  token: string,
): Promise<ApiProduct> {
  return request<ApiProduct>(`/api/v1/products/${productId}/restore`, {
    method: "POST",
    headers: adminHeaders(token),
  });
}

export function createCategory(
  data: CategoryCreateData,
  token: string,
): Promise<ApiCategory> {
  return request<ApiCategory>("/api/v1/categories/", {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify(data),
  });
}

export function updateCategory(
  categoryId: number,
  data: CategoryCreateData,
  token: string,
): Promise<ApiCategory> {
  return request<ApiCategory>(`/api/v1/categories/${categoryId}`, {
    method: "PATCH",
    headers: adminHeaders(token),
    body: JSON.stringify(data),
  });
}

export async function uploadProductImage(
  productId: number,
  file: File,
  token: string,
): Promise<ApiProduct> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`/api/v1/products/${productId}/image`, {
    method: "POST",
    headers: adminHeaders(token),
    body: formData,
  });

  if (!response.ok) {
    let message = `Ошибка загрузки: ${response.status}`;

    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // Ответ не содержит JSON.
    }

    throw new Error(message);
  }

  return response.json() as Promise<ApiProduct>;
}

/** Получить количество новых заказов. */
export async function getNewOrdersCount(token: string): Promise<number> {
  const response = await fetch("/api/v1/orders/admin/new-count", {
    headers: adminHeaders(token),
  });

  if (!response.ok) {
    throw new Error("Не удалось загрузить количество новых заказов.");
  }

  const data: { new_orders_count: number } = await response.json();
  return data.new_orders_count;
}

/** Получить все заказы для панели администратора. */
export function getAdminOrders(token: string): Promise<ApiOrder[]> {
  return request<ApiOrder[]>("/api/v1/orders/?limit=100", {
    headers: adminHeaders(token),
  });
}

/** Изменить статус заказа. */
export function updateOrderStatus(
  orderId: number,
  status: string,
  token: string,
): Promise<ApiOrder> {
  return request<ApiOrder>(`/api/v1/orders/${orderId}/status`, {
    method: "PATCH",
    headers: adminHeaders(token),
    body: JSON.stringify({ status }),
  });
}
export type AdminAnalyticsPeriod = "7d" | "30d" | "90d" | "all" | "custom";
export type AdminAnalytics = {
  period: AdminAnalyticsPeriod;
  date_from: string | null;
  date_to: string | null;
  orders: { total: number; cancelled: number; delivered: number; not_cancelled: number };
  revenue: { not_cancelled: number; delivered: number };
  average_order_value: number;
  delivery_conversion_rate: number;
  trend: { date: string; orders: number; revenue: number; delivered_revenue: number }[];
  /** day — для 7 дней, week — для 30/90, month — за всё время */
  granularity: "day" | "week" | "month";
  revenue_series: { start: string; end: string; revenue: number; orders: number }[];
  /** Сколько заказов сейчас на каждом этапе (не зависит от периода) */
  pipeline: { status: string; count: number }[];
  category_revenue: { name: string; revenue: number }[];
  top_products: { product_id: number; name: string; quantity: number; revenue: number }[];
  low_stock_products: { id: number; name: string; stock_quantity: number; unit: string }[];
};

export function getAdminAnalytics(
  token: string,
  period: AdminAnalyticsPeriod,
  dateFrom?: string,
  dateTo?: string,
): Promise<AdminAnalytics> {
  const params = new URLSearchParams({ period });
  if (period === "custom") {
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
  }
  return request<AdminAnalytics>(`/api/v1/admin/analytics?${params.toString()}`, {
    headers: adminHeaders(token),
  });
}

/** Удалить товар из каталога (мягкое удаление). */
export function deleteProduct(
  productId: number,
  token: string,
): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/v1/products/${productId}`, {
    method: "DELETE",
    headers: adminHeaders(token),
  });
}

/** Удалить категорию, если в ней нет товаров. */
export function deleteCategory(
  categoryId: number,
  token: string,
): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/v1/categories/${categoryId}`, {
    method: "DELETE",
    headers: adminHeaders(token),
  });
}
export type ApiNotification = {
  id: number;
  user_id: number;
  order_id: number | null;
  status: string;
  message: string;
  is_read: number;
  created_at: string;
};

/** Получить уведомления текущего пользователя. */
export function getNotifications(
  token: string,
  unreadOnly = false,
): Promise<ApiNotification[]> {
  const params = new URLSearchParams({
    unread_only: String(unreadOnly),
    limit: "100",
  });

  return request<ApiNotification[]>(
    `/api/v1/notifications/?${params.toString()}`,
    { headers: adminHeaders(token) },
  );
}

/** Получить количество непрочитанных уведомлений. */
export function getUnreadNotificationsCount(
  token: string,
): Promise<{ count: number }> {
  return request<{ count: number }>(
    "/api/v1/notifications/unread-count",
    { headers: adminHeaders(token) },
  );
}

/** Отметить одно уведомление прочитанным. */
export function markNotificationAsRead(
  notificationId: number,
  token: string,
): Promise<ApiNotification> {
  return request<ApiNotification>(
    `/api/v1/notifications/${notificationId}/read`,
    {
      method: "PATCH",
      headers: adminHeaders(token),
    },
  );
}

/** Отметить все уведомления прочитанными. */
export function markAllNotificationsAsRead(
  token: string,
): Promise<{ message: string; count: number }> {
  return request<{ message: string; count: number }>(
    "/api/v1/notifications/read-all",
    {
      method: "PATCH",
      headers: adminHeaders(token),
    },
  );
}

/** Добавить вариант продажи товара (например, «Штука»). */
export function createVariant(
  productId: number,
  data: VariantCreateData,
  token: string,
): Promise<ApiProductVariant> {
  return request<ApiProductVariant>(`/api/v1/products/${productId}/variants`, {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify(data),
  });
}

export function updateVariant(
  productId: number,
  variantId: number,
  data: VariantUpdateData,
  token: string,
): Promise<ApiProductVariant> {
  return request<ApiProductVariant>(
    `/api/v1/products/${productId}/variants/${variantId}`,
    {
      method: "PATCH",
      headers: adminHeaders(token),
      body: JSON.stringify(data),
    },
  );
}

/** Удалить вариант; если он есть в заказах — бэкенд его только скроет. */
export function deleteVariant(
  productId: number,
  variantId: number,
  token: string,
): Promise<{ message: string }> {
  return request<{ message: string }>(
    `/api/v1/products/${productId}/variants/${variantId}`,
    {
      method: "DELETE",
      headers: adminHeaders(token),
    },
  );
}

export function getAdmins(token: string): Promise<ApiAdmin[]> {
  return request<ApiAdmin[]>("/api/v1/admins/", {
    headers: adminHeaders(token),
  });
}

/** Назначить администратором уже зарегистрированного пользователя. */
export function addAdmin(login: string, token: string): Promise<ApiAdmin> {
  return request<ApiAdmin>("/api/v1/admins/", {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify({ login }),
  });
}

export function removeAdmin(userId: number, token: string): Promise<ApiAdmin> {
  return request<ApiAdmin>(`/api/v1/admins/${userId}`, {
    method: "DELETE",
    headers: adminHeaders(token),
  });
}
