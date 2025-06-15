"""Action orchestration with parallel execution and dependency management"""

import asyncio
from typing import Any, Optional, List, Dict, Set, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import networkx as nx

from browser_use.core.intent.views import Intent, SubIntent, IntentExecutionResult, IntentType, ElementIntent
from browser_use.core.resolver.service import MultiStrategyElementResolver, ResolvedElement
from browser_use.utils import time_execution_async
from playwright.async_api import Page
import logging

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
	"""Types of browser actions"""
	CLICK = "click"
	TYPE = "type"
	SELECT = "select"
	HOVER = "hover"
	SCROLL = "scroll"
	WAIT = "wait"
	NAVIGATE = "navigate"
	SCREENSHOT = "screenshot"
	EXTRACT = "extract"
	EXECUTE_JS = "execute_js"
	KEYBOARD = "keyboard"
	DRAG = "drag"
	UPLOAD = "upload"
	CUSTOM = "custom"


@dataclass
class Action:
	"""Represents a single browser action"""
	id: str
	type: ActionType
	target: Optional[ResolvedElement] = None
	parameters: Dict[str, Any] = None
	dependencies: Set[str] = None
	can_parallel: bool = True
	timeout_ms: int = 30000
	retry_count: int = 3
	
	def __post_init__(self):
		if self.parameters is None:
			self.parameters = {}
		if self.dependencies is None:
			self.dependencies = set()


@dataclass
class ActionResult:
	"""Result of executing an action"""
	action_id: str
	success: bool
	duration_ms: float
	result_data: Any = None
	error: Optional[str] = None
	retries_used: int = 0


class ExecutionPlan:
	"""Execution plan with dependency graph"""
	
	def __init__(self):
		self.actions: Dict[str, Action] = {}
		self.graph = nx.DiGraph()
		self._execution_order: Optional[List[List[str]]] = None
	
	def add_action(self, action: Action) -> None:
		"""Add an action to the plan"""
		self.actions[action.id] = action
		self.graph.add_node(action.id)
		
		# Add dependencies
		for dep_id in action.dependencies:
			self.graph.add_edge(dep_id, action.id)
	
	def get_parallel_groups(self) -> List[List[str]]:
		"""Get groups of actions that can be executed in parallel"""
		if self._execution_order is None:
			self._calculate_execution_order()
		return self._execution_order
	
	def _calculate_execution_order(self) -> None:
		"""Calculate execution order respecting dependencies"""
		# Check for cycles
		if not nx.is_directed_acyclic_graph(self.graph):
			raise ValueError("Circular dependencies detected in execution plan")
		
		# Get topological generations (levels)
		generations = list(nx.topological_generations(self.graph))
		
		# Within each generation, group by parallelizability
		self._execution_order = []
		for generation in generations:
			# Check which actions in this generation can run in parallel
			parallel_groups = self._group_parallel_actions(generation)
			self._execution_order.extend(parallel_groups)
	
	def _group_parallel_actions(self, action_ids: List[str]) -> List[List[str]]:
		"""Group actions that can run in parallel"""
		groups = []
		
		# Simple grouping - actions that modify state can't run in parallel
		state_modifying = []
		read_only = []
		
		for action_id in action_ids:
			action = self.actions[action_id]
			
			if not action.can_parallel or action.type in [
				ActionType.CLICK, ActionType.TYPE, ActionType.SELECT,
				ActionType.NAVIGATE, ActionType.EXECUTE_JS, ActionType.DRAG
			]:
				state_modifying.append(action_id)
			else:
				read_only.append(action_id)
		
		# Read-only actions can run in parallel
		if read_only:
			groups.append(read_only)
		
		# State-modifying actions run sequentially
		for action_id in state_modifying:
			groups.append([action_id])
		
		return groups


