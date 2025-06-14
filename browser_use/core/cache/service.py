"""Intelligent caching system for browser automation"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib
import json
from collections import OrderedDict
import pickle

from browser_use.utils import time_execution_async


@dataclass
class CacheEntry:
	"""Single cache entry with metadata"""
	key: str
	value: Any
	timestamp: datetime = field(default_factory=datetime.now)
	hits: int = 0
	size_bytes: int = 0
	ttl_seconds: float = 300  # 5 minutes default
	tags: List[str] = field(default_factory=list)
	
	@property
	def age_seconds(self) -> float:
		"""Age of the cache entry in seconds"""
		return (datetime.now() - self.timestamp).total_seconds()
	
	@property
	def is_expired(self) -> bool:
		"""Check if entry has expired"""
		return self.age_seconds > self.ttl_seconds
	
	def access(self) -> None:
		"""Record an access to this entry"""
		self.hits += 1


class CacheStats:
	"""Cache performance statistics"""
	
	def __init__(self):
		self.hits = 0
		self.misses = 0
		self.evictions = 0
		self.total_size_bytes = 0
		self.avg_hit_time_ms = 0.0
		self.avg_miss_time_ms = 0.0
	
	@property
	def hit_rate(self) -> float:
		"""Calculate cache hit rate"""
		total = self.hits + self.misses
		return self.hits / total if total > 0 else 0.0
	
	def to_dict(self) -> dict:
		"""Convert stats to dictionary"""
		return {
			"hits": self.hits,
			"misses": self.misses,
			"hit_rate": self.hit_rate,
			"evictions": self.evictions,
			"total_size_mb": self.total_size_bytes / (1024 * 1024),
			"avg_hit_time_ms": self.avg_hit_time_ms,
			"avg_miss_time_ms": self.avg_miss_time_ms
		}


class IntelligentCache:
	"""
	Intelligent caching system with:
	- TTL support
	- LRU eviction
	- Tag-based invalidation
	- Size limits
	- Performance tracking
	"""
	
	def __init__(
		self,
		max_size_mb: float = 100,
		default_ttl_seconds: float = 300,
		max_entries: int = 10000
	):
		self.max_size_bytes = int(max_size_mb * 1024 * 1024)
		self.default_ttl_seconds = default_ttl_seconds
		self.max_entries = max_entries
		
		# Use OrderedDict for LRU behavior
		self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
		self._stats = CacheStats()
		self._lock = asyncio.Lock()
		
		# Tag index for fast invalidation
		self._tag_index: Dict[str, List[str]] = {}
	
	@time_execution_async("cache_get")
	async def get(self, key: str) -> Optional[Any]:
		"""Get value from cache"""
		async with self._lock:
			if key in self._cache:
				entry = self._cache[key]
				
				# Check expiration
				if entry.is_expired:
					await self._remove_entry(key)
					self._stats.misses += 1
					return None
				
				# Move to end (LRU)
				self._cache.move_to_end(key)
				entry.access()
				
				self._stats.hits += 1
				return entry.value
			
			self._stats.misses += 1
			return None
	
	async def set(
		self,
		key: str,
		value: Any,
		ttl_seconds: Optional[float] = None,
		tags: Optional[List[str]] = None
	) -> None:
		"""Set value in cache"""
		async with self._lock:
			# Calculate size
			try:
				size_bytes = len(pickle.dumps(value))
			except:
				size_bytes = 1000  # Default size if serialization fails
			
			# Check if we need to evict
			await self._ensure_space(size_bytes)
			
			# Create entry
			entry = CacheEntry(
				key=key,
				value=value,
				ttl_seconds=ttl_seconds or self.default_ttl_seconds,
				tags=tags or [],
				size_bytes=size_bytes
			)
			
			# Remove old entry if exists
			if key in self._cache:
				await self._remove_entry(key)
			
			# Add new entry
			self._cache[key] = entry
			self._stats.total_size_bytes += size_bytes
			
			# Update tag index
			for tag in entry.tags:
				if tag not in self._tag_index:
					self._tag_index[tag] = []
				self._tag_index[tag].append(key)
	
	async def invalidate(self, key: str) -> bool:
		"""Invalidate a specific cache entry"""
		async with self._lock:
			if key in self._cache:
				await self._remove_entry(key)
				return True
			return False
	
	async def invalidate_by_tag(self, tag: str) -> int:
		"""Invalidate all entries with a specific tag"""
		async with self._lock:
			if tag not in self._tag_index:
				return 0
			
			keys_to_remove = list(self._tag_index[tag])
			for key in keys_to_remove:
				await self._remove_entry(key)
			
			return len(keys_to_remove)
	
	async def clear(self) -> None:
		"""Clear entire cache"""
		async with self._lock:
			self._cache.clear()
			self._tag_index.clear()
			self._stats.total_size_bytes = 0
			self._stats.evictions += len(self._cache)
	
	async def get_stats(self) -> Dict[str, Any]:
		"""Get cache statistics"""
		async with self._lock:
			stats = self._stats.to_dict()
			stats["entries"] = len(self._cache)
			stats["tags"] = len(self._tag_index)
			return stats
	
	async def cleanup_expired(self) -> int:
		"""Remove all expired entries"""
		async with self._lock:
			expired_keys = [
				key for key, entry in self._cache.items()
				if entry.is_expired
			]
			
			for key in expired_keys:
				await self._remove_entry(key)
			
			return len(expired_keys)
	
	# Private methods
	
	async def _ensure_space(self, required_bytes: int) -> None:
		"""Ensure there's enough space for new entry"""
		# Check entry count
		while len(self._cache) >= self.max_entries:
			await self._evict_lru()
		
		# Check size limit
		while (self._stats.total_size_bytes + required_bytes > self.max_size_bytes 
			   and len(self._cache) > 0):
			await self._evict_lru()
	
	async def _evict_lru(self) -> None:
		"""Evict least recently used entry"""
		if not self._cache:
			return
		
		# Get oldest key (first in OrderedDict)
		key = next(iter(self._cache))
		await self._remove_entry(key)
		self._stats.evictions += 1
	
	async def _remove_entry(self, key: str) -> None:
		"""Remove entry and update indexes"""
		if key not in self._cache:
			return
		
		entry = self._cache[key]
		
		# Update size
		self._stats.total_size_bytes -= entry.size_bytes
		
		# Update tag index
		for tag in entry.tags:
			if tag in self._tag_index:
				self._tag_index[tag].remove(key)
				if not self._tag_index[tag]:
					del self._tag_index[tag]
		
		# Remove from cache
		del self._cache[key]


