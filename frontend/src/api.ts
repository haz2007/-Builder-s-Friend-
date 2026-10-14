
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

export type ApiCategory = { id: number; name: string };

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
};

export type RegisterData = { phone: string; password: string };
export type CustomerLoginData = { phone: string; password: string };
export type AdminLoginData = { email: string; password: string };
export type LoginData = CustomerLoginData | AdminLoginData;

export type AuthUser = {
  id: number;
  email: string | null;
  phone: string | null;
  role: string;
};

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type CreateOrderData = {
  customer_name: string;
  items: { product_id: number; quantity: number }[];
  delivery_address: string;
};

export type ApiOrderItem = {
  id: number;
  product_id: number;
  quantity: number;
  price: number;
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
};

export type ProductUpdateData = Partial<ProductCreateData>;
export type CategoryCreateData = { name: string };

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