class ParallelActionOrchestrator:
	"""Orchestrates browser actions with parallel execution"""
	
	def __init__(self, element_resolver: MultiStrategyElementResolver):
		self.element_resolver = element_resolver
		self._action_handlers: Dict[ActionType, Any] = {}
		self._custom_actions: Dict[str, Any] = {}
		self._execution_context: Dict[str, Any] = {}
		
		# Register default handlers
		self._register_default_handlers()
	
	@time_execution_async("execute_intent")
	async def execute_intent(
		self,
		intent: Intent,
		page: Page,
		context: Optional[Dict[str, Any]] = None
	) -> IntentExecutionResult:
		"""Execute an intent by converting to actions and running them"""
		start_time = datetime.now()
		self._execution_context = context or {}
		self._execution_context["page"] = page
		self._execution_context["current_intent"] = intent
		
		try:
			# Build execution plan
			plan = await self._build_execution_plan(intent)
			
			# Execute plan
			results = await self._execute_plan(plan)
			
			# Verify success
			success = await self._verify_intent_completion(intent, results, page)
			
			# Build result
			duration = (datetime.now() - start_time).total_seconds()
			
			return IntentExecutionResult(
				intent_id=intent.id,
				success=success,
				sub_intent_results=self._get_sub_intent_results(intent, results),
				actions_taken=[self._action_to_dict(a) for a in plan.actions.values()],
				duration_seconds=duration,
				tokens_used=self._execution_context.get("tokens_used", 0),
				criteria_met=await self._check_success_criteria(intent, page),
				verification_screenshot=await self._take_verification_screenshot(page) if success else None
			)
			
		except Exception as e:
			return IntentExecutionResult(
				intent_id=intent.id,
				success=False,
				duration_seconds=(datetime.now() - start_time).total_seconds(),
				errors=[str(e)]
			)
	
	async def _build_execution_plan(self, intent: Intent) -> ExecutionPlan:
		"""Build execution plan from intent"""
		plan = ExecutionPlan()
		
		# Convert sub-intents to actions
		for sub_intent in intent.sub_intents:
			actions = await self._sub_intent_to_actions(sub_intent)
			
			for action in actions:
				# Map sub-intent dependencies to action dependencies
				if sub_intent.dependencies:
					# Find last action of each dependency
					for dep_id in sub_intent.dependencies:
						dep_actions = [a for a in plan.actions.values() if a.id.startswith(dep_id)]
						if dep_actions:
							last_dep_action = dep_actions[-1]
							action.dependencies.add(last_dep_action.id)
				
				plan.add_action(action)
		
		return plan
	
	async def _sub_intent_to_actions(self, sub_intent: SubIntent) -> List[Action]:
		"""Convert a sub-intent to concrete actions"""
		actions = []
		
		# Debug logging
		import logging
		logger = logging.getLogger(__name__)
		logger.debug(f"Converting sub-intent: type={sub_intent.type}, desc={sub_intent.description}")
		logger.debug(f"Sub-intent parameters: {sub_intent.parameters}")
		
		# Map intent types to actions
		if sub_intent.type == IntentType.NAVIGATION:
			url = self._get_parameter_value(sub_intent, "url")
			if not url:
				# Try to extract URL from description
				import re
				url_match = re.search(r'https?://[^\s]+', sub_intent.description)
				if url_match:
					url = url_match.group(0)
			
			# Ensure URL has protocol
			if url and not url.startswith(('http://', 'https://')):
				url = f'https://{url}'
			
			if url:
				actions.append(Action(
					id=f"{sub_intent.id}_navigate",
					type=ActionType.NAVIGATE,
					parameters={"url": url}
				))
		
		elif sub_intent.type == IntentType.INTERACTION:
			# Find target element
			element_desc = self._get_parameter_value(sub_intent, "element") or sub_intent.description
			element_intent = ElementIntent(description=element_desc)
			
			logger.debug(f"INTERACTION sub-intent: desc='{sub_intent.description}'")
			logger.debug(f"Parameters: {[(p.name, p.value) for p in sub_intent.parameters]}")
			
			# Check if this is a typing interaction
			if any(keyword in sub_intent.description.lower() for keyword in ['type', 'enter', 'input', 'fill', 'write']):
				# Get text value from parameters or description
				text_value = self._get_parameter_value(sub_intent, "text")
				if not text_value:
					# Try to extract text from description
					import re
					# Look for quoted text
					quoted_match = re.search(r"['\"]([^'\"]+)['\"]|'([^']+)'|\"([^\"]+)\"", sub_intent.description)
					if quoted_match:
						text_value = quoted_match.group(1) or quoted_match.group(2) or quoted_match.group(3)
				
				logger.debug(f"TYPE action: text_value='{text_value}', element_desc='{element_desc}'")
				
				if text_value:
					actions.append(Action(
						id=f"{sub_intent.id}_type",
						type=ActionType.TYPE,
						parameters={
							"element_intent": element_intent,
							"text": text_value,
							"clear_first": True
						}
					))
				else:
					# No text found, default to click
					logger.debug(f"No text found for typing, defaulting to click")
					actions.append(Action(
						id=f"{sub_intent.id}_click",
						type=ActionType.CLICK,
						parameters={"element_intent": element_intent}
					))
			else:
				# Default to click action
				actions.append(Action(
					id=f"{sub_intent.id}_click",
					type=ActionType.CLICK,
					parameters={"element_intent": element_intent}
				))
		
		elif sub_intent.type == IntentType.FORM_FILL:
			# Multiple type actions for form fields
			form_data = self._get_parameter_value(sub_intent, "form_data", {})
			
			logger.debug(f"FORM_FILL: description='{sub_intent.description}', form_data={form_data}")
			
			# Check if this is a simple typing task
			text_value = self._get_parameter_value(sub_intent, "text") or self._get_parameter_value(sub_intent, "value")
			if not form_data and text_value:
				# Simple typing task
				element_desc = self._get_parameter_value(sub_intent, "element") or sub_intent.description
				actions.append(Action(
					id=f"{sub_intent.id}_type",
					type=ActionType.TYPE,
					parameters={
						"element_intent": ElementIntent(description=element_desc),
						"text": text_value,
						"clear_first": True
					}
				))
			# If no form_data or text, check if this is a login form fill
			elif not form_data and "username and password" in sub_intent.description.lower():
				# Get username and password from parent intent parameters
				username = None
				password = None
				
				# Find parent intent through context
				parent_intent = self._execution_context.get("current_intent")
				logger.debug(f"Parent intent: {parent_intent}")
				if parent_intent:
					logger.debug(f"Parent intent parameters: {[(p.name, p.value[:20] + '...' if len(p.value) > 20 else p.value) for p in parent_intent.parameters]}")
					for param in parent_intent.parameters:
						if param.name == "username":
							username = param.value
						elif param.name == "password":
							password = param.value
				
				logger.debug(f"Found credentials: username='{username[:20] + '...' if username and len(username) > 20 else username}', password={'*' * len(password) if password else 'None'}")
				
				if username:
					actions.append(Action(
						id=f"{sub_intent.id}_type_username",
						type=ActionType.TYPE,
						parameters={
							"element_intent": ElementIntent(
								description="Username or email input field",
								element_type="input"
							),
							"text": username,
							"clear_first": True
						}
					))
				
				if password:
					actions.append(Action(
						id=f"{sub_intent.id}_type_password",
						type=ActionType.TYPE,
						parameters={
							"element_intent": ElementIntent(
								description="Password input field",
								element_type="input"
							),
							"text": password,
							"clear_first": True
						}
					))
			else:
				for field_name, field_value in form_data.items():
					element_intent = ElementIntent(
						description=f"Input field for {field_name}",
						element_type="input",
						attributes={"name": field_name}
					)
					
					actions.append(Action(
						id=f"{sub_intent.id}_type_{field_name}",
						type=ActionType.TYPE,
						parameters={
							"element_intent": element_intent,
							"text": field_value,
							"clear_first": True
						}
					))
		
		elif sub_intent.type == IntentType.EXTRACTION:
			# Extract data action
			selector = self._get_parameter_value(sub_intent, "selector")
			actions.append(Action(
				id=f"{sub_intent.id}_extract",
				type=ActionType.EXTRACT,
				parameters={
					"selector": selector,
					"attribute": self._get_parameter_value(sub_intent, "attribute", "textContent")
				},
				can_parallel=True  # Extraction doesn't modify state
			))
		
		elif sub_intent.type == IntentType.VERIFICATION:
			# Wait and screenshot for verification
			actions.extend([
				Action(
					id=f"{sub_intent.id}_wait",
					type=ActionType.WAIT,
					parameters={"duration_ms": 1000},
					can_parallel=False
				),
				Action(
					id=f"{sub_intent.id}_screenshot",
					type=ActionType.SCREENSHOT,
					parameters={"full_page": False},
					can_parallel=True
				)
			])
		
		# Add generic fallback
		if not actions:
			# Try to infer from description
			desc_lower = sub_intent.description.lower()
			
			if "click" in desc_lower or "press" in desc_lower:
				element_intent = ElementIntent(description=sub_intent.description)
				actions.append(Action(
					id=f"{sub_intent.id}_click",
					type=ActionType.CLICK,
					parameters={"element_intent": element_intent}
				))
			
			elif "type" in desc_lower or "enter" in desc_lower or "fill" in desc_lower:
				# Extract what to type
				text = self._extract_text_from_description(sub_intent.description)
				element_intent = ElementIntent(description=sub_intent.description)
				
				actions.append(Action(
					id=f"{sub_intent.id}_type",
					type=ActionType.TYPE,
					parameters={
						"element_intent": element_intent,
						"text": text
					}
				))
			
			elif "scroll" in desc_lower:
				actions.append(Action(
					id=f"{sub_intent.id}_scroll",
					type=ActionType.SCROLL,
					parameters={
						"direction": "down" if "down" in desc_lower else "up",
						"amount": 500
					}
				))
		
		return actions
	
	async def _execute_plan(self, plan: ExecutionPlan) -> Dict[str, ActionResult]:
		"""Execute the plan with parallel execution where possible"""
		results = {}
		
		# Get execution order
		parallel_groups = plan.get_parallel_groups()
		
		for group in parallel_groups:
			if len(group) == 1:
				# Single action, execute directly
				action = plan.actions[group[0]]
				result = await self._execute_action(action)
				results[action.id] = result
			else:
				# Multiple actions, execute in parallel
				tasks = []
				for action_id in group:
					action = plan.actions[action_id]
					task = self._execute_action(action)
					tasks.append((action_id, task))
				
				# Wait for all to complete
				for action_id, task in tasks:
					try:
						result = await task
						results[action_id] = result
					except Exception as e:
						results[action_id] = ActionResult(
							action_id=action_id,
							success=False,
							duration_ms=0,
							error=str(e)
						)
			
			# Check if we should continue after failures
			if any(not r.success for r in results.values()):
				# For now, continue execution
				# Could add logic to stop on critical failures
				pass
		
		return results
	
	async def _execute_action(self, action: Action) -> ActionResult:
		"""Execute a single action with retries"""
		start_time = datetime.now()
		last_error = None
		
		logger.info(f"Executing action: id={action.id}, type={action.type}, params={list(action.parameters.keys())}")
		
		for attempt in range(action.retry_count):
			try:
				# Resolve target element if needed
				if action.type in [ActionType.CLICK, ActionType.TYPE, ActionType.HOVER, ActionType.SELECT]:
					if "element_intent" in action.parameters:
						element_intent = action.parameters["element_intent"]
						logger.info(f"Resolving element for {action.type}: {element_intent.description if hasattr(element_intent, 'description') else element_intent}")
						try:
							# Element resolver expects perception_data as second argument
							perception_data = self._execution_context.get("perception_data", {})
							# Ensure page is in perception_data
							if "page" not in perception_data and "page" in self._execution_context:
								perception_data["page"] = self._execution_context["page"]
							
							# Ensure perception_data is JSON-serializable (some strategies might serialize it)
							# Create a copy without non-serializable objects
							clean_perception_data = {}
							for key, value in perception_data.items():
								if key == "page":
									# Keep the page object as-is, it's needed by resolvers
									clean_perception_data[key] = value
								elif hasattr(value, 'model_dump'):
									# Convert Pydantic models to dicts
									clean_perception_data[key] = value.model_dump()
								elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
									clean_perception_data[key] = value
								else:
									# Skip non-serializable objects
									logger.debug(f"Skipping non-serializable perception_data key: {key} (type: {type(value).__name__})")
							
							perception_data = clean_perception_data
							
							resolved = await self.element_resolver.resolve_element(
								element_intent,
								perception_data,
								self._execution_context["page"]
							)
							action.target = resolved
							logger.debug(f"Resolved element for {action.id}: selector={resolved.selector if resolved else 'None'}")
						except Exception as e:
							logger.error(f"Failed to resolve element for {action.id}: {e}")
							# For now, continue without failing completely
							action.target = None
				
				# Execute the action
				handler = self._action_handlers.get(action.type)
				if not handler:
					raise ValueError(f"No handler for action type: {action.type}")
				
				# Ensure execution context has page
				if "page" not in self._execution_context:
					raise ValueError("No page in execution context")
				
				result_data = await handler(action, self._execution_context)
				
				duration = (datetime.now() - start_time).total_seconds() * 1000
				
				return ActionResult(
					action_id=action.id,
					success=True,
					duration_ms=duration,
					result_data=result_data,
					retries_used=attempt
				)
				
			except Exception as e:
				last_error = str(e)
				
				if attempt < action.retry_count - 1:
					# Wait before retry
					await asyncio.sleep(0.5 * (attempt + 1))
					continue
		
		# All retries failed
		duration = (datetime.now() - start_time).total_seconds() * 1000
		
		return ActionResult(
			action_id=action.id,
			success=False,
			duration_ms=duration,
			error=last_error,
			retries_used=action.retry_count
		)
	
	# Action handlers
	
	def _register_default_handlers(self):
		"""Register default action handlers"""
		self._action_handlers = {
			ActionType.CLICK: self._handle_click,
			ActionType.TYPE: self._handle_type,
			ActionType.SELECT: self._handle_select,
			ActionType.HOVER: self._handle_hover,
			ActionType.SCROLL: self._handle_scroll,
			ActionType.WAIT: self._handle_wait,
			ActionType.NAVIGATE: self._handle_navigate,
			ActionType.SCREENSHOT: self._handle_screenshot,
			ActionType.EXTRACT: self._handle_extract,
			ActionType.EXECUTE_JS: self._handle_execute_js,
			ActionType.KEYBOARD: self._handle_keyboard,
		}
	
	async def _handle_click(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle click action"""
		page = context["page"]
		
		logger.debug(f"Click action: has_target={action.target is not None}")
		if action.target:
			logger.debug(f"Target selector: {action.target.selector}, has_bbox: {action.target.bounding_box is not None}")
		
		if action.target and action.target.selector:
			# Use selector
			try:
				await page.click(action.target.selector, timeout=action.timeout_ms)
				logger.debug(f"Successfully clicked {action.target.selector}")
			except Exception as e:
				logger.error(f"Failed to click: {e}")
				raise
		elif action.target and action.target.bounding_box:
			# Use coordinates
			x, y = await action.target.click_point()
			await page.mouse.click(x, y)
			logger.debug(f"Successfully clicked at ({x}, {y})")
		else:
			raise ValueError("No valid target for click action")
		
		return {"clicked": True}
	
	async def _handle_type(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle type action"""
		page = context["page"]
		text = action.parameters.get("text", "")
		clear_first = action.parameters.get("clear_first", False)
		
		logger.info(f"_handle_type called: text='{text}', has_target={action.target is not None}")
		if action.target:
			logger.info(f"Target: selector='{action.target.selector}', element={action.target.element}")
		
		if action.target and action.target.selector:
			try:
				# First check if element exists
				element = await page.query_selector(action.target.selector)
				if not element:
					logger.error(f"Element not found with selector: {action.target.selector}")
					raise ValueError(f"Element not found: {action.target.selector}")
				
				logger.info(f"Element found, typing '{text}' into {action.target.selector}")
				
				if clear_first:
					await page.fill(action.target.selector, text, timeout=action.timeout_ms)
				else:
					await page.type(action.target.selector, text, timeout=action.timeout_ms)
				logger.info(f"Successfully typed text into {action.target.selector}")
			except Exception as e:
				logger.error(f"Failed to type: {e}")
				raise
		else:
			logger.error(f"No valid target for type action - action.target: {action.target}")
			raise ValueError(f"No valid target for type action - target: {action.target}, selector: {action.target.selector if action.target else 'N/A'}")
		
		return {"typed": text}
	
	async def _handle_navigate(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle navigation"""
		page = context["page"]
		url = action.parameters.get("url")
		
		if not url:
			raise ValueError("No URL provided for navigation")
		
		response = await page.goto(url, timeout=action.timeout_ms)
		
		return {
			"navigated": True,
			"url": page.url,
			"status": response.status if response else None
		}
	
	async def _handle_wait(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle wait action"""
		duration_ms = action.parameters.get("duration_ms", 1000)
		await asyncio.sleep(duration_ms / 1000)
		return {"waited": duration_ms}
	
	async def _handle_screenshot(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle screenshot action"""
		page = context["page"]
		full_page = action.parameters.get("full_page", False)
		
		screenshot = await page.screenshot(full_page=full_page)
		
		return {
			"screenshot": screenshot,
			"full_page": full_page
		}
	
	async def _handle_scroll(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle scroll action"""
		page = context["page"]
		direction = action.parameters.get("direction", "down")
		amount = action.parameters.get("amount", 500)
		
		if direction == "down":
			await page.evaluate(f"window.scrollBy(0, {amount})")
		elif direction == "up":
			await page.evaluate(f"window.scrollBy(0, -{amount})")
		elif direction == "right":
			await page.evaluate(f"window.scrollBy({amount}, 0)")
		elif direction == "left":
			await page.evaluate(f"window.scrollBy(-{amount}, 0)")
		
		return {"scrolled": True, "direction": direction, "amount": amount}
	
	async def _handle_hover(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle hover action"""
		page = context["page"]
		
		if action.target and action.target.selector:
			await page.hover(action.target.selector, timeout=action.timeout_ms)
		elif action.target and action.target.bounding_box:
			x, y = await action.target.click_point()
			await page.mouse.move(x, y)
		else:
			raise ValueError("No valid target for hover action")
		
		return {"hovered": True}
	
	async def _handle_select(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle select action"""
		page = context["page"]
		value = action.parameters.get("value")
		
		if not action.target or not action.target.selector:
			raise ValueError("No valid target for select action")
		
		if value:
			await page.select_option(action.target.selector, value, timeout=action.timeout_ms)
		
		return {"selected": value}
	
	async def _handle_extract(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle data extraction"""
		page = context["page"]
		selector = action.parameters.get("selector")
		attribute = action.parameters.get("attribute", "textContent")
		
		if not selector:
			raise ValueError("No selector provided for extraction")
		
		if attribute == "textContent":
			value = await page.text_content(selector)
		else:
			value = await page.get_attribute(selector, attribute)
		
		return {"extracted": value}
	
	async def _handle_execute_js(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle JavaScript execution"""
		page = context["page"]
		script = action.parameters.get("script")
		
		if not script:
			raise ValueError("No script provided")
		
		result = await page.evaluate(script)
		
		return {"result": result}
	
	async def _handle_keyboard(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle keyboard action"""
		page = context["page"]
		key = action.parameters.get("key")
		
		if not key:
			raise ValueError("No key provided")
		
		await page.keyboard.press(key)
		
		return {"pressed": key}
	
	# Helper methods
	
	def _get_parameter_value(self, sub_intent: SubIntent, param_name: str, default: Any = None) -> Any:
		"""Get parameter value from sub-intent"""
		for param in sub_intent.parameters:
			if param.name == param_name:
				return param.value
		return default
	
	def _extract_text_from_description(self, description: str) -> str:
		"""Extract text to type from description"""
		# Simple extraction - in practice would be more sophisticated
		import re
		
		# Look for quoted text
		match = re.search(r'"([^"]+)"', description)
		if match:
			return match.group(1)
		
		match = re.search(r"'([^']+)'", description)
		if match:
			return match.group(1)
		
		# Look for "type X" pattern
		match = re.search(r'type\s+(\S+)', description, re.IGNORECASE)
		if match:
			return match.group(1)
		
		return ""
	
	def _action_to_dict(self, action: Action) -> dict:
		"""Convert action to dictionary for results"""
		# Clean parameters to ensure JSON serializable
		clean_params = {}
		for key, value in action.parameters.items():
			if key == "element_intent" and hasattr(value, "description"):
				# Convert ElementIntent to simple dict
				clean_params[key] = {"description": value.description}
			elif hasattr(value, "__dict__"):
				# Convert other objects to string representation
				clean_params[key] = str(value)
			else:
				clean_params[key] = value
		
		return {
			"id": action.id,
			"type": action.type,
			"parameters": clean_params,
			"has_target": action.target is not None
		}
	
	def _get_sub_intent_results(self, intent: Intent, results: Dict[str, ActionResult]) -> dict[str, bool]:
		"""Map action results back to sub-intents"""
		sub_intent_results = {}
		
		for sub_intent in intent.sub_intents:
			# Check if all actions for this sub-intent succeeded
			sub_intent_actions = [r for aid, r in results.items() if aid.startswith(sub_intent.id)]
			
			if sub_intent_actions:
				sub_intent_results[sub_intent.id] = all(r.success for r in sub_intent_actions)
			else:
				sub_intent_results[sub_intent.id] = False
		
		return sub_intent_results
	
	async def _verify_intent_completion(
		self,
		intent: Intent,
		results: Dict[str, ActionResult],
		page: Page
	) -> bool:
		"""Verify that the intent was completed successfully"""
		# Check if all required actions succeeded
		required_actions = [aid for aid, action in results.items() if aid in results]
		if not all(results[aid].success for aid in required_actions if not results[aid].action_id.endswith("_optional")):
			return False
		
		# Additional verification could be added here
		# For example, checking page state, URLs, etc.
		
		return True
	
	async def _check_success_criteria(self, intent: Intent, page: Page) -> dict[str, bool]:
		"""Check success criteria for the intent"""
		criteria_results = {}
		
		for criterion in intent.success_criteria:
			try:
				if criterion.type == "url_matches":
					current_url = page.url
					expected = criterion.expected
					met = expected in current_url if isinstance(expected, str) else expected == current_url
					criteria_results[f"url_matches_{expected}"] = met
				
				elif criterion.type == "element_visible":
					selector = criterion.expected
					element = await page.query_selector(selector)
					met = element is not None and await element.is_visible()
					criteria_results[f"element_visible_{selector}"] = met
				
				elif criterion.type == "text_present":
					text = criterion.expected
					page_text = await page.text_content("body")
					met = text in page_text if page_text else False
					criteria_results[f"text_present_{text[:20]}"] = met
				
				else:
					# Unknown criterion type
					criteria_results[criterion.type] = False
					
			except Exception:
				criteria_results[criterion.type] = False
		
		return criteria_results
	
	async def _take_verification_screenshot(self, page: Page) -> str:
		"""Take a verification screenshot"""
		import base64
		
		try:
			screenshot = await page.screenshot()
			return base64.b64encode(screenshot).decode()
		except Exception:
			return None
	
	# Custom action registration
	
	def register_custom_action(self, name: str, handler: Any) -> None:
		"""Register a custom action handler"""
		self._custom_actions[name] = handler
		self._action_handlers[ActionType.CUSTOM] = self._handle_custom_action
	
	async def _handle_custom_action(self, action: Action, context: Dict[str, Any]) -> Any:
		"""Handle custom action"""
		action_name = action.parameters.get("custom_action_name")
		
		if not action_name or action_name not in self._custom_actions:
			raise ValueError(f"Unknown custom action: {action_name}")
		
		handler = self._custom_actions[action_name]
		return await handler(action, context)