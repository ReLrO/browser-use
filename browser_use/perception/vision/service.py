"""Vision-based perception using multimodal LLMs"""

import base64
import asyncio
from typing import Any, Optional, Union
from datetime import datetime
import json
from io import BytesIO
from PIL import Image
import numpy as np

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from browser_use.perception.base import (
	IPerceptionSystem, PerceptionElement, PerceptionResult,
	PerceptionQuery, PerceptionCapability, BoundingBox
)
from browser_use.utils import time_execution_async


class VisionEngine(IPerceptionSystem):
	"""Vision-based perception using multimodal LLMs"""
	
	def __init__(self, llm: BaseChatModel):
		self.llm = llm
		self.config = {}
		self._initialized = False
		self._capabilities = PerceptionCapability(
			name="VisionEngine",
			supported_queries=[
				"visual_grounding",
				"element_detection",
				"layout_understanding",
				"text_extraction",
				"ui_quality_assessment",
				"visual_verification"
			],
			strengths=[
				"Understanding complex layouts",
				"Finding elements by visual appearance",
				"Detecting UI issues and inconsistencies",
				"Working with non-standard web elements",
				"Understanding visual relationships"
			],
			limitations=[
				"Requires screenshot capture",
				"Higher latency than DOM-based methods",
				"Token-intensive for large pages",
				"May miss very small elements"
			],
			performance_ms=500  # Typical vision model latency
		)
	
	async def initialize(self, config: dict[str, Any]) -> None:
		"""Initialize the vision engine"""
		self.config = config
		self._initialized = True
		
		# Pre-load any vision-specific prompts
		self._element_detection_prompt = self._build_element_detection_prompt()
		self._grounding_prompt = self._build_grounding_prompt()
		self._quality_assessment_prompt = self._build_quality_assessment_prompt()
	
	@time_execution_async("vision_analyze_page")
	async def analyze_page(self, page_data: dict[str, Any]) -> PerceptionResult:
		"""Analyze a page using vision and return detected elements"""
		if not self._initialized:
			raise RuntimeError("VisionEngine not initialized")
		
		screenshot = page_data.get("screenshot")
		if not screenshot:
			return PerceptionResult(errors=["No screenshot provided"])
		
		try:
			# Decode screenshot if base64
			if isinstance(screenshot, str):
				screenshot = base64.b64decode(screenshot)
			
			# Run multiple vision tasks in parallel
			tasks = [
				self._detect_elements(screenshot),
				self._analyze_layout(screenshot),
				self._extract_text_regions(screenshot)
			]
			
			results = await asyncio.gather(*tasks, return_exceptions=True)
			
			# Combine results
			all_elements = []
			errors = []
			
			for result in results:
				if isinstance(result, Exception):
					errors.append(str(result))
				elif isinstance(result, list):
					all_elements.extend(result)
			
			# Build page context
			page_context = {
				"viewport_size": page_data.get("viewport_size", {}),
				"url": page_data.get("url", ""),
				"visual_analysis_complete": True
			}
			
			return PerceptionResult(
				elements=all_elements,
				page_context=page_context,
				processing_time_ms=500,  # Approximate
				errors=errors
			)
			
		except Exception as e:
			return PerceptionResult(errors=[f"Vision analysis failed: {str(e)}"])
	
	async def find_element(self, query: PerceptionQuery) -> Optional[PerceptionElement]:
		"""Find a specific element using visual grounding"""
		elements = await self.find_elements(query)
		return elements[0] if elements else None
	
	@time_execution_async("vision_find_elements")
	async def find_elements(self, query: PerceptionQuery) -> list[PerceptionElement]:
		"""Find elements matching the query using vision"""
		screenshot = query.context.get("screenshot")
		if not screenshot:
			return []
		
		try:
			# Use visual grounding to find elements
			prompt = self._build_find_element_prompt(query)
			
			messages = [
				SystemMessage(content=self._grounding_prompt),
				HumanMessage(content=[
					{"type": "text", "text": prompt},
					{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}}
				])
			]
			
			response = await self.llm.ainvoke(messages)
			elements = self._parse_grounding_response(response.content, query)
			
			# Filter by confidence threshold
			return [e for e in elements if e.confidence >= query.confidence_threshold]
			
		except Exception as e:
			return []
	
	def get_capabilities(self) -> PerceptionCapability:
		"""Get capabilities of the vision engine"""
		return self._capabilities
	
	async def cleanup(self) -> None:
		"""Clean up resources"""
		self._initialized = False
	
	# Specialized vision methods
	
	async def detect_ui_issues(self, screenshot: bytes) -> dict[str, Any]:
		"""Detect UI quality issues in the screenshot"""
		try:
			messages = [
				SystemMessage(content=self._quality_assessment_prompt),
				HumanMessage(content=[
					{"type": "text", "text": "Analyze this UI for quality issues"},
					{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"}}
				])
			]
			
			response = await self.llm.ainvoke(messages)
			return self._parse_quality_assessment(response.content)
			
		except Exception as e:
			return {"error": str(e)}
	
	async def verify_visual_state(self, screenshot: bytes, expected_state: str) -> bool:
		"""Verify if the visual state matches expectations"""
		try:
			messages = [
				SystemMessage(content="You are a visual verification system. Analyze if the screenshot matches the expected state."),
				HumanMessage(content=[
					{"type": "text", "text": f"Does this screenshot show: {expected_state}? Respond with JSON: {{\"matches\": true/false, \"confidence\": 0-1, \"reason\": \"explanation\"}}"},
					{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"}}
				])
			]
			
			response = await self.llm.ainvoke(messages)
			result = json.loads(response.content)
			return result["matches"] and result["confidence"] > 0.8
			
		except Exception:
			return False
	
	# Private helper methods
	
	async def _detect_elements(self, screenshot: bytes) -> list[PerceptionElement]:
		"""Detect interactive elements in the screenshot"""
		messages = [
			SystemMessage(content=self._element_detection_prompt),
			HumanMessage(content=[
				{"type": "text", "text": "Detect all interactive elements in this screenshot"},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"}}
			])
		]
		
		response = await self.llm.ainvoke(messages)
		return self._parse_element_detection(response.content)
	
	async def _analyze_layout(self, screenshot: bytes) -> list[PerceptionElement]:
		"""Analyze the page layout"""
		messages = [
			SystemMessage(content="Analyze the layout structure of this page. Identify major sections, navigation, content areas, etc."),
			HumanMessage(content=[
				{"type": "text", "text": "Describe the layout structure"},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"}}
			])
		]
		
		response = await self.llm.ainvoke(messages)
		# Parse layout analysis into structural elements
		return []  # Simplified for now
	
	async def _extract_text_regions(self, screenshot: bytes) -> list[PerceptionElement]:
		"""Extract text regions from the screenshot"""
		# In a real implementation, this could use OCR
		# For now, we'll use the vision model
		messages = [
			SystemMessage(content="Identify all text regions in this screenshot with their locations."),
			HumanMessage(content=[
				{"type": "text", "text": "Extract text regions with bounding boxes"},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"}}
			])
		]
		
		response = await self.llm.ainvoke(messages)
		return []  # Simplified for now
	
	def _build_element_detection_prompt(self) -> str:
		"""Build prompt for element detection"""
		return """You are an expert UI element detector. Analyze screenshots and identify all interactive elements.

For each element found, provide:
1. Type (button, input, link, dropdown, checkbox, etc.)
2. Bounding box coordinates [x, y, width, height]
3. Text content or label
4. Visual characteristics (color, size, etc.)
5. Estimated purpose/function
6. Confidence score (0-1)

Respond with a JSON array of elements:
[
  {
    "type": "button",
    "bbox": [100, 200, 150, 40],
    "text": "Submit",
    "description": "Primary submit button",
    "attributes": {"color": "blue", "size": "large"},
    "confidence": 0.95
  }
]

Focus on elements that users can interact with. Include form fields, buttons, links, dropdowns, etc."""
	
	def _build_grounding_prompt(self) -> str:
		"""Build prompt for visual grounding"""
		return """You are a visual grounding system. Given a description of an element, find its location in the screenshot.

Provide precise bounding box coordinates for the described element.
If multiple matches exist, return all of them with confidence scores.
If no match is found, return an empty array.

Respond with JSON:
[
  {
    "bbox": [x, y, width, height],
    "confidence": 0.95,
    "reason": "Matched based on text and appearance"
  }
]"""
	
	def _build_quality_assessment_prompt(self) -> str:
		"""Build prompt for UI quality assessment"""
		return """You are a UI/UX quality assessor. Analyze screenshots for design and usability issues.

Check for:
1. Alignment issues
2. Color inconsistencies
3. Contrast problems
4. Overlapping elements
5. Broken layouts
6. Missing or unclear labels
7. Inconsistent styling
8. Accessibility concerns

Respond with JSON:
{
  "issues": [
    {
      "type": "alignment",
      "severity": "medium",
      "description": "Buttons are not aligned",
      "location": [x, y, width, height]
    }
  ],
  "overall_quality": "good|fair|poor",
  "accessibility_score": 0-10
}"""
	
	def _build_find_element_prompt(self, query: PerceptionQuery) -> str:
		"""Build prompt for finding specific elements"""
		prompt = f"Find elements matching: {query.description}\n"
		
		if query.element_type:
			prompt += f"Element type: {query.element_type}\n"
		
		if query.attributes:
			prompt += f"Required attributes: {json.dumps(query.attributes)}\n"
		
		prompt += "\nReturn precise bounding boxes for all matching elements."
		
		return prompt
	
	def _parse_element_detection(self, response: str) -> list[PerceptionElement]:
		"""Parse element detection response"""
		try:
			# Extract JSON from response
			import re
			json_match = re.search(r'\[[\s\S]*\]', response)
			if json_match:
				data = json.loads(json_match.group())
			else:
				data = json.loads(response)
			
			elements = []
			for item in data:
				bbox = item.get("bbox", [])
				if len(bbox) == 4:
					element = PerceptionElement(
						type=item.get("type", "unknown"),
						bounding_box=BoundingBox(
							x=bbox[0],
							y=bbox[1],
							width=bbox[2],
							height=bbox[3]
						),
						text=item.get("text", ""),
						confidence=item.get("confidence", 0.8),
						description=item.get("description", ""),
						attributes=item.get("attributes", {}),
						is_interactive=True
					)
					elements.append(element)
			
			return elements
			
		except Exception:
			return []
	
	def _parse_grounding_response(self, response: str, query: PerceptionQuery) -> list[PerceptionElement]:
		"""Parse visual grounding response"""
		try:
			# Extract JSON from response
			import re
			json_match = re.search(r'\[[\s\S]*\]', response)
			if json_match:
				data = json.loads(json_match.group())
			else:
				data = json.loads(response)
			
			elements = []
			for item in data:
				bbox = item.get("bbox", [])
				if len(bbox) == 4:
					element = PerceptionElement(
						type=query.element_type or "unknown",
						bounding_box=BoundingBox(
							x=bbox[0],
							y=bbox[1],
							width=bbox[2],
							height=bbox[3]
						),
						confidence=item.get("confidence", 0.8),
						description=query.description,
						attributes=query.attributes,
						is_interactive=True
					)
					elements.append(element)
			
			return elements
			
		except Exception:
			return []
	
	def _parse_quality_assessment(self, response: str) -> dict[str, Any]:
		"""Parse quality assessment response"""
		try:
			# Extract JSON from response
			import re
			json_match = re.search(r'\{[\s\S]*\}', response)
			if json_match:
				return json.loads(json_match.group())
			else:
				return json.loads(response)
		except Exception:
			return {"error": "Failed to parse quality assessment"}