"""Intent to action mapping system with pattern matching"""

import re
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from browser_use.core.intent.views import Intent, SubIntent, IntentType, IntentParameter
from browser_use.core.orchestrator.service import Action, ActionType
from browser_use.core.resolver.service import ElementIntent


class PatternType(str, Enum):
	"""Types of patterns for matching"""
	EXACT = "exact"
	REGEX = "regex"
	CONTAINS = "contains"
	SEMANTIC = "semantic"


@dataclass
class IntentPattern:
	"""Pattern for matching intents to actions"""
	pattern: str
	pattern_type: PatternType
	intent_type: Optional[IntentType] = None
	action_generator: Optional[Callable] = None
	priority: int = 0
	
	def matches(self, intent_text: str, intent_type: Optional[IntentType] = None) -> bool:
		"""Check if pattern matches the intent"""
		# Check intent type if specified
		if self.intent_type and intent_type != self.intent_type:
			return False
		
		# Check text pattern
		if self.pattern_type == PatternType.EXACT:
			return intent_text.lower() == self.pattern.lower()
		
		elif self.pattern_type == PatternType.CONTAINS:
			return self.pattern.lower() in intent_text.lower()
		
		elif self.pattern_type == PatternType.REGEX:
			return bool(re.search(self.pattern, intent_text, re.IGNORECASE))
		
		elif self.pattern_type == PatternType.SEMANTIC:
			# Simplified semantic matching
			pattern_words = set(self.pattern.lower().split())
			intent_words = set(intent_text.lower().split())
			overlap = len(pattern_words & intent_words)
			return overlap >= len(pattern_words) * 0.6
		
		return False


