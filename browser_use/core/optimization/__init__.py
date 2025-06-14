"""Optimization module for browser automation"""

from .token_optimizer import (
	TokenOptimizer, TokenStats, CompressionStrategy, MessageCompressor
)
from .prefetcher import (
	PredictivePrefetcher, PatternLearner, PrefetchPattern, PrefetchTask
)

__all__ = [
	'TokenOptimizer', 'TokenStats', 'CompressionStrategy', 'MessageCompressor',
	'PredictivePrefetcher', 'PatternLearner', 'PrefetchPattern', 'PrefetchTask'
]