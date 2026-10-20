import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./AdminIcons";

import { getActivity, type ApiActivityEntry } from "./api";

type Props = {
  token: string;
  onError: (message: string) => void;
};

/** Журнал: кто и когда менял статусы заказов — покупатели и администраторы. */
export default function ActivitySection({ token, onError }: Props) {
  const [entries, setEntries] = useState<ApiActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEntries(await getActivity(token));
    } catch (error) {
      onError(error instanceof Error ? error.message : "Не удалось загрузить журнал.");
    } finally {
      setLoading(false);
    }
  }, [token, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="admin-card">
      <div className="admin-list-heading">
        <div>
          <h2>Журнал действий</h2>
          <p>Кто и когда менял статусы заказов. Последние 100 записей, новые сверху.</p>
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

      {!loading && entries.length === 0 ? (
        <p className="admin-hint">Записей пока нет.</p>
      ) : (
        <ol className="admin-activity">
          {entries.map((entry) => (
            <li key={entry.id} className={`admin-activity-row is-${entry.status.toLowerCase()}`}>
              <time dateTime={entry.created_at}>
                {new Date(entry.created_at).toLocaleString("ru-RU", {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
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
      )}
    </section>
  );
}
