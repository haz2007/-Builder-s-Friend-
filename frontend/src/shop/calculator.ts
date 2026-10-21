/**
 * Калькулятор материала: сколько штук нужно на площадь или длину.
 * Считаем по номинальным размерам доски и добавляем запас на подрезку.
 */

export const DEFAULT_RESERVE = 0.1;

export type Dimensions = { thickness: number; width: number; length: number };

/** Штук на площадь (пол, обшивка): площадь ÷ площадь одной доски, с запасом. */
export function piecesForArea(area: number, size: Dimensions, reserve = DEFAULT_RESERVE): number {
  const pieceArea = (size.width / 1000) * (size.length / 1000);
  if (!(area > 0) || !(pieceArea > 0)) return 0;
  return Math.ceil((area * (1 + reserve)) / pieceArea - 1e-9);
}

/** Штук на погонные метры (каркас, обвязка, лаги). */
export function piecesForLength(meters: number, size: Dimensions, reserve = DEFAULT_RESERVE): number {
  const pieceLength = size.length / 1000;
  if (!(meters > 0) || !(pieceLength > 0)) return 0;
  return Math.ceil((meters * (1 + reserve)) / pieceLength - 1e-9);
}

/** Объём штук в м³ — чтобы сравнить с ценой за куб. */
export function volumeOf(pieces: number, size: Dimensions): number {
  return (pieces * size.thickness * size.width * size.length) / 1_000_000_000;
}
