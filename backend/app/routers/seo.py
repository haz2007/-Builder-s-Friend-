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
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import store_info
from ..database import get_db
from ..models import Category, Product
from ..services.variant_service import get_primary_variant

router = APIRouter(prefix="/api/v1/seo", tags=["SEO"])

DEFAULT_DESCRIPTION = (
    "Доска, брус, фанера, ОСБ и крепёж — поштучно и кубами. Самовывоз в Химках, "
    f"доставка в Зеленоград, Сходню, Лобню, Долгопрудный. {store_info.YEARS_ON_MARKET} лет опыта."
)
# Короткий хвост описаний товаров и разделов
DELIVERY_NOTE = "Доставка по Химкам, Зеленограду, Сходне и Лобне или самовывоз."
STATIC_PAGES = {
    "/delivery": (
        "Доставка и возврат",
        f"Доставка в {store_info.DELIVERY_AREA_TO}, Митино, Куркино и не только. Самовывоз, правила возврата.",
    ),
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


def website_schema(base: str) -> dict[str, Any]:
    """Название сайта, которое Google пишет в выдаче над адресом."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": store_info.STORE_NAME,
        "url": f"{base}/",
        "inLanguage": "ru",
    }


def store_schema(base: str) -> dict[str, Any]:
    """Магазин для Яндекса и Google: адрес, телефоны, часы работы, точка на карте."""
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "HardwareStore",
        "name": store_info.STORE_NAME,
        "url": f"{base}/",
        "image": f"{base}/og-image.jpg",
        "logo": f"{base}/brand/logo-telegram.png",
        "description": DEFAULT_DESCRIPTION,
        "telephone": store_info.PHONES,
        "email": store_info.EMAIL,
        "openingHours": "Mo-Su 09:00-19:00",
        "priceRange": "₽₽",
        "areaServed": [{"@type": "Place", "name": name} for name in store_info.DELIVERY_AREA],
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
        "sku": str(product.id),
        "url": f"{base}/product/{product.id}",
        "description": product.description or product.name,
        "image": absolute(base, product.image_url),
        "category": product.category.name if product.category else None,
        "offers": {
            "@type": "Offer",
            "price": f"{price:.2f}",
            "priceCurrency": "RUB",
            "itemCondition": "https://schema.org/NewCondition",
            "availability": f"https://schema.org/{'InStock' if in_stock else 'OutOfStock'}",
            "url": f"{base}/product/{product.id}",
            "seller": {"@type": "Organization", "name": store_info.STORE_NAME},
        },
    }


def category_trail(category: Category | None) -> list[Category]:
    """Раздел и его родители, от верхнего к нижнему."""
    trail: list[Category] = []
    while category is not None and category not in trail:
        trail.insert(0, category)
        category = category.parent
    return trail


def breadcrumbs_schema(base: str, crumbs: list[tuple[str, str | None]]) -> dict[str, Any]:
    """«Хлебные крошки» — поисковик показывает их вместо адреса страницы."""
    items = []
    for position, (name, path) in enumerate(crumbs, start=1):
        item: dict[str, Any] = {"@type": "ListItem", "position": position, "name": name}
        if path is not None:
            item["item"] = f"{base}{path}"
        items.append(item)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def category_crumbs(category: Category | None) -> list[tuple[str, str | None]]:
    crumbs: list[tuple[str, str | None]] = [("Каталог", "/catalog")]
    return crumbs + [(c.name, f"/catalog/{c.id}") for c in category_trail(category)]


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def rubles(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def category_ids_with_children(db: Session, category_id: int) -> list[int]:
    child_ids = [cid for (cid,) in db.query(Category.id).filter(Category.parent_id == category_id)]
    return [category_id, *child_ids]


def render_head(
    title: str,
    description: str,
    url: str,
    image: str,
    schemas: list[dict[str, Any]] | None = None,
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
    for schema in schemas or []:
        # </ внутри JSON закрыл бы тег <script>
        payload = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
        tags.append(f'<script type="application/ld+json">{payload}</script>')
    return "\n    ".join(tags)


def short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def default_head(path: str, host: str, scheme: str) -> str:
    """Общие теги без обращения к базе — когда сервер перегружен (app/overload.py)."""
    base = site_url(host, scheme)
    path = "/" + path.strip("/") if path.strip("/") else "/"
    return render_head(
        f"{store_info.STORE_NAME} — доска, брус и крепёж в Химках",
        DEFAULT_DESCRIPTION,
        f"{base}{path}",
        f"{base}/og-image.jpg",
        index=not path.startswith("/admin"),
    )


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
                f"{product.name}: {rubles(price)} за {unit}"
                + (f". {product.description}" if product.description else "")
                + f". {DELIVERY_NOTE}"
            )
            crumbs = category_crumbs(product.category) + [(product.name, None)]
            return render_head(
                f"{product.name} — купить в Химках | {store}",
                description,
                url,
                absolute(base, product.image_url),
                [product_schema(base, product), breadcrumbs_schema(base, crumbs)],
                og_type="product",
            )

    if match := re.fullmatch(r"/catalog/(\d+)", path):
        category = db.get(Category, int(match.group(1)))
        if category is not None:
            count, min_price = (
                db.query(func.count(Product.id), func.min(Product.price))
                .filter(Product.is_active == 1, Product.category_id.in_(category_ids_with_children(db, category.id)))
                .one()
            )
            title = f"{category.name} — купить в Химках | {store}"
            if not count:
                # Пустой раздел — пустая страница в выдаче; не показываем её поисковику
                return render_head(title, DEFAULT_DESCRIPTION, url, image, index=False)
            description = (
                f"{category.name} в Химках: {count} {plural(count, 'позиция', 'позиции', 'позиций')}, "
                f"цены от {rubles(min_price)}. Наличие на складе. {DELIVERY_NOTE}"
            )
            crumbs = category_crumbs(category)
            crumbs[-1] = (category.name, None)
            return render_head(title, description, url, image, [breadcrumbs_schema(base, crumbs)])

    if path == "/catalog":
        count = db.query(func.count(Product.id)).filter(Product.is_active == 1).scalar() or 0
        description = (
            f"{count} {plural(count, 'товар', 'товара', 'товаров')} для стройки: обрезная доска и брус, "
            f"фанера и ОСБ, крепёж, плёнки, инструмент. Цены и остатки на складе. {DELIVERY_NOTE}"
        )
        return render_head(f"Каталог пиломатериалов и крепежа | {store}", short(description), url, image)

    if path in STATIC_PAGES:
        title, description = STATIC_PAGES[path]
        return render_head(f"{title} | {store}", description, url, image)

    if path == "/":
        return render_head(
            f"{store} — доска, брус и крепёж в Химках",
            DEFAULT_DESCRIPTION,
            f"{base}/",
            image,
            [website_schema(base), store_schema(base)],
        )

    # Личный кабинет, скрытый товар, несуществующий адрес — в поиске им не место
    title = f"Личный кабинет | {store}" if path == "/account" else f"{store} — доска, брус и крепёж в Химках"
    return render_head(title, DEFAULT_DESCRIPTION, url, image, index=False)


@router.get("/sitemap.xml")
def sitemap(
    host: str = Query("localhost", max_length=200),
    scheme: str = Query("https", max_length=10),
    db: Session = Depends(get_db),
):
    """Карта сайта для Яндекс Вебмастера: главная, каталог, разделы, товары."""
    base = site_url(host, scheme)
    paths = ["/", "/catalog", "/delivery"]
    # Только разделы, где есть товары (в самом разделе или в его подразделах)
    filled: set[int] = {
        category_id
        for (category_id,) in db.query(Product.category_id).filter(Product.is_active == 1)
        if category_id is not None
    }
    for category_id, parent_id in db.query(Category.id, Category.parent_id):
        if category_id in filled and parent_id is not None:
            filled.add(parent_id)
    paths += [f"/catalog/{category_id}" for category_id in sorted(filled)]
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


def yml_text(value: str) -> str:
    """Текст для YML: спецсимволы — сущностями, включая кавычки и апостроф."""
    return xml_escape(value, {'"': "&quot;", "'": "&apos;"})


@router.get("/yml.xml")
def yml_feed(
    host: str = Query("localhost", max_length=200),
    scheme: str = Query("https", max_length=10),
    db: Session = Depends(get_db),
):
    """Товары, цены и фото в формате YML — для Яндекс Бизнеса и Вебмастера.

    Одна позиция на товар: цена основного варианта, как на странице товара
    при открытии. Нет на складе — available="false" («под заказ»).
    """
    base = site_url(host, scheme)
    categories = db.query(Category).order_by(Category.id).all()
    products = (
        db.query(Product)
        .options(selectinload(Product.variants))
        .filter(Product.is_active == 1)
        .order_by(Product.id)
        .all()
    )

    category_lines = []
    for category in categories:
        parent = f' parentId="{category.parent_id}"' if category.parent_id is not None else ""
        category_lines.append(f'      <category id="{category.id}"{parent}>{yml_text(category.name)}</category>')

    offer_lines = []
    for product in products:
        variant = get_primary_variant(product)
        price = variant.price if variant else product.price
        available = product.stock_quantity >= (variant.base_quantity if variant else 1)
        url = f"{base}/product/{product.id}"
        offer_lines += [
            f'      <offer id="{product.id}" available="{"true" if available else "false"}">',
            f"        <name>{yml_text(product.name)}</name>",
            f"        <url>{yml_text(url)}</url>",
            f"        <price>{price:.2f}</price>",
            "        <currencyId>RUR</currencyId>",
            f"        <categoryId>{product.category_id}</categoryId>",
            f"        <picture>{yml_text(absolute(base, product.image_url))}</picture>",
            "        <store>false</store>",
            "        <pickup>true</pickup>",
            "        <delivery>true</delivery>",
            f"        <description>{yml_text(product.description or product.name)}</description>",
            "      </offer>",
        ]

    # Дата выгрузки с часовым поясом (RFC 3339): старше 10 дней Яндекс не берёт
    date = datetime.now(UTC).isoformat(timespec="seconds")
    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<yml_catalog date="{date}">',
            "  <shop>",
            f"    <name>{yml_text(store_info.STORE_NAME)}</name>",
            f"    <company>{yml_text(store_info.LEGAL_NAME)}</company>",
            f"    <url>{yml_text(base)}/</url>",
            f"    <email>{yml_text(store_info.EMAIL)}</email>",
            '    <currencies><currency id="RUR" rate="1"/></currencies>',
            "    <categories>",
            *category_lines,
            "    </categories>",
            "    <offers>",
            *offer_lines,
            "    </offers>",
            "  </shop>",
            "</yml_catalog>",
            "",
        ]
    )
    return Response(content=body, media_type="application/xml")
