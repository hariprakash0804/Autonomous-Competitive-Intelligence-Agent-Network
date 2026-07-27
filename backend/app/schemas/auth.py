import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


from typing import Optional


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    company_name: Optional[str] = None
    company_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    company_url: Optional[str] = None

