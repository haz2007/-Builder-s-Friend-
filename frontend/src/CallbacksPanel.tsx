import { useEffect, useState } from "react";

import { getCallbackRequests, markCallbackDone } from "./api";
import type { ApiCallbackRequest } from "./api";
import { Icon } from "./AdminIcons";

/** Заявки «перезвоните мне» над списком заказов. Пустой блок не показывается. */
export default function CallbacksPanel({
  token,
  onError,
}: {
  token: string;
  onError: (message: string) => void;
}) {
  const [requests, setRequests] = useState<ApiCallbackRequest[]>([]);
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getCallbackRequests(token, "NEW")
        .then((loaded) => {
          if (!cancelled) setRequests(loaded);
        })
        .catch((err) => console.error("Не удалось загрузить заявки:", err));
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [token]);

  async function handleDone(request: ApiCallbackRequest) {
    setSavingId(request.id);
    try {
      await markCallbackDone(request.id, token);
      setRequests((current) => current.filter((item) => item.id !== request.id));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Не удалось отметить заявку.");
    } finally {
      setSavingId(null);
    }
  }

  if (requests.length === 0) return null;

  return (
    <section className="admin-card admin-callbacks">
      <h2>Перезвонить · {requests.length}</h2>
      <p>Покупатели оставили телефон без регистрации. После звонка отметьте заявку.</p>
      <ul className="admin-callback-list">
        {requests.map((request) => (
          <li key={request.id} className="admin-callback">
            <div className="admin-callback-main">
              <strong>{request.name}</strong>
              <a href={`tel:${request.phone}`}>{request.phone}</a>
              <span>
                №{request.id} · {new Date(request.created_at).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" })}
              </span>
            </div>
            {request.comment && <p className="admin-order-comment">{request.comment}</p>}
            {request.cart_summary && (
              <div className="admin-callback-cart">
                {request.cart_summary.split("\n").map((line) => (
                  <span key={line}>{line}</span>
                ))}
                <b>Примерно {request.cart_total?.toLocaleString("ru-RU")} ₽</b>
              </div>
            )}
            <button
              type="button"
              className="admin-btn admin-btn-primary admin-btn-sm"
              disabled={savingId === request.id}
              onClick={() => void handleDone(request)}
            >
              <Icon name="save" size={15} />
              Перезвонили
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
