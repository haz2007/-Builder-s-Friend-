
import io
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import (
    Category,
    OrderItem,
    Product,
    ProductVariant,
    User,
    is_piece_unit,
)
from .categories import category_with_children_ids
from ..schemas import (
    ProductCreate,
    ProductResponse,
    ProductStockUpdate,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from ..services.variant_service import (
    apply_product_fields_to_primary,
    recalc_cubic_variants,
    sync_product_from_primary,
)

DIMENSION_FIELDS = ("thickness_mm", "width_mm", "length_mm")


router = APIRouter(prefix="/api/v1/products", tags=["Products"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "products"
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


def set_product_categories(
    db: Session,
    product: Product,
    main_category_id: int,
    extra_category_ids: list[int],
) -> None:
    """Связывает товар с основной и дополнительными категориями."""
    category_ids = {main_category_id, *extra_category_ids}
    categories = db.query(Category).filter(Category.id.in_(category_ids)).all()

    if len(categories) != len(category_ids):
        raise HTTPException(status_code=404, detail="Category not found")

    product.categories = categories


def validate_dimensions(product: Product) -> None:
    """Размеры задаются все три сразу; тогда склад ведётся в штуках."""
    dimensions = [getattr(product, field) for field in DIMENSION_FIELDS]

    if not any(dimensions):
        return

    if not all(dimensions):
        raise HTTPException(
            status_code=400,
            detail="Укажи толщину, ширину и длину доски вместе",
        )

    if not is_piece_unit(product.unit):
        raise HTTPException(
            status_code=400,
            detail="Для доски с размерами остаток ведётся в штуках: единица «шт»",
        )

    recalc_cubic_variants(product)


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


def get_variant_or_404(
    db: Session,
    product_id: int,
    variant_id: int,
) -> ProductVariant:
    variant = (
        db.query(ProductVariant)
        .filter(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
        .first()
    )

    if variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")

    return variant


@router.get("/", response_model=list[ProductResponse])
def get_products(
    search: str | None = Query(default=None, min_length=1, max_length=200),
    category_id: int | None = Query(default=None, gt=0),
    is_active: int | None = Query(default=1, ge=0, le=1),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Product)

    if search is not None:
        pattern = f"%{search}%"
        query = query.filter(
            Product.name.ilike(pattern)
            | Product.description.ilike(pattern)
        )

    if category_id is not None:
        # Категория вместе с подкатегориями: «Пиломатериалы» = доска + брус + …
        ids = category_with_children_ids(db, category_id)
        query = query.filter(
            Product.category_id.in_(ids)
            | Product.categories.any(Category.id.in_(ids))
        )

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    if sort_by == "price":
        column = Product.price
    elif sort_by == "name":
        column = Product.name
    elif sort_by == "stock_quantity":
        column = Product.stock_quantity
    else:
        column = Product.id

    query = query.order_by(
        column.desc() if sort_order == "desc" else column.asc()
    )

    return query.offset(offset).limit(limit).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.is_active == 1)
        .first()
    )

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.get("/{product_id}/admin", response_model=ProductResponse)
def get_product_for_admin(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.post("/", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = db.query(Category).filter(
        Category.id == product.category_id
    ).first()

    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    new_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        stock_quantity=product.stock_quantity,
        unit=product.unit,
        category_id=product.category_id,
        thickness_mm=product.thickness_mm,
        width_mm=product.width_mm,
        length_mm=product.length_mm,
    )
    validate_dimensions(new_product)
    set_product_categories(
        db,
        new_product,
        product.category_id,
        product.category_ids,
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return new_product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    if product_data.category_id is not None:
        category = db.query(Category).filter(
            Category.id == product_data.category_id
        ).first()

        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")

    old_category_id = product.category_id

    for field in ("name", "description", "category_id", "stock_quantity"):
        value = getattr(product_data, field)
        if value is not None:
            setattr(product, field, value)

    # null в размерах означает «убрать размеры», поэтому смотрим,
    # какие поля прислали явно
    for field in DIMENSION_FIELDS:
        if field in product_data.model_fields_set:
            setattr(product, field, getattr(product_data, field))

    # Цена из формы — это цена основного варианта
    apply_product_fields_to_primary(
        product,
        price=product_data.price,
        unit=product_data.unit,
    )
    validate_dimensions(product)

    if product_data.category_ids is not None:
        extra_ids = product_data.category_ids
    else:
        extra_ids = [
            category_id
            for category_id in product.category_ids
            if category_id != old_category_id
        ]

    set_product_categories(db, product, product.category_id, extra_ids)

    db.commit()
    db.refresh(product)

    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == 1,
    ).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = 0
    db.commit()

    return {"message": "Product deleted successfully"}


@router.post("/{product_id}/restore", response_model=ProductResponse)
def restore_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.is_active == 1:
        raise HTTPException(status_code=400, detail="Product is already active")

    product.is_active = 1
    db.commit()
    db.refresh(product)

    return product


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_product_stock(
    product_id: int,
    stock_data: ProductStockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product.stock_quantity = stock_data.stock_quantity
    db.commit()
    db.refresh(product)

    return product


@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantResponse,
)
def create_variant(
    product_id: int,
    variant_data: ProductVariantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = get_product_or_404(db, product_id)

    variant = ProductVariant(**variant_data.model_dump(), is_active=1)
    product.variants.append(variant)
    recalc_cubic_variants(product)
    sync_product_from_primary(product)

    db.commit()
    db.refresh(variant)

    return variant


@router.patch(
    "/{product_id}/variants/{variant_id}",
    response_model=ProductVariantResponse,
)
def update_variant(
    product_id: int,
    variant_id: int,
    variant_data: ProductVariantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = get_product_or_404(db, product_id)
    variant = get_variant_or_404(db, product_id, variant_id)

    if variant_data.is_active == 0 and variant.is_active == 1:
        active_count = sum(1 for v in product.variants if v.is_active == 1)
        if active_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Product must have at least one active variant",
            )

    for field, value in variant_data.model_dump(exclude_none=True).items():
        setattr(variant, field, value)

    recalc_cubic_variants(product)
    sync_product_from_primary(product)

    db.commit()
    db.refresh(variant)

    return variant


@router.delete("/{product_id}/variants/{variant_id}")
def delete_variant(
    product_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = get_product_or_404(db, product_id)
    variant = get_variant_or_404(db, product_id, variant_id)

    others_active = [
        v for v in product.variants
        if v.id != variant.id and v.is_active == 1
    ]
    if not others_active:
        raise HTTPException(
            status_code=400,
            detail="Product must have at least one active variant",
        )

    used_in_orders = (
        db.query(OrderItem)
        .filter(OrderItem.variant_id == variant.id)
        .first()
        is not None
    )

    # Вариант из старых заказов не удаляем, а скрываем
    if used_in_orders:
        variant.is_active = 0
    else:
        product.variants.remove(variant)

    sync_product_from_primary(product)
    db.commit()

    return {
        "message": (
            "Variant deactivated" if used_in_orders else "Variant deleted"
        )
    }


@router.post("/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    contents = await file.read(MAX_IMAGE_SIZE + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Файл пустой")

    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Размер изображения не должен превышать 5 МБ",
        )

    try:
        with Image.open(io.BytesIO(contents)) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=400,
            detail="Загрузите корректное изображение JPG, PNG или WebP",
        )

    if image_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только JPG, PNG и WebP",
        )

    extension = ALLOWED_FORMATS[image_format]
    filename = f"{uuid.uuid4().hex}{extension}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / filename

    destination.write_bytes(contents)

    old_image_url = product.image_url
    product.image_url = f"/uploads/products/{filename}"

    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise

    # Удаляем старую фотографию, только если это файл в нашей папке.
    if old_image_url and old_image_url.startswith("/uploads/products/"):
        old_filename = old_image_url.rsplit("/", 1)[-1]
        old_path = UPLOAD_DIR / old_filename
        if old_path.is_file() and old_path.parent == UPLOAD_DIR:
            old_path.unlink(missing_ok=True)

    return product
