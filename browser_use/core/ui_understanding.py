"""Universal UI understanding system that learns patterns from any website"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class UIPatternType(str, Enum):
    """Common UI patterns found across websites"""
    SEARCH_BOX = "search_box"
    LOGIN_FORM = "login_form"
    NAVIGATION_MENU = "navigation_menu"
    SUBMIT_BUTTON = "submit_button"
    TOGGLE_SWITCH = "toggle_switch"
    TAB_NAVIGATION = "tab_navigation"
    MODAL_DIALOG = "modal_dialog"
    DROPDOWN_MENU = "dropdown_menu"
    PAGINATION = "pagination"
    FILTER_CONTROLS = "filter_controls"
    SORT_CONTROLS = "sort_controls"
    RATING_FILTER = "rating_filter"
    PRICE_FILTER = "price_filter"
    RESULTS_LIST = "results_list"


@dataclass
class UIPattern:
    """Represents a detected UI pattern"""
    type: UIPatternType
    confidence: float
    elements: List[Dict[str, Any]]
    relationships: Dict[str, Any]
    context: Dict[str, Any]


class UniversalUIAnalyzer:
    """Analyzes any webpage to understand its UI patterns and relationships"""
    
    def __init__(self):
        self._pattern_cache = {}
    
    async def analyze_page(self, page) -> Dict[str, Any]:
        """Analyze a page to understand its UI structure and patterns"""
        
        # Extract comprehensive UI information
        ui_data = await page.evaluate("""() => {
            // Helper functions
            const getElementRole = (el) => {
                // Determine the semantic role of an element
                const tag = el.tagName.toLowerCase();
                const type = el.getAttribute('type');
                const role = el.getAttribute('role');
                
                if (role) return role;
                if (tag === 'button' || type === 'submit' || type === 'button') return 'button';
                if (tag === 'a') return 'link';
                if (tag === 'input') {
                    if (type === 'search' || el.name?.includes('search') || el.id?.includes('search')) return 'searchbox';
                    if (type === 'text' || type === 'email') return 'textbox';
                    if (type === 'password') return 'password';
                    if (type === 'checkbox') return 'checkbox';
                    if (type === 'radio') return 'radio';
                }
                if (tag === 'select') return 'combobox';
                if (tag === 'textarea') return 'textbox';
                return tag;
            };
            
            const getVisualProximity = (el1, el2) => {
                // Calculate visual proximity between two elements
                const rect1 = el1.getBoundingClientRect();
                const rect2 = el2.getBoundingClientRect();
                
                const centerX1 = rect1.x + rect1.width / 2;
                const centerY1 = rect1.y + rect1.height / 2;
                const centerX2 = rect2.x + rect2.width / 2;
                const centerY2 = rect2.y + rect2.height / 2;
                
                const distance = Math.sqrt(
                    Math.pow(centerX2 - centerX1, 2) + 
                    Math.pow(centerY2 - centerY1, 2)
                );
                
                return {
                    distance: distance,
                    horizontal: Math.abs(centerX2 - centerX1),
                    vertical: Math.abs(centerY2 - centerY1),
                    isAligned: rect1.y === rect2.y || rect1.x === rect2.x,
                    isAdjacent: (
                        (Math.abs(rect1.right - rect2.left) < 20) ||
                        (Math.abs(rect2.right - rect1.left) < 20) ||
                        (Math.abs(rect1.bottom - rect2.top) < 20) ||
                        (Math.abs(rect2.bottom - rect1.top) < 20)
                    )
                };
            };
            
            const detectPatterns = (elements) => {
                const patterns = [];
                
                // Detect search patterns
                elements.forEach((el, idx) => {
                    if (el.role === 'searchbox' || el.role === 'textbox') {
                        // Look for nearby submit buttons
                        const nearbyButtons = elements.filter((other, otherIdx) => {
                            if (otherIdx === idx || other.role !== 'button') return false;
                            const proximity = getVisualProximity(
                                document.querySelector(el.selector),
                                document.querySelector(other.selector)
                            );
                            return proximity.distance < 100 && proximity.isAdjacent;
                        });
                        
                        if (nearbyButtons.length > 0) {
                            patterns.push({
                                type: 'search_pattern',
                                inputIndex: idx,
                                buttonIndices: nearbyButtons.map(b => elements.indexOf(b)),
                                confidence: 0.9
                            });
                        }
                    }
                });
                
                // Detect form patterns
                const forms = document.querySelectorAll('form');
                forms.forEach(form => {
                    const formElements = elements.filter(el => {
                        const domEl = document.querySelector(el.selector);
                        return domEl && form.contains(domEl);
                    });
                    
                    if (formElements.length > 0) {
                        patterns.push({
                            type: 'form_pattern',
                            elements: formElements.map(el => elements.indexOf(el)),
                            hasSubmit: formElements.some(el => el.role === 'button'),
                            confidence: 0.95
                        });
                    }
                });
                
                // Detect filter controls (checkboxes, links with "filter" text)
                const filterElements = elements.filter(el => {
                    const text = (el.text || '').toLowerCase();
                    const isCheckbox = el.role === 'checkbox' || el.attributes.type === 'checkbox';
                    const isFilterLink = (el.role === 'link' || el.role === 'button') && 
                        (text.includes('filter') || text.includes('stars') || text.includes('rating'));
                    return isCheckbox || isFilterLink;
                });
                
                if (filterElements.length > 0) {
                    patterns.push({
                        type: 'filter_controls',
                        elements: filterElements.map(el => elements.indexOf(el)),
                        confidence: 0.8
                    });
                }
                
                // Detect sort controls (dropdowns or links with "sort" text)
                const sortElements = elements.filter(el => {
                    const text = (el.text || '').toLowerCase();
                    const isDropdown = el.role === 'combobox' || el.attributes.type === 'select';
                    const isSortLink = (el.role === 'link' || el.role === 'button') && 
                        (text.includes('sort') || text.includes('price') || text.includes('relevance'));
                    return isDropdown || isSortLink;
                });
                
                if (sortElements.length > 0) {
                    patterns.push({
                        type: 'sort_controls',
                        elements: sortElements.map(el => elements.indexOf(el)),
                        confidence: 0.85
                    });
                }
                
                // Detect rating filters specifically
                const ratingElements = elements.filter(el => {
                    const text = (el.text || '').toLowerCase();
                    return text.includes('star') || text.includes('rating') || 
                           text.includes('★') || text.includes('☆');
                });
                
                if (ratingElements.length > 0) {
                    patterns.push({
                        type: 'rating_filter',
                        elements: ratingElements.map(el => elements.indexOf(el)),
                        confidence: 0.9
                    });
                }
                
                return patterns;
            };
            
            // Get all interactive elements
            const interactiveElements = [];
            const selectors = [
                'button', 'a', 'input', 'select', 'textarea',
                '[role="button"]', '[role="link"]', '[onclick]',
                '[tabindex]:not([tabindex="-1"])'
            ];
            
            const seen = new Set();
            selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    if (seen.has(el) || !el.offsetParent) return;
                    seen.add(el);
                    
                    const rect = el.getBoundingClientRect();
                    const computedStyle = window.getComputedStyle(el);
                    
                    // Build a unique selector
                    let uniqueSelector = '';
                    if (el.id) {
                        uniqueSelector = '#' + el.id;
                    } else {
                        let path = [];
                        let current = el;
                        while (current && current !== document.body) {
                            let selector = current.tagName.toLowerCase();
                            if (current.className) {
                                const classes = Array.from(current.classList)
                                    .filter(c => c && !c.includes(' '))
                                    .slice(0, 2); // Limit classes
                                if (classes.length) {
                                    selector += '.' + classes.join('.');
                                }
                            }
                            path.unshift(selector);
                            current = current.parentElement;
                        }
                        uniqueSelector = path.join(' > ');
                    }
                    
                    interactiveElements.push({
                        selector: uniqueSelector,
                        role: getElementRole(el),
                        text: el.textContent.trim().substring(0, 100),
                        rect: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        },
                        style: {
                            fontSize: computedStyle.fontSize,
                            fontWeight: computedStyle.fontWeight,
                            color: computedStyle.color,
                            backgroundColor: computedStyle.backgroundColor
                        },
                        attributes: {
                            type: el.type,
                            name: el.name,
                            placeholder: el.placeholder,
                            'aria-label': el.getAttribute('aria-label'),
                            title: el.title
                        }
                    });
                });
            });
            
            // Detect patterns
            const patterns = detectPatterns(interactiveElements);
            
            // Analyze layout
            const layout = {
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                hasHeader: !!document.querySelector('header'),
                hasNav: !!document.querySelector('nav'),
                hasMain: !!document.querySelector('main'),
                hasFooter: !!document.querySelector('footer'),
                hasSidebar: !!document.querySelector('aside')
            };
            
            return {
                elements: interactiveElements,
                patterns: patterns,
                layout: layout,
                documentTitle: document.title,
                url: window.location.href
            };
        }""")
        
        return ui_data
    
    def find_ui_pattern(self, ui_data: Dict[str, Any], pattern_type: str) -> Optional[UIPattern]:
        """Find a specific UI pattern in the analyzed data"""
        
        patterns = ui_data.get('patterns', [])
        elements = ui_data.get('elements', [])
        
        for pattern in patterns:
            if pattern['type'] == pattern_type:
                pattern_elements = []
                
                if pattern_type == 'search_pattern':
                    # Get search input and button
                    input_el = elements[pattern['inputIndex']]
                    pattern_elements.append(input_el)
                    
                    for btn_idx in pattern['buttonIndices']:
                        pattern_elements.append(elements[btn_idx])
                
                elif pattern_type == 'form_pattern':
                    # Get all form elements
                    for el_idx in pattern['elements']:
                        pattern_elements.append(elements[el_idx])
                
                return UIPattern(
                    type=UIPatternType.SEARCH_BOX if pattern_type == 'search_pattern' else UIPatternType.LOGIN_FORM,
                    confidence=pattern['confidence'],
                    elements=pattern_elements,
                    relationships=pattern,
                    context=ui_data.get('layout', {})
                )
        
        return None


class SmartElementMatcher:
    """Matches element descriptions to actual elements using intelligent pattern matching"""
    
    def __init__(self, llm):
        self.llm = llm
        self.ui_analyzer = UniversalUIAnalyzer()
    
    async def find_element_smart(self, page, description: str) -> Optional[Dict[str, Any]]:
        """Find an element using smart pattern matching"""
        
        # Analyze the page UI
        ui_data = await self.ui_analyzer.analyze_page(page)
        
        # Create a smarter prompt that understands UI patterns
        prompt = f"""You are an expert at understanding web UI/UX. Analyze this webpage structure and find the element that matches the user's intent.

