"""A truly robust browser automation agent"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from playwright.async_api import Page
import base64

from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.core.robust_element_finder import RobustElementFinder
from browser_use.core.robust_action_executor import RobustActionExecutor, ActionType, ActionResult

logger = logging.getLogger(__name__)


class RobustBrowserAgent:
	"""Robust agent that combines all strategies for reliability"""
	
	def __init__(self, llm, browser_profile: Optional[BrowserProfile] = None):
		self.llm = llm
		self.browser_profile = browser_profile or BrowserProfile()
		self.browser_session = None
		self.page = None
		
		# Robust components
		self.element_finder = RobustElementFinder(llm)
		self.action_executor = RobustActionExecutor()
		
		# State tracking
		self.action_history: List[ActionResult] = []
		self.current_url: Optional[str] = None
		
	async def initialize(self):
		"""Initialize browser"""
		self.browser_session = BrowserSession(browser_profile=self.browser_profile)
		await self.browser_session.start()
		
		# Get page
		if self.browser_session.browser_context:
			pages = self.browser_session.browser_context.pages
			if pages:
				self.page = pages[0]
			else:
				self.page = await self.browser_session.browser_context.new_page()
				
		# Set up event listeners
		self.page.on('load', self._on_page_load)
		self.page.on('domcontentloaded', self._on_dom_ready)
		
	async def cleanup(self):
		"""Clean up resources"""
		if self.browser_session:
			await self.browser_session.close()
			
	async def execute_task(self, task: str, max_retries: int = 3) -> Dict[str, Any]:
		"""Execute a task with full robustness"""
		
		logger.info(f"Executing task: {task}")
		
		# Parse task intent
		intent = await self._parse_task_intent(task)
		
		# Execute based on intent
		result = None
		for attempt in range(max_retries):
			try:
				if intent['type'] == 'navigate':
					result = await self._handle_navigation(intent)
				elif intent['type'] == 'search':
					result = await self._handle_search(intent)
				elif intent['type'] == 'click':
					result = await self._handle_click(intent)
				elif intent['type'] == 'type':
					result = await self._handle_type(intent)
				elif intent['type'] == 'extract':
					result = await self._handle_extract(intent)
				else:
					# Complex task - use LLM guidance
					result = await self._handle_complex_task(task, intent)
					
				if result and result.get('success'):
					break
					
			except Exception as e:
				logger.error(f"Attempt {attempt + 1} failed: {e}")
				if attempt < max_retries - 1:
					# Wait before retry with exponential backoff
					await asyncio.sleep(2 ** attempt)
					
		return result or {'success': False, 'error': 'Max retries exceeded'}
		
	async def _parse_task_intent(self, task: str) -> Dict[str, Any]:
		"""Parse task to understand intent"""
		task_lower = task.lower()
		
		# Navigation
		if any(phrase in task_lower for phrase in ['go to', 'navigate', 'open', 'visit']):
			import re
			url_match = re.search(r'(?:go to|navigate to|open|visit)\s+(\S+)', task_lower)
			if url_match:
				url = url_match.group(1)
				if not url.startswith(('http://', 'https://')):
					url = f'https://{url}'
				return {'type': 'navigate', 'url': url}
				
		# Search
		elif 'search for' in task_lower:
			import re
			query_match = re.search(r"search for\s+['\"]?([^'\"]+)['\"]?", task_lower)
			if query_match:
				return {'type': 'search', 'query': query_match.group(1).strip()}
				
		# Click
		elif 'click' in task_lower:
			return {'type': 'click', 'target': task}
			
		# Type
		elif any(word in task_lower for word in ['type', 'enter', 'fill', 'input']):
			return {'type': 'type', 'description': task}
			
		# Extract
		elif any(word in task_lower for word in ['extract', 'get', 'find', 'read']):
			return {'type': 'extract', 'target': task}
			
		# Unknown - let LLM figure it out
		return {'type': 'complex', 'task': task}
		
	async def _handle_navigation(self, intent: Dict[str, Any]) -> Dict[str, Any]:
		"""Handle navigation robustly"""
		url = intent['url']
		
		result = await self.action_executor.execute_action(
			self.page,
			ActionType.NAVIGATE,
			parameters={'url': url}
		)
		
		if result.success:
			self.current_url = self.page.url
			self.action_history.append(result)
			
			# Wait for page to be ready
			await self._wait_for_page_ready()
			
		return {
			'success': result.success,
			'url': self.page.url if result.success else None,
			'error': result.error
		}
		
	async def _handle_search(self, intent: Dict[str, Any]) -> Dict[str, Any]:
		"""Handle search with multiple strategies"""
		query = intent['query']
		
		# Find search box
		search_element = await self.element_finder.find_element(
			self.page,
			"search input field",
			element_type="input"
		)
		
		if not search_element:
			logger.error("Could not find search box")
			# Try with vision
			search_element = await self._find_element_with_vision("search box or search input field")
			
		if not search_element:
			return {'success': False, 'error': 'Could not find search box'}
			
		# Type search query
		type_result = await self.action_executor.execute_action(
			self.page,
			ActionType.TYPE,
			target=search_element,
			parameters={'text': query}
		)
		
		if not type_result.success:
			return {'success': False, 'error': f'Could not type query: {type_result.error}'}
			
		# Submit search
		submit_result = await self._submit_search()
		
		if submit_result['success']:
			# Wait for results
			await self._wait_for_search_results()
			
		return {
			'success': submit_result['success'],
			'query': query,
			'error': submit_result.get('error')
		}
		
	async def _handle_click(self, intent: Dict[str, Any]) -> Dict[str, Any]:
		"""Handle click robustly"""
		target_desc = intent['target']
		
		# Find element
		element = await self.element_finder.find_element(self.page, target_desc)
		
		if not element:
			# Try with vision
			element = await self._find_element_with_vision(target_desc)
			
		if not element:
			return {'success': False, 'error': f'Could not find element: {target_desc}'}
			
		# Click element
		click_result = await self.action_executor.execute_action(
			self.page,
			ActionType.CLICK,
			target=element
		)
		
		if click_result.success:
			self.action_history.append(click_result)
			# Wait for potential navigation
			await self._wait_for_stability()
			
		return {
			'success': click_result.success,
			'clicked': target_desc if click_result.success else None,
			'error': click_result.error
		}
		
	async def _handle_type(self, intent: Dict[str, Any]) -> Dict[str, Any]:
		"""Handle typing robustly"""
		# Extract what to type and where
		import re
		
		# Try to extract quoted text
		text_match = re.search(r"['\"]([^'\"]+)['\"]", intent['description'])
		if text_match:
			text = text_match.group(1)
		else:
			# Try to extract after "type"
			text_match = re.search(r"type\s+(.+?)(?:\s+in|\s+into|$)", intent['description'], re.IGNORECASE)
			text = text_match.group(1) if text_match else ""
			
		# Find target element
		element_desc = intent['description']
		element = await self.element_finder.find_element(self.page, element_desc)
		
		if not element:
			element = await self._find_element_with_vision(element_desc)
			
		if not element:
			return {'success': False, 'error': 'Could not find input field'}
			
		# Type text
		type_result = await self.action_executor.execute_action(
			self.page,
			ActionType.TYPE,
			target=element,
			parameters={'text': text}
		)
		
		return {
			'success': type_result.success,
			'typed': text if type_result.success else None,
			'error': type_result.error
		}
		
	async def _handle_extract(self, intent: Dict[str, Any]) -> Dict[str, Any]:
		"""Handle data extraction"""
		# Get page text content
		page_text = await self.page.text_content('body')
		
		# Use LLM to extract specific information
		prompt = f"""From the page content below, extract: {intent['target']}

