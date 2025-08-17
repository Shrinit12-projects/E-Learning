# tasks/backup_tasks.py
import asyncio
import logging
from datetime import datetime, timedelta
from fastapi.concurrency import run_in_threadpool
from services.cache_backup import CacheBackupService
from services.cache_recovery import CacheRecoveryService

logger = logging.getLogger(__name__)

async def scheduled_backup_task(db, redis):
    """Scheduled backup task"""
    try:
        backup_service = CacheBackupService(redis, db)
        backup_name = await backup_service.create_backup()
        logger.info(f"Scheduled backup created: {backup_name}")
        
        # Cleanup old backups (keep last 7 days)
        await cleanup_old_backups(backup_service)
        
    except Exception as e:
        logger.error(f"Scheduled backup failed: {e}")

async def cleanup_old_backups(backup_service: CacheBackupService, days_to_keep: int = 7):
    """Clean up old backup files"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Get old backups from MongoDB
        def _find_old_backups():
            cursor = backup_service.db.cache_backups.find({
                "created_at": {"$lt": cutoff_date}
            })
            return list(cursor)
        
        old_backups = await run_in_threadpool(_find_old_backups)
        
        # Delete old backups
        for backup in old_backups:
            await backup_service.delete_backup(backup["name"])
            logger.info(f"Deleted old backup: {backup['name']}")
            
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")

async def health_monitor_task(db, redis):
    """Continuous health monitoring with automatic recovery"""
    try:
        backup_service = CacheBackupService(redis, db)
        recovery_service = CacheRecoveryService(redis, db, backup_service)
        
        # Always attempt auto-recovery if needed
        health_status = await recovery_service.health_check_with_recovery()
        
        if health_status["recovery_attempted"]:
            if health_status["recovery_successful"]:
                logger.info("Automatic recovery completed successfully")
            else:
                logger.error("Automatic recovery failed - manual intervention required")
                
    except Exception as e:
        logger.error(f"Auto-recovery monitor failed: {e}")

async def incremental_backup_task(db, redis):
    """Create incremental backups for frequently changing data"""
    try:
        backup_service = CacheBackupService(redis, db)
        
        # Create backup with timestamp
        backup_name = f"incremental_{datetime.now().strftime('%Y%m%d_%H%M')}"
        await backup_service.create_backup(backup_name)
        
        logger.info(f"Incremental backup created: {backup_name}")
        
    except Exception as e:
        logger.error(f"Incremental backup failed: {e}")

def schedule_backup_jobs(scheduler, db, redis):
    """Schedule backup-related jobs"""
    
    # Automatic backup every 4 hours
    scheduler.add_job(
        scheduled_backup_task,
        'interval',
        hours=4,
        args=[db, redis],
        id='auto_cache_backup',
        replace_existing=True
    )
    
    # Continuous health monitoring with auto-recovery every 30 seconds
    scheduler.add_job(
        health_monitor_task,
        'interval',
        seconds=30,
        args=[db, redis],
        id='auto_cache_recovery',
        replace_existing=True
    )
    
    # Incremental backup every hour for high-frequency changes
    scheduler.add_job(
        incremental_backup_task,
        'interval',
        hours=1,
        args=[db, redis],
        id='incremental_backup',
        replace_existing=True
    )
    
    logger.info("Cache backup jobs scheduled")