"""Backward compatibility layer for existing browser-use code"""

import asyncio
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.agent.service import Agent as LegacyAgent
from browser_use.agent.views import AgentSettings, ActionModel
from browser_use.browser.views import BrowserStateSummary

from browser_use.core import (
	Intent, IntentType, SubIntent, IntentParameter,
	ElementIntent, SuccessCriteria
)


# Legacy action types for compatibility
class LegacyActionType(str, Enum):
	"""Legacy action types for backward compatibility"""
	CLICK = "click"
	TYPE = "type"
	SCROLL = "scroll"
	WAIT = "wait"
	GO_TO_URL = "go_to_url"
	SEARCH_GOOGLE = "search_google"
	DONE = "done"
	EXTRACT = "extract_page_content"
	SWITCH_TAB = "switch_tab"
	OPEN_TAB = "open_tab"
	CLOSE_TAB = "close_tab"
	SEND_KEYS = "send_keys"


class BackwardCompatibleAgent(NextGenBrowserAgent):
	"""
	Backward compatible agent that supports both legacy and new APIs
	
	This allows existing code to continue working while providing
	access to new intent-driven features.
	"""
	
	def __init__(
		self,
		task: str = "",
		llm: Any = None,
		browser_profile: Optional[Any] = None,
		agent_settings: Optional[AgentSettings] = None,
		**kwargs
	):
		# Handle legacy initialization
		if agent_settings:
			use_vision = agent_settings.use_vision
			# Extract other settings
		else:
			use_vision = kwargs.get("use_vision", True)
		
		# Initialize parent with new architecture
		super().__init__(
			llm=llm,
			browser_profile=browser_profile,
			use_vision=use_vision,
			use_accessibility=True,
			enable_streaming=True
		)
		
		# Store legacy task
		self.legacy_task = task
		self.agent_settings = agent_settings or AgentSettings()
		
		# Legacy state tracking
		self._legacy_history: List[ActionModel] = []
		self._legacy_state: Optional[BrowserState] = None
	
	# Legacy API methods
	
	async def run(self, task: Optional[str] = None) -> List[ActionModel]:
		"""Legacy run method - converts to intent-based execution"""
		task = task or self.legacy_task
		
		if not task:
			raise ValueError("No task provided")
		
		# Execute using new system
		result = await self.execute_task(task)
		
		# Convert to legacy format
		legacy_actions = self._convert_to_legacy_actions(result)
		self._legacy_history.extend(legacy_actions)
		
		return legacy_actions
	
	async def act(self, action: Union[str, ActionModel]) -> Any:
		"""Legacy act method - single action execution"""
		if isinstance(action, str):
			# Parse action string
			action_model = self._parse_action_string(action)
		else:
			action_model = action
		
		# Convert to intent
		intent = self._action_to_intent(action_model)
		
		# Execute
		result = await self.execute_intent_directly(intent)
		
		# Update legacy history
		self._legacy_history.append(action_model)
		
		return result
	
	async def multi_act(self, actions: List[ActionModel]) -> List[Any]:
		"""Legacy multi_act method - parallel action execution"""
		# Convert actions to composite intent
		sub_intents = []
		for i, action in enumerate(actions):
			sub_intent = self._action_to_sub_intent(action, f"action_{i}")
			sub_intents.append(sub_intent)
		
		intent = Intent(
			task_description="Execute multiple actions",
			type=IntentType.COMPOSITE,
			primary_goal="Execute provided actions",
			sub_intents=sub_intents
		)
		
		# Execute
		result = await self.execute_intent_directly(intent)
		
		# Update history
		self._legacy_history.extend(actions)
		
		return result["actions_taken"]
	
	def get_state(self) -> Optional[BrowserState]:
		"""Get legacy browser state"""
		return self._legacy_state
	
	def get_history(self) -> List[ActionModel]:
		"""Get legacy action history"""
		return self._legacy_history
	
	# Conversion methods
	
	def _convert_to_legacy_actions(self, result: Dict[str, Any]) -> List[ActionModel]:
		"""Convert execution result to legacy action models"""
		legacy_actions = []
		
		for action_data in result.get("actions_taken", []):
			action_type = self._map_action_type_to_legacy(action_data["type"])
			
			# Extract relevant data
			if action_type == LegacyActionType.CLICK:
				target = action_data.get("parameters", {}).get("element_intent", {}).get("description", "")
				coordinate = None  # Would need to extract from resolved element
			elif action_type == LegacyActionType.TYPE:
				target = action_data.get("parameters", {}).get("element_intent", {}).get("description", "")
				text = action_data.get("parameters", {}).get("text", "")
			else:
				target = None
				text = None
				coordinate = None
			
			action = ActionModel(
				action_type=action_type,
				coordinate=coordinate,
				target=target,
				text=text
			)
			
			legacy_actions.append(action)
		
		return legacy_actions
	
	def _action_to_intent(self, action: ActionModel) -> Intent:
		"""Convert legacy action to intent"""
		# Determine intent type
		if action.action_type == LegacyActionType.NAVIGATE:
			intent_type = IntentType.NAVIGATION
			goal = f"Navigate to {action.url}"
			params = [IntentParameter(name="url", value=action.url, type="string")]
		elif action.action_type in [LegacyActionType.CLICK, LegacyActionType.HOVER]:
			intent_type = IntentType.INTERACTION
			goal = f"{action.action_type.value} on element"
			params = []
		elif action.action_type == LegacyActionType.TYPE:
			intent_type = IntentType.FORM_FILL
			goal = f"Type text in field"
			params = [IntentParameter(name="text", value=action.text or "", type="string")]
		else:
			intent_type = IntentType.CUSTOM
			goal = f"Execute {action.action_type.value}"
			params = []
		
		# Create element intent if needed
		element_intent = None
		if action.target:
			element_intent = ElementIntent(
				description=action.target,
				css_selector=action.target if action.target.startswith(("#", ".")) else None
			)
		elif action.coordinate:
			# Coordinate-based clicking not directly supported in new system
			# Would need to use visual grounding
			element_intent = ElementIntent(
				description=f"Element at coordinates {action.coordinate}"
			)
		
		# Build intent
		return Intent(
			task_description=goal,
			type=intent_type,
			primary_goal=goal,
			parameters=params,
			context={
				"legacy_action": action.model_dump(),
				"element_intent": element_intent.model_dump() if element_intent else None
			}
		)
	
	def _action_to_sub_intent(self, action: ActionModel, sub_id: str) -> SubIntent:
		"""Convert legacy action to sub-intent"""
		intent = self._action_to_intent(action)
		
		return SubIntent(
			id=sub_id,
			description=intent.primary_goal,
			type=intent.type,
			parameters=intent.parameters
		)
	
	def _parse_action_string(self, action_str: str) -> ActionModel:
		"""Parse legacy action string to action model"""
		# Simple parsing - in practice would be more sophisticated
		action_lower = action_str.lower()
		
		if "click" in action_lower:
			# Extract target
			import re
			match = re.search(r"click\s+(?:on\s+)?(.+)", action_str, re.IGNORECASE)
			target = match.group(1) if match else action_str
			
			return ActionModel(
				action_type=LegacyActionType.CLICK,
				target=target
			)
		
		elif "type" in action_lower or "enter" in action_lower:
			# Extract text and target
			import re
			match = re.search(r"(?:type|enter)\s+[\"']([^\"']+)[\"'](?:\s+in\s+(.+))?", action_str, re.IGNORECASE)
			if match:
				text = match.group(1)
				target = match.group(2) or "focused element"
			else:
				text = action_str
				target = "focused element"
			
			return ActionModel(
				action_type=LegacyActionType.TYPE,
				text=text,
				target=target
			)
		
		elif "navigate" in action_lower or "go to" in action_lower:
			# Extract URL
			import re
			match = re.search(r"(?:navigate|go)\s+(?:to\s+)?(.+)", action_str, re.IGNORECASE)
			url = match.group(1) if match else action_str
			
			return ActionModel(
				action_type=LegacyActionType.NAVIGATE,
				url=url
			)
		
		else:
			# Generic action
			return ActionModel(
				action_type=LegacyActionType.CUSTOM,
				text=action_str
			)
	
	def _map_action_type_to_legacy(self, action_type: str) -> LegacyActionType:
		"""Map new action types to legacy types"""
		mapping = {
			"click": LegacyActionType.CLICK,
			"type": LegacyActionType.TYPE,
			"navigate": LegacyActionType.NAVIGATE,
			"scroll": LegacyActionType.SCROLL,
			"wait": LegacyActionType.WAIT,
			"screenshot": LegacyActionType.SCREENSHOT,
			"hover": LegacyActionType.HOVER,
			"select": LegacyActionType.SELECT_OPTION,
			"keyboard": LegacyActionType.PRESS,
			"drag": LegacyActionType.DRAG_AND_DROP
		}
		
		return mapping.get(action_type, LegacyActionType.CUSTOM)
	
	# Additional compatibility methods
	
	async def set_state(self, state: BrowserState) -> None:
		"""Set legacy browser state"""
		self._legacy_state = state
	
	async def get_tabs(self) -> List[Any]:
		"""Get browser tabs"""
		if not self.browser_session:
			return []
		
		contexts = self.browser_session.browser.contexts
		tabs = []
		for context in contexts:
			tabs.extend(context.pages)
		
		return tabs
	
	async def switch_to_tab(self, index: int) -> None:
		"""Switch to tab by index"""
		tabs = await self.get_tabs()
		if 0 <= index < len(tabs):
			await self.switch_tab(tabs[index])
	
	def has_browser(self) -> bool:
		"""Check if browser is initialized"""
		return self.browser_session is not None


def create_agent(
	task: str = "",
	llm: Any = None,
	**kwargs
) -> BackwardCompatibleAgent:
	"""
	Factory function that maintains backward compatibility
	
	This allows existing code using:
	```
	agent = create_agent(task="...", llm=model)
	```
	
	To continue working while using the new architecture.
	"""
	return BackwardCompatibleAgent(task=task, llm=llm, **kwargs)