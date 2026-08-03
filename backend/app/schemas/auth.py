import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=4, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    company_name: Optional[str] = None
    company_url: Optional[str] = None
    company_description: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    is_onboarded: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    company_url: Optional[str] = None
    company_description: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    is_onboarded: Optional[bool] = None


class OnboardingRequest(BaseModel):
    company_name: Optional[str] = None
    method: str = Field(..., description="Method used: 'url', 'text', or 'document'")
    company_url: Optional[str] = None
    description_text: Optional[str] = None


