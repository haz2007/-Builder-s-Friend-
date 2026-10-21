import { describe, expect, it } from "vitest";

import { FILTER_STATUSES, orderStages, orderStatusLabel } from "./orderStatus";

describe("статусы заказа", () => {
  it("у самовывоза свои подписи", () => {
    expect(orderStatusLabel("READY_FOR_DELIVERY", "DELIVERY")).toBe("Готов к доставке");
    expect(orderStatusLabel("READY_FOR_DELIVERY", "PICKUP")).toBe("Готов к выдаче");
    expect(orderStatusLabel("DELIVERED", "PICKUP")).toBe("Выдан");
  });

  it("неизвестный статус показывается как есть", () => {
    expect(orderStatusLabel("SOMETHING")).toBe("SOMETHING");
  });

  it("у самовывоза на шкале нет этапа «В пути»", () => {
    const pickup = orderStages("PICKUP").map((stage) => stage.value);
    expect(pickup).not.toContain("ON_THE_WAY");
    expect(pickup.at(-1)).toBe("DELIVERED");
    expect(orderStages("DELIVERY")).toHaveLength(6);
  });

  it("в фильтре админки есть отмена, но нет старого этапа с водителем", () => {
    const values = FILTER_STATUSES.map((status) => status.value);
    expect(values).toContain("CANCELLED");
    expect(values).not.toContain("ASSIGNED_TO_DRIVER");
  });
});
