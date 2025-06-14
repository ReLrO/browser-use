"""Intent system data models for browser automation"""

from typing import Any, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from uuid_extensions import uuid7str
from enum import Enum


class IntentType(str, Enum):
	"""Types of intents the system can handle"""
	NAVIGATION = "navigation"
	FORM_FILL = "form_fill"
	AUTHENTICATION = "authentication"
	SEARCH = "search"
	INTERACTION = "interaction"
	EXTRACTION = "extraction"
	VERIFICATION = "verification"
	COMPOSITE = "composite"
	CUSTOM = "custom"


class IntentPriority(str, Enum):
	"""Priority levels for intent execution"""
	CRITICAL = "critical"
	HIGH = "high"
	MEDIUM = "medium"
	LOW = "low"


class IntentConstraint(BaseModel):
	"""Constraints that must be satisfied during intent execution"""
	model_config = ConfigDict(extra='forbid')
	
	type: str = Field(description="Type of constraint (e.g., 'time_limit', 'element_must_exist')")
	value: Any = Field(description="Value for the constraint")
	description: Optional[str] = Field(None, description="Human-readable description")


class IntentParameter(BaseModel):
	"""Parameters required for intent execution"""
	model_config = ConfigDict(extra='forbid')
	
	name: str = Field(description="Parameter name")
	value: Any = Field(description="Parameter value")
	type: str = Field(description="Parameter type for validation")
	required: bool = Field(default=True, description="Whether parameter is required")
	sensitive: bool = Field(default=False, description="Whether parameter contains sensitive data")


class SuccessCriteria(BaseModel):
	"""Criteria for determining if an intent was successfully executed"""
	model_config = ConfigDict(extra='forbid')
	
	type: str = Field(description="Type of success check (e.g., 'element_visible', 'url_matches')")
	expected: Any = Field(description="Expected value or condition")
	description: Optional[str] = Field(None, description="Human-readable description")
	timeout: Optional[float] = Field(None, description="Timeout for this criteria in seconds")


class SubIntent(BaseModel):
	"""Sub-intent that's part of a larger intent"""
	model_config = ConfigDict(extra='forbid')
	
	id: str = Field(default_factory=uuid7str)
	description: str = Field(description="What this sub-intent accomplishes")
	type: IntentType = Field(description="Type of sub-intent")
	parameters: list[IntentParameter] = Field(default_factory=list)
	dependencies: list[str] = Field(default_factory=list, description="IDs of sub-intents that must complete first")
	optional: bool = Field(default=False, description="Whether this sub-intent is optional")


class Intent(BaseModel):
	"""Core intent model representing what the user wants to accomplish"""
	model_config = ConfigDict(extra='forbid')
	
	id: str = Field(default_factory=uuid7str)
	task_description: str = Field(description="Original task description from user")
	type: IntentType = Field(description="Primary type of intent")
	priority: IntentPriority = Field(default=IntentPriority.MEDIUM)
	
	# Decomposed understanding
	primary_goal: str = Field(description="Primary goal to accomplish")
	sub_intents: list[SubIntent] = Field(default_factory=list, description="Decomposed sub-tasks")
	
	# Execution parameters
	parameters: list[IntentParameter] = Field(default_factory=list)
	constraints: list[IntentConstraint] = Field(default_factory=list)
	success_criteria: list[SuccessCriteria] = Field(default_factory=list)
	
	# Context and metadata
	context: dict[str, Any] = Field(default_factory=dict, description="Additional context for execution")
	created_at: datetime = Field(default_factory=datetime.now)
	parent_intent_id: Optional[str] = Field(None, description="ID of parent intent if this is a sub-intent")
	
	# Execution tracking
	status: str = Field(default="pending", description="Current status of intent execution")
	attempts: int = Field(default=0, description="Number of execution attempts")
	last_error: Optional[str] = Field(None, description="Last error encountered")


class IntentAnalysisResult(BaseModel):
	"""Result of analyzing a user task into intents"""
	model_config = ConfigDict(extra='forbid')
	
	intent: Intent = Field(description="Analyzed intent")
	confidence: float = Field(description="Confidence in the analysis (0-1)")
	alternative_interpretations: list[Intent] = Field(default_factory=list)
	requires_clarification: bool = Field(default=False)
	clarification_questions: list[str] = Field(default_factory=list)


class IntentExecutionResult(BaseModel):
	"""Result of executing an intent"""
	model_config = ConfigDict(extra='forbid')
	
	intent_id: str = Field(description="ID of the executed intent")
	success: bool = Field(description="Whether the intent was successfully executed")
	sub_intent_results: dict[str, bool] = Field(default_factory=dict)
	
	# Execution details
	actions_taken: list[dict[str, Any]] = Field(default_factory=list)
	duration_seconds: float = Field(description="Total execution time")
	tokens_used: int = Field(default=0, description="Total tokens used")
	
	# Verification
	criteria_met: dict[str, bool] = Field(default_factory=dict, description="Which success criteria were met")
	verification_screenshot: Optional[str] = Field(None, description="Base64 screenshot for verification")
	
	# Error handling
	errors: list[str] = Field(default_factory=list)
	recovery_actions: list[dict[str, Any]] = Field(default_factory=list)


class ElementIntent(BaseModel):
	"""Intent to find/interact with a specific element"""
	model_config = ConfigDict(extra='forbid')
	
	# Core description
	description: str = Field(description="Natural language description of the element")
	element_type: Optional[str] = Field(None, description="Type of element (button, input, link, etc)")
	
	# Specific selectors (in priority order)
	test_id: Optional[str] = Field(None, description="Test ID attribute")
	aria_label: Optional[str] = Field(None, description="ARIA label")
	css_selector: Optional[str] = Field(None, description="CSS selector")
	xpath: Optional[str] = Field(None, description="XPath selector")
	text_content: Optional[str] = Field(None, description="Text content to match")
	
	# Context and constraints
	near_element: Optional['ElementIntent'] = Field(None, description="Element should be near this one")
	proximity_threshold: Optional[float] = Field(None, description="Max distance in pixels if using proximity")
	include_disabled: bool = Field(default=False, description="Include disabled elements")
	visible_only: bool = Field(default=True, description="Only find visible elements")
	
	# Additional hints
	attributes: dict[str, Any] = Field(default_factory=dict, description="Expected attributes")
	index: Optional[int] = Field(None, description="If multiple matches, which one (0-based)")


# Update the forward reference
ElementIntent.model_rebuild()