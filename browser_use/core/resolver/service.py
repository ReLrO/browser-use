"""Multi-strategy element resolution service"""

import asyncio
from typing import Any, Optional, List, Dict, Tuple
from datetime import datetime
from enum import Enum

from browser_use.perception.base import (
	PerceptionElement, PerceptionQuery, BoundingBox
)
from browser_use.perception.vision.service import VisionEngine
from browser_use.perception.dom.service import IncrementalDOMProcessor
from browser_use.perception.accessibility.service import AccessibilityProcessor
from browser_use.perception.fusion.service import MultiModalPerceptionFusion
from browser_use.core.intent.views import ElementIntent
from browser_use.utils import time_execution_async
from playwright.async_api import Page
from browser_use.core.resolver.strategies import SimpleFinderStrategy, DOMProcessorStrategy, LLMFinderStrategy
import logging

logger = logging.getLogger(__name__)


class ResolutionStrategy(str, Enum):
	"""Element resolution strategies"""
	TEST_ID = "test_id"
	ARIA_LABEL = "aria_label"
	TEXT_CONTENT = "text_content"
	VISUAL_GROUNDING = "visual_grounding"
	SEMANTIC_SEARCH = "semantic_search"
	PROXIMITY = "proximity"
	CSS_SELECTOR = "css_selector"
	XPATH = "xpath"
	COMBINED = "combined"


class ResolvedElement:
	"""Result of element resolution"""
	
	def __init__(
		self,
		element: PerceptionElement,
		confidence: float,
		strategy: ResolutionStrategy,
		resolution_time_ms: float,
		alternatives: List[PerceptionElement] = None
	):
		self.element = element
		self.confidence = confidence
		self.strategy = strategy
		self.resolution_time_ms = resolution_time_ms
		self.alternatives = alternatives or []
	
	@property
	def selector(self) -> Optional[str]:
		"""Get the best selector for this element"""
		return self.element.selector
	
	@property
	def bounding_box(self) -> Optional[BoundingBox]:
		"""Get bounding box if available"""
		return self.element.bounding_box
	
	async def click_point(self) -> Tuple[float, float]:
		"""Get the best point to click"""
		if self.bounding_box:
			return (self.bounding_box.center_x, self.bounding_box.center_y)
		return (0, 0)