class MultiLevelCache:
	"""
	Multi-level cache with different storage strategies:
	- L1: Fast in-memory cache for hot data
	- L2: Larger persistent cache for warm data
	"""
	
	def __init__(
		self,
		l1_size_mb: float = 10,
		l2_size_mb: float = 100,
		l1_ttl_seconds: float = 60,
		l2_ttl_seconds: float = 3600
	):
		self.l1_cache = IntelligentCache(
			max_size_mb=l1_size_mb,
			default_ttl_seconds=l1_ttl_seconds,
			max_entries=1000
		)
		
		self.l2_cache = IntelligentCache(
			max_size_mb=l2_size_mb,
			default_ttl_seconds=l2_ttl_seconds,
			max_entries=10000
		)
		
		# Promotion/demotion thresholds
		self.promotion_hits = 3  # Promote to L1 after 3 hits
		self.demotion_age = 30   # Demote from L1 after 30 seconds
	
	async def get(self, key: str) -> Optional[Any]:
		"""Get from cache, checking L1 then L2"""
		# Check L1
		value = await self.l1_cache.get(key)
		if value is not None:
			return value
		
		# Check L2
		value = await self.l2_cache.get(key)
		if value is not None:
			# Check if should promote to L1
			entry = self.l2_cache._cache.get(key)
			if entry and entry.hits >= self.promotion_hits:
				await self.l1_cache.set(key, value, tags=entry.tags)
			
			return value
		
		return None
	
	async def set(
		self,
		key: str,
		value: Any,
		ttl_seconds: Optional[float] = None,
		tags: Optional[List[str]] = None,
		level: int = 2
	) -> None:
		"""Set in cache at specified level"""
		if level == 1:
			await self.l1_cache.set(key, value, ttl_seconds, tags)
		else:
			await self.l2_cache.set(key, value, ttl_seconds, tags)
	
	async def invalidate(self, key: str) -> bool:
		"""Invalidate from all levels"""
		l1_removed = await self.l1_cache.invalidate(key)
		l2_removed = await self.l2_cache.invalidate(key)
		return l1_removed or l2_removed
	
	async def invalidate_by_tag(self, tag: str) -> int:
		"""Invalidate by tag from all levels"""
		l1_count = await self.l1_cache.invalidate_by_tag(tag)
		l2_count = await self.l2_cache.invalidate_by_tag(tag)
		return l1_count + l2_count
	
	async def get_stats(self) -> Dict[str, Any]:
		"""Get combined statistics"""
		return {
			"l1": await self.l1_cache.get_stats(),
			"l2": await self.l2_cache.get_stats(),
			"combined_hit_rate": await self._calculate_combined_hit_rate()
		}
	
	async def _calculate_combined_hit_rate(self) -> float:
		"""Calculate overall hit rate"""
		l1_stats = self.l1_cache._stats
		l2_stats = self.l2_cache._stats
		
		total_hits = l1_stats.hits + l2_stats.hits
		total_requests = total_hits + l2_stats.misses  # L1 misses become L2 requests
		
		return total_hits / total_requests if total_requests > 0 else 0.0


