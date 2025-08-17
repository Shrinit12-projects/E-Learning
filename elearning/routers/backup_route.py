
# routers/backup_route.py
# This module defines API endpoints for cache backup and recovery operations.
# It provides routes for creating, restoring, listing, and deleting cache backups,
# as well as health checks and auto-recovery features.

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict
from deps import get_redis, get_db
from services.cache_backup import CacheBackupService
from services.cache_recovery import CacheRecoveryService


# Initialize the API router for cache backup endpoints
router = APIRouter(prefix="/api/cache/backup", tags=["Cache Backup"])


# Dependency to provide a CacheBackupService instance
def get_backup_service(redis=Depends(get_redis), db=Depends(get_db)):
    return CacheBackupService(redis, db)


# Dependency to provide a CacheRecoveryService instance
def get_recovery_service(redis=Depends(get_redis), db=Depends(get_db), backup_service=Depends(get_backup_service)):
    return CacheRecoveryService(redis, db, backup_service)


# Endpoint to create a new cache backup
# Optionally accepts a backup name; if not provided, a name is generated.
@router.post("/create")
async def create_backup(
    background_tasks: BackgroundTasks,
    backup_name: str = None,
    backup_service: CacheBackupService = Depends(get_backup_service)
):
    """Create a cache backup"""
    try:
        backup_name = await backup_service.create_backup(backup_name)
        return {"status": "success", "backup_name": backup_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


# Endpoint to restore cache from a specific backup
# Optionally clears existing cache before restore
@router.post("/restore/{backup_name}")
async def restore_backup(
    backup_name: str,
    clear_existing: bool = True,
    recovery_service: CacheRecoveryService = Depends(get_recovery_service)
):
    """Restore cache from backup"""
    try:
        success = await recovery_service.manual_recovery(backup_name, clear_existing)
        if success:
            return {"status": "success", "message": "Cache restored successfully"}
        else:
            raise HTTPException(status_code=404, detail="Backup not found or restore failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")


# Endpoint to list all available cache backups
@router.get("/list")
async def list_backups(backup_service: CacheBackupService = Depends(get_backup_service)):
    """List all available backups"""
    try:
        backups = await backup_service.list_backups()
        return {"backups": backups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


# Endpoint to delete a specific cache backup
@router.delete("/{backup_name}")
async def delete_backup(
    backup_name: str,
    backup_service: CacheBackupService = Depends(get_backup_service)
):
    """Delete a backup"""
    try:
        success = await backup_service.delete_backup(backup_name)
        if success:
            return {"status": "success", "message": "Backup deleted"}
        else:
            raise HTTPException(status_code=404, detail="Backup not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# Endpoint to perform a cache health check and trigger auto-recovery if needed
@router.get("/health")
async def cache_health_check(recovery_service: CacheRecoveryService = Depends(get_recovery_service)):
    """Health check with auto-recovery"""
    try:
        health_status = await recovery_service.health_check_with_recovery()
        return health_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Endpoint to manually trigger cache auto-recovery
@router.post("/auto-recovery")
async def trigger_auto_recovery(recovery_service: CacheRecoveryService = Depends(get_recovery_service)):
    """Manually trigger auto-recovery"""
    try:
        success = await recovery_service.auto_recovery()
        if success:
            return {"status": "success", "message": "Auto-recovery completed"}
        else:
            return {"status": "failed", "message": "Auto-recovery failed or not needed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-recovery failed: {str(e)}")