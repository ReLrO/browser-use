"""Universal UI Analyzer using Vision Models for true one-size-fits-all solution"""

import base64
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


@dataclass
class UIElement:
    """Represents a UI element detected by vision"""
    description: str
    purpose: str
    location: str  # e.g., "top-right", "center", "bottom-left"
    confidence: float
    related_elements: List[str] = None
    

@dataclass
class UIPattern:
    """Represents a detected UI pattern"""
    pattern_type: str
    description: str
    elements: List[UIElement]
    confidence: float


class VisionBasedUIAnalyzer:
    """Analyzes UI using vision models for universal understanding"""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self._system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for UI understanding"""
        return """You are an expert UI/UX analyst with perfect vision. Your job is to understand any user interface by looking at it, just like a human would.

IMPORTANT: You understand UI through visual patterns, NOT through hardcoded rules. Every website is unique, but they all follow human-understandable patterns.

Your analysis should identify:
1. What actions the user can take
2. Where important elements are located
3. How elements relate to each other
4. The purpose and function of each element

You think like a user, not a developer. You understand:
- Buttons might have text, icons, or both
- Search boxes might have magnifying glass icons
- Filters might be checkboxes, links, or dropdowns
- Submit buttons are often near input fields
- Important actions are usually prominent

Return your analysis as structured JSON."""

    async def analyze_ui(self, screenshot: bytes, user_intent: str = None) -> Dict[str, Any]:
        """Analyze UI from screenshot with optional user intent context"""
        
        # Encode screenshot
        screenshot_b64 = base64.b64encode(screenshot).decode()
        
        # Build the analysis prompt
        analysis_prompt = f"""Analyze this user interface screenshot and identify all interactive elements and patterns.

{f"User wants to: {user_intent}" if user_intent else "Provide a general UI analysis."}

Think step by step:
1. What type of page is this? (search results, product page, form, etc.)
2. What are the main sections/areas?
3. What actions can a user take?
4. How do elements relate to each other?

Provide a comprehensive analysis that would help someone interact with this page.

Format your response as JSON:
{{
    "page_type": "description of page type",
    "main_purpose": "what this page is for",
    "layout": {{
        "header": "description of header area",
        "main_content": "description of main area",
        "sidebar": "description if exists",
        "footer": "description if exists"
    }},
    "interactive_elements": [
        {{
            "description": "what the element is",
            "purpose": "what it does",
            "location": "where on page (top-left, center, etc)",
            "visual_cues": "what makes it identifiable (color, size, text, icons)",
            "related_to": "other elements it's connected to"
        }}
    ],
    "detected_patterns": [
        {{
            "pattern": "search_interface|form|navigation|filters|results_list|etc",
            "description": "how this pattern appears on the page",
            "key_elements": ["list of related elements"]
        }}
    ],
    "user_flow": {{
        "current_state": "where the user is in their journey",
        "possible_actions": ["list of actions user can take"],
        "recommended_action": "what to do based on user intent" if user_intent else null
    }}
}}"""

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=[
                {"type": "text", "text": analysis_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
            ])
        ]
        
        try:
            # Apply rate limiting
            from browser_use.core.caching import rate_limiter
            await rate_limiter.acquire()
            
            response = await self.llm.ainvoke(messages)
            rate_limiter.report_success()
            
            # Parse the response
            response_text = response.content
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return analysis
            else:
                logger.error("Could not parse vision analysis response")
                return {}
                
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            if "quota" in str(e).lower() or "429" in str(e):
                rate_limiter.report_error(e)
            raise

    async def find_element_for_action(self, screenshot: bytes, action_description: str) -> Optional[Dict[str, Any]]:
        """Find the best element for a specific action using vision"""
        
        screenshot_b64 = base64.b64encode(screenshot).decode()
        
        prompt = f"""Look at this screenshot and find the best element for this action: "{action_description}"

Think like a human user:
1. What would a user naturally look for to perform this action?
2. Where would they expect to find it?
3. What visual cues would guide them?

Consider:
- Text labels (might be abbreviated or use icons)
- Visual prominence (size, color, position)
- Common UI patterns (search boxes with buttons, filters as links/checkboxes)
- Proximity (related elements are usually near each other)

Return the single best matching element as JSON:
{{
    "found": true/false,
    "element": {{
        "description": "what the element is",
        "visual_appearance": "what it looks like",
        "location": "where it is on the page",
        "confidence": 0.0-1.0,
        "reasoning": "why this is the right element"
    }},
    "alternatives": [
        // Other possible matches if any
    ]
}}"""

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
            ])
        ]
        
        try:
            # Apply rate limiting
            from browser_use.core.caching import rate_limiter
            await rate_limiter.acquire()
            
            response = await self.llm.ainvoke(messages)
            rate_limiter.report_success()
            
            # Parse response
            import re
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    # Ensure required fields
                    if 'found' not in result:
                        result['found'] = bool(result.get('element'))
                    return result
                except json.JSONDecodeError:
                    logger.warning("Failed to parse vision response as JSON")
            
            # Fallback - assume not found
            return {"found": False, "reason": "Could not parse vision response"}
            
        except Exception as e:
            logger.error(f"Element finding failed: {e}")
            if "quota" in str(e).lower() or "429" in str(e):
                rate_limiter.report_error(e)
            return None

    async def understand_page_state(self, screenshot: bytes, previous_action: str = None) -> Dict[str, Any]:
        """Understand the current state of the page"""
        
        screenshot_b64 = base64.b64encode(screenshot).decode()
        
        prompt = f"""Analyze the current state of this webpage.

{f"Previous action: {previous_action}" if previous_action else "This is the initial page state."}

Determine:
1. What type of page/state is this?
2. Did the previous action succeed?
3. What feedback or changes are visible?
4. What should happen next?

Return analysis as JSON:
{{
    "page_state": "description of current state",
    "action_result": {{
        "success": true/false,
        "evidence": "what shows success/failure",
        "feedback_messages": ["any messages shown to user"]
    }} if previous_action else null,
    "available_actions": ["what user can do now"],
    "recommendations": ["suggested next steps"]
}}"""

        messages = [
            SystemMessage(content="You are an expert at understanding web page states and user flows."),
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
            ])
        ]
        
        try:
            # Apply rate limiting
            from browser_use.core.caching import rate_limiter
            await rate_limiter.acquire()
            
            response = await self.llm.ainvoke(messages)
            rate_limiter.report_success()
            
            # Parse response
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
                
            return {"page_state": "unknown", "error": "Could not parse response"}
            
        except Exception as e:
            logger.error(f"Page state analysis failed: {e}")
            if "quota" in str(e).lower() or "429" in str(e):
                rate_limiter.report_error(e)
            return {"page_state": "error", "error": str(e)}