import { ArrowRight } from "lucide-react";
import { useState, type FormEvent } from "react";

import { createCallbackRequest } from "../api";
import type { CartEntry } from "../shop/types";
import ConsentCheckbox from "./ConsentCheckbox";
import PhoneInput from "./PhoneInput";

/**
 * Заказ без регистрации: имя и телефон, корзина уходит менеджеру.
 * Он перезванивает и оформляет заказ во время разговора.
 */
export default function CallbackForm({
  cart,
  initialName,
  initialComment,
  intro = "Оставьте имя и телефон — перезвоним в рабочее время, уточним заказ и доставку. Регистрироваться и придумывать пароль не нужно.",
  cancelLabel = "← Оформить заказ самому",
  onDone,
  onCancel,
}: {
  cart: CartEntry[];
  initialName: string;
  initialComment: string;
  intro?: string;
  cancelLabel?: string;
  onDone: (requestId: number) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initialName);
  const [phone, setPhone] = useState("");
  const [comment, setComment] = useState(initialComment);
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSending(true);
    try {
      const request = await createCallbackRequest({
        name: name.trim(),
        phone: phone.trim(),
        comment: comment.trim(),
        items: cart.map((entry) => ({ variant_id: entry.variant.id, quantity: entry.quantity })),
        privacy_accepted: true,
      });
      onDone(request.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось отправить заявку.");
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="checkout-form" onSubmit={handleSubmit}>
      <p className="checkout-description">{intro}</p>
      <label className="checkout-field">
        <span>Как к вам обращаться?</span>
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Ваше имя"
          autoComplete="name"
          minLength={2}
          maxLength={100}
          required
        />
      </label>
      <label className="checkout-field">
        <span>Номер телефона</span>
        <PhoneInput value={phone} onChange={setPhone} required />
      </label>
      <label className="checkout-field">
        <span>
          Комментарий <small className="checkout-optional">— необязательно</small>
        </span>
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Например: нужен распил, удобно звонить после 18:00"
          maxLength={500}
          rows={2}
        />
      </label>
      <ConsentCheckbox checked={consent} onChange={setConsent} />
      {error && (
        <p className="checkout-error" role="alert">
          {error}
        </p>
      )}
      <button className="button button-primary checkout-button" type="submit" disabled={sending || !consent}>
        {sending ? "Отправляем..." : "Жду звонка"}
        {!sending && <ArrowRight size={18} />}
      </button>
      <button type="button" className="checkout-switch" onClick={onCancel}>
        {cancelLabel}
      </button>
    </form>
  );
}
