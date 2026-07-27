from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
import uuid

from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """FastAPI dependency: decode JWT, fetch user, raise 401 if invalid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_or_api_key(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Optional[User]:
    """
    Dual-auth dependency for service-to-service calls (n8n, cron):
    1. If 'Authorization: Bearer <jwt>' header is present → standard JWT user auth.
    2. If 'X-Internal-Api-Key' header matches INTERNAL_API_KEY → returns first user (service account).
    3. Otherwise → raises 401.
    """
    # Check for internal API key first
    api_key = request.headers.get("x-internal-api-key")
    if api_key and settings.INTERNAL_API_KEY and api_key == settings.INTERNAL_API_KEY:
        # Service-to-service auth: return first user as the service account
        service_user = db.query(User).first()
        if service_user:
            return service_user

    # Fall back to JWT Bearer token auth
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
        except JWTError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials. Provide a valid JWT Bearer token or X-Internal-Api-Key header.",
    )

