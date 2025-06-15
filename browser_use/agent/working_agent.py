"""A browser agent that actually works"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from playwright.async_api import Page, ElementHandle
import base64

from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile

logger = logging.getLogger(__name__)


class WorkingAgent:
    """Simple, direct browser automation that works"""
    
    def __init__(self, llm, browser_profile: Optional[BrowserProfile] = None):
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
    
    async def cleanup(self):
        """Clean up"""
        if self.browser_session:
            await self.browser_session.close()
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute task with minimal complexity"""
        try:
            task_lower = task.lower()
            
            # Navigation
            if 'go to' in task_lower or 'navigate' in task_lower:
                # Extract URL
                import re
                url_match = re.search(r'(?:go to|navigate to)\s+(\S+)', task_lower)
                if url_match:
                    url = url_match.group(1)
                    if not url.startswith(('http://', 'https://')):
                        url = f'https://{url}'
                    await self.page.goto(url)
                    return {"success": True, "action": "navigated", "url": url}
            
            # Search (combined type + submit)
            elif 'search for' in task_lower:
                # Extract search query
                import re
                query_match = re.search(r"search for\s+['\"]?([^'\"]+)['\"]?", task_lower)
                if query_match:
                    query = query_match.group(1).strip()
                    
                    # Find search box
                    search_box = await self._find_search_box()
                    if search_box:
                        await search_box.fill(query)
                        await self.page.keyboard.press('Enter')
                        await self.page.wait_for_load_state('networkidle', timeout=5000)
                        return {"success": True, "action": "searched", "query": query}
                    else:
                        return {"success": False, "error": "Could not find search box"}
            
            # Type text
            elif 'type' in task_lower:
                # Extract text
                import re
                text_match = re.search(r"type\s+['\"]?([^'\"]+)['\"]?", task_lower)
                if text_match:
                    text = text_match.group(1).strip()
                    
                    # Find input field
                    element = await self._find_input_field(task)
                    if element:
                        await element.fill(text)
                        return {"success": True, "action": "typed", "text": text}
                    else:
                        return {"success": False, "error": "Could not find input field"}
            
            # Click
            elif 'click' in task_lower:
                element = await self._find_clickable(task)
                if element:
                    await element.click()
                    await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                    return {"success": True, "action": "clicked"}
                else:
                    return {"success": False, "error": "Could not find element to click"}
            
            # Press key
            elif 'press' in task_lower and ('enter' in task_lower or 'return' in task_lower):
                await self.page.keyboard.press('Enter')
                return {"success": True, "action": "pressed_key", "key": "Enter"}
            
            # Scroll
            elif 'scroll' in task_lower:
                direction = 'down' if 'down' in task_lower else 'up'
                amount = 500
                if direction == 'down':
                    await self.page.evaluate(f"window.scrollBy(0, {amount})")
                else:
                    await self.page.evaluate(f"window.scrollBy(0, -{amount})")
                return {"success": True, "action": "scrolled", "direction": direction}
            
            # Fallback - ask LLM what to do
            else:
                return await self._llm_guided_action(task)
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _find_search_box(self) -> Optional[ElementHandle]:
        """Find search input box"""
        # Try common selectors
        selectors = [
            'input[type="search"]',
            'input[name*="search"]',
            'input[placeholder*="search" i]',
            'input[aria-label*="search" i]',
            '#search',
            '.search-input',
            'textarea[placeholder*="search" i]',
            'input[type="text"]'  # Last resort
        ]
        
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=1000)
                if element and await element.is_visible():
                    return element
            except:
                continue
        
        return None
    
    async def _find_input_field(self, task: str) -> Optional[ElementHandle]:
        """Find input field based on task description"""
        # Try to find by label or placeholder
        task_lower = task.lower()
        
        # Common field names
        if 'username' in task_lower or 'user' in task_lower:
            selectors = ['input[name*="user"]', 'input[type="text"]', '#username']
        elif 'password' in task_lower:
            selectors = ['input[type="password"]', 'input[name*="pass"]']
        elif 'email' in task_lower:
            selectors = ['input[type="email"]', 'input[name*="email"]']
        else:
            selectors = ['input[type="text"]:visible', 'textarea:visible']
        
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=1000)
                if element and await element.is_visible():
                    return element
            except:
                continue
        
        return None
    
    async def _find_clickable(self, task: str) -> Optional[ElementHandle]:
        """Find clickable element"""
        task_lower = task.lower()
        
        # Special case: search results
        if 'first' in task_lower and ('result' in task_lower or 'link' in task_lower):
            return await self._find_first_search_result()
        
        # Try text-based search first
        if 'click on' in task_lower:
            # Extract text after "click on"
            import re
            text_match = re.search(r'click on\s+(.+?)(?:\s|$)', task_lower)
            if text_match:
                text = text_match.group(1).strip('"\'')
                
                # Try to find by text
                try:
                    element = await self.page.get_by_text(text).first.element_handle()
                    if element:
                        return element
                except:
                    pass
        
        # Blue links
        if 'blue link' in task_lower:
            try:
                # Find links that are likely search results
                links = await self.page.locator('a:visible').all()
                for link in links:
                    # Check if it's in the main content area
                    box = await link.bounding_box()
                    if box and box['y'] > 200:  # Not in header
                        text = await link.text_content()
                        if text and len(text) > 20:  # Substantial text
                            return await link.element_handle()
            except:
                pass
        
        return None
    
    async def _find_first_search_result(self) -> Optional[ElementHandle]:
        """Find first search result link"""
        try:
            # Wait a bit for results
            await self.page.wait_for_timeout(1000)
            
            # Get all links
            all_links = await self.page.locator('a:visible').all()
            
            # Find good candidates
            for link in all_links:
                try:
                    text = await link.text_content()
                    if not text:
                        continue
                    
                    text = text.strip()
                    
                    # Check href
                    href = await link.get_attribute('href')
                    if not href or href == '#':
                        continue
                    
                    # Check position
                    box = await link.bounding_box()
                    if not box or box['y'] < 200:  # Skip header
                        continue
                    
                    # Skip navigation
                    skip_words = ['sign in', 'log in', 'about', 'privacy', 'terms', 'help']
                    if any(word in text.lower() for word in skip_words):
                        continue
                    
                    # Found a good candidate
                    if len(text) > 15:  # Substantial text
                        logger.info(f"Found search result: {text[:50]}...")
                        return await link.element_handle()
                        
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error finding search result: {e}")
        
        return None
    
    async def _llm_guided_action(self, task: str) -> Dict[str, Any]:
        """Use LLM with screenshot for complex tasks"""
        try:
            # Take screenshot
            screenshot = await self.page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot).decode()
            
            prompt = f"""Look at this screenshot and help me: {task}

I need you to identify what element to interact with and how.

Return ONLY a JSON object like this:
{{
    "action": "click|type|select",
    "selector": "CSS selector for the element",
    "value": "text to type if action is type"
}}

Be specific with the selector."""

            from langchain_core.messages import HumanMessage
            
            response = await self.llm.ainvoke([
                HumanMessage(content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                ])
            ])
            
            # Parse response
            import json
            import re
            
            response_text = response.content
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group())
                
                if data['action'] == 'click':
                    element = await self.page.wait_for_selector(data['selector'], timeout=5000)
                    await element.click()
                    return {"success": True, "action": "clicked"}
                    
                elif data['action'] == 'type':
                    element = await self.page.wait_for_selector(data['selector'], timeout=5000)
                    await element.fill(data.get('value', ''))
                    return {"success": True, "action": "typed"}
            
            return {"success": False, "error": "Could not parse LLM response"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}