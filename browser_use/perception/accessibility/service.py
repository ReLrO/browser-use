"""Accessibility tree processing for semantic understanding"""

import asyncio
from typing import Any, Optional, Dict, List
from datetime import datetime
from playwright.async_api import Page

from browser_use.perception.base import (
	IPerceptionSystem, PerceptionElement, PerceptionResult,
	PerceptionQuery, PerceptionCapability, BoundingBox
)
from browser_use.utils import time_execution_async


class AccessibilityProcessor(IPerceptionSystem):
	"""Leverages browser's accessibility tree for semantic understanding"""
	
	def __init__(self):
		self.config = {}
		self._initialized = False
		self._role_mappings = self._build_role_mappings()
		self._semantic_cache: Dict[str, Any] = {}
		self._capabilities = PerceptionCapability(
			name="AccessibilityProcessor",
			supported_queries=[
				"semantic_structure",
				"aria_navigation",
				"form_structure",
				"landmark_detection",
				"heading_hierarchy",
				"label_association"
			],
			strengths=[
				"Understanding page semantics",
				"Finding elements by role",
				"Navigating complex forms",
				"Screen reader compatibility",
				"Accessible name computation"
			],
			limitations=[
				"Depends on proper ARIA implementation",
				"May miss visual-only cues",
				"Limited by developer's accessibility markup"
			],
			performance_ms=100  # Fast but slower than direct DOM
		)
	
	async def initialize(self, config: dict[str, Any]) -> None:
		"""Initialize the accessibility processor"""
		self.config = config
		self._initialized = True
	
	@time_execution_async("a11y_analyze_page")
	async def analyze_page(self, page_data: dict[str, Any]) -> PerceptionResult:
		"""Analyze page accessibility tree"""
		if not self._initialized:
			raise RuntimeError("AccessibilityProcessor not initialized")
		
		page = page_data.get("page")
		if not page:
			return PerceptionResult(errors=["No page object provided"])
		
		try:
			# Get accessibility tree
			a11y_tree = await page.accessibility.snapshot()
			
			if not a11y_tree:
				return PerceptionResult(errors=["Could not get accessibility tree"])
			
			# Process tree into elements
			elements = []
			self._process_node(a11y_tree, elements)
			
			# Extract semantic structure
			semantic_structure = self._extract_semantic_structure(a11y_tree)
			
			# Build page context
			page_context = {
				"landmarks": semantic_structure["landmarks"],
				"heading_structure": semantic_structure["headings"],
				"form_count": len(semantic_structure["forms"]),
				"navigation_count": len(semantic_structure["navigations"]),
				"has_main_content": "main" in semantic_structure["landmarks"]
			}
			
			return PerceptionResult(
				elements=elements,
				page_context=page_context,
				processing_time_ms=100
			)
			
		except Exception as e:
			return PerceptionResult(errors=[f"Accessibility analysis failed: {str(e)}"])
	
	async def find_element(self, query: PerceptionQuery) -> Optional[PerceptionElement]:
		"""Find element using accessibility properties"""
		elements = await self.find_elements(query)
		return elements[0] if elements else None
	
	@time_execution_async("a11y_find_elements")
	async def find_elements(self, query: PerceptionQuery) -> list[PerceptionElement]:
		"""Find elements using accessibility tree"""
		page = query.context.get("page")
		if not page:
			return []
		
		try:
			# Get accessibility tree
			a11y_tree = await page.accessibility.snapshot()
			if not a11y_tree:
				return []
			
			# Search based on query type
			if "role" in query.attributes:
				return await self._find_by_role(page, query.attributes["role"])
			elif "label" in query.attributes:
				return await self._find_by_label(page, query.attributes["label"])
			elif query.description:
				return await self._find_by_semantic_description(page, query.description)
			
			return []
			
		except Exception:
			return []
	
	def get_capabilities(self) -> PerceptionCapability:
		"""Get capabilities"""
		return self._capabilities
	
	async def cleanup(self) -> None:
		"""Clean up resources"""
		self._initialized = False
		self._semantic_cache.clear()
	
	# Specialized accessibility methods
	
	async def get_form_structure(self, page: Page) -> dict[str, Any]:
		"""Extract complete form structure with labels and relationships"""
		form_data = await page.evaluate("""
			() => {
				const forms = [];
				document.querySelectorAll('form').forEach((form, formIndex) => {
					const formInfo = {
						index: formIndex,
						name: form.name || form.getAttribute('aria-label') || '',
						fields: []
					};
					
					// Find all form fields
					const fields = form.querySelectorAll('input, select, textarea');
					fields.forEach(field => {
						// Find associated label
						let label = '';
						if (field.id) {
							const labelEl = document.querySelector(`label[for="${field.id}"]`);
							if (labelEl) label = labelEl.textContent.trim();
						}
						if (!label && field.getAttribute('aria-label')) {
							label = field.getAttribute('aria-label');
						}
						if (!label && field.placeholder) {
							label = field.placeholder;
						}
						
						formInfo.fields.push({
							type: field.type || field.tagName.toLowerCase(),
							name: field.name,
							label: label,
							required: field.required || field.getAttribute('aria-required') === 'true',
							value: field.value,
							selector: field.id ? `#${field.id}` : null
						});
					});
					
					forms.push(formInfo);
				});
				
				return forms;
			}
		""")
		
		return {"forms": form_data}
	
	async def get_navigation_structure(self, page: Page) -> dict[str, Any]:
		"""Extract navigation structure"""
		nav_data = await page.evaluate("""
			() => {
				const navigations = [];
				
				// Find nav elements and elements with navigation role
				const navElements = document.querySelectorAll('nav, [role="navigation"]');
				navElements.forEach(nav => {
					const links = [];
					nav.querySelectorAll('a[href]').forEach(link => {
						links.push({
							text: link.textContent.trim(),
							href: link.href,
							isActive: link.getAttribute('aria-current') === 'page'
						});
					});
					
					navigations.push({
						label: nav.getAttribute('aria-label') || 'Navigation',
						links: links
					});
				});
				
				return navigations;
			}
		""")
		
		return {"navigations": nav_data}
	
	# Private methods
	
	def _build_role_mappings(self) -> dict[str, list[str]]:
		"""Build mappings of semantic roles to element types"""
		return {
			"button": ["button", "[role='button']", "input[type='submit']", "input[type='button']"],
			"link": ["a[href]", "[role='link']"],
			"textbox": ["input[type='text']", "textarea", "[role='textbox']"],
			"navigation": ["nav", "[role='navigation']"],
			"main": ["main", "[role='main']"],
			"form": ["form", "[role='form']"],
			"search": ["[role='search']", "form[role='search']"],
			"combobox": ["select", "[role='combobox']"],
			"checkbox": ["input[type='checkbox']", "[role='checkbox']"],
			"radio": ["input[type='radio']", "[role='radio']"]
		}
	
	def _process_node(self, node: dict, elements: list[PerceptionElement], parent_id: Optional[str] = None) -> None:
		"""Recursively process accessibility tree node"""
		if not node:
			return
		
		# Create element from node
		if node.get("role") and node.get("name"):
			element = PerceptionElement(
				type=node.get("role", "generic"),
				role=node.get("role"),
				label=node.get("name"),
				description=node.get("description", ""),
				attributes={
					"level": node.get("level"),
					"checked": node.get("checked"),
					"pressed": node.get("pressed"),
					"expanded": node.get("expanded"),
					"selected": node.get("selected"),
					"disabled": node.get("disabled"),
					"readonly": node.get("readonly"),
					"required": node.get("required"),
					"invalid": node.get("invalid"),
					"value": node.get("value")
				},
				is_interactive=self._is_interactive_role(node.get("role")),
				is_disabled=node.get("disabled", False),
				parent_id=parent_id
			)
			
			# Clean up None attributes
			element.attributes = {k: v for k, v in element.attributes.items() if v is not None}
			
			elements.append(element)
			parent_id = element.id
		
		# Process children
		for child in node.get("children", []):
			self._process_node(child, elements, parent_id)
	
	def _is_interactive_role(self, role: Optional[str]) -> bool:
		"""Check if a role indicates an interactive element"""
		if not role:
			return False
		
		interactive_roles = {
			"button", "link", "textbox", "combobox", "checkbox",
			"radio", "slider", "spinbutton", "searchbox", "switch",
			"tab", "menuitem", "option", "treeitem"
		}
		
		return role.lower() in interactive_roles
	
	def _extract_semantic_structure(self, tree: dict) -> dict[str, Any]:
		"""Extract semantic structure from accessibility tree"""
		structure = {
			"landmarks": {},
			"headings": [],
			"forms": [],
			"navigations": []
		}
		
		def traverse(node: dict, level: int = 0):
			if not node:
				return
			
			role = node.get("role", "").lower()
			
			# Landmarks
			if role in ["main", "navigation", "banner", "contentinfo", "complementary", "search"]:
				structure["landmarks"][role] = node.get("name", role)
			
			# Headings
			if role == "heading":
				structure["headings"].append({
					"text": node.get("name", ""),
					"level": node.get("level", 1)
				})
			
			# Forms
			if role == "form":
				structure["forms"].append({
					"name": node.get("name", ""),
					"fields": []  # Would need deeper analysis
				})
			
			# Navigation
			if role == "navigation":
				structure["navigations"].append({
					"name": node.get("name", "Navigation")
				})
			
			# Traverse children
			for child in node.get("children", []):
				traverse(child, level + 1)
		
		traverse(tree)
		return structure
	
	async def _find_by_role(self, page: Page, role: str) -> list[PerceptionElement]:
		"""Find elements by ARIA role"""
		selectors = self._role_mappings.get(role.lower(), [f"[role='{role}']"])
		
		elements = []
		for selector in selectors:
			try:
				element_handles = await page.query_selector_all(selector)
				for handle in element_handles:
					# Get element properties
					props = await handle.evaluate("""
						(el) => {
							const rect = el.getBoundingClientRect();
							return {
								role: el.getAttribute('role') || el.tagName.toLowerCase(),
								label: el.getAttribute('aria-label') || el.textContent?.trim(),
								selector: el.id ? `#${el.id}` : null,
								bbox: {
									x: rect.x,
									y: rect.y,
									width: rect.width,
									height: rect.height
								},
								isVisible: rect.width > 0 && rect.height > 0
							};
						}
					""")
					
					if props["isVisible"]:
						element = PerceptionElement(
							type=role,
							role=props["role"],
							label=props["label"],
							selector=props["selector"],
							bounding_box=BoundingBox(**props["bbox"]) if props["bbox"] else None,
							is_interactive=True
						)
						elements.append(element)
				
			except Exception:
				continue
		
		return elements
	
	async def _find_by_label(self, page: Page, label: str) -> list[PerceptionElement]:
		"""Find elements by accessible label"""
		elements_data = await page.evaluate("""
			(searchLabel) => {
				const elements = [];
				const allElements = document.querySelectorAll('*');
				
				for (const el of allElements) {
					// Check aria-label
					const ariaLabel = el.getAttribute('aria-label');
					if (ariaLabel && ariaLabel.toLowerCase().includes(searchLabel.toLowerCase())) {
						const rect = el.getBoundingClientRect();
						if (rect.width > 0 && rect.height > 0) {
							elements.push({
								role: el.getAttribute('role') || el.tagName.toLowerCase(),
								label: ariaLabel,
								bbox: {
									x: rect.x,
									y: rect.y,
									width: rect.width,
									height: rect.height
								}
							});
						}
					}
					
					// Check associated label
					if (el.id) {
						const label = document.querySelector(`label[for="${el.id}"]`);
						if (label && label.textContent.toLowerCase().includes(searchLabel.toLowerCase())) {
							const rect = el.getBoundingClientRect();
							if (rect.width > 0 && rect.height > 0) {
								elements.push({
									role: el.getAttribute('role') || el.tagName.toLowerCase(),
									label: label.textContent.trim(),
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
				}
				
				return elements;
			}
		""", label)
		
		return [
			PerceptionElement(
				type=data["role"],
				role=data["role"],
				label=data["label"],
				bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
				is_interactive=True
			)
			for data in elements_data
		]
	
	async def _find_by_semantic_description(self, page: Page, description: str) -> list[PerceptionElement]:
		"""Find elements by semantic description"""
		# Parse description for semantic cues
		description_lower = description.lower()
		
		# Check for landmark references
		for landmark in ["main", "navigation", "header", "footer", "sidebar"]:
			if landmark in description_lower:
				return await self._find_by_role(page, landmark)
		
		# Check for common UI patterns
		if "button" in description_lower and ("submit" in description_lower or "save" in description_lower):
			elements = await page.evaluate("""
				() => {
					const buttons = [];
					const candidates = document.querySelectorAll('button, input[type="submit"], [role="button"]');
					
					for (const el of candidates) {
						const text = el.textContent?.toLowerCase() || el.value?.toLowerCase() || '';
						if (text.includes('submit') || text.includes('save')) {
							const rect = el.getBoundingClientRect();
							buttons.push({
								role: 'button',
								label: el.textContent?.trim() || el.value,
								bbox: {
									x: rect.x,
									y: rect.y,
									width: rect.width,
									height: rect.height
								}
							});
						}
					}
					
					return buttons;
				}
			""")
			
			return [
				PerceptionElement(
					type="button",
					role="button",
					label=data["label"],
					bounding_box=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
					is_interactive=True
				)
				for data in elements
			]
		
		# Fall back to label search
		words = description.split()
		for word in words:
			if len(word) > 3:  # Skip short words
				elements = await self._find_by_label(page, word)
				if elements:
					return elements
		
		return []