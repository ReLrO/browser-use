"""Robust action execution with intelligent retries and adaptation"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeout
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
	CLICK = "click"
	TYPE = "type"
	NAVIGATE = "navigate"
	SCROLL = "scroll"
	WAIT = "wait"
	KEYBOARD = "keyboard"
	HOVER = "hover"
	SELECT = "select"
	DRAG = "drag"


@dataclass
class ActionResult:
	success: bool
	action_type: ActionType
	details: Dict[str, Any]
	error: Optional[str] = None
	retry_count: int = 0
	execution_time_ms: float = 0


class RobustActionExecutor:
	"""Execute actions with smart retries and fallback strategies"""
	
	def __init__(self):
		self.retry_strategies = {
			ActionType.CLICK: [
				self._click_standard,
				self._click_force,
				self._click_javascript,
				self._click_coordinates,
				self._click_with_scroll,
				self._click_with_wait_and_retry
			],
			ActionType.TYPE: [
				self._type_standard,
				self._type_with_clear,
				self._type_with_focus,
				self._type_javascript,
				self._type_keyboard_events
			]
		}
		
		# Track what works for faster execution
		self.success_history: Dict[str, List[str]] = {}
	
	async def execute_action(
		self,
		page: Page,
		action_type: ActionType,
		target: Optional[ElementHandle] = None,
		parameters: Optional[Dict[str, Any]] = None
	) -> ActionResult:
		"""Execute action with intelligent retries"""
		
		parameters = parameters or {}
		start_time = asyncio.get_event_loop().time()
		
		# Get strategies for this action type
		strategies = self.retry_strategies.get(action_type, [])
		
		if not strategies:
			# Simple actions without retries
			return await self._execute_simple_action(page, action_type, target, parameters)
			
		# Try strategies in order
		last_error = None
		retry_count = 0
		
		# Check history for what worked before
		history_key = f"{action_type}_{page.url}"
		successful_strategies = self.success_history.get(history_key, [])
		
		# Reorder strategies based on history
		ordered_strategies = []
		for strategy_name in successful_strategies:
			for strategy in strategies:
				if strategy.__name__ == strategy_name:
					ordered_strategies.append(strategy)
					
		# Add remaining strategies
		for strategy in strategies:
			if strategy not in ordered_strategies:
				ordered_strategies.append(strategy)
				
		# Execute strategies
		for strategy in ordered_strategies:
			try:
				logger.debug(f"Trying {action_type} strategy: {strategy.__name__}")
				
				result = await strategy(page, target, parameters)
				
				if result:
					# Record success
					execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
					
					# Update history
					if history_key not in self.success_history:
						self.success_history[history_key] = []
					if strategy.__name__ not in self.success_history[history_key]:
						self.success_history[history_key].insert(0, strategy.__name__)
						# Keep only top 3
						self.success_history[history_key] = self.success_history[history_key][:3]
						
					return ActionResult(
						success=True,
						action_type=action_type,
						details={
							'strategy': strategy.__name__,
							'parameters': parameters
						},
						retry_count=retry_count,
						execution_time_ms=execution_time
					)
					
			except Exception as e:
				last_error = str(e)
				logger.debug(f"Strategy {strategy.__name__} failed: {e}")
				retry_count += 1
				
				# Brief pause before next strategy
				await asyncio.sleep(0.1)
				
		# All strategies failed
		execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
		
		return ActionResult(
			success=False,
			action_type=action_type,
			details={'parameters': parameters},
			error=last_error,
			retry_count=retry_count,
			execution_time_ms=execution_time
		)
	
	async def _execute_simple_action(
		self,
		page: Page,
		action_type: ActionType,
		target: Optional[ElementHandle],
		parameters: Dict[str, Any]
	) -> ActionResult:
		"""Execute simple actions without retries"""
		
		start_time = asyncio.get_event_loop().time()
		
		try:
			if action_type == ActionType.NAVIGATE:
				url = parameters.get('url')
				if not url:
					raise ValueError("No URL provided")
				await page.goto(url, wait_until='domcontentloaded', timeout=30000)
				result = {'navigated_to': page.url}
				
			elif action_type == ActionType.WAIT:
				duration_ms = parameters.get('duration_ms', 1000)
				await asyncio.sleep(duration_ms / 1000)
				result = {'waited_ms': duration_ms}
				
			elif action_type == ActionType.SCROLL:
				direction = parameters.get('direction', 'down')
				amount = parameters.get('amount', 500)
				
				if direction == 'down':
					await page.evaluate(f"window.scrollBy(0, {amount})")
				elif direction == 'up':
					await page.evaluate(f"window.scrollBy(0, -{amount})")
				elif direction == 'right':
					await page.evaluate(f"window.scrollBy({amount}, 0)")
				elif direction == 'left':
					await page.evaluate(f"window.scrollBy(-{amount}, 0)")
					
				result = {'scrolled': direction, 'amount': amount}
				
			elif action_type == ActionType.KEYBOARD:
				key = parameters.get('key')
				if not key:
					raise ValueError("No key provided")
				await page.keyboard.press(key)
				result = {'pressed': key}
				
			else:
				raise ValueError(f"Unknown simple action type: {action_type}")
				
			execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
			
			return ActionResult(
				success=True,
				action_type=action_type,
				details=result,
				execution_time_ms=execution_time
			)
			
		except Exception as e:
			execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
			
			return ActionResult(
				success=False,
				action_type=action_type,
				details={'parameters': parameters},
				error=str(e),
				execution_time_ms=execution_time
			)
	
	# Click strategies
	
	async def _click_standard(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Standard click"""
		await element.click(timeout=5000)
		return True
		
	async def _click_force(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Force click bypassing actionability checks"""
		await element.click(force=True, timeout=5000)
		return True
		
	async def _click_javascript(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Click using JavaScript"""
		await element.evaluate("el => el.click()")
		return True
		
	async def _click_coordinates(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Click using coordinates"""
		box = await element.bounding_box()
		if not box:
			return False
			
		x = box['x'] + box['width'] / 2
		y = box['y'] + box['height'] / 2
		
		await page.mouse.click(x, y)
		return True
		
	async def _click_with_scroll(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Scroll element into view then click"""
		await element.scroll_into_view_if_needed()
		await page.wait_for_timeout(500)  # Wait for scroll to complete
		await element.click(timeout=5000)
		return True
		
	async def _click_with_wait_and_retry(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Wait for element to be stable then click"""
		# Wait for element to be stable
		for _ in range(3):
			try:
				await element.wait_for_element_state('stable', timeout=2000)
				await element.click(timeout=3000)
				return True
			except:
				await asyncio.sleep(0.5)
				
		return False
	
	# Type strategies
	
	async def _type_standard(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Standard typing"""
		text = parameters.get('text', '')
		await element.type(text, delay=50)
		return True
		
	async def _type_with_clear(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Clear then type"""
		text = parameters.get('text', '')
		await element.fill(text)
		return True
		
	async def _type_with_focus(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Focus first then type"""
		text = parameters.get('text', '')
		await element.focus()
		await page.wait_for_timeout(100)
		await element.type(text, delay=50)
		return True
		
	async def _type_javascript(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Type using JavaScript"""
		text = parameters.get('text', '')
		await element.evaluate(f"el => {{ el.value = '{text}'; el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}")
		return True
		
	async def _type_keyboard_events(self, page: Page, element: ElementHandle, parameters: Dict[str, Any]) -> bool:
		"""Type using keyboard events"""
		text = parameters.get('text', '')
		await element.click()  # Focus
		await page.wait_for_timeout(100)
		
		# Clear existing text
		await page.keyboard.press('Control+A')
		await page.keyboard.press('Delete')
		
		# Type new text
		await page.keyboard.type(text, delay=50)
		return True