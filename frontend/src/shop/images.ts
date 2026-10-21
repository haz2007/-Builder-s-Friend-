import type { SyntheticEvent } from "react";

const FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1513467655676-561b7d489a88?auto=format&fit=crop&w=900&q=85";

/**
 * Картинка нужной ширины. У Unsplash (пробные фото) ширина задаётся в адресе:
 * карточке хватает 600 px вместо 900–2000. Свои фото с сервера уже сжаты в
 * WebP до 1600 px и отдаются как есть.
 */
export function sizedImage(url: string, width: number): string {
  if (!url.includes("images.unsplash.com")) return url;
  return url.replace(/([?&])w=\d+/, `$1w=${width}`);
}

/** Если файл фото пропал с сервера, показываем запасную картинку. */
export function showFallbackImage(event: SyntheticEvent<HTMLImageElement>) {
  const image = event.currentTarget;
  if (image.dataset.fallback) return;
  image.dataset.fallback = "1";
  image.src = FALLBACK_IMAGE;
}
