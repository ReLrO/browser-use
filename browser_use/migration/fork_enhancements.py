"""Migration helpers to preserve fork enhancements in the new architecture"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from browser_use.controller.actions.enhanced_scroll import (
	ScrollStrategy,
	ScrollDirection,
	EnhancedScrollAction,
	SmartScrollToFindAction
)

from browser_use.core.orchestrator.service import Action, ActionType
from browser_use.core import ElementIntent


class ForkEnhancementsMigrator:
	"""Preserves and enhances fork-specific features in the new architecture"""
	
	def __init__(self):
		self.enhanced_features = {
			"enhanced_scrolling": True,
			"dom_caching": True,
			"memory_optimization": True,
			"recording_traces": True,
			"parallel_tabs": True,
			"timeout_handling": True,
			"token_reduction": True,
			"action_batching": True,
			"smart_scrolling": True,
			"error_handling": True,
			"retry_logic": True,
			"performance_metrics": True
		}
	
	def migrate_enhanced_scrolling(self, new_agent: Any) -> None:
		"""Migrate enhanced scrolling capabilities to new system"""
		
		# Register enhanced scroll actions
		scroll_actions = [
			"enhanced_scroll",
			"detect_scrollable_areas",
			"scroll_to_element",
			"scroll_until_visible",
			"handle_infinite_scroll",
			"smart_scroll_to_find"
		]
		
		for action_name in scroll_actions:
			new_agent.register_custom_action(
				action_name,
				self._create_scroll_handler(action_name)
			)
		
		# Register scroll patterns for intent mapping
		scroll_patterns = [
			("scroll down until you find", "smart_scroll_to_find"),
			("keep scrolling until", "scroll_until_visible"),
			("scroll to the bottom", "enhanced_scroll"),
			("find scrollable areas", "detect_scrollable_areas"),
			("infinite scroll", "handle_infinite_scroll")
		]
		
		for pattern, action in scroll_patterns:
			new_agent.register_intent_pattern(
				pattern=pattern,
				pattern_type="contains",
				action_generator=self._create_scroll_action_generator(action),
				priority=10
			)
	
	def _create_scroll_handler(self, action_name: str):
		"""Create handler for enhanced scroll actions"""
		
		async def handler(action: Action, context: Dict[str, Any]) -> Any:
			page = context["page"]
			params = action.parameters
			
			# Create legacy scroll controller
			scroll_controller = EnhancedScrollController()
			
			if action_name == "enhanced_scroll":
				direction = ScrollDirection(params.get("direction", "down"))
				strategy = ScrollStrategy(params.get("strategy", "pixels"))
				amount = params.get("amount", 500)
				
				result = await scroll_controller.enhanced_scroll(
					page, direction, strategy, amount
				)
				
			elif action_name == "smart_scroll_to_find":
				target = params.get("target", "")
				pattern = params.get("pattern")
				
				if pattern:
					scroll_pattern = ScrollPattern(
						type=pattern.get("type", "geography"),
						keywords=pattern.get("keywords", []),
						priority_direction=pattern.get("priority_direction", "down")
					)
				else:
					scroll_pattern = None
				
				result = await scroll_controller.smart_scroll_to_find(
					page, target, scroll_pattern
				)
				
			elif action_name == "detect_scrollable_areas":
				areas = await scroll_controller.detect_scrollable_areas(page)
				result = {"scrollable_areas": areas}
				
			elif action_name == "scroll_until_visible":
				selector = params.get("selector", "")
				max_scrolls = params.get("max_scrolls", 10)
				
				result = await scroll_controller.scroll_until_visible(
					page, selector, max_scrolls
				)
				
			elif action_name == "handle_infinite_scroll":
				max_scrolls = params.get("max_scrolls", 20)
				wait_time = params.get("wait_time", 2.0)
				
				result = await scroll_controller.handle_infinite_scroll(
					page, max_scrolls, wait_time
				)
				
			else:
				result = {"error": f"Unknown scroll action: {action_name}"}
			
			return result
		
		return handler
	
	def _create_scroll_action_generator(self, action_name: str):
		"""Create action generator for scroll patterns"""
		
		async def generator(description: str, params: Dict[str, Any]) -> Action:
			# Extract parameters from description
			action_params = {"description": description}
			
			if "until" in description.lower():
				# Extract target
				import re
				match = re.search(r"until\s+(?:you\s+find\s+)?(.+)", description, re.I)
				if match:
					action_params["target"] = match.group(1)
			
			return Action(
				id=f"scroll_{action_name}",
				type=ActionType.CUSTOM,
				parameters={
					"custom_action_name": action_name,
					**action_params
				}
			)
		
		return generator
	
	def enhance_dom_caching(self, new_agent: Any) -> None:
		"""Enhance DOM caching in the new architecture"""
		
		# The new IncrementalDOMProcessor already includes advanced caching
		# But we can add the fork's specific cache configuration
		
		if hasattr(new_agent.dom_processor, "config"):
			# Apply fork's cache settings
			new_agent.dom_processor.config.update({
				"cache_ttl": 5.0,  # From fork
				"enable_quick_hash": True,
				"cache_hit_tracking": True,
				"max_cache_size": 10000
			})
	
	def migrate_memory_optimization(self, new_agent: Any) -> None:
		"""Migrate memory optimization with importance scoring"""
		
		# Add importance scoring to the intent manager
		original_register = new_agent.intent_manager.register_intent
		
		async def register_with_importance(intent: Any) -> None:
			# Calculate importance score (from fork logic)
			importance = self._calculate_intent_importance(intent)
			
			# Only register if important enough
			if importance >= 0.5:
				await original_register(intent)
		
		new_agent.intent_manager.register_intent = register_with_importance
	
	def _calculate_intent_importance(self, intent: Any) -> float:
		"""Calculate importance score for an intent (from fork)"""
		score = 0.5  # Base score
		
		# High importance for errors
		if hasattr(intent, "last_error") and intent.last_error:
			score += 0.3
		
		# High importance for successful complex intents
		if hasattr(intent, "sub_intents") and len(intent.sub_intents) > 3:
			score += 0.2
		
		# Medium importance for state changes
		if intent.type in ["navigation", "authentication", "form_fill"]:
			score += 0.1
		
		# Low importance for high token usage (from fork)
		if hasattr(intent, "context") and intent.context.get("token_count", 0) > 1000:
			score -= 0.1
		
		return max(0, min(1, score))
	
	def enhance_timeout_handling(self, new_agent: Any) -> None:
		"""Apply fork's graceful timeout handling"""
		
		# Wrap action handlers with timeout protection
		for action_type, handler in new_agent.action_orchestrator._action_handlers.items():
			new_agent.action_orchestrator._action_handlers[action_type] = \
				self._wrap_with_timeout(handler)
	
	def _wrap_with_timeout(self, handler):
		"""Wrap handler with graceful timeout (from fork)"""
		
		async def wrapped_handler(action: Action, context: Dict[str, Any]) -> Any:
			import asyncio
			
			# Use fork's 5-second timeout for wait_for_load_state
			timeout = 5.0 if "wait_for_load_state" in str(handler) else 30.0
			
			try:
				return await asyncio.wait_for(
					handler(action, context),
					timeout=timeout
				)
			except asyncio.TimeoutError:
				# Graceful handling from fork
				return {
					"success": False,
					"error": "Operation timed out gracefully",
					"timeout": timeout
				}
		
		return wrapped_handler
	
	def apply_token_reduction(self, new_agent: Any) -> None:
		"""Apply fork's token reduction strategies"""
		
		# The new architecture already has much better token usage
		# But we can add the fork's sliding window approach
		
		if hasattr(new_agent, "intent_analyzer"):
			# Configure token limits
			new_agent.intent_analyzer._max_context_tokens = 4000
			new_agent.intent_analyzer._use_sliding_window = True
	
	def enable_recording_traces(self, new_agent: Any) -> None:
		"""Enable fork's recording and trace functionality"""
		
		# Add trace saving to intent completion
		original_execute = new_agent.execute_task
		
		async def execute_with_trace(task: str, **kwargs) -> Dict[str, Any]:
			result = await original_execute(task, **kwargs)
			
			# Save trace if enabled
			if new_agent._execution_context.get("save_trace", False):
				await self._save_trace(new_agent, task, result)
			
			return result
		
		new_agent.execute_task = execute_with_trace
	
	async def _save_trace(self, agent: Any, task: str, result: Dict[str, Any]) -> None:
		"""Save execution trace (from fork)"""
		import json
		import aiofiles
		from pathlib import Path
		
		trace_dir = Path("browser_traces")
		trace_dir.mkdir(exist_ok=True)
		
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		trace_file = trace_dir / f"trace_{timestamp}.json"
		
		trace_data = {
			"task": task,
			"timestamp": timestamp,
			"result": result,
			"intent_history": [
				intent.model_dump() for intent in await agent.get_intent_history()
			]
		}
		
		async with aiofiles.open(trace_file, "w") as f:
			await f.write(json.dumps(trace_data, indent=2))
	
	def migrate_all_enhancements(self, new_agent: Any) -> Dict[str, bool]:
		"""Apply all fork enhancements to the new agent"""
		results = {}
		
		migrations = [
			("enhanced_scrolling", self.migrate_enhanced_scrolling),
			("dom_caching", self.enhance_dom_caching),
			("memory_optimization", self.migrate_memory_optimization),
			("timeout_handling", self.enhance_timeout_handling),
			("token_reduction", self.apply_token_reduction),
			("recording_traces", self.enable_recording_traces)
		]
		
		for name, migration_func in migrations:
			try:
				migration_func(new_agent)
				results[name] = True
			except Exception as e:
				print(f"Failed to migrate {name}: {e}")
				results[name] = False
		
		return results


# Helper functions for easy migration

def apply_fork_enhancements(new_agent: Any) -> None:
	"""
	Apply all fork enhancements to a new agent
	
	Usage:
	```
	agent = NextGenBrowserAgent(llm=model)
	apply_fork_enhancements(agent)
	```
	"""
	migrator = ForkEnhancementsMigrator()
	results = migrator.migrate_all_enhancements(new_agent)
	
	successful = sum(1 for v in results.values() if v)
	print(f"Successfully migrated {successful}/{len(results)} fork enhancements")


def create_enhanced_agent(llm: Any, **kwargs) -> Any:
	"""
	Create a new agent with all fork enhancements pre-applied
	
	Usage:
	```
	agent = create_enhanced_agent(llm=model, use_vision=True)
	```
	"""
	from browser_use.agent.next_gen_agent import NextGenBrowserAgent
	
	# Create base agent
	agent = NextGenBrowserAgent(llm=llm, **kwargs)
	
	# Apply enhancements
	apply_fork_enhancements(agent)
	
	return agent