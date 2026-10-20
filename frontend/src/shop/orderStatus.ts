/** Статусы заказа — одинаковые подписи на сайте, в админке и в боте. */

export type DeliveryMethod = "DELIVERY" | "PICKUP" | undefined;

const LABELS: Record<string, string> = {
  NEW: "Новый",
  CONFIRMED: "Подтверждён",
  PREPARING: "Готовится",
  READY_FOR_DELIVERY: "Готов к доставке",
  // Этап, который был раньше; остался в истории старых заказов
  ASSIGNED_TO_DRIVER: "Назначен водитель",
  ON_THE_WAY: "В пути",
  DELIVERED: "Доставлен",
  CANCELLED: "Отменён",
};

// Самовывоз: заказ не везут, а выдают на складе
const PICKUP_LABELS: Record<string, string> = {
  ...LABELS,
  READY_FOR_DELIVERY: "Готов к выдаче",
  DELIVERED: "Выдан",
};

export function orderStatusLabel(status: string, method?: DeliveryMethod) {
  return (method === "PICKUP" ? PICKUP_LABELS : LABELS)[status] ?? status;
}

/** Этапы на шкале заказа: у самовывоза нет «В пути». */
export function orderStages(method?: DeliveryMethod) {
  const stages = ["NEW", "CONFIRMED", "PREPARING", "READY_FOR_DELIVERY", "ON_THE_WAY", "DELIVERED"]
    .filter((status) => method !== "PICKUP" || status !== "ON_THE_WAY");
  return stages.map((value) => ({ value, label: orderStatusLabel(value, method) }));
}

/** Для фильтра заказов в админке: все статусы, кроме убранного этапа. */
export const FILTER_STATUSES = [...orderStages("DELIVERY"), { value: "CANCELLED", label: LABELS.CANCELLED }];
