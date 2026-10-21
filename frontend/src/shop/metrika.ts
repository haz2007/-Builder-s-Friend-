/**
 * Яндекс Метрика: сколько людей заходит, откуда и что смотрят.
 *
 * - Только в собранной версии сайта (в разработке и тестах — нет).
 * - Только витрина: в /admin счётчик не загружается — Вебвизор не должен
 *   видеть данные покупателей в админке.
 * - Загружается после страницы, когда браузер свободен, — не тормозит показ.
 * - Формы с личными данными скрыты от Вебвизора классом ym-hide-content
 *   (оформление, вход, кабинет, заявка).
 */

export const METRIKA_ID = 113724669;

type Ym = ((id: number, method: string, ...args: unknown[]) => void) & { a?: unknown[]; l?: number };

declare global {
  interface Window {
    ym?: Ym;
  }
}

let started = false;

export function startMetrika() {
  if (started || !import.meta.env.PROD || window.location.pathname.startsWith("/admin")) return;
  started = true;

  // Стандартная заглушка Метрики: вызовы копятся, пока грузится tag.js
  const ym: Ym = (...args) => {
    (ym.a = ym.a || []).push(args);
  };
  ym.l = Date.now();
  window.ym = ym;

  const load = () => {
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://mc.yandex.ru/metrika/tag.js";
    document.head.appendChild(script);
  };
  if ("requestIdleCallback" in window) window.requestIdleCallback(load, { timeout: 4000 });
  else setTimeout(load, 2000);

  ym(METRIKA_ID, "init", {
    // Просмотры при переходах внутри сайта шлём сами (trackPageView)
    defer: true,
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: true,
  });
}

/** Просмотр страницы — при каждом переходе внутри сайта. */
export function trackPageView(url: string, referrer?: string) {
  if (!window.ym || url.startsWith("/admin")) return;
  window.ym(METRIKA_ID, "hit", url, { referer: referrer, title: document.title });
}
