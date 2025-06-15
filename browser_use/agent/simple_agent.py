"""Simple, fast, and effective browser agent"""

import asyncio
import logging
from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from playwright.async_api import Page

from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile

logger = logging.getLogger(__name__)


class SimpleAgent:
    """Direct browser automation without overcomplicated layers"""
    
    def __init__(self, llm: BaseChatModel, browser_profile: Optional[BrowserProfile] = None):
        self.llm = llm
        self.browser_profile = browser_profile or BrowserProfile()
        self.browser_session = None
        self.page = None
        
    async def initialize(self):
        """Start browser"""
        self.browser_session = BrowserSession(browser_profile=self.browser_profile)
        await self.browser_session.start()
        
        # Get page
        if self.browser_session.browser_context:
            pages = self.browser_session.browser_context.pages
            if pages:
                self.page = pages[0]
            else:
                self.page = await self.browser_session.browser_context.new_page()
        else:
            raise Exception("Failed to create browser context")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.browser_session:
            await self.browser_session.close()
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute a task directly without multiple layers"""
        try:
            # Simple task analysis - just ask what to do
            prompt = f"""You are controlling a web browser. The user wants to: {task}

Current URL: {self.page.url if self.page else 'about:blank'}

What single action should I take? Be specific and direct.

Respond with ONE of these formats:

For navigation:
ACTION: navigate
URL: <url>

For typing:
ACTION: type
SELECTOR: <css selector or text description>
TEXT: <text to type>

For clicking:
ACTION: click
SELECTOR: <css selector or text description>

For pressing keys:
ACTION: key
KEY: <Enter|Tab|Escape|etc>

For scrolling:
ACTION: scroll
DIRECTION: <up|down>

For waiting:
ACTION: wait
SECONDS: <number>

Choose the most direct action to accomplish the task."""

            response = await self.llm.ainvoke(prompt)
            action_text = response.content.strip()
            
            # Parse action
            lines = action_text.split('\n')
            action_type = None
            params = {}
            
            for line in lines:
                if line.startswith('ACTION:'):
                    action_type = line.split(':', 1)[1].strip().lower()
                elif ':' in line:
                    key, value = line.split(':', 1)
                    params[key.strip().lower()] = value.strip()
            
            if not action_type:
                return {"success": False, "error": "Could not parse action"}
            
            # Execute action
            if action_type == 'navigate':
                url = params.get('url', '')
                if not url.startswith(('http://', 'https://')):
                    url = f'https://{url}'
                await self.page.goto(url)
                return {"success": True, "action": "navigated", "url": url}
                
            elif action_type == 'type':
                selector = params.get('selector', '')
                text = params.get('text', '')
                
                # Find element
                element = await self._find_element(selector)
                if element:
                    await element.fill(text)
                    return {"success": True, "action": "typed", "text": text}
                else:
                    return {"success": False, "error": f"Could not find element: {selector}"}
                    
            elif action_type == 'click':
                selector = params.get('selector', '')
                
                # Find element
                element = await self._find_element(selector)
                if element:
                    await element.click()
                    return {"success": True, "action": "clicked"}
                else:
                    return {"success": False, "error": f"Could not find element: {selector}"}
                    
            elif action_type == 'key':
                key = params.get('key', 'Enter')
                await self.page.keyboard.press(key)
                return {"success": True, "action": "pressed_key", "key": key}
                
            elif action_type == 'scroll':
                direction = params.get('direction', 'down')
                amount = 500
                if direction == 'down':
                    await self.page.evaluate(f"window.scrollBy(0, {amount})")
                else:
                    await self.page.evaluate(f"window.scrollBy(0, -{amount})")
                return {"success": True, "action": "scrolled", "direction": direction}
                
            elif action_type == 'wait':
                seconds = float(params.get('seconds', 1))
                await asyncio.sleep(seconds)
                return {"success": True, "action": "waited", "seconds": seconds}
                
            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _find_element(self, selector: str):
        """Find element by selector or description"""
        # First try as CSS selector
        if selector.startswith(('#', '.', '[')) or ' ' not in selector:
            try:
                element = await self.page.wait_for_selector(selector, timeout=5000)
                if element:
                    return element
            except:
                pass
        
        # If that fails, try to find by description
        # Take screenshot
        screenshot = await self.page.screenshot()
        
        # Ask LLM to find element
        import base64
        screenshot_b64 = base64.b64encode(screenshot).decode()
        
        prompt = f"""Look at this screenshot and find: {selector}

Return the CSS selector for this element. Common patterns:
- Search boxes: input[type="search"], textarea, #searchInput
- Buttons: button, input[type="submit"], [role="button"]
- Links: a (especially with meaningful text)
- First search result: Usually an <a> tag with substantial text, not in header

Just return the CSS selector, nothing else."""

        from langchain_core.messages import HumanMessage
        
        response = await self.llm.ainvoke([
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
            ])
        ])
        
        css_selector = response.content.strip()
        
        # Remove any markdown or quotes
        css_selector = css_selector.strip('`"\'')
        
        try:
            element = await self.page.wait_for_selector(css_selector, timeout=5000)
            return element
        except:
            # Last resort - try text matching
            if 'first' in selector.lower() and 'result' in selector.lower():
                # Special case for search results
                try:
                    # Find first substantial link not in header
                    element = await self.page.locator('a').filter(has_text=True).nth(5).element_handle()
                    return element
                except:
                    pass
            
            return None