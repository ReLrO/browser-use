"""Next-generation browser agent with intent-driven architecture"""

import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import base64

from langchain_core.language_models import BaseChatModel
from playwright.async_api import Browser, BrowserContext, Page

from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile

from browser_use.core import (
	IntentAnalyzer, IntentManager,
	StreamingStateManager, EventStreamConfig,
	MultiStrategyElementResolver,
	ParallelActionOrchestrator,
	IntentToActionMapper,
	IntentVerificationService
)

from browser_use.perception import (
	VisionEngine, IncrementalDOMProcessor,
	AccessibilityProcessor, MultiModalPerceptionFusion
)

from browser_use.utils import time_execution_async


class NextGenBrowserAgent:
	"""Intent-driven browser automation agent"""
	
	def __init__(
		self,
		llm: BaseChatModel,
		browser_profile: Optional[BrowserProfile] = None,
		use_vision: bool = True,
		use_accessibility: bool = True,
		enable_streaming: bool = True,
		event_config: Optional[EventStreamConfig] = None
	):
		self.llm = llm
		self.browser_profile = browser_profile or BrowserProfile()
		self.use_vision = use_vision
		self.use_accessibility = use_accessibility
		self.enable_streaming = enable_streaming
		
		# Core components
		self.intent_analyzer = IntentAnalyzer(llm)
		self.intent_manager = IntentManager()
		
		# Perception systems
		self.vision_engine = VisionEngine(llm) if use_vision else None
		self.dom_processor = IncrementalDOMProcessor()
		self.accessibility_processor = AccessibilityProcessor() if use_accessibility else None
		self.perception_fusion = MultiModalPerceptionFusion()
		
		# State management
		self.state_manager = StreamingStateManager(event_config) if enable_streaming else None
		
		# Resolution and orchestration
		self.element_resolver = MultiStrategyElementResolver(
			vision_engine=self.vision_engine,
			dom_processor=self.dom_processor,
			accessibility_processor=self.accessibility_processor,
			perception_fusion=self.perception_fusion,
			llm=self.llm
		)
		
		self.action_orchestrator = ParallelActionOrchestrator(self.element_resolver)
		self.intent_mapper = IntentToActionMapper()
		self.verification_service = IntentVerificationService(self.vision_engine)
		
		# Browser management
		self.browser_session: Optional[BrowserSession] = None
		self.current_page: Optional[Page] = None
		self._tab_counter = 0
		
		# Execution context
		self._execution_context: Dict[str, Any] = {}
		self._initialized = False
	
	async def initialize(self) -> None:
		"""Initialize all components"""
		if self._initialized:
			return
		
		# Initialize perception systems
		if self.vision_engine:
			await self.vision_engine.initialize({})
		
		await self.dom_processor.initialize({
			"cache_ttl": 5.0,
			"mutation_batch_size": 100,
			"full_scan_interval": 60.0
		})
		
		if self.accessibility_processor:
			await self.accessibility_processor.initialize({})
		
		# Register perception systems with fusion
		self.perception_fusion.register_system("dom", self.dom_processor)
		if self.vision_engine:
			self.perception_fusion.register_system("vision", self.vision_engine)
		if self.accessibility_processor:
			self.perception_fusion.register_system("accessibility", self.accessibility_processor)
		
		# Start state manager
		if self.state_manager:
			await self.state_manager.start()
		
		self._initialized = True
	
	async def cleanup(self) -> None:
		"""Clean up all resources"""
		# Stop browser
		if self.browser_session:
			await self.browser_session.close()
		
		# Clean up perception systems
		if self.vision_engine:
			await self.vision_engine.cleanup()
		await self.dom_processor.cleanup()
		if self.accessibility_processor:
			await self.accessibility_processor.cleanup()
		
		# Stop state manager
		if self.state_manager:
			await self.state_manager.stop()
		
		self._initialized = False
	
	@time_execution_async("execute_task")
	async def execute_task(
		self,
		task: str,
		url: Optional[str] = None,
		context: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""Execute a high-level task"""
		
		# Ensure initialized
		if not self._initialized:
			await self.initialize()
		
		# Start browser if needed
		if not self.browser_session:
			await self._start_browser()
		
		# Navigate if URL provided
		if url and self.current_page:
			await self.current_page.goto(url)
		
		# Clean execution context to avoid serialization issues
		clean_context = {}
		if context:
			for k, v in context.items():
				# Skip non-serializable objects
				if not hasattr(v, '_remote_object'):  # Skip Playwright objects
					clean_context[k] = v
		
		# Reset execution context for this task
		self._execution_context = clean_context
		self._execution_context["start_time"] = datetime.now().isoformat()
		
		try:
			# Analyze task into intent
			analysis_result = await self.intent_analyzer.analyze(task, self._execution_context)
			
			if analysis_result.requires_clarification:
				return {
					"success": False,
					"requires_clarification": True,
					"questions": analysis_result.clarification_questions
				}
			
			intent = analysis_result.intent
			await self.intent_manager.register_intent(intent)
			
			# Get current perception data
			perception_data = await self._get_perception_data()
			# Make a copy without the page object for context
			clean_perception_data = {k: v for k, v in perception_data.items() if k != "page"}
			self._execution_context["perception_data"] = clean_perception_data
			# Keep page in execution context separately
			self._execution_context["page"] = self.current_page
			
			# Execute intent
			execution_result = await self.action_orchestrator.execute_intent(
				intent,
				self.current_page,
				self._execution_context
			)
			
			# Update intent status
			await self.intent_manager.update_intent_status(
				intent.id,
				"completed" if execution_result.success else "failed",
				execution_result.errors[0] if execution_result.errors else None
			)
			
			# Build response
			return {
				"success": execution_result.success,
				"intent_id": intent.id,
				"actions_taken": len(execution_result.actions_taken),
				"duration_seconds": execution_result.duration_seconds,
				"tokens_used": execution_result.tokens_used,
				"verification": {
					"criteria_met": execution_result.criteria_met,
					"screenshot": execution_result.verification_screenshot
				},
				"errors": execution_result.errors,
				"data": getattr(execution_result, 'extracted_data', {})
			}
			
		except Exception as e:
			import logging
			logger = logging.getLogger(__name__)
			logger.error(f"Error executing task: {e}", exc_info=True)
			return {
				"success": False,
				"error": str(e),
				"error_type": type(e).__name__
			}
	
	async def execute_intent_directly(self, intent: Any) -> Dict[str, Any]:
		"""Execute a pre-built intent directly"""
		if not self._initialized:
			await self.initialize()
		
		if not self.browser_session:
			await self._start_browser()
		
		await self.intent_manager.register_intent(intent)
		
		# Initialize execution context if not exists
		if not hasattr(self, '_execution_context'):
			self._execution_context = {}
		
		perception_data = await self._get_perception_data()
		self._execution_context["perception_data"] = perception_data
		
		execution_result = await self.action_orchestrator.execute_intent(
			intent,
			self.current_page,
			self._execution_context
		)
		
		return execution_result.model_dump()
	
	# Browser management
	
	async def _start_browser(self) -> None:
		"""Start browser session"""
		self.browser_session = BrowserSession(browser_profile=self.browser_profile)
		await self.browser_session.start()
		
		# Get or create page
		if self.browser_session.browser and self.browser_session.browser.contexts:
			context = self.browser_session.browser.contexts[0]
			pages = context.pages
			if pages:
				self.current_page = pages[0]
			else:
				self.current_page = await context.new_page()
		elif self.browser_session.browser:
			context = await self.browser_session.browser.new_context()
			self.current_page = await context.new_page()
		else:
			# Use the browser context from session
			if self.browser_session.browser_context:
				self.current_page = await self.browser_session.browser_context.new_page()
		
		# Set up monitoring
		if self.state_manager:
			tab_id = f"tab_{self._tab_counter}"
			self._tab_counter += 1
			await self.state_manager.setup_page_monitoring(self.current_page, tab_id)
		
		# Set up DOM mutation observer
		await self.dom_processor.setup_mutation_observer(self.current_page)
	
	async def new_tab(self) -> Page:
		"""Open a new tab"""
		if not self.browser_session:
			await self._start_browser()
		
		context = self.current_page.context
		page = await context.new_page()
		
		# Set up monitoring
		if self.state_manager:
			tab_id = f"tab_{self._tab_counter}"
			self._tab_counter += 1
			await self.state_manager.setup_page_monitoring(page, tab_id)
		
		# Set up DOM observer
		await self.dom_processor.setup_mutation_observer(page)
		
		return page
	
	async def switch_tab(self, page: Page) -> None:
		"""Switch to a different tab"""
		self.current_page = page
		self._execution_context["page"] = page
	
	# Perception
	
	async def _get_perception_data(self) -> Dict[str, Any]:
		"""Get current perception data from all systems"""
		if not self.current_page:
			return {}
		
		perception_data = {
			"url": self.current_page.url,
			"timestamp": datetime.now().isoformat()
		}
		
		# Take screenshot if vision enabled
		if self.use_vision:
			try:
				screenshot = await self.current_page.screenshot()
				perception_data["screenshot"] = base64.b64encode(screenshot).decode()
			except Exception:
				pass
		
		# Run perception systems
		perception_results = {}
		perception_results_for_fusion = {}  # Keep raw results for fusion
		
		# DOM analysis
		try:
			dom_result = await self.dom_processor.analyze_page({"page": self.current_page})
			perception_results_for_fusion["dom"] = dom_result
			# Convert to dict if it's a model
			if hasattr(dom_result, 'model_dump'):
				perception_results["dom"] = dom_result.model_dump(mode='json')
			else:
				perception_results["dom"] = dom_result
		except Exception as e:
			perception_results["dom"] = {"error": str(e)}
		
		# Vision analysis
		if self.vision_engine and perception_data.get("screenshot"):
			try:
				vision_result = await self.vision_engine.analyze_page(perception_data)
				perception_results_for_fusion["vision"] = vision_result
				# Convert to dict if it's a model
				if hasattr(vision_result, 'model_dump'):
					perception_results["vision"] = vision_result.model_dump(mode='json')
				else:
					perception_results["vision"] = vision_result
			except Exception as e:
				perception_results["vision"] = {"error": str(e)}
		
		# Accessibility analysis
		if self.accessibility_processor:
			try:
				a11y_result = await self.accessibility_processor.analyze_page({"page": self.current_page})
				perception_results_for_fusion["accessibility"] = a11y_result
				# Convert to dict if it's a model
				if hasattr(a11y_result, 'model_dump'):
					perception_results["accessibility"] = a11y_result.model_dump(mode='json')
				else:
					perception_results["accessibility"] = a11y_result
			except Exception as e:
				perception_results["accessibility"] = {"error": str(e)}
		
		# Fuse results using the raw PerceptionResult objects
		if len(perception_results_for_fusion) > 1:
			try:
				fused_result = await self.perception_fusion.fuse_results(perception_results_for_fusion)
				if hasattr(fused_result, 'model_dump'):
					perception_data["fused_perception"] = fused_result.model_dump(mode='json')
				elif isinstance(fused_result, dict):
					perception_data["fused_perception"] = fused_result
				else:
					# Convert to dict if it's not already
					perception_data["fused_perception"] = {"elements": [], "errors": ["Failed to convert fusion result"]}
			except Exception:
				pass
		
		perception_data["perception_results"] = perception_results
		
		# Get streaming state if enabled
		if self.state_manager:
			tab_id = self._execution_context.get("current_tab_id", "tab_0")
			state = await self.state_manager.get_relevant_state(
				None,  # No intent yet
				since=self._execution_context.get("start_time"),
				tab_id=tab_id
			)
			perception_data["streaming_state"] = state
		
		return perception_data
	
	# Custom action registration
	
	def register_custom_action(self, name: str, handler: Any) -> None:
		"""Register a custom action handler"""
		self.action_orchestrator.register_custom_action(name, handler)
	
	def register_intent_pattern(
		self,
		pattern: str,
		pattern_type: Any,
		action_generator: Any,
		priority: int = 0
	) -> None:
		"""Register a custom intent pattern"""
		self.intent_mapper.register_pattern(
			pattern,
			pattern_type,
			action_generator,
			priority=priority
		)
	
	def register_custom_verifier(self, name: str, verifier: Any) -> None:
		"""Register a custom verification function"""
		self.verification_service.register_custom_verifier(name, verifier)
	
	# State access
	
	async def get_current_state(self) -> Dict[str, Any]:
		"""Get current browser and perception state"""
		return await self._get_perception_data()
	
	async def get_intent_history(self, limit: int = 10) -> List[Any]:
		"""Get recent intent history"""
		return await self.intent_manager.get_intent_history(limit)
	
	async def get_active_intents(self) -> List[Any]:
		"""Get currently active intents"""
		return await self.intent_manager.get_active_intents()
	
	# Utility methods
	
	async def take_screenshot(self, full_page: bool = False) -> bytes:
		"""Take a screenshot"""
		if not self.current_page:
			raise RuntimeError("No active page")
		
		return await self.current_page.screenshot(full_page=full_page)
	
	async def get_page_text(self) -> str:
		"""Get all text from the page"""
		if not self.current_page:
			raise RuntimeError("No active page")
		
		return await self.current_page.text_content("body") or ""
	
	async def wait_for_stable_state(self, timeout: float = 5.0) -> None:
		"""Wait for page to reach stable state"""
		if not self.current_page:
			return
		
		try:
			# Wait for network idle
			await self.current_page.wait_for_load_state("networkidle", timeout=timeout * 1000)
		except Exception:
			# Timeout is okay, page might still be loading
			pass
		
		# Additional stability check
		await asyncio.sleep(0.5)