"""Predictive prefetching for browser automation"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import numpy as np

from browser_use.core.intent.views import Intent, IntentType
from browser_use.core.cache.service import MultiLevelCache, CacheKeyBuilder
from browser_use.utils import time_execution_async


@dataclass
class PrefetchPattern:
	"""Pattern for predictive prefetching"""
	pattern_id: str
	intent_sequence: List[IntentType]
	confidence: float
	occurrence_count: int = 1
	last_seen: datetime = field(default_factory=datetime.now)
	
	def matches_prefix(self, sequence: List[IntentType]) -> bool:
		"""Check if sequence matches the beginning of this pattern"""
		if len(sequence) > len(self.intent_sequence):
			return False
		
		return all(
			s == p for s, p in zip(sequence, self.intent_sequence)
		)
	
	def get_next_intents(self, current_sequence: List[IntentType]) -> List[IntentType]:
		"""Get predicted next intents based on current sequence"""
		if not self.matches_prefix(current_sequence):
			return []
		
		start_idx = len(current_sequence)
		return self.intent_sequence[start_idx:]


@dataclass
class PrefetchTask:
	"""Task to prefetch data"""
	task_id: str
	resource_type: str  # 'element', 'page_data', 'perception'
	parameters: Dict[str, Any]
	priority: float
	created_at: datetime = field(default_factory=datetime.now)
	completed: bool = False
	result: Optional[Any] = None


class PatternLearner:
	"""Learns patterns from intent execution history"""
	
	def __init__(self, min_pattern_length: int = 2, min_confidence: float = 0.6):
		self.min_pattern_length = min_pattern_length
		self.min_confidence = min_confidence
		self.patterns: Dict[str, PrefetchPattern] = {}
		self.sequence_history: deque = deque(maxlen=1000)
		
		# Markov chain for transition probabilities
		self.transitions: Dict[IntentType, Dict[IntentType, int]] = defaultdict(lambda: defaultdict(int))
		self.intent_counts: Dict[IntentType, int] = defaultdict(int)
	
	def record_intent(self, intent: Intent) -> None:
		"""Record an intent execution"""
		intent_type = intent.type
		
		# Update counts
		self.intent_counts[intent_type] += 1
		
		# Update transitions if we have history
		if self.sequence_history:
			last_intent = self.sequence_history[-1]
			self.transitions[last_intent][intent_type] += 1
		
		# Add to history
		self.sequence_history.append(intent_type)
		
		# Update patterns
		self._update_patterns()
	
	def predict_next_intents(
		self,
		current_sequence: List[IntentType],
		top_k: int = 3
	) -> List[Tuple[IntentType, float]]:
		"""Predict most likely next intents"""
		predictions = []
		
		# Pattern-based prediction
		pattern_predictions = self._predict_from_patterns(current_sequence)
		
		# Markov-based prediction
		if current_sequence:
			markov_predictions = self._predict_from_markov(current_sequence[-1])
			
			# Combine predictions
			all_predictions = {}
			
			for intent_type, conf in pattern_predictions:
				all_predictions[intent_type] = conf * 0.7  # Weight pattern predictions higher
			
			for intent_type, prob in markov_predictions:
				if intent_type in all_predictions:
					all_predictions[intent_type] += prob * 0.3
				else:
					all_predictions[intent_type] = prob * 0.3
			
			# Sort by combined confidence
			predictions = sorted(
				all_predictions.items(),
				key=lambda x: x[1],
				reverse=True
			)[:top_k]
		else:
			predictions = pattern_predictions[:top_k]
		
		return predictions
	
	def _update_patterns(self) -> None:
		"""Update patterns from recent history"""
		if len(self.sequence_history) < self.min_pattern_length:
			return
		
		# Extract subsequences
		for length in range(self.min_pattern_length, min(6, len(self.sequence_history) + 1)):
			for i in range(len(self.sequence_history) - length + 1):
				subsequence = list(self.sequence_history)[i:i + length]
				pattern_id = "-".join(str(s) for s in subsequence)
				
				if pattern_id in self.patterns:
					# Update existing pattern
					pattern = self.patterns[pattern_id]
					pattern.occurrence_count += 1
					pattern.last_seen = datetime.now()
					pattern.confidence = min(0.95, pattern.confidence + 0.05)
				else:
					# Create new pattern
					self.patterns[pattern_id] = PrefetchPattern(
						pattern_id=pattern_id,
						intent_sequence=subsequence,
						confidence=0.5  # Start with medium confidence
					)
	
	def _predict_from_patterns(
		self,
		current_sequence: List[IntentType]
	) -> List[Tuple[IntentType, float]]:
		"""Predict using learned patterns"""
		predictions = defaultdict(float)
		
		for pattern in self.patterns.values():
			if pattern.confidence < self.min_confidence:
				continue
			
			next_intents = pattern.get_next_intents(current_sequence)
			if next_intents:
				# Weight by pattern confidence and recency
				age_days = (datetime.now() - pattern.last_seen).days
				recency_weight = 1.0 / (1.0 + age_days * 0.1)
				
				weight = pattern.confidence * recency_weight
				
				# Add first predicted intent
				predictions[next_intents[0]] += weight
		
		# Normalize and sort
		total_weight = sum(predictions.values())
		if total_weight > 0:
			normalized = [(k, v / total_weight) for k, v in predictions.items()]
			return sorted(normalized, key=lambda x: x[1], reverse=True)
		
		return []
	
	def _predict_from_markov(
		self,
		current_intent: IntentType
	) -> List[Tuple[IntentType, float]]:
		"""Predict using Markov chain"""
		if current_intent not in self.transitions:
			return []
		
		transitions = self.transitions[current_intent]
		total_transitions = sum(transitions.values())
		
		if total_transitions == 0:
			return []
		
		# Calculate probabilities
		probabilities = [
			(intent_type, count / total_transitions)
			for intent_type, count in transitions.items()
		]
		
		return sorted(probabilities, key=lambda x: x[1], reverse=True)


class PredictivePrefetcher:
	"""Predictively prefetches resources based on patterns"""
	
	def __init__(
		self,
		cache: MultiLevelCache,
		pattern_learner: Optional[PatternLearner] = None,
		max_concurrent_prefetches: int = 3
	):
		self.cache = cache
		self.pattern_learner = pattern_learner or PatternLearner()
		self.max_concurrent_prefetches = max_concurrent_prefetches
		
		# Prefetch queue and active tasks
		self.prefetch_queue: asyncio.Queue[PrefetchTask] = asyncio.Queue()
		self.active_tasks: Set[str] = set()
		self.completed_tasks: Dict[str, PrefetchTask] = {}
		
		# Prefetch strategies
		self.prefetch_strategies = {
			"element": self._prefetch_element,
			"page_data": self._prefetch_page_data,
			"perception": self._prefetch_perception_data
		}
		
		# Worker task
		self._worker_task: Optional[asyncio.Task] = None
		self._running = False
	
	async def start(self) -> None:
		"""Start the prefetcher"""
		if self._running:
			return
		
		self._running = True
		self._worker_task = asyncio.create_task(self._prefetch_worker())
	
	async def stop(self) -> None:
		"""Stop the prefetcher"""
		self._running = False
		
		if self._worker_task:
			self._worker_task.cancel()
			try:
				await self._worker_task
			except asyncio.CancelledError:
				pass
	
	async def record_intent(self, intent: Intent) -> None:
		"""Record intent and trigger predictive prefetching"""
		# Learn from the pattern
		self.pattern_learner.record_intent(intent)
		
		# Get predictions
		current_sequence = list(self.pattern_learner.sequence_history)[-5:]  # Last 5
		predictions = self.pattern_learner.predict_next_intents(current_sequence)
		
		# Schedule prefetch tasks
		for predicted_intent, confidence in predictions:
			if confidence > 0.3:  # Minimum confidence threshold
				await self._schedule_prefetch_for_intent(predicted_intent, confidence)
	
	async def get_prefetched(
		self,
		resource_type: str,
		key: str
	) -> Optional[Any]:
		"""Get prefetched resource if available"""
		# Check completed tasks
		task_key = f"{resource_type}:{key}"
		if task_key in self.completed_tasks:
			task = self.completed_tasks[task_key]
			if task.completed and task.result is not None:
				return task.result
		
		# Check cache
		return await self.cache.get(key)
	
	async def _schedule_prefetch_for_intent(
		self,
		intent_type: IntentType,
		confidence: float
	) -> None:
		"""Schedule prefetch tasks based on predicted intent"""
		# Determine what to prefetch based on intent type
		prefetch_configs = self._get_prefetch_config(intent_type)
		
		for config in prefetch_configs:
			task = PrefetchTask(
				task_id=f"{config['type']}:{config['key']}",
				resource_type=config['type'],
				parameters=config['params'],
				priority=confidence * config.get('importance', 1.0)
			)
			
			# Only add if not already prefetched or in progress
			if (task.task_id not in self.active_tasks and
				task.task_id not in self.completed_tasks):
				await self.prefetch_queue.put(task)
	
	def _get_prefetch_config(self, intent_type: IntentType) -> List[Dict[str, Any]]:
		"""Get prefetch configuration for intent type"""
		configs = []
		
		if intent_type == IntentType.NAVIGATION:
			# Prefetch common page elements
			configs.extend([
				{
					"type": "element",
					"key": "navigation_elements",
					"params": {"selectors": ["nav", "header", "[role='navigation']"]},
					"importance": 0.8
				},
				{
					"type": "page_data",
					"key": "page_metadata",
					"params": {"data_types": ["title", "meta", "links"]},
					"importance": 0.6
				}
			])
		
		elif intent_type == IntentType.FORM_FILL:
			# Prefetch form elements
			configs.extend([
				{
					"type": "element",
					"key": "form_elements",
					"params": {"selectors": ["form", "input", "select", "textarea"]},
					"importance": 0.9
				},
				{
					"type": "element",
					"key": "submit_buttons",
					"params": {"selectors": ["button[type='submit']", "input[type='submit']"]},
					"importance": 0.8
				}
			])
		
		elif intent_type == IntentType.AUTHENTICATION:
			# Prefetch login elements
			configs.extend([
				{
					"type": "element",
					"key": "auth_elements",
					"params": {"selectors": [
						"input[type='email']", "input[type='password']",
						"input[name*='user']", "input[name*='pass']",
						"button[type='submit']", "[class*='oauth']"
					]},
					"importance": 0.95
				}
			])
		
		elif intent_type == IntentType.SEARCH:
			# Prefetch search elements
			configs.extend([
				{
					"type": "element",
					"key": "search_elements",
					"params": {"selectors": [
						"input[type='search']", "[role='search']",
						"input[placeholder*='search']", "[class*='search']"
					]},
					"importance": 0.85
				}
			])
		
		return configs
	
	async def _prefetch_worker(self) -> None:
		"""Worker that processes prefetch tasks"""
		while self._running:
			try:
				# Get task with timeout
				task = await asyncio.wait_for(
					self.prefetch_queue.get(),
					timeout=1.0
				)
				
				# Check if we can process more tasks
				if len(self.active_tasks) < self.max_concurrent_prefetches:
					asyncio.create_task(self._process_prefetch_task(task))
				else:
					# Put back in queue
					await self.prefetch_queue.put(task)
					await asyncio.sleep(0.1)
				
			except asyncio.TimeoutError:
				continue
			except Exception as e:
				# Log error but continue
				pass
	
	async def _process_prefetch_task(self, task: PrefetchTask) -> None:
		"""Process a single prefetch task"""
		if task.task_id in self.active_tasks:
			return
		
		self.active_tasks.add(task.task_id)
		
		try:
			# Execute prefetch strategy
			strategy = self.prefetch_strategies.get(task.resource_type)
			if strategy:
				result = await strategy(task.parameters)
				task.result = result
				task.completed = True
				
				# Cache the result
				cache_key = CacheKeyBuilder.build(
					task.resource_type,
					**task.parameters
				)
				await self.cache.set(
					cache_key,
					result,
					ttl_seconds=300,  # 5 minutes
					tags=[task.resource_type, "prefetched"],
					level=1  # Put in L1 cache since it's likely to be used soon
				)
			
			# Mark as completed
			self.completed_tasks[task.task_id] = task
			
		except Exception as e:
			# Log error but don't fail
			pass
		
		finally:
			self.active_tasks.discard(task.task_id)
	
	# Prefetch strategies
	
	async def _prefetch_element(self, params: Dict[str, Any]) -> Any:
		"""Prefetch element data"""
		# This would interact with the DOM processor
		# For now, return mock data
		return {
			"selectors": params.get("selectors", []),
			"prefetched_at": datetime.now().isoformat()
		}
	
	async def _prefetch_page_data(self, params: Dict[str, Any]) -> Any:
		"""Prefetch page metadata"""
		return {
			"data_types": params.get("data_types", []),
			"prefetched_at": datetime.now().isoformat()
		}
	
	async def _prefetch_perception_data(self, params: Dict[str, Any]) -> Any:
		"""Prefetch perception analysis"""
		return {
			"perception_type": params.get("type", "general"),
			"prefetched_at": datetime.now().isoformat()
		}
	
	async def get_stats(self) -> Dict[str, Any]:
		"""Get prefetcher statistics"""
		return {
			"active_tasks": len(self.active_tasks),
			"completed_tasks": len(self.completed_tasks),
			"queue_size": self.prefetch_queue.qsize(),
			"patterns_learned": len(self.pattern_learner.patterns),
			"hit_rate": self._calculate_hit_rate()
		}
	
	def _calculate_hit_rate(self) -> float:
		"""Calculate prefetch hit rate"""
		if not self.completed_tasks:
			return 0.0
		
		# This would track actual usage of prefetched data
		# For now return mock value
		return 0.75