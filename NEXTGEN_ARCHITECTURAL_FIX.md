# Next-Generation Browser-Use: Architectural Fix Proposal

## Vision: True Intent-Driven, Vision-First Browser Automation

The current implementation has all the right components but they're not connected properly. Here's how to fix it to create a truly vision-based, intent-driven system.

## Core Philosophy

**"See First, Then Act"** - Like a human, the system should:
1. Look at the page (vision)
2. Understand what it sees (perception fusion)
3. Decide what to do (intent mapping)
4. Do it (action execution)

## Architectural Fixes

### 1. Make Vision the Primary Strategy

```python
# In browser_use/core/resolver/service.py
class MultiStrategyElementResolver:
    def __init__(self, vision_engine, dom_processor, accessibility_processor, perception_fusion, llm):
        self.strategies = []
        
        # Vision FIRST - this is the key change
        if vision_engine:
            from browser_use.core.resolver.vision_strategy import VisionResolutionStrategy
            self.strategies.append(VisionResolutionStrategy(llm))
        
        # Then intelligent LLM-based resolution
        if llm:
            self.strategies.append(LLMFinderStrategy(llm))
        
        # Simple fallback last
        self.strategies.append(SimpleFinderStrategy())
```

### 2. Fix the LLM Element Finder Error Handling

```python
# In browser_use/core/resolver/llm_element_finder.py
async def find_element(self, page, element_intent, max_elements=50, page_elements=None):
    try:
        # ... existing code ...
        
        # Better JSON extraction
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Try multiple JSON extraction methods
        result = None
        
        # Method 1: Find JSON block
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except:
                pass
        
        # Method 2: Try parsing after cleaning
        if not result:
            try:
                # Remove markdown code blocks if present
                cleaned = re.sub(r'```json?\s*|\s*```', '', response_text)
                result = json.loads(cleaned.strip())
            except:
                pass
        
        # Method 3: Extract key-value pairs manually
        if not result:
            index_match = re.search(r'"?index"?\s*:\s*(-?\d+)', response_text)
            confidence_match = re.search(r'"?confidence"?\s*:\s*(\d+\.?\d*)', response_text)
            
            if index_match:
                result = {
                    "index": int(index_match.group(1)),
                    "confidence": float(confidence_match.group(1)) if confidence_match else 0.8,
                    "reasoning": "Extracted from malformed JSON"
                }
        
        # If still no result, return None to try next strategy
        if not result:
            logger.warning("Could not parse LLM response, trying next strategy")
            return None
            
    except Exception as e:
        logger.warning(f"LLM element finder error: {e}, trying next strategy")
        return None  # Don't raise, let next strategy try
```

### 3. Implement Proper Perception Fusion

```python
# In browser_use/agent/next_gen_agent.py
async def _get_perception_data(self) -> Dict[str, Any]:
    """Get unified perception data from all systems"""
    page = self.current_page
    
    # Take screenshot first (for vision)
    screenshot = await page.screenshot()
    screenshot_b64 = base64.b64encode(screenshot).decode()
    
    # Get viewport info
    viewport = await page.viewport_size()
    
    perception_data = {
        'page': page,
        'url': page.url,
        'screenshot': screenshot_b64,
        'viewport': viewport,
        'timestamp': datetime.now()
    }
    
    # Run all perception systems in parallel
    tasks = []
    
    # Vision analysis
    if self.use_vision and self.vision_engine:
        tasks.append(('vision', self._get_vision_perception(screenshot)))
    
    # DOM analysis with proper element extraction
    tasks.append(('dom', self._get_dom_perception(page)))
    
    # Accessibility tree
    if self.use_accessibility:
        tasks.append(('accessibility', self._get_accessibility_perception(page)))
    
    # Wait for all
    results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
    
    # Merge results
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"{name} perception failed: {result}")
        else:
            perception_data[name] = result
    
    # CRITICAL: Ensure page_elements is available for resolvers
    if 'page_elements' not in perception_data:
        # Extract comprehensive element data
        elements = await self._extract_all_elements(page)
        perception_data['page_elements'] = elements
    
    return perception_data

async def _extract_all_elements(self, page: Page) -> List[Dict[str, Any]]:
    """Extract ALL interactive elements comprehensively"""
    return await page.evaluate("""() => {
        const elements = [];
        const seen = new WeakSet();
        
        // Get ALL potentially interactive elements
        const allElements = document.querySelectorAll('*');
        
        for (const el of allElements) {
            if (seen.has(el)) continue;
            
            // Check if element is interactive
            const isInteractive = 
                el.tagName.match(/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/i) ||
                el.hasAttribute('onclick') ||
                el.hasAttribute('href') ||
                el.getAttribute('role')?.match(/button|link|textbox|searchbox/i) ||
                el.style.cursor === 'pointer' ||
                el.tabIndex >= 0;
            
            if (!isInteractive) continue;
            
            seen.add(el);
            
            const rect = el.getBoundingClientRect();
            const isVisible = rect.width > 0 && rect.height > 0 && 
                window.getComputedStyle(el).visibility !== 'hidden';
            
            if (!isVisible) continue;
            
            elements.push({
                tag: el.tagName.toLowerCase(),
                text: el.textContent?.trim().substring(0, 200) || '',
                type: el.type || el.getAttribute('type') || '',
                role: el.getAttribute('role') || '',
                placeholder: el.placeholder || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                name: el.name || '',
                id: el.id || '',
                className: el.className || '',
                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                isInput: el.tagName.match(/^(INPUT|TEXTAREA)$/i) || el.getAttribute('role')?.match(/textbox|searchbox/i),
                isButton: el.tagName === 'BUTTON' || el.type === 'submit' || el.getAttribute('role') === 'button',
                isLink: el.tagName === 'A',
                isSearchInput: el.type === 'search' || el.name?.includes('search') || el.id?.includes('search'),
                isVisible: true
            });
        }
        
        return elements;
    })""")
```

