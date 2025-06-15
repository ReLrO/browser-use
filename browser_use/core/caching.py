"""Caching utilities for browser automation"""

import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheConfig:
    """Configuration for caching behavior"""
    
    def __init__(
        self,
        dom_cache_ttl: float = 5.0,
        element_cache_ttl: float = 10.0,
        screenshot_cache_ttl: float = 2.0,
        perception_cache_size: int = 100,
        enable_disk_cache: bool = False,
        cache_directory: str = "./cache"
    ):
        self.dom_cache_ttl = dom_cache_ttl
        self.element_cache_ttl = element_cache_ttl
        self.screenshot_cache_ttl = screenshot_cache_ttl
        self.perception_cache_size = perception_cache_size
        self.enable_disk_cache = enable_disk_cache
        self.cache_directory = cache_directory


class ElementCache:
    """Cache for element resolution to reduce LLM calls"""
    
    def __init__(self, ttl_seconds: float = 10.0):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
    
    def _make_key(self, url: str, description: str, element_type: Optional[str] = None) -> str:
        """Create cache key from element search parameters"""
        key_data = {
            "url": url,
            "description": description,
            "element_type": element_type
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(self, url: str, description: str, element_type: Optional[str] = None) -> Optional[Any]:
        """Get cached element if still valid"""
        async with self._lock:
            key = self._make_key(url, description, element_type)
            
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    logger.debug(f"Cache hit for element: {description}")
                    return value
                else:
                    # Expired
                    del self._cache[key]
            
            return None
    
    async def set(self, url: str, description: str, element_type: Optional[str], value: Any) -> None:
        """Cache an element resolution result"""
        async with self._lock:
            key = self._make_key(url, description, element_type)
            self._cache[key] = (value, time.time())
            logger.debug(f"Cached element: {description}")
            
            # Clean old entries if cache is too large
            if len(self._cache) > 1000:
                self._clean_expired()
    
    def _clean_expired(self) -> None:
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            k for k, (_, timestamp) in self._cache.items()
            if current_time - timestamp >= self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]
    
    async def clear(self) -> None:
        """Clear all cached data"""
        async with self._lock:
            self._cache.clear()


class PageElementsCache:
    """Cache for page elements extraction"""
    
    def __init__(self, ttl_seconds: float = 5.0):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
    
    def _make_key(self, url: str) -> str:
        """Create cache key from URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def get(self, url: str) -> Optional[Any]:
        """Get cached page elements if still valid"""
        async with self._lock:
            key = self._make_key(url)
            
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    logger.debug(f"Cache hit for page elements: {url}")
                    return value
                else:
                    del self._cache[key]
            
            return None
    
    async def set(self, url: str, elements: Any) -> None:
        """Cache page elements"""
        async with self._lock:
            key = self._make_key(url)
            self._cache[key] = (elements, time.time())
            logger.debug(f"Cached {len(elements)} page elements for: {url}")
    
    async def invalidate(self, url: str) -> None:
        """Invalidate cache for a specific URL"""
        async with self._lock:
            key = self._make_key(url)
            if key in self._cache:
                del self._cache[key]


class RateLimiter:
    """Rate limiter for API calls with exponential backoff"""
    
    def __init__(self, calls_per_minute: int = 10, burst_size: int = 5):
        self.calls_per_minute = calls_per_minute
        self.burst_size = burst_size
        self._call_times: list[float] = []
        self._lock = asyncio.Lock()
        self._backoff_until: Optional[float] = None
        self._consecutive_errors = 0
    
    async def acquire(self) -> None:
        """Wait if necessary to respect rate limits"""
        async with self._lock:
            now = time.time()
            
            # Check if we're in backoff period
            if self._backoff_until and now < self._backoff_until:
                wait_time = self._backoff_until - now
                logger.info(f"In backoff period, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                now = time.time()
            
            # Remove calls older than 1 minute
            self._call_times = [t for t in self._call_times if now - t < 60]
            
            # Check if we're at the limit
            if len(self._call_times) >= self.calls_per_minute:
                # Wait until the oldest call is older than 1 minute
                oldest = self._call_times[0]
                wait_time = 60 - (now - oldest) + 0.1  # Add small buffer
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    # Recurse to re-check
                    await self.acquire()
                    return
            
            # Check burst limit (calls in last 10 seconds)
            recent_calls = [t for t in self._call_times if now - t < 10]
            if len(recent_calls) >= self.burst_size:
                wait_time = 10 - (now - recent_calls[0]) + 0.1
                if wait_time > 0:
                    logger.info(f"Burst limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    await self.acquire()
                    return
            
            # Record this call
            self._call_times.append(now)
    
    def report_error(self, error: Exception) -> None:
        """Report an API error for backoff calculation"""
        if "quota" in str(error).lower() or "429" in str(error):
            self._consecutive_errors += 1
            # Exponential backoff: 2^n seconds, max 300 seconds
            backoff_seconds = min(2 ** self._consecutive_errors, 300)
            self._backoff_until = time.time() + backoff_seconds
            logger.warning(f"API quota error, backing off for {backoff_seconds}s")
    
    def report_success(self) -> None:
        """Report successful API call to reset error counter"""
        self._consecutive_errors = 0
        self._backoff_until = None
    
    def get_remaining_calls(self) -> int:
        """Get number of remaining calls in current minute"""
        now = time.time()
        recent_calls = [t for t in self._call_times if now - t < 60]
        return max(0, self.calls_per_minute - len(recent_calls))


# Global instances
element_cache = ElementCache()
page_elements_cache = PageElementsCache()
rate_limiter = RateLimiter(calls_per_minute=10, burst_size=5)