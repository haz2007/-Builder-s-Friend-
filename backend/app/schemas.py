
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, computed_field, model_validator

PICKUP_ADDRESS = "Самовывоз со склада"



def as_utc(value: datetime) -> datetime:
    """В базе время хранится в UTC без пометки — помечаем, чтобы браузер
    показал его в часовом поясе покупателя, а не сдвинутым на 3 часа."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


UtcDatetime = Annotated[datetime, PlainSerializer(lambda value: as_utc(value).isoformat())]

class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # None — категория верхнего уровня
    parent_id: int | None = None


class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductVariantBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=20)
    price: float = Field(gt=0)
    # Сколько базовых единиц товара в 1 единице варианта.
    # Для «м³» у досок с размерами считается автоматически.
    base_quantity: float = Field(default=1, gt=0)


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    price: float | None = Field(default=None, gt=0)
    base_quantity: float | None = Field(default=None, gt=0)
    is_active: int | None = Field(default=None, ge=0, le=1)


class ProductVariantResponse(ProductVariantBase):
    id: int
    product_id: int
    is_active: int
    # Сколько единиц варианта доступно из общего склада
    stock_quantity: float

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    price: float = Field(gt=0)
    stock_quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=20)
    category_id: int = Field(gt=0)
    thickness_mm: float | None = Field(default=None, gt=0)
    width_mm: float | None = Field(default=None, gt=0)
    length_mm: float | None = Field(default=None, gt=0)


class ProductCreate(ProductBase):
    # Дополнительные категории, помимо основной category_id
    category_ids: list[int] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    price: float | None = Field(default=None, gt=0)
    stock_quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    category_id: int | None = Field(default=None, gt=0)
    category_ids: list[int] | None = None
    thickness_mm: float | None = Field(default=None, gt=0)
    width_mm: float | None = Field(default=None, gt=0)
    length_mm: float | None = Field(default=None, gt=0)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    stock_quantity: float
    unit: str
    category_id: int
    is_active: int
    image_url: str | None = None
    category_ids: list[int] = []
    thickness_mm: float | None = None
    width_mm: float | None = None
    length_mm: float | None = None
    pieces_per_cubic_meter: int | None = None
    variants: list[ProductVariantResponse] = []

    model_config = ConfigDict(from_attributes=True)


class OrderItemCreate(BaseModel):
    product_id: int
    # Без variant_id используется основной вариант товара
    variant_id: int | None = None
    quantity: float


class OrderCreate(BaseModel):
    customer_name: str = Field(default="Покупатель", min_length=2, max_length=100)
    items: list[OrderItemCreate]
    # Доставка магазином или самовывоз (своя или нанятая машина)
    delivery_method: Literal["DELIVERY", "PICKUP"] = "DELIVERY"
    delivery_address: str = Field(default="", max_length=500)
    comment: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def check_address(self):
        self.comment = " ".join(self.comment.split())
        if self.delivery_method == "PICKUP":
            self.delivery_address = PICKUP_ADDRESS
        elif len(self.delivery_address.strip()) < 5:
            raise ValueError("Укажи адрес доставки — не менее 5 символов")
        return self


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    variant_id: int
    quantity: float
    price: float
    unit: str
    base_quantity: float = 1
    product_name: str | None = None
    variant_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderStatus(str, Enum):
    NEW = "NEW"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    ON_THE_WAY = "ON_THE_WAY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    order_id: int | None = None
    status: str | None = None
    message: str
    is_read: int
    created_at: UtcDatetime

    model_config = ConfigDict(from_attributes=True)


class OrderStatusHistoryResponse(BaseModel):
    id: int
    order_id: int
    status: str
    created_at: UtcDatetime
    changed_by_id: int | None = None
    # «Админ admin@…» / «Покупатель +7999…»; пусто у старых записей
    changed_by: str | None = Field(default=None, validation_alias="changed_by_label")

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    status: str
    total_price: float
    delivery_address: str
    delivery_method: str = "DELIVERY"
    customer_name: str
    customer_phone: str | None = None
    comment: str | None = None
    # Нужен админке, чтобы сбросить пароль покупателю
    user_id: int | None = None
    created_at: UtcDatetime | None = None
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse] = []

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]  # так в документации pydantic
    @property
    def allowed_statuses(self) -> list[str]:
        """Куда можно перевести заказ: следующий этап и/или отмена."""
        from .services.order_service import allowed_transitions

        order = ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY",
                 "ON_THE_WAY", "DELIVERED", "CANCELLED"]
        allowed = allowed_transitions(self.status, self.delivery_method)
        return [status for status in order if status in allowed]


# Минимальная длина пароля при регистрации; старые короткие пароли продолжают работать
PASSWORD_MIN_LENGTH = 8


class UserRegister(BaseModel):
    phone: str = Field(min_length=10, max_length=30)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    # Согласие с политикой конфиденциальности — без него регистрации нет (152-ФЗ)
    privacy_accepted: Literal[True]


class PasswordResetRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=30)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)


class AccountDelete(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class PasswordResetConfirm(BaseModel):
    phone: str = Field(min_length=10, max_length=30)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)


class TemporaryPasswordResponse(BaseModel):
    user_id: int
    phone: str | None
    temporary_password: str


class UserResponse(BaseModel):
    id: int
    email: str | None = None
    phone: str | None = None
    role: str
    is_owner: int = 0

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    # Вход только по телефону: все аккаунты, и админы тоже, — по номеру
    phone: str = Field(min_length=10, max_length=30)
    password: str = Field(min_length=1, max_length=128)



class AdminCreate(BaseModel):
    # Телефон уже зарегистрированного пользователя
    login: str = Field(min_length=10, max_length=30)


class AdminResponse(UserResponse):
    has_telegram: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class ProductStockUpdate(BaseModel):
    stock_quantity: float = Field(ge=0)


class CallbackItem(BaseModel):
    variant_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100_000)


class CallbackRequestCreate(BaseModel):
    """Заявка «перезвоните мне»: телефон и, если есть, корзина."""

    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=30)
    comment: str = Field(default="", max_length=500)
    items: list[CallbackItem] = Field(default_factory=list, max_length=50)
    # Телефон и имя — персональные данные: без согласия заявку не принимаем
    privacy_accepted: Literal[True]

    @model_validator(mode="after")
    def normalize(self):
        digits = "".join(ch for ch in self.phone if ch.isdigit())
        if len(digits) == 11 and digits[0] in "78":
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Укажите номер телефона из 10 цифр, например +7 999 123-45-67")
        self.phone = f"+7{digits}"
        self.name = " ".join(self.name.split())
        self.comment = " ".join(self.comment.split())
        return self


class CallbackRequestResponse(BaseModel):
    id: int
    name: str
    phone: str
    comment: str | None
    cart_summary: str | None
    cart_total: float | None
    status: str
    created_at: UtcDatetime
    handled_at: UtcDatetime | None = None
    handled_by_label: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductSuggestion(BaseModel):
    id: int
    name: str
    # Похожесть 0…1 (word_similarity из pg_trgm)
    score: float