class IntentToActionMapper:
	"""Maps intents to concrete actions using patterns and rules"""
	
	def __init__(self):
		self.patterns: List[IntentPattern] = []
		self._register_default_patterns()
	
	def register_pattern(
		self,
		pattern: str,
		pattern_type: PatternType,
		action_generator: Callable,
		intent_type: Optional[IntentType] = None,
		priority: int = 0
	) -> None:
		"""Register a new pattern for intent mapping"""
		self.patterns.append(IntentPattern(
			pattern=pattern,
			pattern_type=pattern_type,
			intent_type=intent_type,
			action_generator=action_generator,
			priority=priority
		))
		
		# Sort by priority descending
		self.patterns.sort(key=lambda p: p.priority, reverse=True)
	
	async def map_intent_to_actions(self, intent: Intent) -> List[Action]:
		"""Map an intent to a list of actions"""
		all_actions = []
		
		# Process each sub-intent
		for sub_intent in intent.sub_intents:
			actions = await self.map_sub_intent_to_actions(sub_intent)
			all_actions.extend(actions)
		
		# If no sub-intents, try to map the main intent
		if not intent.sub_intents:
			actions = await self._map_by_patterns(
				intent.primary_goal,
				intent.type,
				intent.parameters
			)
			all_actions.extend(actions)
		
		return all_actions
	
	async def map_sub_intent_to_actions(self, sub_intent: SubIntent) -> List[Action]:
		"""Map a sub-intent to actions"""
		# Try pattern matching first
		actions = await self._map_by_patterns(
			sub_intent.description,
			sub_intent.type,
			sub_intent.parameters
		)
		
		if actions:
			# Add sub-intent ID prefix
			for action in actions:
				action.id = f"{sub_intent.id}_{action.id}"
			return actions
		
		# Fallback to type-based mapping
		return await self._map_by_type(sub_intent)
	
	async def _map_by_patterns(
		self,
		description: str,
		intent_type: Optional[IntentType],
		parameters: List[IntentParameter]
	) -> List[Action]:
		"""Map using registered patterns"""
		for pattern in self.patterns:
			if pattern.matches(description, intent_type):
				if pattern.action_generator:
					# Convert parameters to dict
					param_dict = {p.name: p.value for p in parameters}
					
					# Generate actions
					actions = await pattern.action_generator(description, param_dict)
					if actions:
						return actions if isinstance(actions, list) else [actions]
		
		return []
	
	async def _map_by_type(self, sub_intent: SubIntent) -> List[Action]:
		"""Fallback mapping based on intent type"""
		actions = []
		base_id = sub_intent.id
		
		if sub_intent.type == IntentType.NAVIGATION:
			# Extract URL
			url = self._get_param_value(sub_intent, "url")
			if not url:
				# Try to extract from description
				url = self._extract_url_from_text(sub_intent.description)
			
			if url:
				actions.append(Action(
					id=f"{base_id}_nav",
					type=ActionType.NAVIGATE,
					parameters={"url": url}
				))
		
		elif sub_intent.type == IntentType.FORM_FILL:
			# Map form fields to type actions
			form_data = self._get_param_value(sub_intent, "form_data", {})
			
			for field_name, value in form_data.items():
				actions.append(Action(
					id=f"{base_id}_fill_{field_name}",
					type=ActionType.TYPE,
					parameters={
						"element_intent": ElementIntent(
							description=f"Form field for {field_name}",
							element_type="input",
							attributes={"name": field_name}
						),
						"text": str(value),
						"clear_first": True
					}
				))
			
			# Add submit action if specified
			if self._get_param_value(sub_intent, "submit", False):
				actions.append(Action(
					id=f"{base_id}_submit",
					type=ActionType.CLICK,
					parameters={
						"element_intent": ElementIntent(
							description="Submit button",
							element_type="button",
							text_content="Submit"
						)
					}
				))
		
		elif sub_intent.type == IntentType.AUTHENTICATION:
			# Login flow
			username = self._get_param_value(sub_intent, "username")
			password = self._get_param_value(sub_intent, "password")
			provider = self._get_param_value(sub_intent, "provider")
			
			if provider and provider.lower() in ["google", "github", "microsoft"]:
				# OAuth flow
				actions.append(Action(
					id=f"{base_id}_oauth_click",
					type=ActionType.CLICK,
					parameters={
						"element_intent": ElementIntent(
							description=f"Sign in with {provider} button",
							text_content=provider
						)
					}
				))
			else:
				# Traditional login
				if username:
					actions.append(Action(
						id=f"{base_id}_username",
						type=ActionType.TYPE,
						parameters={
							"element_intent": ElementIntent(
								description="Username or email field",
								element_type="input",
								attributes={"type": "email", "name": "username"}
							),
							"text": username,
							"clear_first": True
						}
					))
				
				if password:
					actions.append(Action(
						id=f"{base_id}_password",
						type=ActionType.TYPE,
						parameters={
							"element_intent": ElementIntent(
								description="Password field",
								element_type="input",
								attributes={"type": "password"}
							),
							"text": password,
							"clear_first": True
						}
					))
				
				actions.append(Action(
					id=f"{base_id}_login",
					type=ActionType.CLICK,
					parameters={
						"element_intent": ElementIntent(
							description="Login or Sign in button",
							element_type="button"
						)
					}
				))
		
		elif sub_intent.type == IntentType.SEARCH:
			query = self._get_param_value(sub_intent, "query")
			if query:
				# Type in search box
				actions.append(Action(
					id=f"{base_id}_search_type",
					type=ActionType.TYPE,
					parameters={
						"element_intent": ElementIntent(
							description="Search input field",
							element_type="input",
							attributes={"type": "search"}
						),
						"text": query,
						"clear_first": True
					}
				))
				
				# Press Enter or click search
				actions.append(Action(
					id=f"{base_id}_search_submit",
					type=ActionType.KEYBOARD,
					parameters={"key": "Enter"}
				))
		
		elif sub_intent.type == IntentType.EXTRACTION:
			# Data extraction
			selector = self._get_param_value(sub_intent, "selector")
			if selector:
				actions.append(Action(
					id=f"{base_id}_extract",
					type=ActionType.EXTRACT,
					parameters={
						"selector": selector,
						"attribute": self._get_param_value(sub_intent, "attribute", "textContent")
					},
					can_parallel=True
				))
		
		return actions
	
	def _register_default_patterns(self):
		"""Register default patterns for common intents"""
		
		# Navigation patterns
		self.register_pattern(
			r"(go to|navigate to|open|visit)\s+(.+)",
			PatternType.REGEX,
			self._generate_navigation_action,
			priority=10
		)
		
		# Click patterns
		self.register_pattern(
			r"(click|press|tap)\s+(on\s+)?(the\s+)?(.+)",
			PatternType.REGEX,
			self._generate_click_action,
			priority=10
		)
		
		# Type patterns
		self.register_pattern(
			r"(type|enter|input|fill)\s+[\"']([^\"']+)[\"']\s*(in|into)?\s*(.+)?",
			PatternType.REGEX,
			self._generate_type_action,
			priority=10
		)
		
		# Scroll patterns
		self.register_pattern(
			r"scroll\s+(up|down|left|right)(\s+by\s+(\d+))?",
			PatternType.REGEX,
			self._generate_scroll_action,
			priority=8
		)
		
		# Wait patterns
		self.register_pattern(
			r"wait\s+(for\s+)?(\d+)\s*(seconds?|ms|milliseconds?)?",
			PatternType.REGEX,
			self._generate_wait_action,
			priority=8
		)
		
		# Screenshot patterns
		self.register_pattern(
			"screenshot",
			PatternType.CONTAINS,
			self._generate_screenshot_action,
			priority=7
		)
		
		# Form submission
		self.register_pattern(
			"submit",
			PatternType.CONTAINS,
			self._generate_submit_action,
			priority=9
		)
	
	# Action generators
	
	async def _generate_navigation_action(self, description: str, params: dict) -> Action:
		"""Generate navigation action from pattern match"""
		match = re.search(r"(go to|navigate to|open|visit)\s+(.+)", description, re.IGNORECASE)
		if match:
			url = match.group(2).strip()
			
			# Add protocol if missing
			if not url.startswith(("http://", "https://", "file://")):
				url = f"https://{url}"
			
			return Action(
				id="navigate",
				type=ActionType.NAVIGATE,
				parameters={"url": url}
			)
		return None
	
	async def _generate_click_action(self, description: str, params: dict) -> Action:
		"""Generate click action from pattern match"""
		match = re.search(r"(click|press|tap)\s+(on\s+)?(the\s+)?(.+)", description, re.IGNORECASE)
		if match:
			target_desc = match.group(4).strip()
			
			return Action(
				id="click",
				type=ActionType.CLICK,
				parameters={
					"element_intent": ElementIntent(
						description=target_desc
					)
				}
			)
		return None
	
	async def _generate_type_action(self, description: str, params: dict) -> List[Action]:
		"""Generate type action from pattern match"""
		match = re.search(
			r"(type|enter|input|fill)\s+[\"']([^\"']+)[\"']\s*(in|into)?\s*(.+)?",
			description,
			re.IGNORECASE
		)
		
		if match:
			text = match.group(2)
			target = match.group(4)
			
			actions = []
			
			# Click on field first if target specified
			if target:
				actions.append(Action(
					id="focus_field",
					type=ActionType.CLICK,
					parameters={
						"element_intent": ElementIntent(
							description=target.strip()
						)
					}
				))
			
			# Type the text
			actions.append(Action(
				id="type_text",
				type=ActionType.TYPE,
				parameters={
					"text": text,
					"element_intent": ElementIntent(
						description=target.strip() if target else "focused input field"
					) if target else None
				}
			))
			
			return actions
		
		return []
	
	async def _generate_scroll_action(self, description: str, params: dict) -> Action:
		"""Generate scroll action from pattern match"""
		match = re.search(r"scroll\s+(up|down|left|right)(\s+by\s+(\d+))?", description, re.IGNORECASE)
		if match:
			direction = match.group(1).lower()
			amount = int(match.group(3)) if match.group(3) else 500
			
			return Action(
				id="scroll",
				type=ActionType.SCROLL,
				parameters={
					"direction": direction,
					"amount": amount
				}
			)
		return None
	
	async def _generate_wait_action(self, description: str, params: dict) -> Action:
		"""Generate wait action from pattern match"""
		match = re.search(r"wait\s+(for\s+)?(\d+)\s*(seconds?|ms|milliseconds?)?", description, re.IGNORECASE)
		if match:
			duration = int(match.group(2))
			unit = match.group(3)
			
			# Convert to milliseconds
			if unit and "second" in unit.lower():
				duration *= 1000
			
			return Action(
				id="wait",
				type=ActionType.WAIT,
				parameters={"duration_ms": duration}
			)
		return None
	
	async def _generate_screenshot_action(self, description: str, params: dict) -> Action:
		"""Generate screenshot action"""
		full_page = "full" in description.lower() or "entire" in description.lower()
		
		return Action(
			id="screenshot",
			type=ActionType.SCREENSHOT,
			parameters={"full_page": full_page},
			can_parallel=True
		)
	
	async def _generate_submit_action(self, description: str, params: dict) -> Action:
		"""Generate form submission action"""
		# Try to be smart about what to click
		element_intent = ElementIntent(
			description="Submit button",
			element_type="button",
			text_content="Submit"
		)
		
		# Check for specific form mentioned
		if "form" in description.lower():
			words = description.lower().split()
			if "login" in words:
				element_intent.text_content = "Log in"
			elif "search" in words:
				element_intent.text_content = "Search"
			elif "register" in words or "signup" in words:
				element_intent.text_content = "Sign up"
		
		return Action(
			id="submit",
			type=ActionType.CLICK,
			parameters={"element_intent": element_intent}
		)
	
	# Helper methods
	
	def _get_param_value(self, sub_intent: SubIntent, param_name: str, default: Any = None) -> Any:
		"""Get parameter value from sub-intent"""
		for param in sub_intent.parameters:
			if param.name == param_name:
				return param.value
		return default
	
	def _extract_url_from_text(self, text: str) -> Optional[str]:
		"""Extract URL from text"""
		# Look for URLs
		url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
		match = re.search(url_pattern, text)
		if match:
			return match.group()
		
		# Look for domain-like patterns
		domain_pattern = r'(?:www\.)?[\w\-]+(?:\.[\w\-]+)+(?:/[^\s]*)?'
		match = re.search(domain_pattern, text)
		if match:
			url = match.group()
			if not url.startswith(("http://", "https://")):
				url = f"https://{url}"
			return url
		
		return None