User wants to: {description}

Page Analysis:
- Total interactive elements: {len(ui_data['elements'])}
- Detected patterns: {[p['type'] for p in ui_data['patterns']]}
- Layout: {ui_data['layout']}

Elements and Patterns:
{json.dumps(ui_data, indent=2)}

IMPORTANT PRINCIPLES:
1. Understand user intent, not just literal descriptions
2. "Press Enter" often means either:
   - Type in an input and press Enter key
   - Click the associated submit/search button
3. Consider element relationships and proximity
4. Icon buttons near inputs are usually submit buttons
5. Elements in the same form or container are related
6. For filters and sorting:
   - "4 stars and up" means clicking a rating filter (link, checkbox, or button)
   - "sort by price" means finding sort controls (dropdown or links)
   - Look for text containing stars (★), "rating", "filter", "sort", etc.
7. Complex UI actions may require multiple steps:
   - Opening dropdown menus before selecting options
   - Clicking filter checkboxes or links
   - Navigating through tabs or sections

Based on the UI analysis and patterns detected, which element best matches the user's intent?

Return the element index and reasoning.
Format: {{"index": <number>, "confidence": <0-1>, "reasoning": "<explanation>"}}
"""
        
        # Use rate limiting
        from browser_use.core.caching import rate_limiter
        await rate_limiter.acquire()
        
        try:
            response = await self.llm.ainvoke(prompt)
            rate_limiter.report_success()
            result = self._parse_response(response.content)
        except Exception as e:
            rate_limiter.report_error(e)
            raise
        
        if result and result['index'] >= 0:
            element = ui_data['elements'][result['index']]
            return {
                'selector': element['selector'],
                'confidence': result['confidence'],
                'element_data': element,
                'reasoning': result['reasoning']
            }
        
        return None
    
    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response"""
        try:
            import re
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return None


