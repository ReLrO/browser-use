"""Streaming state management data models"""

from typing import Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid_extensions import uuid7str
from enum import Enum


class EventType(str, Enum):
	"""Types of events in the browser"""
	DOM_MUTATION = "dom_mutation"
	NAVIGATION = "navigation"
	NETWORK_REQUEST = "network_request"
	NETWORK_RESPONSE = "network_response"
	CONSOLE_LOG = "console_log"
	USER_INTERACTION = "user_interaction"
	PAGE_LOAD = "page_load"
	ERROR = "error"
	CUSTOM = "custom"


class EventPriority(str, Enum):
	"""Priority of events for processing"""
	CRITICAL = "critical"
	HIGH = "high"
	MEDIUM = "medium"
	LOW = "low"
	DEBUG = "debug"


class DOMChange(BaseModel):
	"""Represents a change in the DOM"""
	model_config = ConfigDict(extra='forbid')
	
	type: str = Field(description="Type of mutation: added|removed|modified|attributes")
	target_selector: Optional[str] = Field(None, description="CSS selector of changed element")
	target_xpath: Optional[str] = Field(None, description="XPath of changed element")
	old_value: Optional[Any] = Field(None, description="Previous value if applicable")
	new_value: Optional[Any] = Field(None, description="New value if applicable")
	attribute_name: Optional[str] = Field(None, description="Changed attribute name if applicable")
	added_nodes: list[dict] = Field(default_factory=list, description="Nodes added to DOM")
	removed_nodes: list[dict] = Field(default_factory=list, description="Nodes removed from DOM")


class NetworkEvent(BaseModel):
	"""Represents a network event"""
	model_config = ConfigDict(extra='forbid')
	
	url: str = Field(description="URL of the request/response")
	method: Optional[str] = Field(None, description="HTTP method")
	status: Optional[int] = Field(None, description="HTTP status code")
	resource_type: Optional[str] = Field(None, description="Type of resource")
	size: Optional[int] = Field(None, description="Size in bytes")
	duration_ms: Optional[float] = Field(None, description="Duration in milliseconds")
	headers: dict[str, str] = Field(default_factory=dict)
	is_navigation: bool = Field(default=False)


class ConsoleEvent(BaseModel):
	"""Represents a console event"""
	model_config = ConfigDict(extra='forbid')
	
	level: str = Field(description="Console level: log|info|warn|error")
	message: str = Field(description="Console message")
	args: list[Any] = Field(default_factory=list, description="Console arguments")
	stack_trace: Optional[str] = Field(None, description="Stack trace if error")


class BrowserEvent(BaseModel):
	"""Base event model for all browser events"""
	model_config = ConfigDict(extra='forbid')
	
	id: str = Field(default_factory=uuid7str)
	type: EventType = Field(description="Type of event")
	priority: EventPriority = Field(default=EventPriority.MEDIUM)
	timestamp: datetime = Field(default_factory=datetime.now)
	
	# Event-specific data
	dom_change: Optional[DOMChange] = Field(None)
	network_event: Optional[NetworkEvent] = Field(None)
	console_event: Optional[ConsoleEvent] = Field(None)
	
	# Common metadata
	page_url: Optional[str] = Field(None, description="Current page URL when event occurred")
	tab_id: Optional[str] = Field(None, description="Tab ID where event occurred")
	custom_data: dict[str, Any] = Field(default_factory=dict)
	
	# Relevance scoring
	relevance_score: float = Field(default=0.5, description="Relevance score 0-1")
	tags: list[str] = Field(default_factory=list, description="Tags for filtering")


class EventFilter(BaseModel):
	"""Filter for querying events"""
	model_config = ConfigDict(extra='forbid')
	
	event_types: Optional[list[EventType]] = Field(None)
	priorities: Optional[list[EventPriority]] = Field(None)
	since_timestamp: Optional[datetime] = Field(None)
	until_timestamp: Optional[datetime] = Field(None)
	tab_ids: Optional[list[str]] = Field(None)
	tags: Optional[list[str]] = Field(None)
	min_relevance: Optional[float] = Field(None)
	url_pattern: Optional[str] = Field(None)
	limit: Optional[int] = Field(100)


class StreamState(BaseModel):
	"""Current state derived from event streams"""
	model_config = ConfigDict(extra='forbid')
	
	# Current page state
	current_url: str = Field(description="Current page URL")
	page_title: Optional[str] = Field(None)
	is_loading: bool = Field(default=False)
	
	# Recent activity summary
	recent_dom_changes: int = Field(default=0, description="DOM changes in last 5 seconds")
	recent_network_requests: int = Field(default=0, description="Network requests in last 5 seconds")
	recent_errors: list[str] = Field(default_factory=list, description="Recent error messages")
	
	# Key elements present (derived from events)
	form_elements: list[dict] = Field(default_factory=list)
	interactive_elements: list[dict] = Field(default_factory=list)
	
	# Network state
	pending_requests: list[str] = Field(default_factory=list)
	failed_requests: list[str] = Field(default_factory=list)
	
	# Derived insights
	is_stable: bool = Field(default=True, description="Whether page is stable (no recent changes)")
	has_errors: bool = Field(default=False)
	last_update: datetime = Field(default_factory=datetime.now)


class EventStreamConfig(BaseModel):
	"""Configuration for event streaming"""
	model_config = ConfigDict(extra='forbid')
	
	# Event collection settings
	collect_dom_mutations: bool = Field(default=True)
	collect_network: bool = Field(default=True)
	collect_console: bool = Field(default=True)
	collect_navigation: bool = Field(default=True)
	
	# Performance settings
	max_events_per_second: int = Field(default=100, description="Rate limit for events")
	max_event_queue_size: int = Field(default=10000)
	event_ttl_seconds: int = Field(default=300, description="How long to keep events")
	
	# Filtering settings
	dom_mutation_throttle_ms: int = Field(default=50, description="Throttle DOM mutations")
	ignored_network_patterns: list[str] = Field(
		default_factory=lambda: ["*analytics*", "*tracking*", "*.gif", "*.png", "*.jpg"]
	)
	console_levels: list[str] = Field(default_factory=lambda: ["warn", "error"])
	
	# Relevance scoring
	auto_score_relevance: bool = Field(default=True)
	relevance_decay_rate: float = Field(default=0.95, description="How fast relevance decays over time")