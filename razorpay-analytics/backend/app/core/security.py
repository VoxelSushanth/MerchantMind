"""
Security utilities: JWT, password hashing, token encryption.
"""
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional

import jwt
from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()


def get_fernet_key() -> bytes:
    """Get or generate Fernet key for encryption."""
    if settings.FERNET_KEY:
        return settings.FERNET_KEY.encode()

    # Generate deterministic key from SECRET_KEY
    key_hash = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)


def encrypt_token(token: str) -> str:
    """Encrypt sensitive token (e.g., Razorpay access token)."""
    fernet = Fernet(get_fernet_key())
    encrypted = fernet.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt previously encrypted token."""
    fernet = Fernet(get_fernet_key())
    decrypted = fernet.decrypt(encrypted_token.encode())
    return decrypted.decode()


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
