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
        max_elements: int = 50,
        page_elements: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[PerceptionElement]:
        """Find element using LLM to understand page content"""
        
        logger.debug(f"LLM finding element: {element_intent.description}")
        
        # Use provided elements or extract them
        if page_elements is None:
            page_elements = await self._extract_page_elements(page, max_elements)
        
        if not page_elements:
            logger.warning("No elements found on page")
            return None
        
        # Ask LLM to find the best matching element
        # Create simplified element list for better matching
        simplified_elements = []
        for i, el in enumerate(page_elements):
            if el.get('isVisible', True):
                simplified_elements.append({
                    'index': i,
                    'tag': el.get('tag'),
                    'type': el.get('type'),
                    'role': el.get('role'),
                    'placeholder': el.get('placeholder'),
                    'text': (el.get('text', '') or '')[:50],
                    'name': el.get('name'),
                    'id': el.get('id'),
                    'className': (el.get('className', '') or '')[:50],
                    'isInput': el.get('isInput', False),
                    'isButton': el.get('isButton', False),
                    'isLink': el.get('tag') == 'a',
                    'isSearchInput': el.get('isSearchInput', False),
                    'rect': el.get('rect'),
                    'href': el.get('attributes', {}).get('href', '') if el.get('tag') == 'a' else None
                })
        
        prompt = f"""You are an expert at understanding web UI/UX patterns. Find the element that best matches this description:

Description: {element_intent.description}
Element Type: {element_intent.element_type or 'any'}

CRITICAL MATCHING RULES:
1. For input/type/search tasks: ONLY consider elements where isInput=true
2. For button/click tasks: Prefer elements where isButton=true
3. For link/result/navigation tasks: Consider elements where isLink=true (tag='a')
4. For "first search result": Look for links (isLink=true) with substantial text (>20 chars), below header (y>200)
5. Check these fields in order: type, role, placeholder, name, id, className, text
6. Search inputs often have: type="search" OR placeholder containing "search" OR id/name containing "search"
7. Main search boxes are usually large (width > 200) and in the header (y < 100)
8. Avoid ads: Skip elements with text containing "Ad", "Sponsored", "Promotion"

Page Elements (showing key fields for matching):
{json.dumps(simplified_elements, indent=2)}

EXAMPLES:
- "Enter search query" → Find element with isInput=true AND (type="search" OR placeholder/name contains "search")
- "Click search button" → Find element with isButton=true near a search input
- "Type laptop" → Find the main input field (usually search box on e-commerce sites)
- "Click the first search result" → Find first link (isLink=true) with substantial text, below header area
- "Click on product" → Find link with product-like text (long description, not navigation)
- "Navigate to result" → Find clickable link element

Return the index of the best matching element, or -1 if no match.

Response format:
{{
    "index": <number>,
    "confidence": <number>,
    "reasoning": "<string>"
}}
"""
        
        try:
            # Check cache first
            from browser_use.core.caching import element_cache, rate_limiter
            
            # Try to get from cache
            current_url = page.url
            cached_result = await element_cache.get(
                current_url,
                element_intent.description,
                element_intent.element_type
            )
            
            if cached_result:
                logger.info("Using cached element resolution")
                return cached_result
            
            # Apply rate limiting before LLM call
            await rate_limiter.acquire()
            
            try:
                response = await self.llm.ainvoke(prompt)
                rate_limiter.report_success()
            except Exception as e:
                rate_limiter.report_error(e)
                raise
            
            # Extract text from response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Try to find JSON in the response with multiple methods
            import re
            result = None
            
            # Method 1: Find JSON block (improved regex to handle nested objects)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    logger.debug("Successfully parsed JSON using regex extraction")
                except json.JSONDecodeError:
                    logger.debug("Regex found JSON-like text but parsing failed")
                    pass
            
            # Method 2: Remove markdown code blocks and try parsing
            if not result:
                try:
                    # Remove markdown code blocks if present
                    cleaned = re.sub(r'```json?\s*|\s*```', '', response_text)
                    cleaned = cleaned.strip()
                    result = json.loads(cleaned)
                    logger.debug("Successfully parsed JSON after removing markdown")
                except json.JSONDecodeError:
                    pass
            
            # Method 3: Extract key-value pairs manually
            if not result:
                index_match = re.search(r'"?index"?\s*:\s*(-?\d+)', response_text)
                confidence_match = re.search(r'"?confidence"?\s*:\s*(\d+\.?\d*)', response_text)
                reasoning_match = re.search(r'"?reasoning"?\s*:\s*"([^"]*)"', response_text)
                
                if index_match:
                    result = {
                        "index": int(index_match.group(1)),
                        "confidence": float(confidence_match.group(1)) if confidence_match else 0.8,
                        "reasoning": reasoning_match.group(1) if reasoning_match else "Extracted from malformed JSON"
                    }
                    logger.debug("Manually extracted values from malformed JSON")
            
            # If still no result, this strategy failed
            if not result:
                logger.warning("Could not parse LLM response in any format, will try next strategy")
                return None
            
            # Validate the result
            if "index" not in result:
                logger.warning("LLM response missing 'index' field")
                return None
            
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
                
                perception_element = PerceptionElement(
                    type=element_info['tag'],
                    text=element_info.get('text', ''),
                    selector=selector,
                    attributes=element_info.get('attributes', {}),
                    bounding_box=bounding_box,
                    confidence=result['confidence'],
                    is_interactive=True,
                    is_visible=True
                )
                
                # Cache the successful result
                await element_cache.set(
                    current_url,
                    element_intent.description,
                    element_intent.element_type,
                    perception_element
                )
                
                return perception_element
            else:
                logger.info(f"LLM could not find matching element: {result.get('reasoning', 'No reason provided')}")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in LLM element finding: {e}")
            if 'response_text' in locals():
                logger.debug(f"Response text was: {response_text[:500]}...")
            return None  # Don't raise - let other strategies try
        except Exception as e:
            logger.warning(f"Error in LLM element finding: {e}")
            return None  # Don't raise - let other strategies try
    
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
            # Escape quotes in placeholder
            placeholder = attrs["placeholder"].replace('"', '\\"')
            selector_parts.append(f'[placeholder="{placeholder}"]')
        if attrs.get('aria-label'):
            # Escape quotes in aria-label
            aria_label = attrs["aria-label"].replace('"', '\\"')
            selector_parts.append(f'[aria-label="{aria_label}"]')
        
        # If we have enough specificity, use it
        if len(selector_parts) > 1:
            return ''.join(selector_parts)
        
        # Try class-based selector
        if attrs.get('class'):
            classes = attrs['class'].strip().split()
            if classes:
                # Use first meaningful class
                for cls in classes:
                    if cls and not cls.startswith('_'):  # Skip private classes
                        return f'{tag}.{cls}'
        
        # Try text content for buttons and links
        if tag in ['button', 'a'] and element_info.get('text'):
            text = element_info['text'][:30].replace('"', '\\"')  # Escape quotes
            return f'{tag}:has-text("{text}")'
        
        # Last resort - use exact text match
        if element_info.get('text'):
            return f'text="{element_info["text"]}"'
        
        # Ultimate fallback
        return tag