"""Incremental DOM processing for efficient element detection"""

import asyncio
from typing import Any, Optional, Set
from datetime import datetime, timedelta
import json
from playwright.async_api import Page, ElementHandle

from browser_use.perception.base import (
	IPerceptionSystem, PerceptionElement, PerceptionResult,
	PerceptionQuery, PerceptionCapability, BoundingBox
)
from browser_use.utils import time_execution_async


class IncrementalDOMProcessor(IPerceptionSystem):
	"""Efficient DOM processing with incremental updates"""
	
	def __init__(self):
		self.config = {}
		self._initialized = False
		self._dom_state: dict[str, Any] = {}
		self._element_cache: dict[str, PerceptionElement] = {}
		self._mutation_tracking: dict[str, Set[str]] = {}
		self._last_full_scan: Optional[datetime] = None
		self._capabilities = PerceptionCapability(
			name="IncrementalDOMProcessor",
			supported_queries=[
				"dom_traversal",
				"element_by_selector",
				"element_by_text",
				"form_detection",
				"interactive_elements",
				"semantic_structure"
			],
			strengths=[
				"Very fast for repeated queries",
				"Efficient incremental updates",
				"Precise element selection",
				"Low resource usage",
				"Handles dynamic content well"
			],
			limitations=[
				"Cannot see visual-only elements",
				"Misses canvas/WebGL content",
				"Requires JavaScript injection"
			],
			performance_ms=50  # Very fast after initial scan
		)
	
	async def initialize(self, config: dict[str, Any]) -> None:
		"""Initialize the DOM processor"""
		self.config = config
		self._initialized = True
		
		# Configuration
		self.cache_ttl = config.get("cache_ttl", 5.0)  # seconds
		self.mutation_batch_size = config.get("mutation_batch_size", 100)
		self.full_scan_interval = config.get("full_scan_interval", 60.0)  # seconds
	
	@time_execution_async("dom_analyze_page")
	async def analyze_page(self, page_data: dict[str, Any]) -> PerceptionResult:
		"""Analyze page DOM and return detected elements"""
		if not self._initialized:
			raise RuntimeError("IncrementalDOMProcessor not initialized")
		
		page = page_data.get("page")
		if not page:
			return PerceptionResult(errors=["No page object provided"])
		
		try:
			# Check if we need a full scan
			need_full_scan = (
				not self._last_full_scan or
				(datetime.now() - self._last_full_scan).total_seconds() > self.full_scan_interval
			)
			
			if need_full_scan:
				elements = await self._full_dom_scan(page)
				self._last_full_scan = datetime.now()
			else:
				# Incremental update
				elements = await self._incremental_update(page)
			
			# Build page context
			page_context = {
				"total_elements": len(elements),
				"interactive_elements": sum(1 for e in elements if e.is_interactive),
				"form_elements": sum(1 for e in elements if e.type in ["input", "select", "textarea"]),
				"last_full_scan": self._last_full_scan.isoformat() if self._last_full_scan else None
			}
			
			return PerceptionResult(
				elements=elements,
				page_context=page_context,
				processing_time_ms=50 if not need_full_scan else 200
			)
			
		except Exception as e:
			return PerceptionResult(errors=[f"DOM analysis failed: {str(e)}"])
	
	async def find_element(self, query: PerceptionQuery) -> Optional[PerceptionElement]:
		"""Find a single element matching the query"""
		elements = await self.find_elements(query)
		return elements[0] if elements else None
	
	@time_execution_async("dom_find_elements")
	async def find_elements(self, query: PerceptionQuery) -> list[PerceptionElement]:
		"""Find elements matching the query"""
		page = query.context.get("page")
		if not page:
			return []
		
		try:
			# Try cache first
			cache_key = self._get_cache_key(query)
			if cache_key in self._element_cache:
				cached = self._element_cache[cache_key]
				if self._is_cache_valid(cached):
					return [cached]
			
			# Use appropriate search strategy
			if "selector" in query.attributes:
				elements = await self._find_by_selector(page, query.attributes["selector"])
			elif "text" in query.attributes:
				elements = await self._find_by_text(page, query.attributes["text"])
			elif query.element_type:
				elements = await self._find_by_type(page, query.element_type)
			else:
				elements = await self._find_by_description(page, query.description)
			
			# Cache results
			for element in elements[:5]:  # Cache top 5 results
				self._element_cache[self._get_cache_key_for_element(element)] = element
			
			return elements
			
		except Exception:
			return []
	
	def get_capabilities(self) -> PerceptionCapability:
		"""Get capabilities of the DOM processor"""
		return self._capabilities
	
	async def cleanup(self) -> None:
		"""Clean up resources"""
		self._initialized = False
		self._element_cache.clear()
		self._dom_state.clear()
		self._mutation_tracking.clear()
	
	# Setup methods
	
	async def setup_mutation_observer(self, page: Page) -> None:
		"""Set up mutation observer for incremental updates"""
		await page.evaluate("""
			(() => {
				if (window.__domProcessor) return;
				
				window.__domProcessor = {
					mutations: [],
					elementMap: new WeakMap(),
					nextId: 1,
					
					// Track element IDs
					getElementId: function(element) {
						if (!this.elementMap.has(element)) {
							this.elementMap.set(element, this.nextId++);
						}
						return this.elementMap.get(element);
					},
					
					// Build selector for element
					getSelector: function(element) {
						const path = [];
						while (element && element.nodeType === Node.ELEMENT_NODE) {
							let selector = element.nodeName.toLowerCase();
							if (element.id) {
								selector += '#' + element.id;
								path.unshift(selector);
								break;
							}
							if (element.className) {
								selector += '.' + element.className.split(' ').join('.');
							}
							path.unshift(selector);
							element = element.parentElement;
						}
						return path.join(' > ');
					},
					
					// Process mutations
					processMutation: function(mutation) {
						const record = {
							type: mutation.type,
							timestamp: Date.now(),
							target: {
								id: this.getElementId(mutation.target),
								selector: this.getSelector(mutation.target),
								tag: mutation.target.nodeName
							}
						};
						
						if (mutation.type === 'childList') {
							record.added = Array.from(mutation.addedNodes)
								.filter(n => n.nodeType === Node.ELEMENT_NODE)
								.map(n => ({
									id: this.getElementId(n),
									selector: this.getSelector(n),
									tag: n.nodeName
								}));
							record.removed = Array.from(mutation.removedNodes)
								.filter(n => n.nodeType === Node.ELEMENT_NODE)
								.map(n => ({
									tag: n.nodeName
								}));
						} else if (mutation.type === 'attributes') {
							record.attribute = mutation.attributeName;
							record.oldValue = mutation.oldValue;
							record.newValue = mutation.target.getAttribute(mutation.attributeName);
						}
						
						this.mutations.push(record);
					},
					
					// Start observing
					observer: new MutationObserver((mutations) => {
						mutations.forEach(m => this.processMutation(m));
					})
				};
				
				// Start observing
				window.__domProcessor.observer.observe(document.body, {
					childList: true,
					attributes: true,
					subtree: true,
					attributeOldValue: true
				});
			})();
		""")
	
	# Private methods
	
	async def _full_dom_scan(self, page: Page) -> list[PerceptionElement]:
		"""Perform a full DOM scan"""
		# First, set up mutation observer if not already done
		await self.setup_mutation_observer(page)
		
		# Get all interactive elements
		elements_data = await page.evaluate("""
			(() => {
				const interactiveSelectors = [
					'a[href]', 'button', 'input', 'select', 'textarea',
					'[role="button"]', '[role="link"]', '[role="checkbox"]',
					'[role="radio"]', '[role="textbox"]', '[role="combobox"]',
					'[onclick]', '[tabindex]'
				];
				
				const elements = [];
				const seen = new Set();
				
				// Get all interactive elements
				for (const selector of interactiveSelectors) {
					const matches = document.querySelectorAll(selector);
					for (const el of matches) {
						if (seen.has(el)) continue;
						seen.add(el);
						
						const rect = el.getBoundingClientRect();
						const style = window.getComputedStyle(el);
						
						// Skip invisible elements
						if (rect.width === 0 || rect.height === 0 ||
							style.display === 'none' || style.visibility === 'hidden' ||
							style.opacity === '0') {
							continue;
						}
						
						elements.push({
							id: window.__domProcessor.getElementId(el),
							type: el.tagName.toLowerCase(),
							selector: window.__domProcessor.getSelector(el),
							text: el.textContent?.trim().substring(0, 100),
							bbox: {
								x: rect.x,
								y: rect.y,
								width: rect.width,
								height: rect.height
							},
							attributes: {
								href: el.href,
								value: el.value,
								placeholder: el.placeholder,
								name: el.name,
								id: el.id,
								class: el.className,
								role: el.getAttribute('role'),
								'aria-label': el.getAttribute('aria-label')
							},
							isDisabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
							isFocused: el === document.activeElement
						});
					}
				}
				
				return elements;
			})();
		""")
		
		# Convert to PerceptionElements
		elements = []
		for data in elements_data:
			element = PerceptionElement(
				type=data["type"],
				selector=data["selector"],
				text=data.get("text", ""),
				bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
				attributes={k: v for k, v in data["attributes"].items() if v is not None},
				is_interactive=True,
				is_disabled=data.get("isDisabled", False),
				is_focused=data.get("isFocused", False)
			)
			elements.append(element)
			
			# Update cache
			self._element_cache[data["id"]] = element
		
		# Clear mutations after full scan
		await page.evaluate("window.__domProcessor.mutations = []")
		
		return elements
	
	async def _incremental_update(self, page: Page) -> list[PerceptionElement]:
		"""Perform incremental DOM update based on mutations"""
		# Get mutations since last check
		mutations = await page.evaluate("window.__domProcessor.mutations.splice(0)")
		
		if not mutations:
			# No changes, return cached elements
			return list(self._element_cache.values())
		
		# Process mutations
		invalidated_selectors = set()
		new_elements = []
		
		for mutation in mutations:
			if mutation["type"] == "childList":
				# Invalidate parent and added elements
				invalidated_selectors.add(mutation["target"]["selector"])
				
				# Check added nodes
				for added in mutation.get("added", []):
					# We'll need to scan these new elements
					new_elements.append(added["selector"])
			
			elif mutation["type"] == "attributes":
				# Invalidate the changed element
				invalidated_selectors.add(mutation["target"]["selector"])
		
		# Remove invalidated elements from cache
		self._element_cache = {
			k: v for k, v in self._element_cache.items()
			if v.selector not in invalidated_selectors
		}
		
		# Scan new/changed elements
		if new_elements or invalidated_selectors:
			selectors_to_scan = list(new_elements) + list(invalidated_selectors)
			
			# Scan specific elements
			new_elements_data = await page.evaluate("""
				(selectors) => {
					const elements = [];
					
					for (const selector of selectors) {
						try {
							const el = document.querySelector(selector);
							if (!el) continue;
							
							const rect = el.getBoundingClientRect();
							const style = window.getComputedStyle(el);
							
							// Skip invisible elements
							if (rect.width === 0 || rect.height === 0 ||
								style.display === 'none' || style.visibility === 'hidden') {
								continue;
							}
							
							elements.push({
								id: window.__domProcessor.getElementId(el),
								type: el.tagName.toLowerCase(),
								selector: selector,
								text: el.textContent?.trim().substring(0, 100),
								bbox: {
									x: rect.x,
									y: rect.y,
									width: rect.width,
									height: rect.height
								},
								attributes: {
									href: el.href,
									value: el.value,
									placeholder: el.placeholder,
									name: el.name,
									id: el.id,
									class: el.className,
									role: el.getAttribute('role')
								},
								isDisabled: el.disabled,
								isFocused: el === document.activeElement
							});
						} catch (e) {
							// Invalid selector, skip
						}
					}
					
					return elements;
				}
			""", selectors_to_scan[:50])  # Limit to 50 selectors per batch
			
			# Add new elements to cache
			for data in new_elements_data:
				element = PerceptionElement(
					type=data["type"],
					selector=data["selector"],
					text=data.get("text", ""),
					bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
					attributes={k: v for k, v in data["attributes"].items() if v is not None},
					is_interactive=True,
					is_disabled=data.get("isDisabled", False),
					is_focused=data.get("isFocused", False)
				)
				self._element_cache[data["id"]] = element
		
		return list(self._element_cache.values())
	
	async def _find_by_selector(self, page: Page, selector: str) -> list[PerceptionElement]:
		"""Find elements by CSS selector"""
		elements_data = await page.evaluate("""
			(selector) => {
				const elements = [];
				try {
					const matches = document.querySelectorAll(selector);
					for (const el of matches) {
						const rect = el.getBoundingClientRect();
						elements.push({
							type: el.tagName.toLowerCase(),
							selector: window.__domProcessor.getSelector(el),
							text: el.textContent?.trim().substring(0, 100),
							bbox: {
								x: rect.x,
								y: rect.y,
								width: rect.width,
								height: rect.height
							}
						});
					}
				} catch (e) {
					// Invalid selector
				}
				return elements;
			}
		""", selector)
		
		return [
			PerceptionElement(
				type=data["type"],
				selector=data["selector"],
				text=data.get("text", ""),
				bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
				is_interactive=True
			)
			for data in elements_data
		]
	
	async def _find_by_text(self, page: Page, text: str) -> list[PerceptionElement]:
		"""Find elements by text content"""
		elements_data = await page.evaluate("""
			(searchText) => {
				const elements = [];
				const walker = document.createTreeWalker(
					document.body,
					NodeFilter.SHOW_ELEMENT,
					null,
					false
				);
				
				let node;
				while (node = walker.nextNode()) {
					if (node.textContent && node.textContent.includes(searchText)) {
						const rect = node.getBoundingClientRect();
						if (rect.width > 0 && rect.height > 0) {
							elements.push({
								type: node.tagName.toLowerCase(),
								selector: window.__domProcessor.getSelector(node),
								text: node.textContent.trim().substring(0, 100),
								bbox: {
									x: rect.x,
									y: rect.y,
									width: rect.width,
									height: rect.height
								}
							});
						}
					}
				}
				
				return elements;
			}
		""", text)
		
		return [
			PerceptionElement(
				type=data["type"],
				selector=data["selector"],
				text=data.get("text", ""),
				bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
				is_interactive=True
			)
			for data in elements_data
		]
	
	async def _find_by_type(self, page: Page, element_type: str) -> list[PerceptionElement]:
		"""Find elements by type"""
		return await self._find_by_selector(page, element_type)
	
	async def _find_by_description(self, page: Page, description: str) -> list[PerceptionElement]:
		"""Find elements by description - uses heuristics"""
		# This is a simplified implementation
		# In reality, this would use more sophisticated matching
		words = description.lower().split()
		
		# Try to find by text content first
		for word in words:
			elements = await self._find_by_text(page, word)
			if elements:
				return elements
		
		# Try common element types
		if "button" in description.lower():
			return await self._find_by_selector(page, "button, [role='button']")
		elif "link" in description.lower():
			return await self._find_by_selector(page, "a[href]")
		elif "input" in description.lower() or "field" in description.lower():
			return await self._find_by_selector(page, "input, textarea")
		
		return []
	
	def _get_cache_key(self, query: PerceptionQuery) -> str:
		"""Generate cache key for a query"""
		return f"{query.description}:{query.element_type}:{json.dumps(query.attributes, sort_keys=True)}"
	
	def _get_cache_key_for_element(self, element: PerceptionElement) -> str:
		"""Generate cache key for an element"""
		return f"{element.selector}:{element.type}"
	
	def _is_cache_valid(self, element: PerceptionElement) -> bool:
		"""Check if cached element is still valid"""
		age = (datetime.now() - element.timestamp).total_seconds()
		return age < self.cache_ttl