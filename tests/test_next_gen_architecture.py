"""Comprehensive test suite for next-generation browser automation architecture"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import base64

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.core import (
	Intent, IntentType, IntentPriority, ElementIntent,
	IntentParameter, SuccessCriteria, SubIntent
)
from browser_use.perception.base import PerceptionElement, BoundingBox
from browser_use.core.cache import IntelligentCache, MultiLevelCache
from browser_use.core.optimization import TokenOptimizer, PredictivePrefetcher


# Fixtures

@pytest.fixture
def mock_llm():
	"""Mock LLM for testing"""
	llm = AsyncMock()
	llm.ainvoke = AsyncMock(return_value=Mock(content='{"primary_goal": "test", "intent_type": "interaction"}'))
	return llm


@pytest.fixture
def mock_page():
	"""Mock Playwright page"""
	page = AsyncMock()
	page.url = "https://example.com"
	page.title = AsyncMock(return_value="Test Page")
	page.screenshot = AsyncMock(return_value=b"fake_screenshot_data")
	page.text_content = AsyncMock(return_value="Page text content")
	page.query_selector = AsyncMock(return_value=Mock())
	page.query_selector_all = AsyncMock(return_value=[Mock(), Mock()])
	page.evaluate = AsyncMock(return_value=[])
	page.wait_for_selector = AsyncMock(return_value=Mock())
	page.click = AsyncMock()
	page.type = AsyncMock()
	page.fill = AsyncMock()
	page.goto = AsyncMock()
	return page


@pytest.fixture
async def agent(mock_llm):
	"""Create test agent"""
	agent = NextGenBrowserAgent(
		llm=mock_llm,
		use_vision=True,
		use_accessibility=True,
		enable_streaming=True
	)
	await agent.initialize()
	yield agent
	await agent.cleanup()


# Intent System Tests

class TestIntentSystem:
	"""Test intent analysis and management"""
	
	@pytest.mark.asyncio
	async def test_intent_analysis(self, agent):
		"""Test basic intent analysis"""
		result = await agent.intent_analyzer.analyze("Click the submit button")
		
		assert result.intent is not None
		assert result.confidence > 0
		assert not result.requires_clarification
	
	@pytest.mark.asyncio
	async def test_complex_intent_decomposition(self, agent):
		"""Test decomposition of complex intents"""
		complex_task = "Login to the website with username test@example.com and password, then navigate to settings"
		
		# Mock LLM response
		agent.llm.ainvoke = AsyncMock(return_value=Mock(content='''
		{
			"primary_goal": "Login and navigate to settings",
			"intent_type": "composite",
			"priority": "high",
			"sub_intents": [
				{
					"description": "Login with credentials",
					"type": "authentication",
					"parameters": [
						{"name": "username", "value": "test@example.com", "type": "string", "required": true},
						{"name": "password", "value": "", "type": "string", "required": true, "sensitive": true}
					]
				},
				{
					"description": "Navigate to settings",
					"type": "navigation",
					"parameters": [
						{"name": "url", "value": "/settings", "type": "string", "required": true}
					],
					"dependencies": ["0"]
				}
			],
			"confidence": 0.9,
			"requires_clarification": false
		}
		'''))
		
		result = await agent.intent_analyzer.analyze(complex_task)
		
		assert result.intent.type == IntentType.COMPOSITE
		assert len(result.intent.sub_intents) == 2
		assert result.intent.sub_intents[0].type == IntentType.AUTHENTICATION
		assert result.intent.sub_intents[1].type == IntentType.NAVIGATION
		assert result.intent.sub_intents[1].dependencies == ["0"]
	
	@pytest.mark.asyncio
	async def test_intent_manager_lifecycle(self, agent):
		"""Test intent manager lifecycle"""
		intent = Intent(
			task_description="Test intent",
			type=IntentType.INTERACTION,
			primary_goal="Test goal"
		)
		
		# Register intent
		await agent.intent_manager.register_intent(intent)
		
		# Verify it's active
		active_intents = await agent.intent_manager.get_active_intents()
		assert len(active_intents) == 1
		assert active_intents[0].id == intent.id
		
		# Update status
		await agent.intent_manager.update_intent_status(intent.id, "completed")
		
		# Verify it's in history
		history = await agent.intent_manager.get_intent_history()
		assert len(history) == 1
		assert history[0].status == "completed"


# Perception System Tests

class TestPerceptionSystem:
	"""Test multi-modal perception"""
	
	@pytest.mark.asyncio
	async def test_dom_processor(self, agent, mock_page):
		"""Test incremental DOM processing"""
		# Mock DOM data
		mock_page.evaluate = AsyncMock(return_value=[
			{
				"id": "1",
				"type": "button",
				"selector": "#submit",
				"text": "Submit",
				"bbox": {"x": 100, "y": 200, "width": 80, "height": 40},
				"attributes": {"id": "submit", "class": "btn btn-primary"},
				"isDisabled": False,
				"isFocused": False
			}
		])
		
		result = await agent.dom_processor.analyze_page({"page": mock_page})
		
		assert len(result.elements) == 1
		element = result.elements[0]
		assert element.type == "button"
		assert element.text == "Submit"
		assert element.bounding_box is not None
		assert element.is_interactive
	
	@pytest.mark.asyncio
	async def test_vision_engine(self, agent):
		"""Test vision-based perception"""
		# Mock vision analysis
		agent.vision_engine.llm.ainvoke = AsyncMock(return_value=Mock(content='''
		[
			{
				"type": "button",
				"bbox": [100, 200, 80, 40],
				"text": "Submit",
				"description": "Blue submit button",
				"confidence": 0.95
			}
		]
		'''))
		
		screenshot = base64.b64encode(b"fake_screenshot").decode()
		result = await agent.vision_engine.analyze_page({"screenshot": screenshot})
		
		assert len(result.elements) == 1
		element = result.elements[0]
		assert element.type == "button"
		assert element.confidence == 0.95
	
	@pytest.mark.asyncio
	async def test_perception_fusion(self, agent):
		"""Test fusion of multiple perception results"""
		# Create mock results from different systems
		dom_element = PerceptionElement(
			type="button",
			text="Submit",
			selector="#submit",
			bounding_box=BoundingBox(x=100, y=200, width=80, height=40),
			confidence=1.0
		)
		
		vision_element = PerceptionElement(
			type="button",
			text="Submit",
			bounding_box=BoundingBox(x=98, y=198, width=82, height=42),
			confidence=0.9
		)
		
		from browser_use.perception.base import PerceptionResult
		
		results = {
			"dom": PerceptionResult(elements=[dom_element]),
			"vision": PerceptionResult(elements=[vision_element])
		}
		
		fused_result = await agent.perception_fusion.fuse_results(results)
		
		# Should combine into single element
		assert len(fused_result.elements) == 1
		fused_element = fused_result.elements[0]
		
		# Should have higher confidence due to agreement
		assert fused_element.confidence > 0.9
		# Should have selector from DOM
		assert fused_element.selector == "#submit"


# Element Resolution Tests

class TestElementResolution:
	"""Test element resolution strategies"""
	
	@pytest.mark.asyncio
	async def test_multi_strategy_resolution(self, agent, mock_page):
		"""Test element resolution with multiple strategies"""
		element_intent = ElementIntent(
			description="Blue submit button",
			element_type="button",
			text_content="Submit"
		)
		
		# Mock DOM results
		mock_element = PerceptionElement(
			type="button",
			text="Submit",
			selector="button[type='submit']",
			confidence=0.9
		)
		
		agent.dom_processor.find_elements = AsyncMock(return_value=[mock_element])
		
		perception_data = {"page": mock_page}
		
		resolved = await agent.element_resolver.resolve_element(
			element_intent,
			perception_data,
			mock_page
		)
		
		assert resolved is not None
		assert resolved.confidence > 0
		assert resolved.element.type == "button"
	
	@pytest.mark.asyncio
	async def test_element_caching(self, agent, mock_page):
		"""Test element resolution caching"""
		element_intent = ElementIntent(
			description="Submit button",
			css_selector="#submit"
		)
		
		mock_element = PerceptionElement(
			type="button",
			selector="#submit"
		)
		
		agent.dom_processor.find_elements = AsyncMock(return_value=[mock_element])
		
		perception_data = {"page": mock_page}
		
		# First resolution
		resolved1 = await agent.element_resolver.resolve_element(
			element_intent,
			perception_data,
			mock_page
		)
		
		# Second resolution should use cache
		resolved2 = await agent.element_resolver.resolve_element(
			element_intent,
			perception_data,
			mock_page
		)
		
		# Should only call find_elements once
		assert agent.dom_processor.find_elements.call_count == 1


# Action Orchestration Tests

class TestActionOrchestration:
	"""Test action planning and execution"""
	
	@pytest.mark.asyncio
	async def test_parallel_action_execution(self, agent, mock_page):
		"""Test parallel execution of independent actions"""
		# Create intent with parallel sub-intents
		intent = Intent(
			task_description="Extract data from multiple elements",
			type=IntentType.EXTRACTION,
			primary_goal="Extract page data",
			sub_intents=[
				SubIntent(
					id="extract_1",
					description="Extract title",
					type=IntentType.EXTRACTION,
					parameters=[IntentParameter(name="selector", value="h1", type="string")]
				),
				SubIntent(
					id="extract_2",
					description="Extract description",
					type=IntentType.EXTRACTION,
					parameters=[IntentParameter(name="selector", value="p", type="string")]
				)
			]
		)
		
		# Mock page methods
		mock_page.text_content = AsyncMock(side_effect=["Page Title", "Page Description"])
		
		result = await agent.action_orchestrator.execute_intent(intent, mock_page)
		
		assert result.success
		assert len(result.actions_taken) == 2
		
		# Both extractions should have run
		assert mock_page.text_content.call_count == 2
	
	@pytest.mark.asyncio
	async def test_action_retry_logic(self, agent, mock_page):
		"""Test action retry on failure"""
		from browser_use.core.orchestrator.service import Action, ActionType
		
		# Create action that fails first time
		click_count = 0
		
		async def mock_click(*args, **kwargs):
			nonlocal click_count
			click_count += 1
			if click_count == 1:
				raise Exception("Element not ready")
			return None
		
		mock_page.click = mock_click
		
		action = Action(
			id="test_click",
			type=ActionType.CLICK,
			target=Mock(selector="#button"),
			retry_count=3
		)
		
		result = await agent.action_orchestrator._execute_action(action)
		
		assert result.success
		assert result.retries_used == 1
		assert click_count == 2


# Optimization Tests

class TestOptimization:
	"""Test performance optimization features"""
	
	@pytest.mark.asyncio
	async def test_intelligent_caching(self):
		"""Test intelligent cache operations"""
		cache = IntelligentCache(max_size_mb=1, max_entries=10)
		
		# Test basic operations
		await cache.set("key1", "value1", ttl_seconds=60)
		value = await cache.get("key1")
		assert value == "value1"
		
		# Test TTL expiration
		await cache.set("key2", "value2", ttl_seconds=0.1)
		await asyncio.sleep(0.2)
		value = await cache.get("key2")
		assert value is None
		
		# Test LRU eviction
		for i in range(15):
			await cache.set(f"key_{i}", f"value_{i}")
		
		# First keys should be evicted
		assert await cache.get("key_0") is None
		assert await cache.get("key_14") is not None
		
		# Test tag-based invalidation
		await cache.set("tagged1", "value", tags=["group1"])
		await cache.set("tagged2", "value", tags=["group1"])
		await cache.set("tagged3", "value", tags=["group2"])
		
		invalidated = await cache.invalidate_by_tag("group1")
		assert invalidated == 2
		assert await cache.get("tagged1") is None
		assert await cache.get("tagged3") is not None
	
	@pytest.mark.asyncio
	async def test_token_optimization(self):
		"""Test token compression"""
		optimizer = TokenOptimizer()
		
		# Test prompt compression
		long_prompt = "This is a very long prompt. " * 100
		compressed, stats = optimizer.optimize_prompt(long_prompt, max_tokens=100)
		
		assert stats.compressed_tokens < stats.original_tokens
		assert stats.compression_ratio < 1.0
		
		# Test element optimization
		elements = [
			PerceptionElement(
				type="div",
				text="Some text " * 20,
				attributes={"class": "long-class-name", "id": "element-id"},
				is_interactive=False
			)
			for _ in range(50)
		]
		
		optimized_elements, stats = optimizer.optimize_perception_data(elements, max_tokens=500)
		
		assert len(optimized_elements) < len(elements)
		assert stats.elements_removed > 0
	
	@pytest.mark.asyncio
	async def test_predictive_prefetching(self):
		"""Test pattern learning and prefetching"""
		from browser_use.core.optimization import PatternLearner
		
		learner = PatternLearner()
		
		# Record a pattern
		intents = [
			Intent(task_description="Navigate", type=IntentType.NAVIGATION, primary_goal="Go to page"),
			Intent(task_description="Login", type=IntentType.AUTHENTICATION, primary_goal="Login"),
			Intent(task_description="Fill form", type=IntentType.FORM_FILL, primary_goal="Submit form")
		]
		
		for intent in intents:
			learner.record_intent(intent)
		
		# Test prediction
		predictions = learner.predict_next_intents([IntentType.NAVIGATION])
		
		assert len(predictions) > 0
		assert predictions[0][0] == IntentType.AUTHENTICATION  # Should predict login after navigation


# Integration Tests

class TestIntegration:
	"""Test complete workflows"""
	
	@pytest.mark.asyncio
	async def test_complete_task_execution(self, agent, mock_page):
		"""Test executing a complete task"""
		# Mock browser session
		mock_browser_session = AsyncMock()
		mock_browser = AsyncMock()
		mock_context = AsyncMock()
		
		mock_browser.contexts = [mock_context]
		mock_context.pages = [mock_page]
		mock_browser_session.start = AsyncMock(return_value=mock_browser)
		
		with patch.object(agent, 'browser_session', mock_browser_session):
			agent.browser_session = mock_browser_session
			agent.current_page = mock_page
			
			# Execute task
			result = await agent.execute_task(
				"Click the submit button",
				url="https://example.com"
			)
			
			assert "success" in result
			assert "intent_id" in result
	
	@pytest.mark.asyncio
	async def test_backward_compatibility(self, mock_llm):
		"""Test backward compatibility layer"""
		from browser_use.agent.compatibility import BackwardCompatibleAgent
		
		agent = BackwardCompatibleAgent(
			task="Click submit button",
			llm=mock_llm
		)
		
		await agent.initialize()
		
		# Test legacy run method
		mock_page = AsyncMock()
		agent.current_page = mock_page
		agent.browser_session = AsyncMock()
		
		actions = await agent.run()
		
		assert isinstance(actions, list)
		
		await agent.cleanup()
	
	@pytest.mark.asyncio
	async def test_custom_action_migration(self, agent):
		"""Test custom action migration"""
		from browser_use.migration import CustomActionMigrator
		
		# Create mock legacy action
		async def custom_handler(page, param1):
			return f"Executed with {param1}"
		
		from browser_use.controller.registry.views import RegisteredAction
		
		legacy_action = RegisteredAction(
			name="custom_action",
			description="Test custom action",
			handler=custom_handler,
			param_model=None
		)
		
		# Migrate action
		migrator = CustomActionMigrator()
		migrator.migrate_action(legacy_action, agent)
		
		# Verify it's registered
		assert "custom_action" in agent.action_orchestrator._custom_actions


# Performance Tests

class TestPerformance:
	"""Test performance characteristics"""
	
	@pytest.mark.asyncio
	async def test_performance_monitoring(self, agent, mock_page):
		"""Test performance monitoring"""
		from browser_use.core.optimization.performance import PerformanceMonitor
		
		monitor = PerformanceMonitor()
		
		async with monitor:
			# Simulate some work
			await asyncio.sleep(0.1)
		
		assert len(monitor.metrics) > 0
		
		# Check metrics
		time_metric = next(m for m in monitor.metrics if m.name == "execution_time")
		assert time_metric.value > 0.1
	
	@pytest.mark.asyncio
	async def test_benchmark_suite(self, agent):
		"""Test benchmark execution"""
		from browser_use.core.optimization.performance import PerformanceBenchmark
		
		benchmark = PerformanceBenchmark()
		
		# Run a simple benchmark
		async def test_operation():
			await asyncio.sleep(0.01)
		
		stats = await benchmark.benchmark_operation(
			"test_operation",
			test_operation,
			iterations=5,
			warmup=1
		)
		
		assert "mean" in stats
		assert "median" in stats
		assert stats["mean"] > 0.01


# Error Handling Tests

class TestErrorHandling:
	"""Test error handling and recovery"""
	
	@pytest.mark.asyncio
	async def test_intent_error_recovery(self, agent, mock_page):
		"""Test recovery from intent execution errors"""
		# Create intent that will fail
		intent = Intent(
			task_description="Click non-existent button",
			type=IntentType.INTERACTION,
			primary_goal="Click button"
		)
		
		# Mock element resolution to fail
		agent.element_resolver.resolve_element = AsyncMock(
			side_effect=Exception("Element not found")
		)
		
		result = await agent.action_orchestrator.execute_intent(intent, mock_page)
		
		assert not result.success
		assert len(result.errors) > 0
	
	@pytest.mark.asyncio
	async def test_graceful_timeout_handling(self, agent, mock_page):
		"""Test graceful timeout handling"""
		# Create slow operation
		async def slow_operation():
			await asyncio.sleep(10)
		
		mock_page.wait_for_selector = slow_operation
		
		# Should timeout gracefully
		with pytest.raises(asyncio.TimeoutError):
			await asyncio.wait_for(
				mock_page.wait_for_selector("selector"),
				timeout=0.1
			)


if __name__ == "__main__":
	pytest.main([__file__, "-v"])