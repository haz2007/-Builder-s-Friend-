"""Фото товаров: уменьшаем и пересохраняем в WebP перед записью на диск.

Снимок с телефона — 3–8 МБ и 4000 px; в каталоге он нужен шириной до
1600 px. После пересохранения — обычно 100–300 КБ: каталог быстро
открывается с мобильного интернета, а диск дешёвого сервера не забивается.
Заодно пропадают EXIF-метаданные телефона, в том числе GPS-координаты.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
WEBP_QUALITY = 82
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class BadImage(ValueError):
    """Файл — не картинка или формат не поддерживается."""


def compress_photo(contents: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(contents)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise BadImage("Разрешены только JPG, PNG и WebP")
            # Телефон пишет поворот в EXIF, а не в сами пиксели
            image = ImageOps.exif_transpose(source)
            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            result = io.BytesIO()
            image.save(result, "WEBP", quality=WEBP_QUALITY, method=6)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise BadImage("Загрузите корректное изображение JPG, PNG или WebP") from None
    return result.getvalue()
