
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
from ..models import Category, Product, User
from ..schemas import (
    ProductCreate,
    ProductResponse,
    ProductStockUpdate,
    ProductUpdate,
)


router = APIRouter(prefix="/api/v1/products", tags=["Products"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "products"
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


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
        query = query.filter(Product.category_id == category_id)

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

    for field in (
        "name",
        "description",
        "price",
        "stock_quantity",
        "unit",
        "category_id",
    ):
        value = getattr(product_data, field)
        if value is not None:
            setattr(product, field, value)

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