class AdaptiveActionExecutor:
    """Executes actions adaptively based on UI understanding"""
    
    def __init__(self, page, llm):
        self.page = page
        self.matcher = SmartElementMatcher(llm)
    
    async def execute_smart_action(self, description: str) -> Dict[str, Any]:
        """Execute an action using smart UI understanding"""
        
        # Special handling for keyboard actions
        if any(phrase in description.lower() for phrase in ['press enter', 'hit enter']):
            # First check if an input is focused
            focused = await self.page.evaluate('document.activeElement.tagName')
            if focused in ['INPUT', 'TEXTAREA']:
                await self.page.keyboard.press('Enter')
                return {'success': True, 'action': 'keyboard_enter'}
        
        # Find element using smart matching
        match = await self.matcher.find_element_smart(self.page, description)
        
        if match:
            selector = match['selector']
            
            # Determine action type from description
            desc_lower = description.lower()
            
            if any(word in desc_lower for word in ['type', 'enter', 'input', 'fill']):
                # Extract text to type
                import re
                text_match = re.search(r"['\"]([^'\"]+)['\"]", description)
                if text_match:
                    text = text_match.group(1)
                    await self.page.fill(selector, text)
                    return {'success': True, 'action': 'type', 'text': text}
            
            elif any(word in desc_lower for word in ['select', 'choose', 'pick']):
                # Handle select/dropdown
                import re
                value_match = re.search(r"['\"]([^'\"]+)['\"]", description)
                if value_match:
                    value = value_match.group(1)
                    await self.page.select_option(selector, label=value)
                    return {'success': True, 'action': 'select', 'value': value}
            
            else:
                # Default to click
                await self.page.click(selector)
                return {'success': True, 'action': 'click', 'selector': selector}
        
        return {'success': False, 'error': 'Could not find matching element'}