Page content:
{page_text[:2000] if page_text else 'No text content found'}

Return the extracted information clearly."""

		response = await self.llm.ainvoke(prompt)
		
		return {
			'success': True,
			'extracted': response.content,
			'target': intent['target']
		}
		
	async def _handle_complex_task(self, task: str, intent: Dict[str, Any]) -> Dict[str, Any]:
		"""Handle complex tasks using LLM guidance"""
		
		# Take screenshot
		screenshot = await self.page.screenshot()
		screenshot_b64 = base64.b64encode(screenshot).decode()
		
		# Get current page state
		page_state = await self._get_page_state()
		
		prompt = f"""I need to: {task}

Current page URL: {self.page.url}
Page title: {await self.page.title()}

Based on the screenshot, tell me the exact steps to accomplish this task.
Return a JSON array of actions like:
[
  {{"action": "click", "target": "description of element to click"}},
  {{"action": "type", "target": "description of input", "text": "what to type"}},
  {{"action": "wait", "duration": 1000}}
]

Be specific about element descriptions."""

		from langchain_core.messages import HumanMessage
		
		response = await self.llm.ainvoke([
			HumanMessage(content=[
				{"type": "text", "text": prompt},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
			])
		])
		
		# Parse response
		import json
		import re
		
		try:
			# Extract JSON from response
			json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
			if json_match:
				actions = json.loads(json_match.group())
				
				# Execute actions
				results = []
				for action in actions:
					if action['action'] == 'click':
						result = await self._handle_click({'target': action['target']})
					elif action['action'] == 'type':
						result = await self._handle_type({
							'description': f"type '{action['text']}' in {action['target']}"
						})
					elif action['action'] == 'wait':
						await asyncio.sleep(action.get('duration', 1000) / 1000)
						result = {'success': True}
					else:
						result = {'success': False, 'error': f"Unknown action: {action['action']}"}
						
					results.append(result)
					
					if not result.get('success'):
						break
						
				return {
					'success': all(r.get('success') for r in results),
					'actions_executed': len([r for r in results if r.get('success')]),
					'total_actions': len(actions),
					'results': results
				}
		except Exception as e:
			logger.error(f"Failed to parse LLM response: {e}")
			
		return {'success': False, 'error': 'Could not parse LLM response'}
		
	async def _find_element_with_vision(self, description: str) -> Optional[Any]:
		"""Find element using vision as fallback"""
		# For now, just return None - would implement vision later
		logger.info(f"Vision-based finding not implemented yet for: {description}")
		return None
		
	async def _submit_search(self) -> Dict[str, Any]:
		"""Submit search with multiple strategies"""
		
		# Strategy 1: Press Enter
		try:
			await self.page.keyboard.press('Enter')
			await self._wait_for_navigation_or_change()
			return {'success': True, 'method': 'enter_key'}
		except:
			pass
			
		# Strategy 2: Click search button
		search_button = await self.element_finder.find_element(
			self.page,
			"search button or submit button"
		)
		
		if search_button:
			click_result = await self.action_executor.execute_action(
				self.page,
				ActionType.CLICK,
				target=search_button
			)
			
			if click_result.success:
				await self._wait_for_navigation_or_change()
				return {'success': True, 'method': 'search_button'}
				
		# Strategy 3: Submit form
		try:
			await self.page.evaluate("""() => {
				const forms = document.querySelectorAll('form');
				for (const form of forms) {
					const hasSearch = form.querySelector('input[type="search"], input[name*="search"], input[name="q"]');
					if (hasSearch) {
						form.submit();
						return true;
					}
				}
				return false;
			}""")
			
			await self._wait_for_navigation_or_change()
			return {'success': True, 'method': 'form_submit'}
		except:
			pass
			
		return {'success': False, 'error': 'Could not submit search'}
		
	async def _wait_for_page_ready(self, timeout: int = 10000):
		"""Wait for page to be fully ready"""
		try:
			# Wait for basic load
			await self.page.wait_for_load_state('domcontentloaded', timeout=timeout)
			
			# Wait for network to be idle
			await self.page.wait_for_load_state('networkidle', timeout=timeout)
			
			# Additional wait for dynamic content
			await self.page.wait_for_timeout(500)
			
		except Exception as e:
			logger.debug(f"Page ready wait interrupted: {e}")
			
	async def _wait_for_navigation_or_change(self, timeout: int = 5000):
		"""Wait for navigation or significant page change"""
		try:
			# Try to wait for navigation
			await self.page.wait_for_navigation(timeout=timeout)
		except:
			# If no navigation, wait for DOM changes
			try:
				await self.page.wait_for_function(
					"""() => {
						return document.readyState === 'complete' && 
							   performance.timing.loadEventEnd > 0;
					}""",
					timeout=timeout
				)
			except:
				# Just wait a bit
				await asyncio.sleep(1)
				
	async def _wait_for_search_results(self, timeout: int = 5000):
		"""Wait for search results to appear"""
		try:
			# Wait for common result indicators
			await self.page.wait_for_selector(
				'a[href]:not([href="#"]):not([href^="javascript:"]):visible',
				timeout=timeout
			)
		except:
			# Just wait a bit
			await asyncio.sleep(2)
			
	async def _wait_for_stability(self, timeout: int = 3000):
		"""Wait for page to stabilize after action"""
		try:
			# Wait for any animations
			await self.page.wait_for_timeout(300)
			
			# Wait for network to settle
			await self.page.wait_for_load_state('networkidle', timeout=timeout)
			
		except:
			pass
			
	async def _get_page_state(self) -> Dict[str, Any]:
		"""Get current page state"""
		return {
			'url': self.page.url,
			'title': await self.page.title(),
			'ready_state': await self.page.evaluate('() => document.readyState'),
			'has_forms': await self.page.evaluate('() => document.forms.length > 0'),
			'has_inputs': await self.page.evaluate('() => document.querySelectorAll("input, textarea").length')
		}
		
	def _on_page_load(self):
		"""Handle page load event"""
		logger.debug(f"Page loaded: {self.page.url}")
		self.current_url = self.page.url
		
	def _on_dom_ready(self):
		"""Handle DOM ready event"""
		logger.debug("DOM ready")