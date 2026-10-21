/**
 * Маска российского номера: «+7 999 123-45-67».
 * Покупатель вводит только цифры — «+7» уже стоит; вставка «8 999…» или
 * «+7 (999)…» тоже превращается в этот вид. Сервер сам приводит номер
 * к одному формату, так что маска — только для удобства.
 */

export const PHONE_PREFIX = "+7 ";
export const PHONE_PATTERN = "\\+7 \\d{3} \\d{3}-\\d{2}-\\d{2}";

/** Десять цифр номера без кода страны. */
export function phoneDigits(value: string): string {
  let digits = value.replace(/\D/g, "");
  // «+7» из самого поля — это код страны, а не первая цифра номера
  if (value.trim().startsWith("+7")) digits = digits.slice(1);
  // Вставили номер целиком («8 999…», «+7 999…») поверх «+7 » — ещё один код страны
  if (digits.length >= 11 && /^[78]/.test(digits)) digits = digits.slice(1);
  return digits.slice(0, 10);
}

export function formatPhone(value: string): string {
  const d = phoneDigits(value);
  if (!d) return "";
  let result = PHONE_PREFIX + d.slice(0, 3);
  if (d.length > 3) result += " " + d.slice(3, 6);
  if (d.length > 6) result += "-" + d.slice(6, 8);
  if (d.length > 8) result += "-" + d.slice(8, 10);
  return result;
}

export function isCompletePhone(value: string): boolean {
  return phoneDigits(value).length === 10;
}