class CacheKeyBuilder:
	"""Helper for building consistent cache keys"""
	
	@staticmethod
	def build(prefix: str, **kwargs) -> str:
		"""Build cache key from prefix and parameters"""
		# Sort kwargs for consistent ordering
		sorted_params = sorted(kwargs.items())
		
		# Create string representation
		param_str = json.dumps(sorted_params, sort_keys=True)
		
		# Hash if too long
		if len(param_str) > 100:
			param_hash = hashlib.md5(param_str.encode()).hexdigest()
			return f"{prefix}:{param_hash}"
		
		return f"{prefix}:{param_str}"
	
	@staticmethod
	def build_intent_key(intent_id: str, context: Optional[dict] = None) -> str:
		"""Build cache key for intent-related data"""
		if context:
			# Include relevant context in key
			relevant_context = {
				k: v for k, v in context.items()
				if k in ["url", "page_id", "user_id"]
			}
			return CacheKeyBuilder.build("intent", id=intent_id, **relevant_context)
		
		return f"intent:{intent_id}"
	
	@staticmethod
	def build_element_key(
		description: str,
		url: str,
		element_type: Optional[str] = None
	) -> str:
		"""Build cache key for element resolution"""
		return CacheKeyBuilder.build(
			"element",
			desc=description[:50],  # Limit description length
			url=url,
			type=element_type or "any"
		)


# Global cache instances
_intelligent_cache: Optional[IntelligentCache] = None
_multi_level_cache: Optional[MultiLevelCache] = None


def get_intelligent_cache() -> IntelligentCache:
	"""Get or create global intelligent cache"""
	global _intelligent_cache
	if _intelligent_cache is None:
		_intelligent_cache = IntelligentCache()
	return _intelligent_cache


def get_multi_level_cache() -> MultiLevelCache:
	"""Get or create global multi-level cache"""
	global _multi_level_cache
	if _multi_level_cache is None:
		_multi_level_cache = MultiLevelCache()
	return _multi_level_cache