class MultiStrategyElementResolver:
	"""Resolves elements using multiple strategies in parallel"""
	
	def __init__(
		self,
		vision_engine: Optional[VisionEngine] = None,
		dom_processor: Optional[IncrementalDOMProcessor] = None,
		accessibility_processor: Optional[AccessibilityProcessor] = None,
		perception_fusion: Optional[MultiModalPerceptionFusion] = None,
		llm = None
	):
		self.vision_engine = vision_engine
		self.dom_processor = dom_processor
		self.accessibility_processor = accessibility_processor
		self.perception_fusion = perception_fusion or MultiModalPerceptionFusion()
		self.llm = llm
		
		# Initialize resolution strategies - LLM first if available
		self.strategies = []
		
		if llm:
			self.strategies.append(LLMFinderStrategy(llm))
		
		self.strategies.append(SimpleFinderStrategy())  # Fallback strategy
		
		if dom_processor:
			self.strategies.append(DOMProcessorStrategy(dom_processor))
		
		# Strategy weights for scoring
		self.strategy_weights = {
			ResolutionStrategy.TEST_ID: 1.0,
			ResolutionStrategy.ARIA_LABEL: 0.9,
			ResolutionStrategy.CSS_SELECTOR: 0.85,
			ResolutionStrategy.TEXT_CONTENT: 0.8,
			ResolutionStrategy.SEMANTIC_SEARCH: 0.75,
			ResolutionStrategy.VISUAL_GROUNDING: 0.7,
			ResolutionStrategy.PROXIMITY: 0.6,
			ResolutionStrategy.XPATH: 0.5
		}
		
		# Cache for resolved elements
		self._resolution_cache: Dict[str, ResolvedElement] = {}
		self._cache_ttl_seconds = 10
	
	@time_execution_async("resolve_element")
	async def resolve_element(
		self,
		intent: ElementIntent,
		perception_data: Dict[str, Any],
		page: Page
	) -> Optional[ResolvedElement]:
		"""Resolve an element using multiple strategies"""
		
		logger.debug(f"Resolving element: description='{intent.description}', type='{intent.element_type}'")
		logger.debug(f"Element attributes: {intent.attributes}")
		
		# Try each strategy
		for strategy in self.strategies:
			try:
				logger.debug(f"Trying strategy: {strategy.__class__.__name__}")
				element = await strategy.resolve(intent, perception_data, page)
				if element:
					logger.debug(f"Found element with {strategy.__class__.__name__}: selector={element.selector}")
					# Return a ResolvedElement
					return ResolvedElement(
						element=element,
						confidence=0.9,
						strategy=ResolutionStrategy.SEMANTIC_SEARCH,
						resolution_time_ms=0
					)
				else:
					logger.debug(f"No element found with {strategy.__class__.__name__}")
			except Exception as e:
				logger.debug(f"Strategy {strategy.__class__.__name__} failed: {e}")
				# Log but continue with other strategies
				pass
		
		logger.warning(f"Could not resolve element: {intent.description}")
		return None
	
	def _select_strategies(self, intent: ElementIntent) -> List[ResolutionStrategy]:
		"""Select appropriate strategies based on intent"""
		strategies = []
		
		# Always try test ID if available
		if intent.test_id:
			strategies.append(ResolutionStrategy.TEST_ID)
		
		# ARIA label strategy
		if intent.aria_label or "label" in intent.description.lower():
			strategies.append(ResolutionStrategy.ARIA_LABEL)
		
		# CSS selector strategy
		if intent.css_selector:
			strategies.append(ResolutionStrategy.CSS_SELECTOR)
		
		# Text-based strategies
		if intent.text_content or any(word in intent.description.lower() for word in ["text", "contains", "says"]):
			strategies.append(ResolutionStrategy.TEXT_CONTENT)
		
		# Visual strategies
		if self.vision_engine and ("button" in intent.description.lower() or "image" in intent.description.lower()):
			strategies.append(ResolutionStrategy.VISUAL_GROUNDING)
		
		# Semantic search for complex descriptions
		if len(intent.description.split()) > 3:
			strategies.append(ResolutionStrategy.SEMANTIC_SEARCH)
		
		# Proximity-based if context provided
		if intent.near_element:
			strategies.append(ResolutionStrategy.PROXIMITY)
		
		# Default fallback
		if not strategies:
			strategies = [
				ResolutionStrategy.SEMANTIC_SEARCH,
				ResolutionStrategy.TEXT_CONTENT,
				ResolutionStrategy.VISUAL_GROUNDING
			]
		
		return strategies
	
	async def _execute_strategy(
		self,
		strategy: ResolutionStrategy,
		intent: ElementIntent,
		context: Dict[str, Any]
	) -> Optional[List[PerceptionElement]]:
		"""Execute a specific resolution strategy"""
		
		if strategy == ResolutionStrategy.TEST_ID:
			return await self._resolve_by_test_id(intent, context)
		
		elif strategy == ResolutionStrategy.ARIA_LABEL:
			return await self._resolve_by_aria_label(intent, context)
		
		elif strategy == ResolutionStrategy.CSS_SELECTOR:
			return await self._resolve_by_css_selector(intent, context)
		
		elif strategy == ResolutionStrategy.TEXT_CONTENT:
			return await self._resolve_by_text(intent, context)
		
		elif strategy == ResolutionStrategy.VISUAL_GROUNDING:
			return await self._resolve_by_vision(intent, context)
		
		elif strategy == ResolutionStrategy.SEMANTIC_SEARCH:
			return await self._resolve_by_semantic_search(intent, context)
		
		elif strategy == ResolutionStrategy.PROXIMITY:
			return await self._resolve_by_proximity(intent, context)
		
		elif strategy == ResolutionStrategy.XPATH:
			return await self._resolve_by_xpath(intent, context)
		
		return None
	
	# Strategy implementations
	
	async def _resolve_by_test_id(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve by test ID - highest priority"""
		if not intent.test_id or not self.dom_processor:
			return None
		
		query = PerceptionQuery(
			description=f"Element with test ID: {intent.test_id}",
			attributes={"selector": f"[data-testid='{intent.test_id}'], [data-test-id='{intent.test_id}'], #{intent.test_id}"},
			context=context
		)
		
		elements = await self.dom_processor.find_elements(query)
		return elements if elements else None
	
	async def _resolve_by_aria_label(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve by ARIA label"""
		if not self.accessibility_processor:
			return None
		
		label = intent.aria_label or intent.description
		
		query = PerceptionQuery(
			description=f"Element with label: {label}",
			attributes={"label": label},
			context=context
		)
		
		elements = await self.accessibility_processor.find_elements(query)
		return elements if elements else None
	
	async def _resolve_by_css_selector(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve by CSS selector"""
		if not intent.css_selector or not self.dom_processor:
			return None
		
		query = PerceptionQuery(
			description=f"Element matching selector: {intent.css_selector}",
			attributes={"selector": intent.css_selector},
			context=context
		)
		
		elements = await self.dom_processor.find_elements(query)
		return elements if elements else None
	
	async def _resolve_by_text(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve by text content"""
		if not self.dom_processor:
			return None
		
		text = intent.text_content or intent.description
		
		query = PerceptionQuery(
			description=f"Element containing text: {text}",
			attributes={"text": text},
			context=context
		)
		
		elements = await self.dom_processor.find_elements(query)
		return elements if elements else None
	
	async def _resolve_by_vision(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve using visual grounding"""
		if not self.vision_engine or not context.get("screenshot"):
			return None
		
		query = PerceptionQuery(
			description=intent.description,
			element_type=intent.element_type,
			context=context
		)
		
		elements = await self.vision_engine.find_elements(query)
		return elements if elements else None
	
	async def _resolve_by_semantic_search(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve using semantic understanding across all systems"""
		if not self.perception_fusion:
			return None
		
		# Run all perception systems
		results = {}
		
		if self.dom_processor:
			query = PerceptionQuery(
				description=intent.description, 
				element_type=intent.element_type,
				attributes=intent.attributes,
				context=context
			)
			results["dom"] = await self.dom_processor.find_elements(query)
		
		if self.accessibility_processor:
			query = PerceptionQuery(description=intent.description, context=context)
			results["accessibility"] = await self.accessibility_processor.find_elements(query)
		
		if self.vision_engine and context.get("screenshot"):
			query = PerceptionQuery(description=intent.description, context=context)
			results["vision"] = await self.vision_engine.find_elements(query)
		
		# Flatten all results
		all_elements = []
		for elements in results.values():
			if elements:
				all_elements.extend(elements)
		
		return all_elements if all_elements else None
	
	async def _resolve_by_proximity(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve by proximity to another element"""
		if not intent.near_element:
			return None
		
		# First resolve the reference element
		reference = await self.resolve_element(intent.near_element, context, context["page"])
		
		if not reference or not reference.bounding_box:
			return None
		
		# Find elements near the reference
		all_elements = []
		
		# Get all elements from DOM
		if self.dom_processor:
			page_result = await self.dom_processor.analyze_page({"page": context["page"]})
			all_elements.extend(page_result.elements)
		
		# Filter by proximity
		nearby_elements = []
		max_distance = intent.proximity_threshold or 200  # pixels
		
		for element in all_elements:
			if element.bounding_box:
				distance = self._calculate_distance(reference.bounding_box, element.bounding_box)
				if distance <= max_distance:
					# Also check if it matches the description
					if self._element_matches_description(element, intent.description):
						nearby_elements.append(element)
		
		return nearby_elements if nearby_elements else None
	
	async def _resolve_by_xpath(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[List[PerceptionElement]]:
		"""Resolve by XPath - lowest priority due to brittleness"""
		if not intent.xpath:
			return None
		
		page = context["page"]
		
		try:
			elements_data = await page.evaluate("""
				(xpath) => {
					const result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
					const elements = [];
					
					for (let i = 0; i < result.snapshotLength; i++) {
						const el = result.snapshotItem(i);
						const rect = el.getBoundingClientRect();
						
						elements.push({
							type: el.tagName.toLowerCase(),
							text: el.textContent?.trim(),
							bbox: {
								x: rect.x,
								y: rect.y,
								width: rect.width,
								height: rect.height
							}
						});
					}
					
					return elements;
				}
			""", intent.xpath)
			
			return [
				PerceptionElement(
					type=data["type"],
					text=data.get("text", ""),
					bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
					xpath=intent.xpath
				)
				for data in elements_data
			]
			
		except Exception:
			return None
	
	# Scoring and ranking
	
	def _score_and_rank(
		self,
		results: List[Tuple[ResolutionStrategy, List[PerceptionElement]]],
		intent: ElementIntent
	) -> Optional[ResolvedElement]:
		"""Score and rank resolution results"""
		if not results:
			return None
		
		scored_elements = []
		
		for strategy, elements in results:
			strategy_weight = self.strategy_weights.get(strategy, 0.5)
			
			for element in elements:
				# Calculate element score
				score = self._calculate_element_score(element, intent, strategy_weight)
				scored_elements.append((score, strategy, element))
		
		# Sort by score descending
		scored_elements.sort(key=lambda x: x[0], reverse=True)
		
		if not scored_elements:
			return None
		
		# Get best match and alternatives
		best_score, best_strategy, best_element = scored_elements[0]
		
		# Confidence threshold
		if best_score < 0.4:
			return None
		
		# Get alternatives (different elements with good scores)
		alternatives = []
		seen_elements = {self._element_signature(best_element)}
		
		for score, strategy, element in scored_elements[1:]:
			sig = self._element_signature(element)
			if sig not in seen_elements and score > 0.5:
				alternatives.append(element)
				seen_elements.add(sig)
				if len(alternatives) >= 3:
					break
		
		return ResolvedElement(
			element=best_element,
			confidence=best_score,
			strategy=best_strategy,
			resolution_time_ms=0,  # Will be set by timing decorator
			alternatives=alternatives
		)
	
	def _calculate_element_score(
		self,
		element: PerceptionElement,
		intent: ElementIntent,
		strategy_weight: float
	) -> float:
		"""Calculate score for an element"""
		score = element.confidence * strategy_weight
		
		# Boost score based on matches
		if intent.element_type and element.type == intent.element_type:
			score *= 1.2
		
		if intent.text_content and element.text:
			if intent.text_content.lower() in element.text.lower():
				score *= 1.3
		
		# Penalize invisible or disabled elements
		if not element.is_visible:
			score *= 0.3
		
		if element.is_disabled and not intent.include_disabled:
			score *= 0.5
		
		# Boost interactive elements if looking for something to click
		if any(word in intent.description.lower() for word in ["click", "press", "tap", "select"]):
			if element.is_interactive:
				score *= 1.2
		
		return min(1.0, score)
	
	# Deep search fallback
	
	async def _deep_search(self, intent: ElementIntent, context: Dict[str, Any]) -> Optional[ResolvedElement]:
		"""Perform exhaustive search when normal strategies fail"""
		# This is a simplified version - in practice would be more sophisticated
		
		# Try all perception systems with relaxed criteria
		query = PerceptionQuery(
			description=intent.description,
			confidence_threshold=0.3  # Lower threshold
		)
		
		results = {}
		
		if self.dom_processor:
			dom_result = await self.dom_processor.analyze_page({"page": context["page"]})
			# Filter by description match
			matching = [e for e in dom_result.elements if self._element_matches_description(e, intent.description)]
			if matching:
				results["dom"] = matching
		
		if self.vision_engine and context.get("screenshot"):
			vision_elements = await self.vision_engine.find_elements(query)
			if vision_elements:
				results["vision"] = vision_elements
		
		# Try to find best match
		all_matches = []
		for system, elements in results.items():
			for element in elements:
				score = self._calculate_element_score(element, intent, 0.5)
				all_matches.append((score, ResolutionStrategy.COMBINED, element))
		
		if all_matches:
			all_matches.sort(key=lambda x: x[0], reverse=True)
			score, _, element = all_matches[0]
			
			if score > 0.3:
				return ResolvedElement(
					element=element,
					confidence=score,
					strategy=ResolutionStrategy.COMBINED,
					resolution_time_ms=0
				)
		
		return None
	
	# Helper methods
	
	def _element_matches_description(self, element: PerceptionElement, description: str) -> bool:
		"""Check if element matches description"""
		description_lower = description.lower()
		
		# Check text content
		if element.text and any(word in element.text.lower() for word in description_lower.split()):
			return True
		
		# Check label
		if element.label and any(word in element.label.lower() for word in description_lower.split()):
			return True
		
		# Check type
		if element.type and element.type in description_lower:
			return True
		
		# Check role
		if element.role and element.role in description_lower:
			return True
		
		return False
	
	def _calculate_distance(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
		"""Calculate distance between two bounding boxes"""
		center1_x = bbox1.x + bbox1.width / 2
		center1_y = bbox1.y + bbox1.height / 2
		center2_x = bbox2.x + bbox2.width / 2
		center2_y = bbox2.y + bbox2.height / 2
		
		return ((center2_x - center1_x) ** 2 + (center2_y - center1_y) ** 2) ** 0.5
	
	def _element_signature(self, element: PerceptionElement) -> str:
		"""Create a signature for element deduplication"""
		parts = [element.type]
		
		if element.selector:
			parts.append(element.selector)
		elif element.bounding_box:
			parts.append(f"{element.bounding_box.x},{element.bounding_box.y}")
		
		if element.text:
			parts.append(element.text[:50])
		
		return "|".join(parts)
	
	# Cache management
	
	def _get_cache_key(self, intent: ElementIntent) -> str:
		"""Generate cache key for intent"""
		parts = [
			intent.description,
			str(intent.element_type),
			str(intent.test_id),
			str(intent.css_selector),
			str(intent.text_content)
		]
		return "|".join(parts)
	
	def _get_from_cache(self, key: str) -> Optional[ResolvedElement]:
		"""Get element from cache if valid"""
		if key in self._resolution_cache:
			cached = self._resolution_cache[key]
			age = (datetime.now() - cached.element.timestamp).total_seconds()
			
			if age < self._cache_ttl_seconds:
				return cached
			else:
				del self._resolution_cache[key]
		
		return None
	
	def _add_to_cache(self, key: str, element: ResolvedElement) -> None:
		"""Add element to cache"""
		self._resolution_cache[key] = element
		
		# Clean old entries if cache is too large
		if len(self._resolution_cache) > 1000:
			# Remove oldest entries
			sorted_entries = sorted(
				self._resolution_cache.items(),
				key=lambda x: x[1].element.timestamp
			)
			
			for old_key, _ in sorted_entries[:200]:
				del self._resolution_cache[old_key]


class ElementNotFoundError(Exception):
	"""Raised when element cannot be resolved"""
	pass