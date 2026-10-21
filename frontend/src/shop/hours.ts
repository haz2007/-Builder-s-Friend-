import { CLOSE_HOUR, OPEN_HOUR } from "./contacts";

/** Час по Москве: склад работает по местному времени, где бы ни был покупатель. */
export function moscowHour(now: Date = new Date()): number {
  const hour = new Intl.DateTimeFormat("ru-RU", {
    hour: "numeric",
    hourCycle: "h23",
    timeZone: "Europe/Moscow",
  }).format(now);
  return Number(hour);
}

/** «Сейчас открыто» или когда откроемся — для главной страницы. */
export function storeStatus(now: Date = new Date()): { open: boolean; text: string } {
  const hour = moscowHour(now);
  if (hour >= OPEN_HOUR && hour < CLOSE_HOUR) {
    return { open: true, text: "Открыто, без выходных" };
  }
  return { open: false, text: hour < OPEN_HOUR ? `Откроемся в ${OPEN_HOUR}:00` : `Откроемся завтра в ${OPEN_HOUR}:00` };
}
