"""
Immediate fixes to get browser-use next-gen working

Apply these changes to get basic functionality:
"""

# 1. FIX: In browser_use/core/resolver/service.py around line 89
# ADD the vision strategy to the strategies list:
"""
def __init__(self, vision_engine, dom_processor, accessibility_processor, perception_fusion, llm):
    # ... existing code ...
    
    # Initialize resolution strategies
    self.strategies = []
    
    # ADD THIS: Vision strategy FIRST if available
    if vision_engine and llm:
        from browser_use.core.resolver.vision_strategy import VisionResolutionStrategy
        self.strategies.append(VisionResolutionStrategy(llm))
    
    if llm:
        # LLM finder for intelligent element matching
        self.strategies.append(LLMFinderStrategy(llm))
    
    self.strategies.append(SimpleFinderStrategy())  # Basic fallback
"""

# 2. FIX: In browser_use/core/resolver/llm_element_finder.py around line 178
# REPLACE the error handling to not stop on JSON parse errors:
"""
except json.JSONDecodeError as e:
    logger.warning(f"JSON decode error in LLM response: {e}")
    # Try to extract key values manually
    import re
    index_match = re.search(r'"?index"?\s*:\s*(-?\d+)', response_text)
    
    if index_match:
        index = int(index_match.group(1))
        if 0 <= index < len(page_elements):
            element_info = page_elements[index]
            # Still try to return the element
            selector = await self._create_selector(page, element_info)
            element_handle = await page.query_selector(selector)
            
            if element_handle:
                box = await element_handle.bounding_box()
                return PerceptionElement(
                    type=element_info['tag'],
                    text=element_info.get('text', ''),
                    selector=selector,
                    bounding_box=BoundingBox(**box) if box else None,
                    confidence=0.7,  # Lower confidence due to parse error
                    is_interactive=True,
                    is_visible=True
                )
    
    logger.warning("Could not find element after JSON parse error")
    return None
except Exception as e:
    logger.warning(f"Error in LLM element finding: {e}")
    return None  # Don't raise - let other strategies try
"""

# 3. FIX: In browser_use/core/orchestrator/service.py around line 525
# ENSURE vision is enabled in the test:
"""
# In the test file tests/test_amazon_search.py, change line 35:
use_vision=True,  # ENABLE vision (was False)
"""

# 4. FIX: In browser_use/core/orchestrator/service.py around line 253
# BETTER handling of interaction intents that might be keyboard actions:
"""
# Around line 253, improve the keyboard detection:
desc_lower = sub_intent.description.lower()
if any(phrase in desc_lower for phrase in [
    'press enter', 'hit enter', 'press return', 'hit return',
    'submit the search', 'submit search', 'press the enter key'
]):
    # This is definitely a keyboard action
    logger.debug("Detected keyboard action: Enter key")
    actions.append(Action(
        id=f"{sub_intent.id}_keyboard",
        type=ActionType.KEYBOARD,
        parameters={"key": "Enter"}
    ))
    return actions  # Don't try to find an element
"""

# 5. FIX: In browser_use/agent/next_gen_agent.py
# ADD the _get_perception_data method if missing:
"""
async def _get_perception_data(self) -> Dict[str, Any]:
    '''Get perception data for current page'''
    if not self.current_page:
        return {}
    
    page = self.current_page
    
    # Take screenshot
    screenshot = await page.screenshot()
    screenshot_b64 = base64.b64encode(screenshot).decode()
    
    # Extract page elements
    elements = await page.evaluate('''() => {
        const interactiveSelectors = [
            'input[type="search"]', 'input[type="text"]', 'input:not([type="hidden"])',
            'button', '[type="submit"]', '[role="button"]',
            'a', 'select', 'textarea',
            '[role="searchbox"]', '[role="textbox"]',
            '[onclick]', '[tabindex]:not([tabindex="-1"])'
        ];
        
        const elements = [];
        const seen = new Set();
        
        for (const selector of interactiveSelectors) {
            const found = document.querySelectorAll(selector);
            for (const el of found) {
                if (seen.has(el) || !el.offsetParent) continue;
                seen.add(el);
                
                const rect = el.getBoundingClientRect();
                elements.push({
                    tag: el.tagName.toLowerCase(),
                    text: el.textContent?.trim().substring(0, 100) || '',
                    type: el.type || el.getAttribute('type') || '',
                    role: el.getAttribute('role') || '',
                    placeholder: el.placeholder || '',
                    name: el.name || '',
                    id: el.id || '',
                    className: el.className || '',
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                    isInput: el.tagName === 'INPUT' || el.tagName === 'TEXTAREA',
                    isButton: el.tagName === 'BUTTON' || el.type === 'submit' || el.getAttribute('role') === 'button',
                    isSearchInput: el.type === 'search' || el.name?.includes('search') || el.id?.includes('search'),
                    isVisible: true
                });
            }
        }
        
        return elements;
    }''')
    
    return {
        'page': page,
        'url': page.url,
        'screenshot': screenshot_b64,
        'page_elements': elements,
        'timestamp': datetime.now()
    }
"""

# 6. OPTIONAL but recommended: Add debug logging
"""
# In browser_use/core/resolver/service.py, add debug logging:
logger.debug(f"Trying {len(self.strategies)} resolution strategies")
for i, strategy in enumerate(self.strategies):
    logger.debug(f"Strategy {i}: {strategy.__class__.__name__}")
"""

# 7. Rate limiting fix - add delay in execute_task
"""
# In browser_use/agent/next_gen_agent.py, in execute_task method:
# Add a small delay to avoid rate limits
await asyncio.sleep(0.5)  # Add before LLM calls
"""