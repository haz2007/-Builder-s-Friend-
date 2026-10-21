import type { ApiOrder } from "./api";
import { PHONES, SELLER, STORE_LOCATION, STORE_NAME } from "./shop/contacts";
import { orderStatusLabel } from "./shop/orderStatus";

const money = (value: number) =>
  `${value.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ₽`;

/**
 * Бланк заказа для печати: отдать водителю или покупателю при выдаче.
 * Виден только при печати (@media print в Admin.css).
 */
export default function OrderPrintSheet({ order }: { order: ApiOrder }) {
  const date = order.created_at
    ? new Date(order.created_at).toLocaleString("ru-RU", { dateStyle: "long", timeStyle: "short" })
    : "";
  const pickup = order.delivery_method === "PICKUP";

  return (
    <article className="print-sheet" aria-hidden="true">
      <header className="print-sheet-head">
        <div>
          <h1>Заказ №{order.id}</h1>
          {date && <p>от {date}</p>}
        </div>
        <div className="print-sheet-store">
          <strong>{STORE_NAME}</strong>
          <span>{SELLER.name}, ОГРНИП {SELLER.ogrnip}, ИНН {SELLER.inn}</span>
          {STORE_LOCATION && <span>{STORE_LOCATION.address}</span>}
          <span>{PHONES.map((phone) => phone.display).join(", ")}</span>
        </div>
      </header>

      <dl className="print-sheet-info">
        <dt>Покупатель</dt>
        <dd>
          {order.customer_name || "—"}
          {order.customer_phone ? `, ${order.customer_phone}` : ""}
        </dd>
        <dt>{pickup ? "Получение" : "Адрес доставки"}</dt>
        <dd>{pickup ? "Самовывоз со склада" : order.delivery_address}</dd>
        <dt>Статус</dt>
        <dd>{orderStatusLabel(order.status, order.delivery_method)}</dd>
      </dl>

      <table className="print-sheet-items">
        <thead>
          <tr>
            <th>№</th>
            <th>Товар</th>
            <th>Кол-во</th>
            <th>Цена</th>
            <th>Сумма</th>
          </tr>
        </thead>
        <tbody>
          {order.items.map((item, index) => (
            <tr key={item.id}>
              <td>{index + 1}</td>
              <td>
                {item.product_name ?? `Товар №${item.product_id}`}
                {item.variant_name && item.variant_name !== item.unit ? ` (${item.variant_name})` : ""}
              </td>
              <td>
                {item.quantity.toLocaleString("ru-RU")} {item.unit}
              </td>
              <td>{money(item.price)}</td>
              <td>{money(item.price * item.quantity)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={4}>Итого</td>
            <td>{money(order.total_price)}</td>
          </tr>
        </tfoot>
      </table>

      {!pickup && <p className="print-sheet-note">Стоимость доставки — по договорённости, в сумму не входит.</p>}

      <div className="print-sheet-signatures">
        <span>Выдал ____________________</span>
        <span>Получил, претензий к количеству и качеству нет ____________________</span>
      </div>
    </article>
  );
}
