# auth/jwt.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import jwt
import uuid
from config import settings

ALGORITHM = "HS256"

def _create_token(data: Dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti, "type": token_type})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)

def create_access_token(data: dict) -> str:
    return _create_token(data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")

def create_refresh_token(data: dict) -> str:
    return _create_token(data, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        print("Token expired")
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        print("Invalid token")
        raise ValueError("Invalid token")

def get_token_jti(token: str) -> str:
    print("Token:", token)
    payload = decode_token(token)
    return payload.get("jti")
