import { useEffect, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import { downloadOrdersExcel, getAdminOrders, getNewOrdersCount, resetUserPassword, updateOrderStatus } from "./api";
import type { ApiOrder, ApiProduct } from "./api";
import { Icon } from "./AdminIcons";
import CallbacksPanel from "./CallbacksPanel";
import OrderPrintSheet from "./OrderPrintSheet";
import { FILTER_STATUSES, orderStages, orderStatusLabel } from "./shop/orderStatus";

// Подписи кнопок: что произойдёт с заказом (как в Telegram-боте)
const STATUS_ACTIONS: Record<string, string> = {
  CONFIRMED: "Подтвердить заказ",
  PREPARING: "Начать подготовку",
  READY_FOR_DELIVERY: "Заказ собран",
  ON_THE_WAY: "Отправить в путь",
  DELIVERED: "Отметить доставленным",
  CANCELLED: "Отменить заказ",
};

const PICKUP_STATUS_ACTIONS: Record<string, string> = {
  ...STATUS_ACTIONS,
  READY_FOR_DELIVERY: "Собран — ждёт покупателя",
  DELIVERED: "Выдан покупателю",
};

/** Заливка шкалы ровно до центра точки текущего этапа. */
function progressPercent(stages: { value: string }[], status: string) {
  const index = Math.max(0, stages.findIndex((item) => item.value === status));
  return (index / (stages.length - 1)) * 100;
}

type Props = {
  token: string;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  orders: ApiOrder[];
  /** Для названий позиций старых заказов без сохранённого имени */
  products: ApiProduct[];
  onOrdersChange: (orders: ApiOrder[]) => void;
  onNewOrdersCount: (count: number) => void;
  orderFilter: string;
  onOrderFilterChange: (status: string) => void;
};

/** Заказы: фильтр по статусу, смена статуса, сброс пароля, печать бланка. */
export default function OrdersSection({
  token,
  onError: setError,
  onNotice: setNotice,
  orders,
  products,
  onOrdersChange: setOrders,
  onNewOrdersCount: setNewOrdersCount,
  orderFilter,
  onOrderFilterChange: setOrderFilter,
}: Props) {
  const [ordersLoading, setOrdersLoading] = useState(false);

  const [updatingOrderId, setUpdatingOrderId] = useState<number | null>(null);
  const [exportPeriod, setExportPeriod] = useState("30d");
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await downloadOrdersExcel(token, exportPeriod);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выгрузить заказы.");
    } finally {
      setExporting(false);
    }
  }

  const [printOrder, setPrintOrder] = useState<ApiOrder | null>(null);

  // Бланк рисуется в этой же странице и печатается через window.print():
  // новая вкладка не знала бы токен админа
  useEffect(() => {
    if (!printOrder) return;
    const clear = () => setPrintOrder(null);
    window.addEventListener("afterprint", clear);
    // Эффект срабатывает после отрисовки — бланк уже в документе
    const timer = window.setTimeout(() => window.print(), 0);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("afterprint", clear);
    };
  }, [printOrder]);

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

  async function handleResetPassword(order: ApiOrder) {
    if (!token || !order.user_id) return;
    const who = order.customer_phone ?? order.customer_name;
    if (!window.confirm(`Выдать временный пароль покупателю ${who}? Старый пароль перестанет работать.`)) {
      return;
    }
    setError("");
    try {
      const result = await resetUserPassword(order.user_id, token);
      setNotice(
        `Временный пароль для ${result.phone ?? who}: ${result.temporary_password}. ` +
          "Продиктуйте его покупателю — войти можно сразу, потом пароль лучше сменить.",
      );
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сбросить пароль.");
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

  return (
    <>
      <CallbacksPanel token={token} onError={setError} />
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
                {FILTER_STATUSES.map((status) => (
                  <option key={status.value} value={status.value}>
                    {status.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="admin-btn admin-btn-outline"
                disabled={ordersLoading}

                onClick={() => void loadOrders()}

              >
                <Icon name="refresh" />
                {ordersLoading ? "Обновляем..." : "Обновить"}
              </button>
              <select
                value={exportPeriod}
                onChange={(event) => setExportPeriod(event.target.value)}
                aria-label="Период выгрузки"
              >
                <option value="30d">За 30 дней</option>
                <option value="90d">За 90 дней</option>
                <option value="all">За всё время</option>
              </select>
              <button
                type="button"
                className="admin-btn admin-btn-outline"
                disabled={exporting}
                onClick={() => void handleExport()}
                title="Файл для учёта: заказы и проданные позиции"
              >
                <Icon name="download" />
                {exporting ? "Готовим файл..." : "Скачать Excel"}
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
                        {orderStatusLabel(order.status, order.delivery_method)}
                      </span>
                      {order.delivery_method === "PICKUP" && (
                        <span className="admin-status admin-status-pickup">Самовывоз</span>
                      )}
                      <button
                        type="button"
                        className="admin-btn admin-btn-ghost admin-btn-sm admin-order-print"
                        onClick={() => setPrintOrder(order)}
                        title="Бланк заказа для водителя или покупателя"
                      >
                        <Icon name="print" size={14} />
                        Печать
                      </button>
                      {order.status === "CANCELLED" ? (
                        <div className="admin-order-cancelled-track">
                          <span className="admin-order-cancelled-dot" />
                          <span>Заказ отменён</span>
                        </div>
                      ) : (
                        <div
                          className="admin-order-progress"
                          aria-label={`Этап заказа: ${orderStatusLabel(order.status, order.delivery_method)}`}
                          style={{ "--steps": orderStages(order.delivery_method).length } as CSSProperties}
                        >
                          <div className="admin-order-progress-line">
                            <span
                              className="admin-order-progress-line-fill"
                              style={{
                                width: `${progressPercent(orderStages(order.delivery_method), order.status)}%`,
                              }}
                            />
                          </div>
                          {orderStages(order.delivery_method).map((status, index, stages) => {
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
                    {order.user_id && (
                      <button
                        type="button"
                        className="admin-btn admin-btn-ghost admin-btn-sm admin-reset-password"
                        onClick={() => void handleResetPassword(order)}
                        title="Временный пароль, если покупатель забыл свой и не подключил Telegram-бота"
                      >
                        <Icon name="key" size={14} />
                        Сбросить пароль
                      </button>
                    )}
                  </p>
                  <p>
                    <strong>
                      {order.delivery_method === "PICKUP" ? "Получение:" : "Адрес доставки:"}
                    </strong>{" "}
                    {order.delivery_method === "PICKUP"
                      ? "Самовывоз со склада"
                      : order.delivery_address || "Не указан"}
                  </p>
                  {order.comment && (
                    <p className="admin-order-comment">
                      <strong>Комментарий:</strong> {order.comment}
                    </p>
                  )}

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
                              {item.product_name ?? product?.name ?? `Товар №${item.product_id}`}

                              {item.variant_name && item.variant_name !== item.unit && ` (${item.variant_name})`} ×{" "}

                              {item.quantity} {item.unit}
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
                    {(order.allowed_statuses ?? []).length === 0 ? (
                      <span className="admin-order-final">
                        {order.status === "CANCELLED"
                          ? "Заказ отменён — статус больше не меняется"
                          : "Заказ завершён"}
                      </span>
                    ) : (
                      <div className="admin-order-actions">
                        {(order.allowed_statuses ?? []).map((status) => {
                          const isCancel = status === "CANCELLED";
                          return (
                            <button
                              key={status}
                              type="button"
                              className={
                                isCancel
                                  ? "admin-btn admin-btn-danger"
                                  : "admin-btn admin-btn-primary"
                              }
                              disabled={updatingOrderId === order.id}
                              onClick={() => {
                                if (
                                  isCancel &&
                                  !window.confirm(
                                    `Отменить заказ №${order.id}? Товар вернётся на склад.`,
                                  )
                                ) {
                                  return;
                                }
                                void handleOrderStatusChange(order.id, status);
                              }}
                            >
                              {isCancel && <Icon name="close" />}
                              {(order.delivery_method === "PICKUP" ? PICKUP_STATUS_ACTIONS : STATUS_ACTIONS)[status] ??
                                orderStatusLabel(status, order.delivery_method)}
                              {!isCancel && <Icon name="arrow" />}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {updatingOrderId === order.id && <span>Сохраняем статус...</span>}
                  </div>
                  {order.status_history?.length > 0 && (
                    <details className="admin-order-history">
                      <summary>История статусов</summary>
                      <ul>
                        {order.status_history.map((history) => (
                          <li key={history.id}>
                            <strong>
                              {orderStatusLabel(history.status, order.delivery_method)}
                            </strong>
                            {history.changed_by && (
                              <em className="admin-history-actor">{history.changed_by}</em>
                            )}

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
      {/* Бланк — прямо в body: всё остальное при печати скрыто */}
      {printOrder && createPortal(<OrderPrintSheet order={printOrder} />, document.body)}
    </>
  );
}
