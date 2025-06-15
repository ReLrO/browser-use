"""Truly robust element finding that works universally"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable
from playwright.async_api import Page, ElementHandle, Locator
import base64

logger = logging.getLogger(__name__)


class RobustElementFinder:
	"""Element finder that actually works on any website"""
	
	def __init__(self, llm=None):
		self.llm = llm
		# Strategy chain - try each until one works
		self.strategies: List[Callable] = [
			self._find_by_aria_label,
			self._find_by_placeholder,
			self._find_by_visible_text,
			self._find_by_partial_text,
			self._find_by_role,
			self._find_by_type,
			self._find_by_position,
			self._find_by_visual_analysis,
			self._find_by_heuristics,
			self._find_by_llm_guidance
		]
	
	async def find_element(
		self,
		page: Page,
		description: str,
		element_type: Optional[str] = None,
		timeout: int = 30000
	) -> Optional[ElementHandle]:
		"""Find element with multiple robust strategies"""
		
		logger.info(f"Finding element: {description}")
		
		# Parse description for hints
		context = self._parse_description(description)
		context['element_type'] = element_type
		context['page'] = page
		
		# Try each strategy with timeout
		start_time = asyncio.get_event_loop().time()
		
		for strategy in self.strategies:
			if (asyncio.get_event_loop().time() - start_time) * 1000 > timeout:
				break
				
			try:
				logger.debug(f"Trying strategy: {strategy.__name__}")
				element = await strategy(context)
				
				if element:
					# Verify element is actually interactive
					is_valid = await self._verify_element(element, context)
					if is_valid:
						logger.info(f"Found element with {strategy.__name__}")
						return element
					else:
						logger.debug(f"Element from {strategy.__name__} failed verification")
						
			except Exception as e:
				logger.debug(f"Strategy {strategy.__name__} failed: {e}")
				continue
		
		logger.error(f"Could not find element: {description}")
		return None
	
	def _parse_description(self, description: str) -> Dict[str, Any]:
		"""Parse description for context clues"""
		desc_lower = description.lower()
		
		context = {
			'description': description,
			'desc_lower': desc_lower,
			'keywords': []
		}
		
		# Extract common patterns
		if 'search' in desc_lower:
			context['keywords'].extend(['search', 'query', 'find'])
			context['likely_types'] = ['input', 'textarea']
			context['likely_roles'] = ['searchbox', 'textbox']
			
		if 'button' in desc_lower or 'click' in desc_lower:
			context['keywords'].extend(['button', 'submit', 'click'])
			context['likely_types'] = ['button', 'a']
			context['likely_roles'] = ['button', 'link']
			
		if 'first' in desc_lower:
			context['position'] = 'first'
			
		if 'link' in desc_lower or 'result' in desc_lower:
			context['keywords'].extend(['link', 'result'])
			context['likely_types'] = ['a']
			context['likely_roles'] = ['link']
			
		# Extract quoted text
		import re
		quoted = re.findall(r'"([^"]+)"', description)
		if quoted:
			context['exact_text'] = quoted[0]
			
		return context
	
	async def _find_by_aria_label(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by aria-label"""
		page = context['page']
		
		for keyword in context.get('keywords', []):
			try:
				# Try exact match
				element = await page.locator(f'[aria-label*="{keyword}" i]').first.element_handle(timeout=1000)
				if element and await element.is_visible():
					return element
			except:
				pass
				
		return None
	
	async def _find_by_placeholder(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by placeholder text"""
		page = context['page']
		
		if 'search' in context.get('keywords', []):
			try:
				element = await page.locator('[placeholder*="search" i]').first.element_handle(timeout=1000)
				if element and await element.is_visible():
					return element
			except:
				pass
				
		return None
	
	async def _find_by_visible_text(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by exact visible text"""
		page = context['page']
		
		if 'exact_text' in context:
			try:
				element = await page.get_by_text(context['exact_text'], exact=True).first.element_handle(timeout=1000)
				if element and await element.is_visible():
					return element
			except:
				pass
				
		return None
	
	async def _find_by_partial_text(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by partial text match"""
		page = context['page']
		
		for keyword in context.get('keywords', []):
			try:
				element = await page.get_by_text(keyword).first.element_handle(timeout=1000)
				if element and await element.is_visible():
					return element
			except:
				pass
				
		return None
	
	async def _find_by_role(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by ARIA role"""
		page = context['page']
		
		for role in context.get('likely_roles', []):
			try:
				elements = await page.get_by_role(role).all()
				
				# Filter visible elements
				for element in elements:
					if await element.is_visible():
						# For search, prefer empty inputs
						if 'search' in context.get('keywords', []):
							value = await element.get_attribute('value')
							if not value:
								return await element.element_handle()
						else:
							return await element.element_handle()
			except:
				pass
				
		return None
	
	async def _find_by_type(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by element type"""
		page = context['page']
		
		for elem_type in context.get('likely_types', []):
			try:
				if elem_type == 'input':
					# For inputs, try specific types first
					for input_type in ['search', 'text', 'email']:
						element = await page.locator(f'input[type="{input_type}"]:visible').first.element_handle(timeout=1000)
						if element:
							# Check if it's empty for search
							if 'search' in context.get('keywords', []):
								value = await element.get_attribute('value')
								if not value:
									return element
							else:
								return element
								
				else:
					element = await page.locator(f'{elem_type}:visible').first.element_handle(timeout=1000)
					if element:
						return element
			except:
				pass
				
		return None
	
	async def _find_by_position(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by position (first, last, etc)"""
		page = context['page']
		position = context.get('position')
		
		if not position:
			return None
			
		# For "first result" type searches
		if position == 'first' and 'result' in context.get('keywords', []):
			try:
				# Get all links
				all_links = await page.locator('a:visible').all()
				
				# Filter out navigation/header links
				for link in all_links:
					text = await link.text_content()
					if not text:
						continue
						
					text = text.strip()
					href = await link.get_attribute('href')
					
					# Skip navigation
					skip_words = ['sign in', 'log in', 'about', 'privacy', 'terms', 'help', 'home']
					if any(word in text.lower() for word in skip_words):
						continue
						
					# Skip anchors and javascript
					if href and href not in ['#', 'javascript:void(0)']:
						# Check position - avoid header
						box = await link.bounding_box()
						if box and box['y'] > 150:
							# Found a good candidate
							if len(text) > 15:  # Substantial text
								return await link.element_handle()
			except:
				pass
				
		return None
	
	async def _find_by_visual_analysis(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find by visual analysis of the page"""
		page = context['page']
		
		# Take screenshot and analyze visible elements
		try:
			# Get all potentially interactive elements
			elements = await page.evaluate("""() => {
				const selectors = [
					'input:not([type="hidden"])',
					'textarea',
					'button',
					'a[href]',
					'[role="button"]',
					'[role="link"]',
					'[role="searchbox"]',
					'[role="textbox"]',
					'[contenteditable="true"]',
					'select'
				];
				
				const results = [];
				const seen = new Set();
				
				for (const selector of selectors) {
					document.querySelectorAll(selector).forEach(el => {
						if (seen.has(el)) return;
						seen.add(el);
						
						const rect = el.getBoundingClientRect();
						const style = window.getComputedStyle(el);
						
						if (rect.width > 0 && rect.height > 0 && 
							style.visibility !== 'hidden' &&
							style.display !== 'none' &&
							rect.top >= 0 && rect.top < window.innerHeight) {
							
							results.push({
								selector: el.tagName.toLowerCase() + 
									(el.id ? '#' + el.id : '') +
									(el.className ? '.' + el.className.split(' ').join('.') : ''),
								tag: el.tagName.toLowerCase(),
								text: el.textContent?.trim().substring(0, 100),
								placeholder: el.placeholder,
								type: el.type,
								role: el.getAttribute('role'),
								rect: {
									x: rect.x,
									y: rect.y,
									width: rect.width,
									height: rect.height
								},
								isInViewport: rect.top >= 0 && rect.bottom <= window.innerHeight
							});
						}
					});
				}
				
				return results;
			}""")
			
			# Score elements based on visual prominence and context
			best_score = 0
			best_element = None
			
			for elem_data in elements:
				score = 0
				
				# Type matching
				if elem_data['tag'] in context.get('likely_types', []):
					score += 2
					
				# Role matching
				if elem_data.get('role') in context.get('likely_roles', []):
					score += 2
					
				# Text matching
				if elem_data.get('text'):
					text_lower = elem_data['text'].lower()
					for keyword in context.get('keywords', []):
						if keyword in text_lower:
							score += 1
							
				# Placeholder matching
				if elem_data.get('placeholder'):
					placeholder_lower = elem_data['placeholder'].lower()
					for keyword in context.get('keywords', []):
						if keyword in placeholder_lower:
							score += 2
							
				# Visual prominence
				rect = elem_data['rect']
				if rect['width'] > 200 and rect['height'] > 30:
					score += 1
					
				# In viewport bonus
				if elem_data.get('isInViewport'):
					score += 1
					
				if score > best_score:
					best_score = score
					best_element = elem_data
					
			if best_element and best_score > 2:
				# Try to get the element
				try:
					selector = best_element['selector']
					element = await page.locator(selector).first.element_handle(timeout=1000)
					if element and await element.is_visible():
						return element
				except:
					pass
					
		except Exception as e:
			logger.debug(f"Visual analysis failed: {e}")
			
		return None
	
	async def _find_by_heuristics(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Find using common patterns and heuristics"""
		page = context['page']
		
		# Common search box patterns
		if 'search' in context.get('keywords', []):
			search_selectors = [
				'input[type="search"]',
				'input[name*="search" i]',
				'input[name*="query" i]',
				'input[name="q"]',
				'#search',
				'.search-input',
				'.search-box',
				'[class*="search-field"]',
				'[class*="search-input"]',
				'form input[type="text"]:first-of-type'
			]
			
			for selector in search_selectors:
				try:
					element = await page.locator(selector + ':visible').first.element_handle(timeout=500)
					if element:
						return element
				except:
					pass
					
		# Common button patterns
		if 'button' in context.get('keywords', []) or 'submit' in context.get('keywords', []):
			button_selectors = [
				'button[type="submit"]',
				'input[type="submit"]',
				'button:has-text("Search")',
				'button:has-text("Submit")',
				'[class*="submit-button"]',
				'[class*="search-button"]'
			]
			
			for selector in button_selectors:
				try:
					element = await page.locator(selector + ':visible').first.element_handle(timeout=500)
					if element:
						return element
				except:
					pass
					
		return None
	
	async def _find_by_llm_guidance(self, context: Dict[str, Any]) -> Optional[ElementHandle]:
		"""Use LLM to find element when all else fails"""
		if not self.llm:
			return None
			
		page = context['page']
		
		try:
			# Take screenshot
			screenshot = await page.screenshot()
			screenshot_b64 = base64.b64encode(screenshot).decode()
			
			# Get page structure
			page_structure = await page.evaluate("""() => {
				const elements = [];
				document.querySelectorAll('*').forEach((el, index) => {
					const rect = el.getBoundingClientRect();
					if (rect.width > 0 && rect.height > 0) {
						elements.push({
							index: index,
							tag: el.tagName.toLowerCase(),
							text: el.textContent?.trim().substring(0, 50),
							id: el.id,
							className: el.className,
							rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
						});
					}
				});
				return elements;
			}""")
			
			prompt = f"""I need to find an element on this page: "{context['description']}"

Look at the screenshot and the page structure below. Return ONLY the index number of the element that best matches.

Page structure (showing index, tag, text, position):
{page_structure[:20]}  # First 20 elements

Return ONLY a number (the index of the element)."""

			from langchain_core.messages import HumanMessage
			
			response = await self.llm.ainvoke([
				HumanMessage(content=[
					{"type": "text", "text": prompt},
					{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
				])
			])
			
			# Extract index
			import re
			match = re.search(r'\d+', response.content)
			if match:
				index = int(match.group())
				
				# Get element by index
				element = await page.evaluate(f"""() => {{
					const el = document.querySelectorAll('*')[{index}];
					if (el) {{
						el.setAttribute('data-llm-selected', 'true');
						return true;
					}}
					return false;
				}}""")
				
				if element:
					return await page.locator('[data-llm-selected="true"]').element_handle()
					
		except Exception as e:
			logger.debug(f"LLM guidance failed: {e}")
			
		return None
	
	async def _verify_element(self, element: ElementHandle, context: Dict[str, Any]) -> bool:
		"""Verify element is valid for the intended action"""
		try:
			# Check visibility
			if not await element.is_visible():
				return False
				
			# Check if enabled
			if not await element.is_enabled():
				return False
				
			# For search inputs, prefer empty ones
			if 'search' in context.get('keywords', []):
				tag = await element.evaluate('el => el.tagName.toLowerCase()')
				if tag in ['input', 'textarea']:
					value = await element.get_attribute('value')
					# Prefer empty inputs for search
					if value and len(value) > 0:
						return False
						
			# Check size - too small elements are likely hidden
			box = await element.bounding_box()
			if box:
				if box['width'] < 10 or box['height'] < 10:
					return False
					
			return True
			
		except Exception as e:
			logger.debug(f"Element verification failed: {e}")
			return False