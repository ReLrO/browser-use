"""
LLM-based element finder that uses the language model to understand page context
"""

from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from browser_use.perception.base import PerceptionElement, BoundingBox
from browser_use.core.intent.views import ElementIntent
from langchain_core.language_models import BaseChatModel
import json
import logging

logger = logging.getLogger(__name__)


class LLMElementFinder:
    """Finds elements using LLM understanding of page content"""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
    
    async def find_element(
        self,
        page: Page,
        element_intent: ElementIntent,
        max_elements: int = 50
    ) -> Optional[PerceptionElement]:
        """Find element using LLM to understand page content"""
        
        logger.debug(f"LLM finding element: {element_intent.description}")
        
        # Get page content with element information
        page_elements = await self._extract_page_elements(page, max_elements)
        
        if not page_elements:
            logger.warning("No elements found on page")
            return None
        
        # Ask LLM to find the best matching element
        prompt = f"""Given the following interactive elements on the page, find the element that best matches this description:

Description: {element_intent.description}
Element Type: {element_intent.element_type or 'any'}

Page Elements:
{json.dumps(page_elements, indent=2)}

Return the index of the best matching element (0-based), or -1 if no good match.
Also provide a confidence score (0-1) and reasoning.

IMPORTANT: Return ONLY valid JSON, nothing else. No explanations before or after.

Response format:
{{
    "index": <number>,
    "confidence": <number>,
    "reasoning": "<string>"
}}
"""
        
        try:
            response = await self.llm.ainvoke(prompt)
            
            # Extract text from response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # Fallback: try parsing the whole response
                result = json.loads(response_text.strip())
            
            if result["index"] >= 0 and result["index"] < len(page_elements):
                element_info = page_elements[result["index"]]
                logger.info(f"LLM found element at index {result['index']} with confidence {result['confidence']}: {result['reasoning']}")
                
                # Create selector for the element
                selector = await self._create_selector(page, element_info)
                
                # Get element handle to verify it exists
                element_handle = await page.query_selector(selector)
                if not element_handle:
                    logger.warning(f"Could not find element with selector: {selector}")
                    return None
                
                # Get bounding box
                box = await element_handle.bounding_box()
                bounding_box = None
                if box:
                    bounding_box = BoundingBox(
                        x=box['x'],
                        y=box['y'],
                        width=box['width'],
                        height=box['height']
                    )
                
                return PerceptionElement(
                    type=element_info['tag'],
                    text=element_info.get('text', ''),
                    selector=selector,
                    attributes=element_info.get('attributes', {}),
                    bounding_box=bounding_box,
                    confidence=result['confidence'],
                    is_interactive=True,
                    is_visible=True
                )
            else:
                logger.info(f"LLM could not find matching element: {result.get('reasoning', 'No reason provided')}")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM element finding: {e}")
            return None
    
    async def _extract_page_elements(self, page: Page, max_elements: int) -> List[Dict[str, Any]]:
        """Extract information about interactive elements on the page"""
        
        # JavaScript to extract element information
        elements_info = await page.evaluate("""(maxElements) => {
            const interactiveSelectors = [
                'button',
                'a',
                'input',
                'select',
                'textarea',
                '[role="button"]',
                '[role="link"]',
                '[role="textbox"]',
                '[role="combobox"]',
                '[role="checkbox"]',
                '[role="radio"]',
                '[onclick]',
                '[data-click]'
            ];
            
            const elements = [];
            const seen = new Set();
            
            for (const selector of interactiveSelectors) {
                const found = document.querySelectorAll(selector);
                for (const el of found) {
                    if (seen.has(el) || !el.offsetParent) continue; // Skip duplicates and hidden
                    seen.add(el);
                    
                    // Get element info
                    const rect = el.getBoundingClientRect();
                    const info = {
                        tag: el.tagName.toLowerCase(),
                        text: el.textContent.trim().substring(0, 100),
                        attributes: {},
                        rect: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        },
                        isVisible: rect.width > 0 && rect.height > 0
                    };
                    
                    // Get key attributes
                    const importantAttrs = ['id', 'class', 'name', 'type', 'placeholder', 
                                          'aria-label', 'title', 'href', 'role', 'value'];
                    for (const attr of importantAttrs) {
                        if (el.hasAttribute(attr)) {
                            info.attributes[attr] = el.getAttribute(attr);
                        }
                    }
                    
                    elements.push(info);
                    
                    if (elements.length >= maxElements) {
                        return elements;
                    }
                }
            }
            
            return elements;
        }""", max_elements)
        
        return elements_info
    
    async def _create_selector(self, page: Page, element_info: Dict[str, Any]) -> str:
        """Create a unique selector for the element"""
        
        # Try different selector strategies
        attrs = element_info.get('attributes', {})
        tag = element_info['tag']
        
        # ID is most reliable
        if attrs.get('id'):
            return f"#{attrs['id']}"
        
        # Build attribute selector
        selector_parts = [tag]
        
        # Add specific attributes
        if attrs.get('name'):
            selector_parts.append(f'[name="{attrs["name"]}"]')
        if attrs.get('type'):
            selector_parts.append(f'[type="{attrs["type"]}"]')
        if attrs.get('placeholder'):
            selector_parts.append(f'[placeholder="{attrs["placeholder"]}"]')
        
        # If we have enough specificity, use it
        if len(selector_parts) > 1:
            return ''.join(selector_parts)
        
        # Try text content for buttons and links
        if tag in ['button', 'a'] and element_info.get('text'):
            text = element_info['text'][:30]  # Limit length
            return f'{tag}:has-text("{text}")'
        
        # Last resort - use exact text match
        if element_info.get('text'):
            return f'text="{element_info["text"]}"'
        
        # Ultimate fallback
        return tag