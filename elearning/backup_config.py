# backup_config.py
from pydantic import BaseSettings

class BackupSettings(BaseSettings):
    # Backup directory
    BACKUP_DIR: str = "cache_backups"
    
    # Backup retention (days)
    BACKUP_RETENTION_DAYS: int = 7
    
    # Auto backup schedule (cron format)
    BACKUP_SCHEDULE_HOUR: int = 2
    BACKUP_SCHEDULE_MINUTE: int = 0
    
    # Health check interval (minutes)
    HEALTH_CHECK_INTERVAL: int = 5
    
    # Enable auto recovery
    AUTO_RECOVERY_ENABLED: bool = True
    
    # Auto backup frequency (hours)
    AUTO_BACKUP_HOURS: int = 4
    
    # Incremental backup frequency (hours) 
    INCREMENTAL_BACKUP_HOURS: int = 1
    
    # Health check frequency (seconds)
    HEALTH_CHECK_SECONDS: int = 30
    
    class Config:
        env_file = ".env"

backup_settings = BackupSettings()