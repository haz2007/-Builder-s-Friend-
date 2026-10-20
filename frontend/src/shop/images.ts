import type { SyntheticEvent } from "react";

const FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1513467655676-561b7d489a88?auto=format&fit=crop&w=900&q=85";

/** Если файл фото пропал с сервера, показываем запасную картинку. */
export function showFallbackImage(event: SyntheticEvent<HTMLImageElement>) {
  const image = event.currentTarget;
  if (image.dataset.fallback) return;
  image.dataset.fallback = "1";
  image.src = FALLBACK_IMAGE;
}
