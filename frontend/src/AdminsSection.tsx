import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  addAdmin,
  getAdmins,
  removeAdmin,
  type ApiAdmin,
  type AuthUser,
} from "./api";

type Props = {
  token: string;
  user: AuthUser;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

/** Администраторы магазина. Менять список может только владелец. */
export default function AdminsSection({ token, user, onError, onNotice }: Props) {
  const [admins, setAdmins] = useState<ApiAdmin[]>([]);
  const [login, setLogin] = useState("");
  const [busy, setBusy] = useState(false);
  const isOwner = user.is_owner === 1;

  const load = useCallback(async () => {
    try {
      setAdmins(await getAdmins(token));
    } catch (error) {
      onError(error instanceof Error ? error.message : "Не удалось загрузить администраторов.");
    }
  }, [token, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!login.trim()) return;

    setBusy(true);
    onError("");
    try {
      const admin = await addAdmin(login.trim(), token);
      onNotice(`${admin.phone ?? admin.email} теперь администратор.`);
      setLogin("");
      await load();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Не удалось добавить администратора.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(admin: ApiAdmin) {
    const name = admin.phone ?? admin.email ?? `№${admin.id}`;
    if (!window.confirm(`Снять права администратора с ${name}?`)) return;

    setBusy(true);
    onError("");
    try {
      await removeAdmin(admin.id, token);
      onNotice(`${name} больше не администратор.`);
      await load();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Не удалось снять права.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="admin-card">
      <div className="admin-list-heading">
        <div>
          <h2>Администраторы</h2>
          <p>
            {isOwner
              ? "Ты владелец магазина: можешь назначать и снимать администраторов."
              : "Список меняет только владелец магазина."}
          </p>
        </div>
      </div>

      {isOwner && (
        <form className="admin-admins-form" onSubmit={handleAdd}>
          <label>
            Телефон или email пользователя
            <input
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              placeholder="+7 999 123-45-67"
              maxLength={255}
            />
          </label>
          <button className="admin-primary" disabled={busy || !login.trim()}>
            Сделать администратором
          </button>
          <p className="admin-hint">
            Человек должен сначала зарегистрироваться на сайте по номеру
            телефона. После назначения он входит в админку и в Telegram-бота
            тем же телефоном и паролем.
          </p>
        </form>
      )}

      <div className="admin-admins-list">
        {admins.map((admin) => (
          <div className="admin-admins-row" key={admin.id}>
            <div>
              <strong>{admin.phone ?? admin.email}</strong>
              <span>
                {admin.is_owner === 1 ? "👑 Владелец" : "Администратор"}
                {admin.id === user.id && " · это ты"}
              </span>
            </div>
            <span
              className={`admin-badge ${admin.has_telegram ? "is-on" : ""}`}
              title="Получает уведомления о заказах в Telegram-боте"
            >
              {admin.has_telegram ? "Telegram подключён" : "Без Telegram"}
            </span>
            {isOwner && admin.is_owner !== 1 && admin.id !== user.id && (
              <button
                type="button"
                className="admin-secondary"
                disabled={busy}
                onClick={() => handleRemove(admin)}
              >
                Снять права
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
