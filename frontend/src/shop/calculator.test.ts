import { describe, expect, it } from "vitest";

import { piecesForArea, piecesForLength, volumeOf } from "./calculator";

const board = { thickness: 50, width: 150, length: 6000 }; // 0,9 м² и 0,045 м³ на доску

describe("калькулятор материала", () => {
  it("площадь: 20 м² пола + 10 % запаса → 25 досок", () => {
    // 20 × 1,1 / 0,9 = 24,4 → 25
    expect(piecesForArea(20, board)).toBe(25);
  });

  it("ровное число не округляется вверх лишний раз", () => {
    expect(piecesForArea(9, board, 0)).toBe(10);
  });

  it("длина: 40 м обвязки → 8 досок по 6 м", () => {
    // 40 × 1,1 / 6 = 7,3 → 8
    expect(piecesForLength(40, board)).toBe(8);
  });

  it("пустой или отрицательный ввод — ноль", () => {
    expect(piecesForArea(0, board)).toBe(0);
    expect(piecesForLength(-5, board)).toBe(0);
    expect(piecesForArea(Number.NaN, board)).toBe(0);
  });

  it("объём в кубах", () => {
    expect(volumeOf(25, board)).toBeCloseTo(1.125);
  });
});
