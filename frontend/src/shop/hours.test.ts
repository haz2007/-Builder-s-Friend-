import { describe, expect, it } from "vitest";

import { moscowHour, storeStatus } from "./hours";

// Москва — UTC+3 круглый год
const atMoscow = (hour: number) => new Date(Date.UTC(2026, 9, 21, hour - 3, 30));

describe("часы работы", () => {
  it("считает время по Москве", () => {
    expect(moscowHour(atMoscow(10))).toBe(10);
  });

  it("открыто с 9:00 до 19:00", () => {
    expect(storeStatus(atMoscow(9)).open).toBe(true);
    expect(storeStatus(atMoscow(18)).open).toBe(true);
    expect(storeStatus(atMoscow(19)).open).toBe(false);
  });

  it("подсказывает, открыто ли и когда откроемся", () => {
    expect(storeStatus(atMoscow(12)).text).toBe("Открыто, без выходных");
    expect(storeStatus(atMoscow(7)).text).toBe("Откроемся в 9:00");
    expect(storeStatus(atMoscow(22)).text).toBe("Откроемся завтра в 9:00");
  });
});
