# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from redis.asyncio import Redis
from pymongo.database import Database
import json
from datetime import datetime, timezone

from deps import get_db, get_redis
from repos import users
from schemas.auth_schemas import UserRegister, TokenPair, TokenRefresh
from auth.jwt import create_access_token, create_refresh_token, decode_token, get_token_jti
from services.cache_keys import user_session_key, refresh_tokens_key, blacklisted_jti_key

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_TTL = 60 * 60 * 24
REFRESH_TTL = 60 * 60 * 24 * 7

@router.post("/register")
async def register_user(payload: UserRegister, db: Database = Depends(get_db)):
    try:
        users.create_user(db, payload.email, payload.password, payload.full_name, payload.role)
        return {"message": "User registered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=TokenPair)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Database = Depends(get_db),
    r: Redis = Depends(get_redis)
):
    user = users.get_user_by_email(db, form_data.username)
    if not user or not users.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id, "role": user["role"]})
    refresh_token = create_refresh_token({"sub": user_id, "role": user["role"]})

    await r.set(user_session_key(user_id), json.dumps({"email": user["email"], "role": user["role"]}), ex=SESSION_TTL)
    await r.set(refresh_tokens_key(user_id), refresh_token, ex=REFRESH_TTL)

    return TokenPair(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: TokenRefresh, r: Redis = Depends(get_redis)):
    try:
        print('refresh_route')
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid refresh token type")
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_id = decoded["sub"]
    stored_refresh = await r.get(refresh_tokens_key(user_id))
    if stored_refresh != payload.refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    new_access = create_access_token({"sub": user_id, "role": decoded["role"]})
    return TokenPair(access_token=new_access, refresh_token=payload.refresh_token)

@router.delete("/logout")
async def logout(token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/login")), r: Redis = Depends(get_redis)):
    try:
        print('logout_route')
        decoded = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token")

    jti = decoded["jti"]
    ttl = decoded["exp"] - int(datetime.now(timezone.utc).timestamp())
    await r.set(blacklisted_jti_key(jti), "true", ex=ttl)

    await r.delete(user_session_key(decoded['sub']))
    await r.delete(refresh_tokens_key(decoded['sub']))

    return {"message": "Logged out successfully"}
