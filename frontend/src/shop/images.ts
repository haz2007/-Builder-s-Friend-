import type { SyntheticEvent } from "react";

// Фото с Unsplash лежат на нашем сервере: браузер посетителя не ходит на зарубежный сайт
const FALLBACK_IMAGE = "/photos/boards-1.webp";

/**
 * Картинка нужной ширины. У Unsplash (пробные фото) ширина задаётся в адресе:
 * карточке хватает 600 px вместо 900–2000. Свои фото с сервера уже сжаты в
 * WebP до 1600 px и отдаются как есть.
 */
export function sizedImage(url: string, width: number): string {
  if (!url.includes("images.unsplash.com")) return url;
  return url.replace(/([?&])w=\d+/, `$1w=${width}`);
}

/**
 * Рисунок из каталога (public/catalog), а не фото самого товара. Его подписываем
 * «иллюстрацией»: упаковка на рисунке условная и может не совпадать с настоящей.
 */
export function isIllustration(url: string): boolean {
  return url.includes("/catalog/");
}

/** Если файл фото пропал с сервера, показываем запасную картинку. */
export function showFallbackImage(event: SyntheticEvent<HTMLImageElement>) {
  const image = event.currentTarget;
  if (image.dataset.fallback) return;
  image.dataset.fallback = "1";
  image.src = FALLBACK_IMAGE;
}
