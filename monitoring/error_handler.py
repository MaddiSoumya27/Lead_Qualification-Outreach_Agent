"""
Error handling and monitoring utilities for LQOA
"""

import os
import sys
import traceback
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
STRUCTURED_LOGGING = os.getenv("STRUCTURED_LOGGING", "true").lower() == "true"

# Create logger
logger = logging.getLogger("lqoa")
logger.setLevel(getattr(logging, LOG_LEVEL))

# Create console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(getattr(logging, LOG_LEVEL))

# Create formatter
if STRUCTURED_LOGGING:
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    )
else:
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File handler if LOG_FILE_PATH is set
log_file_path = os.getenv("LOG_FILE_PATH")
if log_file_path:
    os.makedirs(log_file_path, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_file_path, "lqoa.log"))
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def handle_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Handle and log errors with context"""
    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
        "traceback": traceback.format_exc()
    }
    
    if context:
        error_info["context"] = context
    
    logger.error(f"Error occurred: {error_info}")
    
    # In production, you might want to send to external monitoring
    # e.g., Sentry, DataDog, etc.

def log_info(message: str, context: Dict[str, Any] = None) -> None:
    """Log info message with optional context"""
    if context:
        logger.info(f"{message} - Context: {context}")
    else:
        logger.info(message)

def log_warning(message: str, context: Dict[str, Any] = None) -> None:
    """Log warning message with optional context"""
    if context:
        logger.warning(f"{message} - Context: {context}")
    else:
        logger.warning(message)

def log_debug(message: str, context: Dict[str, Any] = None) -> None:
    """Log debug message with optional context"""
    if context:
        logger.debug(f"{message} - Context: {context}")
    else:
        logger.debug(message)

class ErrorTracker:
    """Track and monitor application errors"""
    
    def __init__(self):
        self.error_counts = {}
        self.last_errors = []
        self.max_stored_errors = 100
    
    def record_error(self, error: Exception, context: Dict[str, Any] = None):
        """Record an error for tracking"""
        error_type = type(error).__name__
        
        # Increment count
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Store error details
        error_record = {
            "type": error_type,
            "message": str(error),
            "timestamp": datetime.utcnow(),
            "context": context or {}
        }
        
        self.last_errors.insert(0, error_record)
        
        # Keep only recent errors
        if len(self.last_errors) > self.max_stored_errors:
            self.last_errors = self.last_errors[:self.max_stored_errors]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics"""
        return {
            "error_counts": self.error_counts.copy(),
            "recent_errors": self.last_errors[:10],  # Last 10 errors
            "total_errors": sum(self.error_counts.values())
        }

# Global error tracker instance
error_tracker = ErrorTracker()

def track_error(error: Exception, context: Dict[str, Any] = None):
    """Track error and handle logging"""
    error_tracker.record_error(error, context)
    handle_error(error, context)

# Health check utilities
def check_database_health() -> bool:
    """Check if database is healthy"""
    try:
        from database.connection import get_database_session
        with get_database_session() as session:
            session.execute("SELECT 1")
        return True
    except Exception as e:
        handle_error(e, {"component": "database_health_check"})
        return False

def check_redis_health() -> bool:
    """Check if Redis is healthy (if configured)"""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return True  # Not configured, so not unhealthy
    
    try:
        import redis
        r = redis.from_url(redis_url)
        r.ping()
        return True
    except Exception as e:
        handle_error(e, {"component": "redis_health_check"})
        return False

def get_system_health() -> Dict[str, Any]:
    """Get overall system health status"""
    return {
        "database": check_database_health(),
        "redis": check_redis_health(),
        "errors": error_tracker.get_error_summary(),
        "timestamp": datetime.utcnow().isoformat()
    }