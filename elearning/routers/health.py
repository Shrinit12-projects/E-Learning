# routers/health.py
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pymongo.database import Database
from redis.asyncio import Redis
from deps import get_db, get_redis

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
async def health(db: Database = Depends(get_db), r: Redis = Depends(get_redis)):
    await r.ping()
    await run_in_threadpool(lambda: db.command("ping"))
    return {"status": "ok"}
