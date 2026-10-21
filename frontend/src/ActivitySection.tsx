import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./AdminIcons";

import { getActivity, getAudit, type ApiActivityEntry, type ApiAuditEntry } from "./api";

type Props = {
  token: string;
  onError: (message: string) => void;
};

type Tab = "orders" | "changes";

// Подписи действий журнала изменений
const ACTION_LABELS: Record<string, string> = {
  "product.created": "Новый товар",
  "product.updated": "Товар изменён",
  "product.hidden": "Скрыт",
  "product.restored": "Возвращён",
  "product.stock": "Остаток",
  "product.photo": "Фото",
  "variant.created": "Новый вариант",
  "variant.updated": "Вариант изменён",
  "variant.hidden": "Вариант скрыт",
  "variant.deleted": "Вариант удалён",
  "category.created": "Новая категория",
  "category.updated": "Категория изменена",
  "category.deleted": "Категория удалена",
  "admin.added": "Новый админ",
  "admin.removed": "Снят админ",
  "user.role": "Роль",
  "password.reset": "Сброс пароля",
};

const shortDate = (iso: string) =>
  new Date(iso).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Журнал: смены статусов заказов и изменения товаров и настроек — кто и когда. */
export default function ActivitySection({ token, onError }: Props) {
  const [tab, setTab] = useState<Tab>("orders");
  const [orders, setOrders] = useState<ApiActivityEntry[]>([]);
  const [changes, setChanges] = useState<ApiAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [orderEntries, auditEntries] = await Promise.all([getActivity(token), getAudit(token)]);
      setOrders(orderEntries);
      setChanges(auditEntries);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Не удалось загрузить журнал.");
    } finally {
      setLoading(false);
    }
  }, [token, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  const empty = tab === "orders" ? orders.length === 0 : changes.length === 0;

  return (
    <section className="admin-card">
      <div className="admin-list-heading">
        <div>
          <h2>Журнал действий</h2>
          <p>Кто и когда что менял. Последние 100 записей, новые сверху.</p>
        </div>
        <div className="admin-row-actions">
          <button
            type="button"
            className="admin-btn admin-btn-outline"
            disabled={loading}
            onClick={() => void load()}
          >
            <Icon name="refresh" />
            {loading ? "Обновляем..." : "Обновить"}
          </button>
        </div>
      </div>

      <div className="admin-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "orders"}
          className={tab === "orders" ? "is-active" : ""} onClick={() => setTab("orders")}>
          Заказы
        </button>
        <button type="button" role="tab" aria-selected={tab === "changes"}
          className={tab === "changes" ? "is-active" : ""} onClick={() => setTab("changes")}>
          Товары и настройки
        </button>
      </div>

      {!loading && empty ? (
        <p className="admin-hint">Записей пока нет.</p>
      ) : tab === "orders" ? (
        <ol className="admin-activity">
          {orders.map((entry) => (
            <li key={entry.id} className={`admin-activity-row is-${entry.status.toLowerCase()}`}>
              <time dateTime={entry.created_at}>{shortDate(entry.created_at)}</time>
              <div>
                <strong>
                  <Link to="/admin/orders">Заказ №{entry.order_id}</Link> → {entry.status_name}
                </strong>
                <span>
                  {entry.customer_name} · {Number(entry.total_price).toLocaleString("ru-RU")} ₽
                </span>
              </div>
              <em>{entry.changed_by ?? "до появления журнала"}</em>
            </li>
          ))}
        </ol>
      ) : (
        <ol className="admin-activity">
          {changes.map((entry) => (
            <li key={entry.id} className={`admin-activity-row is-${entry.action.replace(".", "-")}`}>
              <time dateTime={entry.created_at}>{shortDate(entry.created_at)}</time>
              <div>
                <strong>{ACTION_LABELS[entry.action] ?? entry.action}</strong>
                <span>{entry.summary}</span>
              </div>
              <em>{entry.actor ?? "—"}</em>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
