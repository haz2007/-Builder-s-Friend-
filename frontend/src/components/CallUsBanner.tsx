import { Phone, PhoneCall } from "lucide-react";

import { PHONES, WORKING_HOURS } from "../shop/contacts";
import { useShop } from "../shop/ShopContext";

/** «Не нашли нужное?» — под товарами каталога и когда поиск ничего не нашёл. */
export default function CallUsBanner() {
  const { openCallUs } = useShop();
  const [main, ...others] = PHONES;

  return (
    <aside className="call-us-banner">
      <span className="call-us-banner-icon" aria-hidden="true">
        <PhoneCall size={22} />
      </span>
      <div>
        <h3>Не нашли нужное?</h3>
        <p>
          Позвоните — подскажем, что есть на складе, или привезём под заказ. Другой размер, большой
          объём, доставка к сроку — договоримся.
        </p>
        <div className="call-us-banner-actions">
          <a className="call-us-banner-main" href={main.href}>
            <Phone size={16} />
            {main.display}
          </a>
          {others.map((phone) => (
            <a key={phone.href} href={phone.href}>
              <Phone size={16} />
              {phone.display}
            </a>
          ))}
          <button type="button" onClick={() => openCallUs({ callback: true })}>
            Перезвоните мне
          </button>
        </div>
        <small>{WORKING_HOURS}</small>
      </div>
    </aside>
  );
}
