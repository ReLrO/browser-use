"""Success verification system for intent execution"""

import asyncio
import base64
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from browser_use.core.intent.views import Intent, SuccessCriteria, IntentType
from browser_use.perception.vision.service import VisionEngine
from browser_use.utils import time_execution_async
from playwright.async_api import Page


class VerificationType(str, Enum):
	"""Types of verification methods"""
	URL_CHECK = "url_check"
	ELEMENT_PRESENCE = "element_presence"
	TEXT_PRESENCE = "text_presence"
	VISUAL_VERIFICATION = "visual_verification"
	STATE_COMPARISON = "state_comparison"
	CUSTOM_SCRIPT = "custom_script"
	API_CHECK = "api_check"
	SCREENSHOT_DIFF = "screenshot_diff"


class VerificationResult:
	"""Result of a verification check"""
	
	def __init__(
		self,
		success: bool,
		verification_type: VerificationType,
		message: str,
		confidence: float = 1.0,
		evidence: Optional[Dict[str, Any]] = None
	):
		self.success = success
		self.verification_type = verification_type
		self.message = message
		self.confidence = confidence
		self.evidence = evidence or {}
		self.timestamp = datetime.now()


class IntentVerificationService:
	"""Verifies successful completion of intents"""
	
	def __init__(self, vision_engine: Optional[VisionEngine] = None):
		self.vision_engine = vision_engine
		self._verification_strategies: Dict[str, Any] = {}
		self._custom_verifiers: Dict[str, Any] = {}
		self._verification_cache: Dict[str, VerificationResult] = {}
		
		# Register default verification strategies
		self._register_default_strategies()
	
	@time_execution_async("verify_intent")
	async def verify_intent_completion(
		self,
		intent: Intent,
		page: Page,
		context: Optional[Dict[str, Any]] = None
	) -> Tuple[bool, List[VerificationResult]]:
		"""Verify that an intent was successfully completed"""
		context = context or {}
		results = []
		
		# Check each success criterion
		for criterion in intent.success_criteria:
			result = await self._verify_criterion(criterion, page, context)
			results.append(result)
		
		# If no explicit criteria, use intent-type based verification
		if not intent.success_criteria:
			implicit_results = await self._verify_by_intent_type(intent, page, context)
			results.extend(implicit_results)
		
		# Calculate overall success
		if not results:
			# No verification criteria - assume success
			overall_success = True
		else:
			# Weighted success based on confidence
			total_weight = sum(r.confidence for r in results)
			if total_weight > 0:
				success_score = sum(r.confidence for r in results if r.success) / total_weight
				overall_success = success_score >= 0.7  # 70% threshold
			else:
				overall_success = all(r.success for r in results)
		
		return overall_success, results
	
	async def _verify_criterion(
		self,
		criterion: SuccessCriteria,
		page: Page,
		context: Dict[str, Any]
	) -> VerificationResult:
		"""Verify a single success criterion"""
		try:
			if criterion.type == "url_matches":
				return await self._verify_url_match(criterion, page)
			
			elif criterion.type == "element_visible":
				return await self._verify_element_visible(criterion, page)
			
			elif criterion.type == "text_present":
				return await self._verify_text_present(criterion, page)
			
			elif criterion.type == "element_count":
				return await self._verify_element_count(criterion, page)
			
			elif criterion.type == "visual_match":
				return await self._verify_visual_match(criterion, page, context)
			
			elif criterion.type == "custom":
				return await self._verify_custom(criterion, page, context)
			
			else:
				# Unknown criterion type
				return VerificationResult(
					success=False,
					verification_type=VerificationType.CUSTOM_SCRIPT,
					message=f"Unknown verification type: {criterion.type}",
					confidence=0.0
				)
				
		except Exception as e:
			return VerificationResult(
				success=False,
				verification_type=VerificationType.CUSTOM_SCRIPT,
				message=f"Verification error: {str(e)}",
				confidence=0.0
			)
	
	# Verification strategies
	
	async def _verify_url_match(self, criterion: SuccessCriteria, page: Page) -> VerificationResult:
		"""Verify URL matches expected pattern"""
		current_url = page.url
		expected = criterion.expected
		
		if isinstance(expected, str):
			# Exact match or contains
			if expected.startswith("contains:"):
				pattern = expected[9:]
				success = pattern in current_url
			elif expected.startswith("regex:"):
				import re
				pattern = expected[6:]
				success = bool(re.match(pattern, current_url))
			else:
				success = current_url == expected
		else:
			success = False
		
		return VerificationResult(
			success=success,
			verification_type=VerificationType.URL_CHECK,
			message=f"URL {'matches' if success else 'does not match'} expected pattern",
			confidence=1.0,
			evidence={"current_url": current_url, "expected": expected}
		)
	
	async def _verify_element_visible(self, criterion: SuccessCriteria, page: Page) -> VerificationResult:
		"""Verify element is visible on page"""
		selector = criterion.expected
		timeout = int((criterion.timeout or 5) * 1000)  # Convert to ms
		
		try:
			# Wait for element
			element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
			
			if element:
				# Double-check visibility
				is_visible = await element.is_visible()
				bounding_box = await element.bounding_box()
				
				return VerificationResult(
					success=is_visible and bounding_box is not None,
					verification_type=VerificationType.ELEMENT_PRESENCE,
					message=f"Element {selector} is visible",
					confidence=1.0,
					evidence={
						"selector": selector,
						"visible": is_visible,
						"has_size": bounding_box is not None
					}
				)
			else:
				return VerificationResult(
					success=False,
					verification_type=VerificationType.ELEMENT_PRESENCE,
					message=f"Element {selector} not found",
					confidence=1.0
				)
				
		except Exception:
			return VerificationResult(
				success=False,
				verification_type=VerificationType.ELEMENT_PRESENCE,
				message=f"Element {selector} not visible within timeout",
				confidence=1.0,
				evidence={"selector": selector, "timeout": timeout}
			)
	
	async def _verify_text_present(self, criterion: SuccessCriteria, page: Page) -> VerificationResult:
		"""Verify text is present on page"""
		expected_text = criterion.expected
		
		# Get page text
		page_text = await page.text_content("body")
		
		if not page_text:
			return VerificationResult(
				success=False,
				verification_type=VerificationType.TEXT_PRESENCE,
				message="Could not get page text",
				confidence=1.0
			)
		
		# Check for text presence
		if isinstance(expected_text, str):
			success = expected_text in page_text
		elif isinstance(expected_text, list):
			# All texts must be present
			success = all(text in page_text for text in expected_text)
		else:
			success = False
		
		return VerificationResult(
			success=success,
			verification_type=VerificationType.TEXT_PRESENCE,
			message=f"Text {'found' if success else 'not found'} on page",
			confidence=1.0,
			evidence={
				"expected": expected_text,
				"found": success,
				"page_text_length": len(page_text)
			}
		)
	
	async def _verify_element_count(self, criterion: SuccessCriteria, page: Page) -> VerificationResult:
		"""Verify number of elements matches expectation"""
		selector = criterion.expected.get("selector")
		expected_count = criterion.expected.get("count", 0)
		operator = criterion.expected.get("operator", "equals")
		
		# Count elements
		elements = await page.query_selector_all(selector)
		actual_count = len(elements)
		
		# Check count based on operator
		if operator == "equals":
			success = actual_count == expected_count
		elif operator == "greater_than":
			success = actual_count > expected_count
		elif operator == "less_than":
			success = actual_count < expected_count
		elif operator == "at_least":
			success = actual_count >= expected_count
		elif operator == "at_most":
			success = actual_count <= expected_count
		else:
			success = False
		
		return VerificationResult(
			success=success,
			verification_type=VerificationType.ELEMENT_PRESENCE,
			message=f"Element count {operator} check: {actual_count} vs {expected_count}",
			confidence=1.0,
			evidence={
				"selector": selector,
				"actual_count": actual_count,
				"expected_count": expected_count,
				"operator": operator
			}
		)
	
	async def _verify_visual_match(
		self,
		criterion: SuccessCriteria,
		page: Page,
		context: Dict[str, Any]
	) -> VerificationResult:
		"""Verify visual state matches expectation"""
		if not self.vision_engine:
			return VerificationResult(
				success=False,
				verification_type=VerificationType.VISUAL_VERIFICATION,
				message="Vision engine not available",
				confidence=0.0
			)
		
		# Take screenshot
		screenshot = await page.screenshot()
		
		# Use vision engine to verify
		expected_state = criterion.expected
		verified = await self.vision_engine.verify_visual_state(screenshot, expected_state)
		
		return VerificationResult(
			success=verified,
			verification_type=VerificationType.VISUAL_VERIFICATION,
			message=f"Visual state {'matches' if verified else 'does not match'} expectation",
			confidence=0.8,  # Vision verification is less certain
			evidence={
				"expected_state": expected_state,
				"screenshot_size": len(screenshot)
			}
		)
	
	async def _verify_custom(
		self,
		criterion: SuccessCriteria,
		page: Page,
		context: Dict[str, Any]
	) -> VerificationResult:
		"""Run custom verification"""
		custom_name = criterion.expected.get("verifier")
		
		if custom_name in self._custom_verifiers:
			verifier = self._custom_verifiers[custom_name]
			return await verifier(criterion, page, context)
		
		# Try to run as JavaScript
		if "script" in criterion.expected:
			script = criterion.expected["script"]
			try:
				result = await page.evaluate(script)
				
				return VerificationResult(
					success=bool(result),
					verification_type=VerificationType.CUSTOM_SCRIPT,
					message=f"Custom script returned: {result}",
					confidence=1.0,
					evidence={"script_result": result}
				)
			except Exception as e:
				return VerificationResult(
					success=False,
					verification_type=VerificationType.CUSTOM_SCRIPT,
					message=f"Custom script error: {str(e)}",
					confidence=0.0
				)
		
		return VerificationResult(
			success=False,
			verification_type=VerificationType.CUSTOM_SCRIPT,
			message="No custom verifier found",
			confidence=0.0
		)
	
	# Intent-type based verification
	
	async def _verify_by_intent_type(
		self,
		intent: Intent,
		page: Page,
		context: Dict[str, Any]
	) -> List[VerificationResult]:
		"""Implicit verification based on intent type"""
		results = []
		
		if intent.type == IntentType.NAVIGATION:
			# Check if navigation succeeded
			url = self._get_intent_param(intent, "url")
			if url:
				result = await self._verify_url_match(
					SuccessCriteria(type="url_matches", expected=f"contains:{url}"),
					page
				)
				results.append(result)
		
		elif intent.type == IntentType.AUTHENTICATION:
			# Check for common login success indicators
			# Look for logout button
			logout_visible = await self._check_element_exists(page, "[text*='Logout'], [text*='Sign out']")
			
			# Check URL change
			if "login" not in page.url.lower() and "signin" not in page.url.lower():
				results.append(VerificationResult(
					success=True,
					verification_type=VerificationType.URL_CHECK,
					message="Navigated away from login page",
					confidence=0.7
				))
			
			if logout_visible:
				results.append(VerificationResult(
					success=True,
					verification_type=VerificationType.ELEMENT_PRESENCE,
					message="Logout button found",
					confidence=0.9
				))
		
		elif intent.type == IntentType.FORM_FILL:
			# Check for form submission success
			# Look for success message
			success_indicators = [
				"success", "thank you", "submitted", "received",
				"confirmation", "complete"
			]
			
			page_text = await page.text_content("body")
			if page_text:
				found_indicator = any(indicator in page_text.lower() for indicator in success_indicators)
				
				if found_indicator:
					results.append(VerificationResult(
						success=True,
						verification_type=VerificationType.TEXT_PRESENCE,
						message="Success indicator found in page",
						confidence=0.8
					))
		
		elif intent.type == IntentType.SEARCH:
			# Check for search results
			# Look for common result indicators
			result_selectors = [
				"[class*='result']", "[class*='search-result']",
				"[id*='results']", "article", ".item"
			]
			
			for selector in result_selectors:
				count = len(await page.query_selector_all(selector))
				if count > 0:
					results.append(VerificationResult(
						success=True,
						verification_type=VerificationType.ELEMENT_PRESENCE,
						message=f"Found {count} search results",
						confidence=0.8,
						evidence={"selector": selector, "count": count}
					))
					break
		
		return results
	
	# Helper methods
	
	async def _check_element_exists(self, page: Page, selector: str) -> bool:
		"""Check if element exists on page"""
		try:
			element = await page.query_selector(selector)
			return element is not None
		except Exception:
			return False
	
	def _get_intent_param(self, intent: Intent, param_name: str) -> Optional[Any]:
		"""Get parameter value from intent"""
		for param in intent.parameters:
			if param.name == param_name:
				return param.value
		return None
	
	# Strategy registration
	
	def _register_default_strategies(self):
		"""Register default verification strategies"""
		self._verification_strategies = {
			VerificationType.URL_CHECK: self._verify_url_match,
			VerificationType.ELEMENT_PRESENCE: self._verify_element_visible,
			VerificationType.TEXT_PRESENCE: self._verify_text_present,
			VerificationType.VISUAL_VERIFICATION: self._verify_visual_match,
			VerificationType.CUSTOM_SCRIPT: self._verify_custom
		}
	
	def register_custom_verifier(self, name: str, verifier: Any) -> None:
		"""Register a custom verification function"""
		self._custom_verifiers[name] = verifier
	
	# Screenshot comparison
	
	async def take_verification_screenshot(self, page: Page) -> str:
		"""Take and encode a verification screenshot"""
		try:
			screenshot = await page.screenshot(full_page=False)
			return base64.b64encode(screenshot).decode()
		except Exception:
			return None
	
	async def compare_screenshots(
		self,
		before: bytes,
		after: bytes,
		threshold: float = 0.95
	) -> Tuple[bool, float]:
		"""Compare two screenshots for similarity"""
		# This is a placeholder - in production would use image comparison
		# libraries like OpenCV or PIL
		
		# For now, just check sizes
		if len(before) == len(after):
			return True, 1.0
		
		size_ratio = min(len(before), len(after)) / max(len(before), len(after))
		return size_ratio >= threshold, size_ratio