"""Caching module for browser automation"""

from .service import (
	IntelligentCache, MultiLevelCache, CacheEntry, CacheStats,
	CacheKeyBuilder, get_intelligent_cache, get_multi_level_cache
)

__all__ = [
	'IntelligentCache', 'MultiLevelCache', 'CacheEntry', 'CacheStats',
	'CacheKeyBuilder', 'get_intelligent_cache', 'get_multi_level_cache'
]