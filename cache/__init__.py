"""
Cache module for LQOA - Enrichment data caching with Redis fallback to database
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from dataclasses import asdict

from database.connection import get_database_session
from database.repositories import CacheRepository
from monitoring.error_handler import handle_error, log_debug

# Redis setup (optional)
_redis_client = None
REDIS_ENABLED = False
CACHE_TTL = int(os.getenv("REDIS_TTL", "3600"))  # 1 hour default

try:
    import redis
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        _redis_client = redis.from_url(redis_url)
        _redis_client.ping()  # Test connection
        REDIS_ENABLED = True
        log_debug("Redis cache enabled", {"redis_url": redis_url})
except Exception as e:
    log_debug("Redis not available, using database fallback", {"error": str(e)})

def _generate_cache_key(domain: str, company: str, provider: str = "") -> str:
    """Generate consistent cache key for enrichment data"""
    key_data = f"enrichment:{domain}:{company}:{provider}".lower()
    return hashlib.md5(key_data.encode()).hexdigest()

def get_enrichment_cache(domain: str, company: str, provider: str = "") -> Optional[Dict[str, Any]]:
    """
    Get enrichment data from cache
    
    Args:
        domain: Email domain to look up
        company: Company name to look up  
        provider: Enrichment provider used
        
    Returns:
        Cached enrichment data or None if not found
    """
    cache_key = _generate_cache_key(domain, company, provider)
    
    try:
        # Try Redis first if available
        if REDIS_ENABLED and _redis_client:
            cached_data = _redis_client.get(cache_key)
            if cached_data:
                log_debug("Cache hit (Redis)", {"key": cache_key})
                return json.loads(cached_data)
        
        # Fallback to database cache
        with get_database_session() as session:
            cache_repo = CacheRepository(session)
            cached_data = cache_repo.get(cache_key)
            
            if cached_data:
                log_debug("Cache hit (Database)", {"key": cache_key})
                return cached_data
        
        log_debug("Cache miss", {"key": cache_key})
        return None
        
    except Exception as e:
        handle_error(e, {"operation": "get_enrichment_cache", "key": cache_key})
        return None

def set_enrichment_cache(domain: str, company: str, data: Dict[str, Any], provider: str = "") -> bool:
    """
    Store enrichment data in cache
    
    Args:
        domain: Email domain
        company: Company name
        data: Enrichment data to cache
        provider: Enrichment provider used
        
    Returns:
        True if successfully cached, False otherwise
    """
    cache_key = _generate_cache_key(domain, company, provider)
    
    try:
        # Store in Redis if available
        if REDIS_ENABLED and _redis_client:
            _redis_client.setex(
                cache_key, 
                CACHE_TTL, 
                json.dumps(data, default=str)
            )
            log_debug("Cached to Redis", {"key": cache_key})
        
        # Also store in database as fallback
        with get_database_session() as session:
            cache_repo = CacheRepository(session)
            expires_at = datetime.utcnow() + timedelta(seconds=CACHE_TTL)
            cache_repo.set(cache_key, data, expires_at)
            log_debug("Cached to Database", {"key": cache_key})
        
        return True
        
    except Exception as e:
        handle_error(e, {"operation": "set_enrichment_cache", "key": cache_key})
        return False

def clear_enrichment_cache(domain: str = None, company: str = None) -> bool:
    """
    Clear enrichment cache entries
    
    Args:
        domain: Specific domain to clear (None = clear all)
        company: Specific company to clear (None = clear all)
        
    Returns:
        True if successfully cleared
    """
    try:
        if domain and company:
            # Clear specific entry
            cache_key = _generate_cache_key(domain, company)
            
            if REDIS_ENABLED and _redis_client:
                _redis_client.delete(cache_key)
            
            with get_database_session() as session:
                cache_repo = CacheRepository(session)
                cache_repo.delete(cache_key)
            
            log_debug("Cache entry cleared", {"key": cache_key})
        else:
            # Clear all enrichment cache (Redis only supports pattern deletion with SCAN)
            if REDIS_ENABLED and _redis_client:
                # Clear all keys starting with "enrichment:"
                for key in _redis_client.scan_iter(match="enrichment:*"):
                    _redis_client.delete(key)
            
            log_debug("All enrichment cache cleared")
        
        return True
        
    except Exception as e:
        handle_error(e, {"operation": "clear_enrichment_cache"})
        return False

def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics and health information
    
    Returns:
        Dictionary with cache statistics
    """
    stats = {
        "redis_enabled": REDIS_ENABLED,
        "redis_healthy": False,
        "database_cache_enabled": True,
        "ttl_seconds": CACHE_TTL
    }
    
    try:
        # Check Redis health
        if REDIS_ENABLED and _redis_client:
            _redis_client.ping()
            stats["redis_healthy"] = True
            
            # Get Redis info if available
            info = _redis_client.info()
            stats["redis_info"] = {
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
    
    except Exception as e:
        handle_error(e, {"operation": "get_cache_stats"})
        stats["redis_error"] = str(e)
    
    return stats