### 4. Implement Vision-First Resolution

```python
# In browser_use/perception/vision/universal_ui_analyzer.py
async def find_element_for_action(self, screenshot: bytes, action_description: str) -> Dict[str, Any]:
    """Find element for specific action using vision"""
    
    screenshot_b64 = base64.b64encode(screenshot).decode()
    
    prompt = f"""You are looking at a webpage screenshot. Your task is to find the UI element that would accomplish this action:

Action: {action_description}

Analyze the screenshot and identify:
1. What type of element would accomplish this (button, input, link, etc.)
2. Where it is located on the page
3. What visual cues identify it (text, color, position, icons)

Think step-by-step:
- First, understand what the user wants to do
- Then, look for UI patterns that typically handle this action
- Consider multiple possibilities if the first isn't obvious

Return JSON:
{{
    "found": true/false,
    "element": {{
        "description": "what the element is",
        "element_type": "button/input/link/etc",
        "location": "top-left/top-center/top-right/center-left/center/center-right/bottom-left/bottom-center/bottom-right",
        "visual_appearance": "description of how it looks",
        "confidence": 0.0-1.0,
        "reasoning": "why you think this is the right element",
        "alternatives": ["description of other possible elements"]
    }}
}}"""
    
    messages = [
        SystemMessage(content=self._system_prompt),
        HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
        ])
    ]
    
    response = await self.llm.ainvoke(messages)
    
    # Parse response with error handling
    try:
        return json.loads(response.content)
    except:
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"found": False, "reason": "Could not parse response"}
```

### 5. Add Intelligent Action Recovery

```python
# In browser_use/core/orchestrator/service.py
async def _execute_action(self, action: Action) -> ActionResult:
    """Execute action with intelligent recovery"""
    
    # Try resolution with all strategies
    if action.type in [ActionType.CLICK, ActionType.TYPE, ActionType.SELECT]:
        resolved = False
        
        # Get fresh perception data for each attempt
        perception_data = await self._get_fresh_perception_data()
        
        # Try resolution
        if "element_intent" in action.parameters:
            element_intent = action.parameters["element_intent"]
            
            # Try primary resolution
            resolved_element = await self.element_resolver.resolve_element(
                element_intent, perception_data, self._execution_context["page"]
            )
            
            # If failed, try with enhanced description
            if not resolved_element:
                # Use vision to understand the page better
                screenshot = await self._execution_context["page"].screenshot()
                ui_analysis = await self.vision_engine.analyze_ui(
                    screenshot, 
                    f"Find element to: {element_intent.description}"
                )
                
                # Create enhanced intent with visual context
                enhanced_intent = ElementIntent(
                    description=f"{element_intent.description}. Visual context: {ui_analysis.get('suggestions', '')}"
                )
                
                resolved_element = await self.element_resolver.resolve_element(
                    enhanced_intent, perception_data, self._execution_context["page"]
                )
            
            action.target = resolved_element
    
    # Execute with better error handling
    try:
        handler = self._action_handlers.get(action.type)
        result_data = await handler(action, self._execution_context)
        return ActionResult(action_id=action.id, success=True, result_data=result_data)
    except Exception as e:
        # Try alternative approaches
        if action.type == ActionType.CLICK and "Enter" in str(element_intent.description):
            # Maybe they want to press Enter instead
            await self._execution_context["page"].keyboard.press("Enter")
            return ActionResult(action_id=action.id, success=True, result_data={"used": "keyboard"})
        
        raise
```

### 6. Implement Smart Caching

```python
# In browser_use/core/caching.py
class PerceptionCache:
    """Cache perception data to reduce API calls"""
    
    def __init__(self, ttl_seconds: float = 5.0):
        self.cache = {}
        self.ttl = ttl_seconds
    
    async def get_or_compute(self, key: str, compute_func):
        """Get from cache or compute if missing/expired"""
        now = time.time()
        
        if key in self.cache:
            entry, timestamp = self.cache[key]
            if now - timestamp < self.ttl:
                return entry
        
        # Compute new value
        result = await compute_func()
        self.cache[key] = (result, now)
        return result
    
    def invalidate(self, pattern: str = None):
        """Invalidate cache entries"""
        if pattern:
            # Invalidate matching keys
            to_remove = [k for k in self.cache if pattern in k]
            for k in to_remove:
                del self.cache[k]
        else:
            self.cache.clear()
```

## Testing Strategy

1. **Start Simple**: Test with basic pages first
2. **Enable Debug Logging**: See what each strategy is doing
3. **Visual Debugging**: Save annotated screenshots showing what the system sees
4. **Gradual Complexity**: Move from simple forms to complex SPAs

## Expected Outcome

With these changes:
1. The system will truly be vision-first
2. It will recover gracefully from failures
3. It will feel like an intelligent agent that understands what it sees
4. It will work on any website without hardcoding

## Implementation Priority

1. **Fix LLM JSON parsing** (immediate - stops crashes)
2. **Add vision strategy to resolver** (immediate - enables vision)
3. **Implement perception fusion** (high - unifies data flow)
4. **Add smart caching** (medium - improves performance)
5. **Enhance recovery strategies** (medium - improves reliability)

This is a true paradigm shift from DOM-based to vision-based automation.