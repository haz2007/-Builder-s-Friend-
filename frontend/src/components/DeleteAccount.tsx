import { Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { deleteAccount } from "../api";

/**
 * Удаление аккаунта из личного кабинета. Телефон и привязка Telegram
 * удаляются; записи о заказах магазин хранит для учёта.
 */
export default function DeleteAccount({ token, onDeleted }: { token: string; onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSending(true);
    try {
      await deleteAccount(token, password);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить аккаунт.");
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <div className="account-delete-intro">
        <p>Телефон и привязка к Telegram удалятся, войти будет нельзя.</p>
        <button type="button" className="button account-delete-button" onClick={() => setOpen(true)}>
          <Trash2 size={16} />
          Удалить аккаунт
        </button>
      </div>
    );
  }

  return (
    <form className="account-delete" onSubmit={handleSubmit}>
      <strong>Удалить аккаунт?</strong>
      <p>
        Телефон, привязка к Telegram-боту и уведомления удалятся, войти будет нельзя.
        Записи о прошлых заказах магазин хранит для учёта, как требует закон.
      </p>
      <label className="checkout-field">
        <span>Пароль для подтверждения</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {error && (
        <p className="checkout-error" role="alert">
          {error}
        </p>
      )}
      <div className="account-delete-actions">
        <button type="submit" className="button account-delete-confirm" disabled={sending}>
          <Trash2 size={16} />
          {sending ? "Удаляем..." : "Удалить навсегда"}
        </button>
        <button type="button" className="button button-light" onClick={() => setOpen(false)}>
          Отмена
        </button>
      </div>
    </form>
  );
}
