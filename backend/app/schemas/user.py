from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import date

from .item import PublicItemResponse

PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


def validate_password_strength(value: str) -> str:
    """Single source of truth for the password policy.

    Registration and password reset both use it, so a reset can never set a
    password weaker than the one registration accepts.
    """
    if not any(c.isupper() for c in value):
        raise ValueError('La contraseña debe tener al menos una mayúscula')
    if not any(c.islower() for c in value):
        raise ValueError('La contraseña debe tener al menos una minúscula')
    if not any(c.isdigit() for c in value):
        raise ValueError('La contraseña debe tener al menos un número')
    if not any(c in PASSWORD_SPECIAL_CHARS for c in value):
        raise ValueError('La contraseña debe tener al menos un carácter especial')
    return value


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: EmailStr
    birth_date: date


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        return validate_password_strength(v)

    @validator('birth_date')
    def validate_age(cls, v):
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 14:
            raise ValueError('Debes ser mayor de 14 años para crear una cuenta')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    theme_accent: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserPublic(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfilePublic(UserPublic):
    stats: dict


class CollectionResponse(BaseModel):
    user_id: int
    username: str
    total: int
    page: int
    limit: int
    pages: int
    items: List[PublicItemResponse]


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=512)
    new_password: str = Field(..., min_length=8)

    @validator('new_password')
    def validate_new_password(cls, v):
        return validate_password_strength(v)


class ThemeUpdate(BaseModel):
    theme_accent: Optional[str] = None

