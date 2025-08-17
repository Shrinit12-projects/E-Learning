# auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from deps import get_redis, get_db
from auth.jwt import decode_token
from pymongo.database import Database
from bson import ObjectId
from services.cache_keys import blacklisted_jti_key, user_session_key

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    r: Redis = Depends(get_redis),
    db: Database = Depends(get_db)
):
    try:
        print("Received token:", token)
        payload = decode_token(token)
        print("Decoded token:", payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    jti = payload.get("jti")
    if await r.get(blacklisted_jti_key(jti)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    if not await r.get(user_session_key(payload['sub'])):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        print("User not found in database", user)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user

def require_role(*roles: str):
    print("Roles:", roles)
    async def role_checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return role_checker
