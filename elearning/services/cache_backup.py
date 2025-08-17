# services/cache_backup.py
import json
import gzip
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import redis.asyncio as redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool

class CacheBackupService:
    def __init__(self, redis_client: redis.Redis, db: Database, backup_dir: str = "cache_backups"):
        self.redis = redis_client
        self.db = db
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Create a full cache backup"""
        if not backup_name:
            backup_name = f"cache_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_file = self.backup_dir / f"{backup_name}.json.gz"
        
        # Get all keys
        keys = await self.redis.keys("*")
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "total_keys": len(keys),
            "data": {}
        }
        
        # Backup key-value pairs
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            key_type = await self.redis.type(key)
            
            if key_type == b"string":
                backup_data["data"][key_str] = {
                    "type": "string",
                    "value": await self.redis.get(key),
                    "ttl": await self.redis.ttl(key)
                }
            elif key_type == b"hash":
                backup_data["data"][key_str] = {
                    "type": "hash",
                    "value": await self.redis.hgetall(key),
                    "ttl": await self.redis.ttl(key)
                }
            elif key_type == b"set":
                backup_data["data"][key_str] = {
                    "type": "set",
                    "value": list(await self.redis.smembers(key)),
                    "ttl": await self.redis.ttl(key)
                }
        
        # Save compressed backup
        with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
            json.dump(backup_data, f, default=str)
        
        # Store backup metadata in MongoDB
        await self._store_backup_metadata(backup_name, backup_file, backup_data["total_keys"])
        
        return backup_name
    
    async def restore_backup(self, backup_name: str, clear_existing: bool = False) -> bool:
        """Restore cache from backup"""
        backup_file = self.backup_dir / f"{backup_name}.json.gz"
        
        if not backup_file.exists():
            return False
        
        # Clear existing cache if requested
        if clear_existing:
            await self.redis.flushdb()
        
        # Load backup data
        with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Restore data
        pipe = self.redis.pipeline()
        for key, data in backup_data["data"].items():
            if data["type"] == "string":
                pipe.set(key, data["value"])
            elif data["type"] == "hash":
                pipe.hset(key, mapping=data["value"])
            elif data["type"] == "set":
                pipe.sadd(key, *data["value"])
            
            # Set TTL if exists
            if data["ttl"] > 0:
                pipe.expire(key, data["ttl"])
        
        await pipe.execute()
        return True
    
    async def list_backups(self) -> List[Dict]:
        """List available backups"""
        def _list_backups():
            cursor = self.db.cache_backups.find().sort("created_at", -1)
            return list(cursor)
        
        return await run_in_threadpool(_list_backups)
    
    async def delete_backup(self, backup_name: str) -> bool:
        """Delete a backup"""
        backup_file = self.backup_dir / f"{backup_name}.json.gz"
        
        if backup_file.exists():
            backup_file.unlink()
            await run_in_threadpool(self.db.cache_backups.delete_one, {"name": backup_name})
            return True
        return False
    
    async def _store_backup_metadata(self, name: str, file_path: Path, key_count: int):
        """Store backup metadata in MongoDB"""
        metadata = {
            "name": name,
            "file_path": str(file_path),
            "key_count": key_count,
            "file_size": file_path.stat().st_size,
            "created_at": datetime.now()
        }
        return await run_in_threadpool(self.db.cache_backups.insert_one, metadata)