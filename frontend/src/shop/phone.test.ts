import { describe, expect, it } from "vitest";

import { formatPhone, isCompletePhone } from "./phone";

describe("маска телефона", () => {
  it("набираешь цифры — «+7» и разделители появляются сами", () => {
    expect(formatPhone("9")).toBe("+7 9");
    expect(formatPhone("+7 9991")).toBe("+7 999 1");
    expect(formatPhone("+7 999 123-456")).toBe("+7 999 123-45-6");
    expect(formatPhone("9991234567")).toBe("+7 999 123-45-67");
  });

  it("вставка в любом виде приводится к одному", () => {
    expect(formatPhone("8 (999) 123-45-67")).toBe("+7 999 123-45-67");
    expect(formatPhone("+7(999)1234567")).toBe("+7 999 123-45-67");
    expect(formatPhone("79991234567")).toBe("+7 999 123-45-67");
  });

  it("вставка полного номера в поле, где уже стоит «+7 »", () => {
    expect(formatPhone("+7 +79991234567")).toBe("+7 999 123-45-67");
    expect(formatPhone("+7 89991234567")).toBe("+7 999 123-45-67");
  });

  it("лишние цифры отбрасываются, пустое поле остаётся пустым", () => {
    expect(formatPhone("+7 999 123-45-678")).toBe("+7 999 123-45-67");
    expect(formatPhone("+7 ")).toBe("");
    expect(formatPhone("")).toBe("");
  });

  it("городской номер с 8 в начале после +7 не теряет цифру", () => {
    expect(formatPhone("+7 812")).toBe("+7 812");
  });

  it("полный номер — 10 цифр", () => {
    expect(isCompletePhone("+7 999 123-45-67")).toBe(true);
    expect(isCompletePhone("+7 999 123")).toBe(false);
  });
});
