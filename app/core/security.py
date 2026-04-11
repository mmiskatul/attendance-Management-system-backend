"""Security and JWT helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.exceptions import AuthenticationAppError


pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=600000,
)


class AccessTokenPayload(BaseModel):
    """Internal JWT payload."""

    sub: str
    username: str
    role: str
    tenant_id: str
    exp: int
    iat: int


def hash_password(password: str) -> str:
    """Hash a plain-text password."""

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""

    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    *,
    subject: str,
    username: str,
    role: str,
    tenant_id: str,
    secret_key: str,
    algorithm: str,
    expires_delta: timedelta,
) -> str:
    """Create a signed JWT access token."""

    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> AccessTokenPayload:
    """Decode and validate a JWT access token."""

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        raise AuthenticationAppError("Invalid or expired access token.") from exc
    return AccessTokenPayload.model_validate(payload)
