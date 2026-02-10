"""
Rate Limiter for Price Savvy Backend
As per PRD: Basic rate limiting (10 requests/min per IP)
"""
import time
import threading
from typing import Dict, Optional
from functools import wraps
from flask import request, jsonify


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm."""
    
    def __init__(self, requests_per_minute: int = 10):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute per IP
        """
        self._requests_per_minute = requests_per_minute
        self._window_seconds = 60
        self._requests: Dict[str, list] = {}
        self._lock = threading.RLock()
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if a request from the client is allowed.
        
        Args:
            client_id: Client identifier (usually IP address)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - self._window_seconds
            
            if client_id not in self._requests:
                self._requests[client_id] = []
            
            # Remove expired timestamps
            self._requests[client_id] = [
                ts for ts in self._requests[client_id]
                if ts > window_start
            ]
            
            # Check if under limit
            if len(self._requests[client_id]) < self._requests_per_minute:
                self._requests[client_id].append(current_time)
                return True
            
            return False
    
    def get_remaining(self, client_id: str) -> int:
        """
        Get remaining requests for a client in the current window.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Number of remaining requests allowed
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - self._window_seconds
            
            if client_id not in self._requests:
                return self._requests_per_minute
            
            valid_requests = [
                ts for ts in self._requests[client_id]
                if ts > window_start
            ]
            
            return max(0, self._requests_per_minute - len(valid_requests))
    
    def get_reset_time(self, client_id: str) -> Optional[float]:
        """
        Get the time when the rate limit window resets.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Unix timestamp when the oldest request expires, or None
        """
        with self._lock:
            if client_id not in self._requests or not self._requests[client_id]:
                return None
            
            oldest_request = min(self._requests[client_id])
            return oldest_request + self._window_seconds
    
    def cleanup(self) -> int:
        """
        Clean up expired entries.
        
        Returns:
            Number of clients cleaned up
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - self._window_seconds
            
            clients_to_remove = []
            for client_id, timestamps in self._requests.items():
                # Remove old timestamps
                self._requests[client_id] = [
                    ts for ts in timestamps if ts > window_start
                ]
                # Mark empty entries for removal
                if not self._requests[client_id]:
                    clients_to_remove.append(client_id)
            
            for client_id in clients_to_remove:
                del self._requests[client_id]
            
            return len(clients_to_remove)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        from flask import current_app
        try:
            limit = current_app.config.get('RATE_LIMIT_PER_MINUTE', 10)
        except RuntimeError:
            limit = 10
        _rate_limiter = RateLimiter(requests_per_minute=limit)
    return _rate_limiter


def get_client_ip() -> str:
    """Get the client's IP address from the request."""
    # Check for X-Forwarded-For header (for proxied requests)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def rate_limit(func):
    """Decorator to apply rate limiting to an endpoint."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        limiter = get_rate_limiter()
        client_ip = get_client_ip()
        
        if not limiter.is_allowed(client_ip):
            remaining = limiter.get_remaining(client_ip)
            reset_time = limiter.get_reset_time(client_ip)
            
            response = jsonify({
                'success': False,
                'error': 'Rate Limit Exceeded',
                'message': 'Too many requests. Please try again later.',
                'retry_after': int(reset_time - time.time()) if reset_time else 60
            })
            response.status_code = 429
            response.headers['X-RateLimit-Remaining'] = str(remaining)
            if reset_time:
                response.headers['X-RateLimit-Reset'] = str(int(reset_time))
            return response
        
        # Add rate limit headers to response
        response = func(*args, **kwargs)
        
        # If response is a tuple (response, status_code), extract response
        if isinstance(response, tuple):
            resp_obj = response[0]
            status_code = response[1]
        else:
            resp_obj = response
            status_code = None
        
        # Add headers if it's a Response object
        if hasattr(resp_obj, 'headers'):
            resp_obj.headers['X-RateLimit-Remaining'] = str(limiter.get_remaining(client_ip))
            resp_obj.headers['X-RateLimit-Limit'] = str(limiter._requests_per_minute)
        
        return response
    
    return wrapper
