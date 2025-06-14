"""Migration helpers for custom actions from legacy to new system"""

from typing import Any, Callable, Dict, List, Optional
import inspect
from functools import wraps

from browser_use.controller.registry.service import ActionRegistry
from browser_use.controller.registry.views import RegisteredAction
from browser_use.core.orchestrator.service import Action, ActionType
from browser_use.core.orchestrator.intent_mapper import PatternType


class CustomActionMigrator:
	"""Helps migrate custom actions from legacy to new system"""
	
	def __init__(self, legacy_registry: Optional[ActionRegistry] = None):
		self.legacy_registry = legacy_registry
		self._migrated_actions: Dict[str, Any] = {}
	
	def migrate_action(
		self,
		legacy_action: RegisteredAction,
		new_agent: Any
	) -> None:
		"""Migrate a single custom action to the new system"""
		
		# Create wrapper for the legacy action
		async def wrapped_handler(action: Action, context: Dict[str, Any]) -> Any:
			# Extract parameters in legacy format
			legacy_params = self._convert_parameters(action.parameters, legacy_action)
			
			# Call legacy handler
			if inspect.iscoroutinefunction(legacy_action.handler):
				result = await legacy_action.handler(**legacy_params)
			else:
				result = legacy_action.handler(**legacy_params)
			
			return result
		
		# Register with new agent
		new_agent.register_custom_action(legacy_action.name, wrapped_handler)
		
		# If action has patterns, register them too
		if hasattr(legacy_action, "patterns"):
			for pattern in legacy_action.patterns:
				new_agent.register_intent_pattern(
					pattern=pattern,
					pattern_type=PatternType.CONTAINS,
					action_generator=self._create_action_generator(legacy_action.name),
					priority=5
				)
		
		self._migrated_actions[legacy_action.name] = wrapped_handler
	
	def migrate_all_actions(
		self,
		new_agent: Any,
		registry: Optional[ActionRegistry] = None
	) -> List[str]:
		"""Migrate all registered custom actions"""
		registry = registry or self.legacy_registry
		
		if not registry:
			return []
		
		migrated = []
		
		for action_name, action in registry._actions.items():
			try:
				self.migrate_action(action, new_agent)
				migrated.append(action_name)
			except Exception as e:
				# Log error but continue
				print(f"Failed to migrate action {action_name}: {e}")
		
		return migrated
	
	def _convert_parameters(
		self,
		new_params: Dict[str, Any],
		legacy_action: RegisteredAction
	) -> Dict[str, Any]:
		"""Convert parameters from new format to legacy format"""
		converted = {}
		
		# Get parameter names from legacy action
		sig = inspect.signature(legacy_action.handler)
		
		for param_name, param in sig.parameters.items():
			if param_name in new_params:
				converted[param_name] = new_params[param_name]
			elif param_name == "page":
				# Special handling for page parameter
				converted[param_name] = new_params.get("context", {}).get("page")
			elif param_name == "browser":
				# Special handling for browser parameter
				page = new_params.get("context", {}).get("page")
				converted[param_name] = page.context.browser if page else None
			elif param.default != inspect.Parameter.empty:
				# Use default value
				converted[param_name] = param.default
		
		return converted
	
	def _create_action_generator(self, action_name: str) -> Callable:
		"""Create an action generator for the custom action"""
		
		async def generator(description: str, params: Dict[str, Any]) -> Action:
			return Action(
				id=f"custom_{action_name}",
				type=ActionType.CUSTOM,
				parameters={
					"custom_action_name": action_name,
					**params
				}
			)
		
		return generator


def create_legacy_wrapper(new_agent: Any) -> Any:
	"""
	Create a wrapper that makes the new agent look like the legacy controller
	
	This allows code that directly uses the controller to work:
	```
	controller = create_legacy_wrapper(new_agent)
	result = await controller.act("click on submit")
	```
	"""
	
	class LegacyControllerWrapper:
		def __init__(self, agent):
			self.agent = agent
			self.registry = ActionRegistry()
		
		async def act(self, action: str) -> Any:
			"""Legacy act method"""
			# Use compatibility layer
			if hasattr(self.agent, "act"):
				return await self.agent.act(action)
			
			# Direct execution
			result = await self.agent.execute_task(action)
			return result
		
		def register_action(self, action: RegisteredAction) -> None:
			"""Register custom action"""
			migrator = CustomActionMigrator()
			migrator.migrate_action(action, self.agent)
			self.registry.register_action(action)
		
		def get_registry(self) -> ActionRegistry:
			"""Get action registry"""
			return self.registry
	
	return LegacyControllerWrapper(new_agent)


# Decorators for easy migration

def migrate_custom_action(
	name: str,
	description: str = "",
	requires_browser: bool = False
):
	"""
	Decorator to migrate custom actions
	
	Usage:
	```
	@migrate_custom_action("my_action", "Does something special")
	async def my_action(page, param1, param2):
		# Implementation
		pass
	```
	"""
	
	def decorator(func: Callable) -> Callable:
		# Store metadata
		func._action_name = name
		func._action_description = description
		func._requires_browser = requires_browser
		
		@wraps(func)
		async def wrapper(*args, **kwargs):
			return await func(*args, **kwargs)
		
		# Mark as migrated action
		wrapper._is_migrated_action = True
		wrapper._original_func = func
		
		return wrapper
	
	return decorator


def auto_migrate_module(module: Any, new_agent: Any) -> List[str]:
	"""
	Automatically migrate all decorated actions in a module
	
	Usage:
	```
	import my_custom_actions
	migrated = auto_migrate_module(my_custom_actions, new_agent)
	```
	"""
	migrated = []
	
	for name, obj in inspect.getmembers(module):
		if hasattr(obj, "_is_migrated_action"):
			# Create registered action
			action = RegisteredAction(
				name=obj._action_name,
				description=obj._action_description,
				handler=obj._original_func,
				param_model=None  # Would need to infer from signature
			)
			
			# Migrate
			migrator = CustomActionMigrator()
			migrator.migrate_action(action, new_agent)
			
			migrated.append(obj._action_name)
	
	return migrated