# auth/jwt.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from jwt import encode, decode, ExpiredSignatureError, InvalidTokenError
from uuid import uuid4
from config import settings
import logging

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

def _create_token(data: Dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    try:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        jti = str(uuid4())
        to_encode.update({"exp": expire, "jti": jti, "type": token_type})
        return encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Failed to create {token_type} token: {str(e)}")
        raise ValueError(f"Token creation failed: {str(e)}")

def create_access_token(data: Dict[str, Any]) -> str:
    return _create_token(data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")

def create_refresh_token(data: Dict[str, Any]) -> str:
    return _create_token(data, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")

def decode_token(token: str) -> dict:
    try:
        return decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        logger.warning("Attempt to use expired token")
        raise ValueError("Token expired")
    except InvalidTokenError:
        logger.warning("Attempt to use invalid token")
        raise ValueError("Invalid token")
    except Exception as e:
        logger.error(f"Token decoding failed: {str(e)}")
        raise ValueError("Token processing failed")

def get_token_jti(token: str) -> str:
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if not jti:
            raise ValueError("Token missing JTI claim")
        return jti
    except Exception as e:
        logger.error(f"Failed to extract JTI from token: {str(e)}")
        raise
