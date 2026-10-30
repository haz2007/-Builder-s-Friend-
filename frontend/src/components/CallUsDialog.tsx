import { Check, Phone, X } from "lucide-react";
import { useState } from "react";

import { PHONES, WORKING_HOURS } from "../shop/contacts";
import CallbackForm from "./CallbackForm";

/**
 * «Заказать по телефону»: товар под заказ или то, чего нет в каталоге.
 * Номера магазина и заявка «Перезвоните мне» без корзины.
 */
export default function CallUsDialog({
  product,
  callback = false,
  onClose,
}: {
  product?: string;
  /** Сразу открыть «Перезвоните мне» */
  callback?: boolean;
  onClose: () => void;
}) {
  const [callbackMode, setCallbackMode] = useState(callback);
  const [requestId, setRequestId] = useState<number | null>(null);

  return (
    <div className="cart-overlay checkout-overlay" onClick={onClose}>
      <section className="checkout-panel ym-hide-content" onClick={(event) => event.stopPropagation()}>
        <div className="cart-header">
          <div>
            <span className="eyebrow">ДРУГ СТРОИТЕЛЯ</span>
            <h2>{requestId !== null ? "Заявка принята" : callbackMode ? "Перезвоните мне" : "Заказать по телефону"}</h2>
          </div>
          <button className="close-cart" onClick={onClose} aria-label="Закрыть">
            <X size={22} />
          </button>
        </div>

        {requestId !== null ? (
          <div className="checkout-success">
            <span className="checkout-success-icon">
              <Check size={32} />
            </span>
            <h3>Перезвоним!</h3>
            <p>
              Заявка <strong>№{requestId}</strong> уже у менеджера. Позвоним в рабочее время —{" "}
              {WORKING_HOURS.toLowerCase()}.
            </p>
            <button className="button button-dark checkout-button" onClick={onClose}>
              Продолжить покупки
            </button>
          </div>
        ) : callbackMode ? (
          <CallbackForm
            cart={[]}
            initialName=""
            initialComment={product ? `Под заказ: ${product}` : ""}
            intro="Оставьте имя и телефон — перезвоним в рабочее время, расскажем про сроки и цену."
            cancelLabel="← Назад к телефонам"
            onDone={setRequestId}
            onCancel={() => setCallbackMode(false)}
          />
        ) : (
          <div className="call-us-body">
            <p className="checkout-description">
              {product ? (
                <>
                  <strong>{product}</strong> сейчас нет на складе — привезём под заказ. Позвоните: назовём
                  срок и цену.
                </>
              ) : (
                <>Подскажем, что есть на складе, или привезём под заказ. Другой размер, большой объём — договоримся.</>
              )}
            </p>
            <div className="call-us-phones">
              {PHONES.map((phone) => (
                <a key={phone.href} className="button button-dark" href={phone.href}>
                  <Phone size={17} />
                  {phone.display}
                </a>
              ))}
            </div>
            <p className="call-us-hours">{WORKING_HOURS}</p>
            <button type="button" className="checkout-switch" onClick={() => setCallbackMode(true)}>
              Не можете позвонить? Перезвоним сами →
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
