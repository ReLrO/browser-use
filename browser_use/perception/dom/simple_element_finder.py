"""
Simple element finder that actually works with real DOM
"""

from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from browser_use.perception.base import PerceptionElement, BoundingBox


class SimpleElementFinder:
    """Simple but effective element finder using Playwright selectors"""
    
    # Common selector patterns for different element types
    SELECTOR_PATTERNS = {
        'username': [
            'input[name="session_key"]',
            'input[name="username"]',
            'input[name="email"]',
            'input[type="email"]',
            'input[id="username"]',
            'input[id="email"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="username" i]',
        ],
        'password': [
            'input[name="session_password"]',
            'input[name="password"]',
            'input[type="password"]',
            'input[id="password"]',
        ],
        'submit': [
            'button[type="submit"]',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            'button:has-text("Submit")',
            'input[type="submit"]',
        ],
        'button': [
            'button',
            'a[role="button"]',
            'input[type="button"]',
            'input[type="submit"]',
        ]
    }
    
    @staticmethod
    async def find_element_by_description(
        page: Page, 
        description: str,
        element_type: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Optional[PerceptionElement]:
        """Find element by description using smart selector strategies"""
        
        description_lower = description.lower()
        
        # Try specific patterns based on description
        if any(word in description_lower for word in ['username', 'email', 'user']):
            selectors = SimpleElementFinder.SELECTOR_PATTERNS['username']
        elif any(word in description_lower for word in ['password', 'pass']):
            selectors = SimpleElementFinder.SELECTOR_PATTERNS['password']
        elif any(word in description_lower for word in ['sign in', 'log in', 'submit']):
            selectors = SimpleElementFinder.SELECTOR_PATTERNS['submit']
        elif element_type == 'button':
            selectors = SimpleElementFinder.SELECTOR_PATTERNS['button']
        else:
            # Build custom selectors based on attributes
            selectors = []
            
            if attributes:
                # Build selector from attributes - combine them for precision
                base = element_type or 'input'
                
                # Build a precise selector combining all attributes
                if attributes.get('name') and attributes.get('type'):
                    # Most precise - both name and type
                    selectors.insert(0, f'{base}[name="{attributes["name"]}"][type="{attributes["type"]}"]')
                
                # Individual attribute selectors as fallback
                if attributes.get('name'):
                    selectors.append(f'{base}[name="{attributes["name"]}"]')
                if attributes.get('type'):
                    selectors.append(f'{base}[type="{attributes["type"]}"]')
                if attributes.get('id'):
                    selectors.append(f'#{attributes["id"]}')
            
            # Add text-based selectors
            if element_type:
                selectors.extend([
                    f'{element_type}:has-text("{description}")',
                    f'{element_type}[aria-label*="{description}" i]',
                ])
        
        # Try each selector
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    # Get element details
                    tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                    text_content = await element.text_content()
                    
                    # Get bounding box
                    box = await element.bounding_box()
                    bounding_box = None
                    if box:
                        bounding_box = BoundingBox(
                            x=box['x'],
                            y=box['y'],
                            width=box['width'],
                            height=box['height']
                        )
                    
                    # Get attributes
                    attrs = await element.evaluate('''el => {
                        const attrs = {};
                        for (const attr of el.attributes) {
                            attrs[attr.name] = attr.value;
                        }
                        return attrs;
                    }''')
                    
                    return PerceptionElement(
                        type=tag_name,
                        text=text_content or '',
                        selector=selector,
                        attributes=attrs,
                        bounding_box=bounding_box,
                        confidence=0.9,
                        is_interactive=tag_name in ['button', 'input', 'select', 'textarea', 'a'],
                        is_visible=True
                    )
            except:
                continue
        
        return None
    
    @staticmethod
    async def find_elements_by_type(page: Page, element_type: str) -> List[PerceptionElement]:
        """Find all elements of a specific type"""
        elements = []
        
        try:
            handles = await page.query_selector_all(element_type)
            
            for handle in handles:
                if await handle.is_visible():
                    text_content = await handle.text_content()
                    
                    # Get bounding box
                    box = await handle.bounding_box()
                    bounding_box = None
                    if box:
                        bounding_box = BoundingBox(
                            x=box['x'],
                            y=box['y'],
                            width=box['width'],
                            height=box['height']
                        )
                    
                    elements.append(PerceptionElement(
                        type=element_type,
                        text=text_content or '',
                        selector=f'{element_type}:has-text("{text_content[:20]}")' if text_content else element_type,
                        bounding_box=bounding_box,
                        confidence=0.8,
                        is_interactive=element_type in ['button', 'input', 'select', 'textarea', 'a'],
                        is_visible=True
                    ))
        except:
            pass
        
        return elements