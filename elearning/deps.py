from pymongo.database import Database
from pymongo import MongoClient
import redis.asyncio as aioredis
from fastapi import Request
from redis.asyncio import Redis


def create_mongo_client(uri: str) -> MongoClient:
    # synchronous PyMongo client (use run_in_threadpool for blocking calls)
    return MongoClient(uri, maxPoolSize=100, serverSelectionTimeoutMS=5000)

def create_redis_client(url: str):
    # redis.asyncio client (async)
    return aioredis.from_url(url, encoding="utf-8", decode_responses=True)

def get_db(request: Request) -> Database:
    return request.app.state.db

def get_redis(request: Request) -> Redis:
    return request.app.state.redis
