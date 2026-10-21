"""SEO для одностраничного сайта.

Сайт на React отдаёт один и тот же index.html на любой адрес, поэтому
поисковик без JavaScript видит пустую страницу. Caddy при отдаче
index.html вставляет в <head> ответ /api/v1/seo/head (директива templates,
httpInclude): заголовок, описание, превью для мессенджеров и разметку
schema.org — магазин на главной, товар с ценой на странице товара.
"""

import html
import json
import re
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, selectinload

from .. import store_info
from ..database import get_db
from ..models import Category, Product
from ..services.variant_service import get_primary_variant

router = APIRouter(prefix="/api/v1/seo", tags=["SEO"])

DEFAULT_DESCRIPTION = (
    "Обрезная доска, брус, вагонка, крепёж и листовые материалы. Поштучно и кубами, "
    f"доставка на объект или самовывоз в Химках. {store_info.YEARS_ON_MARKET} лет на рынке."
)
STATIC_PAGES = {
    "/delivery": ("Доставка и возврат", "Как мы привозим заказы, самовывоз со склада и правила возврата товара."),
    "/privacy": ("Политика конфиденциальности", "Как магазин обрабатывает и защищает персональные данные."),
    "/consent": ("Согласие на обработку персональных данных", "Текст согласия на обработку персональных данных."),
}


def site_url(host: str, scheme: str) -> str:
    # Хост приходит от Caddy; на всякий случай оставляем только допустимые символы
    host = re.sub(r"[^A-Za-z0-9.\-:\[\]]", "", host) or "localhost"
    scheme = "https" if scheme == "https" else "http"
    return f"{scheme}://{host}"


def absolute(base: str, url: str | None) -> str:
    if not url:
        return f"{base}/og-image.jpg"
    return url if url.startswith("http") else f"{base}{url}"


def store_schema(base: str) -> dict[str, Any]:
    """Магазин для Яндекса и Google: адрес, телефоны, часы работы, точка на карте."""
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "HardwareStore",
        "name": store_info.STORE_NAME,
        "url": f"{base}/",
        "image": f"{base}/og-image.jpg",
        "description": DEFAULT_DESCRIPTION,
        "telephone": store_info.PHONES,
        "openingHours": "Mo-Su 09:00-19:00",
        "priceRange": "₽₽",
    }
    if store_info.ADDRESS:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": store_info.ADDRESS,
            "addressRegion": "Московская область",
            "addressCountry": "RU",
        }
    if store_info.LATITUDE and store_info.LONGITUDE:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": store_info.LATITUDE, "longitude": store_info.LONGITUDE}
    if store_info.YANDEX_MAPS_URL:
        data["sameAs"] = [store_info.YANDEX_MAPS_URL]
    return data


def product_schema(base: str, product: Product) -> dict[str, Any]:
    variant = get_primary_variant(product)
    price = variant.price if variant else product.price
    in_stock = product.stock_quantity > 0
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.description or product.name,
        "image": absolute(base, product.image_url),
        "category": product.category.name if product.category else None,
        "offers": {
            "@type": "Offer",
            "price": f"{price:.2f}",
            "priceCurrency": "RUB",
            "availability": f"https://schema.org/{'InStock' if in_stock else 'OutOfStock'}",
            "url": f"{base}/product/{product.id}",
            "seller": {"@type": "Organization", "name": store_info.STORE_NAME},
        },
    }


def render_head(
    title: str,
    description: str,
    url: str,
    image: str,
    schema: dict[str, Any] | None = None,
    og_type: str = "website",
    index: bool = True,
) -> str:
    e = html.escape
    tags = [
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(description)}" />',
        f'<link rel="canonical" href="{e(url)}" />',
        f'<meta property="og:type" content="{og_type}" />',
        f'<meta property="og:site_name" content="{e(store_info.STORE_NAME)}" />',
        '<meta property="og:locale" content="ru_RU" />',
        f'<meta property="og:title" content="{e(title)}" />',
        f'<meta property="og:description" content="{e(description)}" />',
        f'<meta property="og:url" content="{e(url)}" />',
        f'<meta property="og:image" content="{e(image)}" />',
        '<meta name="twitter:card" content="summary_large_image" />',
    ]
    if not index:
        tags.append('<meta name="robots" content="noindex, nofollow" />')
    if schema:
        # </ внутри JSON закрыл бы тег <script>
        payload = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
        tags.append(f'<script type="application/ld+json">{payload}</script>')
    return "\n    ".join(tags)


def short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


@router.get("/head", response_class=HTMLResponse)
def seo_head(
    path: str = Query("/", max_length=300),
    host: str = Query("localhost", max_length=200),
    scheme: str = Query("https", max_length=10),
    db: Session = Depends(get_db),
):
    base = site_url(host, scheme)
    path = "/" + path.strip("/") if path.strip("/") else "/"
    url = f"{base}{path}"
    store = store_info.STORE_NAME
    image = f"{base}/og-image.jpg"

    if path.startswith("/admin"):
        return render_head(f"Управление магазином — {store}", DEFAULT_DESCRIPTION, url, image, index=False)

    if match := re.fullmatch(r"/product/(\d+)", path):
        product = (
            db.query(Product)
            .options(selectinload(Product.variants), selectinload(Product.category))
            .filter(Product.id == int(match.group(1)), Product.is_active == 1)
            .first()
        )
        if product is not None:
            variant = get_primary_variant(product)
            price = variant.price if variant else product.price
            unit = variant.unit if variant else product.unit
            description = short(
                f"{product.name}: {price:,.0f} ₽ за {unit}".replace(",", " ")
                + (f". {product.description}" if product.description else "")
                + ". Доставка или самовывоз в Химках."
            )
            return render_head(
                f"{product.name} — купить в Химках | {store}",
                description,
                url,
                absolute(base, product.image_url),
                product_schema(base, product),
                og_type="product",
            )

    if match := re.fullmatch(r"/catalog/(\d+)", path):
        category = db.get(Category, int(match.group(1)))
        if category is not None:
            return render_head(
                f"{category.name} — купить в Химках | {store}",
                f"{category.name}: цены, наличие, доставка или самовывоз. {DEFAULT_DESCRIPTION}",
                url,
                image,
            )

    if path == "/catalog":
        return render_head(f"Каталог пиломатериалов и крепежа | {store}", DEFAULT_DESCRIPTION, url, image)

    if path in STATIC_PAGES:
        title, description = STATIC_PAGES[path]
        return render_head(f"{title} | {store}", description, url, image)

    return render_head(
        f"{store} — доска, брус и крепёж в Химках",
        DEFAULT_DESCRIPTION,
        f"{base}/",
        image,
        store_schema(base),
    )


@router.get("/sitemap.xml")
def sitemap(
    host: str = Query("localhost", max_length=200),
    scheme: str = Query("https", max_length=10),
    db: Session = Depends(get_db),
):
    """Карта сайта для Яндекс Вебмастера: главная, каталог, разделы, товары."""
    base = site_url(host, scheme)
    paths = ["/", "/catalog", "/delivery"]
    paths += [f"/catalog/{category_id}" for (category_id,) in db.query(Category.id).order_by(Category.id)]
    paths += [
        f"/product/{product_id}"
        for (product_id,) in db.query(Product.id).filter(Product.is_active == 1).order_by(Product.id)
    ]
    urls = "\n".join(f"  <url><loc>{xml_escape(base + path)}</loc></url>" for path in paths)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")
