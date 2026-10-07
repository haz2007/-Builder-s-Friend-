from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

class CategoryBase(BaseModel):
    name: str


class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    price: float = Field(gt=0)
    stock_quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=20)
    category_id: int = Field(gt=0)


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: float


class OrderCreate(BaseModel):
    items: list[OrderItemCreate]


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: float
    price: float

    model_config = ConfigDict(from_attributes=True)


class OrderStatus(str, Enum):
    NEW = "NEW"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    ASSIGNED_TO_DRIVER = "ASSIGNED_TO_DRIVER"
    ON_THE_WAY = "ON_THE_WAY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class DeliveryStatus(str, Enum):
    WAITING = "WAITING"
    LOADED = "LOADED"
    ON_THE_WAY = "ON_THE_WAY"
    DELIVERED = "DELIVERED"


class DeliveryCreate(BaseModel):
    address: str


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus


class DeliveryResponse(BaseModel):
    id: int
    status: str
    address: str
    order_id: int
    driver_id: int | None

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    status: str
    total_price: float
    items: list[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: str
    password: str


class UserRegister(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str