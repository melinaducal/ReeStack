from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import date

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: EmailStr
    birth_date: date

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe tener al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe tener al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe tener al menos un número')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('La contraseña debe tener al menos un carácter especial')
        return v

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

    class Config:
        from_attributes = True

class ForgotPassword(BaseModel):
    email: EmailStr

class ThemeUpdate(BaseModel):
    theme_accent: Optional[str] = None
