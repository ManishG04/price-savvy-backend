"""
In-memory TTL Cache for Price Savvy Backend
As per PRD: In-memory TTL cache for recent queries/responses
"""

import time
import threading
from typing import Any, Optional, Dict
from functools import wraps


class TTLCache:
    """Thread-safe in-memory cache with TTL expiration."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Initialize TTL cache.

        Args:
            max_size: Maximum number of items to store
            ttl_seconds: Time-to-live in seconds for cache entries
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if time.time() > entry["expires_at"]:
                # Entry expired, remove it
                del self._cache[key]
                return None

            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override in seconds
        """
        with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_oldest()

            expires_at = time.time() + (ttl if ttl is not None else self._ttl_seconds)
            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
            }

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def _evict_oldest(self) -> None:
        """Evict the oldest entry from cache."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["created_at"])
        del self._cache[oldest_key]

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time > entry["expires_at"]
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
            }


# Global cache instance
_cache_instance: Optional[TTLCache] = None


def get_cache() -> TTLCache:
    """Get or create the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        from flask import current_app

        try:
            max_size = current_app.config.get("CACHE_MAX_SIZE", 100)
            ttl = current_app.config.get("CACHE_TTL_SECONDS", 300)
        except RuntimeError:
            # Outside of application context, use defaults
            max_size = 100
            ttl = 300
        _cache_instance = TTLCache(max_size=max_size, ttl_seconds=ttl)
    return _cache_instance


def cached(key_prefix: str, ttl: Optional[int] = None):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Optional TTL override
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key from prefix and arguments
            key_parts = [key_prefix] + [str(arg) for arg in args]
            key_parts += [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = ":".join(key_parts)

            # Check cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator
