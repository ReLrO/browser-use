"""Base classes and interfaces for multi-modal perception"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid_extensions import uuid7str


class BoundingBox(BaseModel):
	"""Represents a bounding box for an element"""
	model_config = ConfigDict(extra='forbid')
	
	x: float = Field(description="X coordinate of top-left corner")
	y: float = Field(description="Y coordinate of top-left corner")
	width: float = Field(description="Width of the box")
	height: float = Field(description="Height of the box")
	
	@property
	def center_x(self) -> float:
		"""Get center X coordinate"""
		return self.x + self.width / 2
	
	@property
	def center_y(self) -> float:
		"""Get center Y coordinate"""
		return self.y + self.height / 2
	
	@property
	def area(self) -> float:
		"""Get area of the box"""
		return self.width * self.height
	
	def contains_point(self, x: float, y: float) -> bool:
		"""Check if a point is inside the box"""
		return (self.x <= x <= self.x + self.width and
				self.y <= y <= self.y + self.height)
	
	def intersects(self, other: 'BoundingBox') -> bool:
		"""Check if this box intersects with another"""
		return not (self.x + self.width < other.x or
				   other.x + other.width < self.x or
				   self.y + self.height < other.y or
				   other.y + other.height < self.y)


class PerceptionElement(BaseModel):
	"""Base class for elements detected by perception systems"""
	model_config = ConfigDict(extra='forbid')
	
	id: str = Field(default_factory=uuid7str)
	type: str = Field(description="Type of element (button, input, text, etc)")
	confidence: float = Field(default=1.0, description="Confidence score 0-1")
	timestamp: datetime = Field(default_factory=datetime.now)
	
	# Location information
	bounding_box: Optional[BoundingBox] = Field(None)
	selector: Optional[str] = Field(None, description="CSS selector if available")
	xpath: Optional[str] = Field(None, description="XPath if available")
	
	# Content
	text: Optional[str] = Field(None, description="Text content of element")
	attributes: dict[str, Any] = Field(default_factory=dict)
	
	# Semantic information
	role: Optional[str] = Field(None, description="ARIA role or semantic role")
	label: Optional[str] = Field(None, description="Accessible label")
	description: Optional[str] = Field(None, description="Human-readable description")
	
	# Relationships
	parent_id: Optional[str] = Field(None)
	child_ids: list[str] = Field(default_factory=list)
	related_ids: list[str] = Field(default_factory=list)
	
	# State
	is_visible: bool = Field(default=True)
	is_interactive: bool = Field(default=False)
	is_focused: bool = Field(default=False)
	is_disabled: bool = Field(default=False)


class PerceptionResult(BaseModel):
	"""Result from a perception system"""
	model_config = ConfigDict(extra='forbid')
	
	elements: list[PerceptionElement] = Field(default_factory=list)
	page_context: dict[str, Any] = Field(default_factory=dict)
	processing_time_ms: float = Field(default=0)
	errors: list[str] = Field(default_factory=list)


class PerceptionQuery(BaseModel):
	"""Query for finding elements"""
	model_config = ConfigDict(extra='forbid')
	
	description: str = Field(description="Natural language description of what to find")
	element_type: Optional[str] = Field(None, description="Specific type to look for")
	attributes: dict[str, Any] = Field(default_factory=dict, description="Required attributes")
	context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
	confidence_threshold: float = Field(default=0.7, description="Minimum confidence")


class PerceptionCapability(BaseModel):
	"""Describes capabilities of a perception system"""
	model_config = ConfigDict(extra='forbid')
	
	name: str = Field(description="Name of the perception system")
	supported_queries: list[str] = Field(description="Types of queries supported")
	strengths: list[str] = Field(description="What this system is good at")
	limitations: list[str] = Field(description="Known limitations")
	performance_ms: float = Field(description="Typical processing time in ms")


class IPerceptionSystem(ABC):
	"""Interface for perception systems"""
	
	@abstractmethod
	async def initialize(self, config: dict[str, Any]) -> None:
		"""Initialize the perception system"""
		pass
	
	@abstractmethod
	async def analyze_page(self, page_data: dict[str, Any]) -> PerceptionResult:
		"""Analyze a page and return detected elements"""
		pass
	
	@abstractmethod
	async def find_element(self, query: PerceptionQuery) -> Optional[PerceptionElement]:
		"""Find a specific element based on query"""
		pass
	
	@abstractmethod
	async def find_elements(self, query: PerceptionQuery) -> list[PerceptionElement]:
		"""Find all elements matching query"""
		pass
	
	@abstractmethod
	def get_capabilities(self) -> PerceptionCapability:
		"""Get capabilities of this perception system"""
		pass
	
	@abstractmethod
	async def cleanup(self) -> None:
		"""Clean up resources"""
		pass


class PerceptionFusion:
	"""Base class for fusing results from multiple perception systems"""
	
	def __init__(self):
		self.systems: dict[str, IPerceptionSystem] = {}
	
	def register_system(self, name: str, system: IPerceptionSystem) -> None:
		"""Register a perception system"""
		self.systems[name] = system
	
	async def fuse_results(self, results: dict[str, PerceptionResult]) -> PerceptionResult:
		"""Fuse results from multiple systems"""
		# This is a simple implementation - can be overridden for more sophisticated fusion
		all_elements = []
		all_errors = []
		total_time = 0
		
		for system_name, result in results.items():
			all_elements.extend(result.elements)
			all_errors.extend(result.errors)
			total_time += result.processing_time_ms
		
		# Deduplicate elements based on location and type
		unique_elements = self._deduplicate_elements(all_elements)
		
		# Merge context from all systems
		merged_context = {}
		for result in results.values():
			merged_context.update(result.page_context)
		
		return PerceptionResult(
			elements=unique_elements,
			page_context=merged_context,
			processing_time_ms=total_time,
			errors=all_errors
		)
	
	def _deduplicate_elements(self, elements: list[PerceptionElement]) -> list[PerceptionElement]:
		"""Deduplicate elements based on location and type"""
		unique = []
		seen_locations = set()
		
		# Sort by confidence descending
		sorted_elements = sorted(elements, key=lambda e: e.confidence, reverse=True)
		
		for element in sorted_elements:
			if element.bounding_box:
				# Create a location key
				location_key = (
					round(element.bounding_box.x, 1),
					round(element.bounding_box.y, 1),
					round(element.bounding_box.width, 1),
					round(element.bounding_box.height, 1),
					element.type
				)
				
				if location_key not in seen_locations:
					seen_locations.add(location_key)
					unique.append(element)
			else:
				# No location info, check by selector/text
				is_duplicate = False
				for existing in unique:
					if (element.selector == existing.selector and
						element.text == existing.text and
						element.type == existing.type):
						is_duplicate = True
						break
				
				if not is_duplicate:
					unique.append(element)
		
		return unique