import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

PHONE_RE = re.compile(r"^\+?\d{8,15}$")


def validate_phone(value: str) -> str:
    """Normalize and validate a phone number (8-15 digits, optional leading +)."""
    cleaned = re.sub(r"[\s\-().]", "", value)
    if not PHONE_RE.match(cleaned):
        raise ValueError("Invalid phone number: expected 8-15 digits, optional leading '+'")
    return cleaned


# --- Auth ---

class RegisterRequest(BaseModel):
    phone: str
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=255)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return validate_phone(v)


class LoginRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return validate_phone(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Users / preferences ---

class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tastes: list[str] = []
    drink_types: list[str] = []
    temperature: str | None = None
    caffeine: str | None = None
    allergies: list[str] = []
    dietary_restrictions: list[str] = []


class PreferenceUpdate(BaseModel):
    tastes: list[str] | None = None
    drink_types: list[str] | None = None
    temperature: str | None = None
    caffeine: str | None = None
    allergies: list[str] | None = None
    dietary_restrictions: list[str] | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    address: str


# --- Menu ---

class MenuItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str
    ingredients: list[str] = []
    price: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=50)
    available: bool = True


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    ingredients: list[str] | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = None
    available: bool | None = None


class MenuItemOut(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# --- Chat ---

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class Recommendation(BaseModel):
    name: str
    description: str
    price: float
    reason: str


class OrderItemOut(BaseModel):
    name: str
    quantity: int
    unit_price: float


class OrderOut(BaseModel):
    id: int
    status: str
    total_price: float
    items: list[OrderItemOut]


class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation] = []
    order: OrderOut | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str


# --- Favorites ---

class FavoriteOut(BaseModel):
    id: int
    menu_item: MenuItemOut

    model_config = ConfigDict(from_attributes=True)
