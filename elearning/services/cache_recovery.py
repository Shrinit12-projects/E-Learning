# services/cache_recovery.py
import asyncio
import logging
from typing import Optional, Dict
import redis.asyncio as redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool
from .cache_backup import CacheBackupService
from .cache_warming import warm_critical_caches

logger = logging.getLogger(__name__)

class CacheRecoveryService:
    def __init__(self, redis_client: redis.Redis, db: Database, backup_service: CacheBackupService):
        self.redis = redis_client
        self.db = db
        self.backup_service = backup_service
        self._recovery_in_progress = False
    
    async def auto_recovery(self) -> bool:
        """Fully automatic recovery with zero-downtime failover"""
        if self._recovery_in_progress:
            return False
        
        self._recovery_in_progress = True
        
        try:
            if not await self._check_redis_health():
                logger.warning("Redis failure detected - initiating immediate recovery")
                
                # Try latest backup first
                latest_backup = await self._get_latest_backup()
                if latest_backup:
                    success = await self.backup_service.restore_backup(latest_backup["name"])
                    if success:
                        await warm_critical_caches(self.db, self.redis)
                        logger.info("Automatic recovery completed")
                        return True
                
                # Fallback: rebuild from database
                await warm_critical_caches(self.db, self.redis)
                logger.info("Fallback recovery from database completed")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Auto-recovery failed: {e}")
            return False
        finally:
            self._recovery_in_progress = False
    
    async def manual_recovery(self, backup_name: str, clear_existing: bool = True) -> bool:
        """Manual recovery from specific backup"""
        if self._recovery_in_progress:
            return False
        
        self._recovery_in_progress = True
        
        try:
            logger.info(f"Starting manual recovery from backup: {backup_name}")
            success = await self.backup_service.restore_backup(backup_name, clear_existing)
            
            if success:
                await warm_critical_caches(self.db, self.redis)
                logger.info("Manual recovery completed successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Manual recovery failed: {e}")
            return False
        finally:
            self._recovery_in_progress = False
    
    async def health_check_with_recovery(self) -> Dict[str, any]:
        """Health check with automatic recovery"""
        health_status = {
            "redis_healthy": False,
            "recovery_attempted": False,
            "recovery_successful": False,
            "cache_keys_count": 0
        }
        
        try:
            # Check Redis health
            health_status["redis_healthy"] = await self._check_redis_health()
            
            if not health_status["redis_healthy"]:
                # Attempt auto recovery
                health_status["recovery_attempted"] = True
                health_status["recovery_successful"] = await self.auto_recovery()
                health_status["redis_healthy"] = await self._check_redis_health()
            
            # Get cache stats
            if health_status["redis_healthy"]:
                health_status["cache_keys_count"] = await self.redis.dbsize()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        
        return health_status
    
    async def _check_redis_health(self) -> bool:
        """Check Redis connectivity"""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False
    
    async def _get_latest_backup(self) -> Optional[Dict]:
        """Get the most recent backup"""
        try:
            def _find_latest():
                return self.db.cache_backups.find_one(
                    sort=[("created_at", -1)]
                )
            
            backup = await run_in_threadpool(_find_latest)
            return backup
        except Exception:
            return None
    
    async def _get_latest_incremental_backup(self) -> Optional[Dict]:
        """Get the most recent incremental backup"""
        try:
            def _find_incremental():
                return self.db.cache_backups.find_one(
                    {"name": {"$regex": "^incremental_"}},
                    sort=[("created_at", -1)]
                )
            
            backup = await run_in_threadpool(_find_incremental)
            return backup
        except Exception:
            return None