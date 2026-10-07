from enum import Enum

from pydantic import BaseModel, ConfigDict

class CategoryBase(BaseModel):
    name: str


class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    description: str | None = None
    price: float
    stock_quantity: float
    unit: str
    category_id: int


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