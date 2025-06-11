"""
Enhanced scrolling actions for browser-use.
Provides advanced scrolling capabilities including container detection,
directional scrolling, and content search while scrolling.
"""

import asyncio
import logging
from typing import Optional, Union
from enum import Enum

from pydantic import BaseModel, Field
from playwright.async_api import Page

from browser_use.browser import BrowserSession
from browser_use.controller.service import Controller
from browser_use.controller.views import ActionResult

logger = logging.getLogger(__name__)


class ScrollDirection(str, Enum):
    """Scrolling directions"""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class ScrollStrategy(str, Enum):
    """Different scrolling strategies"""
    PIXELS = "pixels"
    VIEWPORT = "viewport"
    PAGE = "page"
    TO_END = "to_end"


class ScrollableAreaInfo(BaseModel):
    """Information about a scrollable area"""
    selector: str
    description: str
    dimensions: dict[str, float]
    scroll_info: dict[str, Union[float, bool]]
    is_visible: bool
    is_filter_panel: bool = False
    is_dropdown: bool = False


class EnhancedScrollAction(BaseModel):
    """Parameters for enhanced scroll action"""
    direction: ScrollDirection = Field(default=ScrollDirection.DOWN, description="Direction to scroll")
    amount: Optional[int] = Field(default=None, description="Amount to scroll in pixels (default: one viewport)")
    strategy: ScrollStrategy = Field(default=ScrollStrategy.PIXELS, description="Scrolling strategy to use")
    target_selector: Optional[str] = Field(default=None, description="CSS selector of container to scroll")
    smooth: bool = Field(default=False, description="Use smooth scrolling animation")


class ScrollToElementAction(BaseModel):
    """Parameters for scrolling to a specific element"""
    selector: str = Field(description="CSS selector of the element to scroll to")
    alignment: str = Field(default="center", description="Alignment: 'start', 'center', 'end', or 'nearest'")
    smooth: bool = Field(default=True, description="Use smooth scrolling animation")


class ScrollUntilVisibleAction(BaseModel):
    """Parameters for scrolling until content is visible"""
    text: str = Field(description="Text content to search for while scrolling")
    max_scrolls: int = Field(default=10, description="Maximum number of scroll attempts")
    scroll_amount: int = Field(default=300, description="Pixels to scroll each attempt")
    container_selector: Optional[str] = Field(default=None, description="Container to scroll (default: auto-detect)")


class InfiniteScrollAction(BaseModel):
    """Parameters for handling infinite scroll pages"""
    max_items: Optional[int] = Field(default=None, description="Maximum items to load (default: no limit)")
    max_scrolls: int = Field(default=20, description="Maximum scroll attempts")
    wait_time: float = Field(default=2.0, description="Seconds to wait for new content after each scroll")
    item_selector: Optional[str] = Field(default=None, description="CSS selector to count loaded items")


def register_enhanced_scroll_actions(controller: Controller) -> None:
    """Register all enhanced scrolling actions with the controller"""
    
    @controller.action(
        description="Enhanced scroll with multiple strategies and container detection",
        param_model=EnhancedScrollAction
    )
    async def enhanced_scroll(params: EnhancedScrollAction, browser_session: BrowserSession) -> ActionResult:
        """
        Enhanced scrolling with support for:
        - Multiple directions (up, down, left, right)
        - Different strategies (pixels, viewport percentage, full page, to end)
        - Specific container targeting
        - Smart container detection when no target specified
        """
        page = await browser_session.get_current_page()
        
        try:
            # Calculate scroll amount based on strategy
            if params.strategy == ScrollStrategy.VIEWPORT:
                viewport_width = await page.evaluate("window.innerWidth")
                viewport_height = await page.evaluate("window.innerHeight")
                if params.direction in [ScrollDirection.UP, ScrollDirection.DOWN]:
                    amount = viewport_height * (params.amount or 100) / 100
                else:
                    amount = viewport_width * (params.amount or 100) / 100
            elif params.strategy == ScrollStrategy.PAGE:
                viewport_width = await page.evaluate("window.innerWidth")
                viewport_height = await page.evaluate("window.innerHeight")
                if params.direction in [ScrollDirection.UP, ScrollDirection.DOWN]:
                    amount = viewport_height
                else:
                    amount = viewport_width
            elif params.strategy == ScrollStrategy.TO_END:
                # Will be handled in the JavaScript
                amount = 0
            else:  # PIXELS
                amount = params.amount or 300
            
            # Apply direction
            if params.direction in [ScrollDirection.UP, ScrollDirection.LEFT]:
                amount = -amount
            
            # JavaScript for enhanced scrolling
            js_code = """
            async (options) => {
                const { direction, amount, strategy, targetSelector, smooth } = options;
                
                // Find the scrollable container
                let container = null;
                
                if (targetSelector) {
                    container = document.querySelector(targetSelector);
                    if (!container) {
                        throw new Error(`Container not found: ${targetSelector}`);
                    }
                } else {
                    // Smart container detection
                    const bigEnough = el => el.clientHeight >= window.innerHeight * 0.5;
                    const canScroll = el =>
                        el &&
                        /(auto|scroll|overlay)/.test(getComputedStyle(el).overflowY) &&
                        el.scrollHeight > el.clientHeight &&
                        bigEnough(el);
                    
                    let el = document.activeElement;
                    while (el && !canScroll(el) && el !== document.body) el = el.parentElement;
                    
                    container = canScroll(el)
                        ? el
                        : [...document.querySelectorAll('*')].find(canScroll)
                        || document.scrollingElement
                        || document.documentElement;
                }
                
                // Calculate scroll values
                let scrollX = 0, scrollY = 0;
                
                if (strategy === 'to_end') {
                    if (direction === 'down') {
                        scrollY = container.scrollHeight - container.clientHeight - container.scrollTop;
                    } else if (direction === 'up') {
                        scrollY = -container.scrollTop;
                    } else if (direction === 'right') {
                        scrollX = container.scrollWidth - container.clientWidth - container.scrollLeft;
                    } else if (direction === 'left') {
                        scrollX = -container.scrollLeft;
                    }
                } else {
                    if (direction === 'down') scrollY = amount;
                    else if (direction === 'up') scrollY = amount;
                    else if (direction === 'right') scrollX = amount;
                    else if (direction === 'left') scrollX = amount;
                }
                
                // Perform scroll
                const isRoot = container === document.scrollingElement || 
                              container === document.documentElement || 
                              container === document.body;
                
                const scrollOptions = {
                    top: scrollY,
                    left: scrollX,
                    behavior: smooth ? 'smooth' : 'auto'
                };
                
                if (isRoot) {
                    window.scrollBy(scrollOptions);
                } else {
                    container.scrollBy(scrollOptions);
                }
                
                // Return scroll info
                return {
                    container: targetSelector || (isRoot ? 'window' : container.className || container.tagName),
                    scrolledX: scrollX,
                    scrolledY: scrollY,
                    newPosition: {
                        x: isRoot ? window.scrollX : container.scrollLeft,
                        y: isRoot ? window.scrollY : container.scrollTop
                    },
                    hasMoreContent: {
                        down: container.scrollTop < (container.scrollHeight - container.clientHeight - 5),
                        up: container.scrollTop > 5,
                        right: container.scrollLeft < (container.scrollWidth - container.clientWidth - 5),
                        left: container.scrollLeft > 5
                    }
                };
            }
            """
            
            options = {
                "direction": params.direction.value,
                "amount": amount,
                "strategy": params.strategy.value,
                "targetSelector": params.target_selector,
                "smooth": params.smooth
            }
            
            result = await page.evaluate(js_code, options)
            
            # Build message
            strategy_str = f" using {params.strategy.value} strategy" if params.strategy != ScrollStrategy.PIXELS else ""
            target_str = f" in {result['container']}" if params.target_selector else ""
            amount_str = f"{abs(result['scrolledY'] or result['scrolledX'])} pixels"
            
            msg = f"🔍 Scrolled {params.direction.value}{target_str} by {amount_str}{strategy_str}"
            
            if params.strategy == ScrollStrategy.TO_END:
                msg = f"🔍 Scrolled to the {params.direction.value}{target_str}"
            
            # Add info about remaining content
            more_content = []
            for direction, has_more in result['hasMoreContent'].items():
                if has_more:
                    more_content.append(direction)
            
            if more_content:
                msg += f" (more content available: {', '.join(more_content)})"
            else:
                msg += " (reached limit)"
            
            logger.info(msg)
            return ActionResult(
                data=result,
                extracted_content=msg,
                include_in_memory=True
            )
            
        except Exception as e:
            error_msg = f"Failed to perform enhanced scroll: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg, include_in_memory=True)
    
    @controller.action(
        description="Detect all scrollable areas on the page",
    )
    async def detect_scrollable_areas(browser_session: BrowserSession) -> ActionResult:
        """
        Detects and returns information about all scrollable areas on the page.
        Useful for understanding page structure before scrolling.
        """
        page = await browser_session.get_current_page()
        
        try:
            js_code = """
            () => {
                const scrollableElements = [];
                
                // Helper function to check if element is scrollable
                function isScrollable(element) {
                    const style = window.getComputedStyle(element);
                    const overflowY = style.overflowY;
                    const overflowX = style.overflowX;
                    const overflow = style.overflow;
                    
                    // Check if overflow allows scrolling
                    const hasScrollableOverflow = 
                        /(auto|scroll|overlay)/.test(overflowY) ||
                        /(auto|scroll|overlay)/.test(overflowX) ||
                        /(auto|scroll|overlay)/.test(overflow);
                    
                    // Check if element has content to scroll
                    const canScrollVertically = element.scrollHeight > element.clientHeight;
                    const canScrollHorizontally = element.scrollWidth > element.clientWidth;
                    
                    return hasScrollableOverflow && (canScrollVertically || canScrollHorizontally);
                }
                
                // Helper to get element description
                function getElementDescription(element) {
                    let desc = element.tagName.toLowerCase();
                    if (element.id) desc += `#${element.id}`;
                    if (element.className) {
                        const classes = element.className.toString().split(' ').filter(c => c).slice(0, 3);
                        if (classes.length) desc += `.${classes.join('.')}`;
                    }
                    
                    // Check for ARIA labels
                    const ariaLabel = element.getAttribute('aria-label');
                    if (ariaLabel) desc += ` [${ariaLabel}]`;
                    
                    // Check if it's a known pattern
                    if (element.classList.contains('scaffold-layout__aside')) {
                        desc += ' (LinkedIn Filter Panel)';
                    } else if (element.classList.contains('artdeco-typeahead__results-list')) {
                        desc += ' (LinkedIn Dropdown)';
                    }
                    
                    return desc;
                }
                
                // Find all scrollable elements
                const allElements = document.querySelectorAll('*');
                for (const element of allElements) {
                    if (isScrollable(element)) {
                        const rect = element.getBoundingClientRect();
                        const isVisible = rect.width > 0 && rect.height > 0 && 
                                        rect.top < window.innerHeight && 
                                        rect.bottom > 0;
                        
                        scrollableElements.push({
                            description: getElementDescription(element),
                            selector: element.tagName.toLowerCase() + 
                                     (element.id ? `#${element.id}` : '') +
                                     (element.className ? `.${element.className.toString().split(' ')[0]}` : ''),
                            dimensions: {
                                width: rect.width,
                                height: rect.height,
                                top: rect.top,
                                left: rect.left
                            },
                            scrollInfo: {
                                scrollHeight: element.scrollHeight,
                                clientHeight: element.clientHeight,
                                scrollTop: element.scrollTop,
                                canScrollDown: element.scrollTop < (element.scrollHeight - element.clientHeight),
                                canScrollUp: element.scrollTop > 0,
                                scrollablePixels: element.scrollHeight - element.clientHeight
                            },
                            isVisible: isVisible,
                            isFilterPanel: element.classList.contains('scaffold-layout__aside') ||
                                         element.classList.contains('search-filters-panel'),
                            isDropdown: element.classList.contains('artdeco-typeahead__results-list') ||
                                      element.classList.contains('typeahead-results')
                        });
                    }
                }
                
                // Sort by relevance (visible first, then by size)
                scrollableElements.sort((a, b) => {
                    if (a.isVisible !== b.isVisible) return b.isVisible ? 1 : -1;
                    return (b.dimensions.width * b.dimensions.height) - (a.dimensions.width * a.dimensions.height);
                });
                
                return {
                    count: scrollableElements.length,
                    elements: scrollableElements,
                    summary: {
                        hasFilterPanel: scrollableElements.some(e => e.isFilterPanel),
                        hasDropdown: scrollableElements.some(e => e.isDropdown),
                        visibleScrollables: scrollableElements.filter(e => e.isVisible).length
                    }
                };
            }
            """
            
            result = await page.evaluate(js_code)
            
            # Build helpful message
            msg_parts = [f"Found {result['count']} scrollable areas on the page"]
            
            if result['summary']['hasFilterPanel']:
                msg_parts.append("✓ Filter panel is scrollable")
            
            if result['summary']['hasDropdown']:
                msg_parts.append("✓ Dropdown menu is scrollable")
                
            msg_parts.append(f"\nVisible scrollable areas: {result['summary']['visibleScrollables']}")
            
            # List key scrollable areas
            for i, elem in enumerate(result['elements'][:5]):  # Top 5
                if elem['isVisible']:
                    scroll_status = []
                    if elem['scrollInfo']['canScrollDown']:
                        scroll_status.append("can scroll down")
                    if elem['scrollInfo']['canScrollUp']:
                        scroll_status.append("can scroll up")
                    
                    msg_parts.append(f"\n{i+1}. {elem['description']} - {', '.join(scroll_status) if scroll_status else 'at limits'}")
            
            msg = "\n".join(msg_parts)
            logger.info(msg)
            return ActionResult(
                data=result,
                extracted_content=msg,
                include_in_memory=True
            )
            
        except Exception as e:
            error_msg = f"Failed to detect scrollable areas: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg, include_in_memory=True)
    
    @controller.action(
        description="Scroll to a specific element on the page",
        param_model=ScrollToElementAction
    )
    async def scroll_to_element(params: ScrollToElementAction, browser_session: BrowserSession) -> ActionResult:
        """Scroll to bring a specific element into view"""
        page = await browser_session.get_current_page()
        
        try:
            js_code = """
            (options) => {
                const { selector, alignment, smooth } = options;
                const element = document.querySelector(selector);
                
                if (!element) {
                    throw new Error(`Element not found: ${selector}`);
                }
                
                // Get element info before scroll
                const beforeRect = element.getBoundingClientRect();
                const wasVisible = beforeRect.top >= 0 && 
                                  beforeRect.bottom <= window.innerHeight;
                
                // Perform scroll
                element.scrollIntoView({
                    behavior: smooth ? 'smooth' : 'auto',
                    block: alignment,
                    inline: 'nearest'
                });
                
                // Get element info after scroll (with delay for smooth scroll)
                return new Promise(resolve => {
                    setTimeout(() => {
                        const afterRect = element.getBoundingClientRect();
                        resolve({
                            element: selector,
                            wasVisible: wasVisible,
                            isNowVisible: afterRect.top >= 0 && afterRect.bottom <= window.innerHeight,
                            position: {
                                top: afterRect.top,
                                bottom: afterRect.bottom,
                                left: afterRect.left,
                                right: afterRect.right
                            }
                        });
                    }, smooth ? 500 : 50);
                });
            }
            """
            
            options = {
                "selector": params.selector,
                "alignment": params.alignment,
                "smooth": params.smooth
            }
            
            result = await page.evaluate(js_code, options)
            
            if result['wasVisible']:
                msg = f"🎯 Element '{params.selector}' was already visible"
            else:
                msg = f"🎯 Scrolled to element '{params.selector}' (alignment: {params.alignment})"
            
            logger.info(msg)
            return ActionResult(
                data=result,
                extracted_content=msg,
                include_in_memory=True
            )
            
        except Exception as e:
            error_msg = f"Failed to scroll to element: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg, include_in_memory=True)
    
    @controller.action(
        description="Scroll until specific text content is visible",
        param_model=ScrollUntilVisibleAction
    )
    async def scroll_until_visible(params: ScrollUntilVisibleAction, browser_session: BrowserSession) -> ActionResult:
        """Scroll through page/container until specific text is found and visible"""
        page = await browser_session.get_current_page()
        
        try:
            js_code = """
            async (options) => {
                const { text, maxScrolls, scrollAmount, containerSelector } = options;
                
                // Find scrollable container
                let container = null;
                if (containerSelector) {
                    container = document.querySelector(containerSelector);
                    if (!container) {
                        throw new Error(`Container not found: ${containerSelector}`);
                    }
                } else {
                    // Use smart detection
                    const bigEnough = el => el.clientHeight >= window.innerHeight * 0.5;
                    const canScroll = el =>
                        el &&
                        /(auto|scroll|overlay)/.test(getComputedStyle(el).overflowY) &&
                        el.scrollHeight > el.clientHeight &&
                        bigEnough(el);
                    
                    container = [...document.querySelectorAll('*')].find(canScroll)
                        || document.scrollingElement
                        || document.documentElement;
                }
                
                const isRoot = container === document.scrollingElement || 
                              container === document.documentElement || 
                              container === document.body;
                
                let scrollCount = 0;
                let found = false;
                let foundElement = null;
                
                const searchForText = () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    
                    let node;
                    while (node = walker.nextNode()) {
                        if (node.nodeValue.toLowerCase().includes(text.toLowerCase())) {
                            const element = node.parentElement;
                            const rect = element.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && 
                                rect.top >= 0 && rect.bottom <= window.innerHeight) {
                                foundElement = element;
                                return true;
                            }
                        }
                    }
                    return false;
                };
                
                // Initial check
                if (searchForText()) {
                    return {
                        found: true,
                        scrollCount: 0,
                        message: `Text '${text}' is already visible`
                    };
                }
                
                // Scroll and search
                while (scrollCount < maxScrolls && !found) {
                    const oldScrollTop = isRoot ? window.scrollY : container.scrollTop;
                    
                    if (isRoot) {
                        window.scrollBy(0, scrollAmount);
                    } else {
                        container.scrollBy(0, scrollAmount);
                    }
                    
                    // Wait for content to load
                    await new Promise(r => setTimeout(r, 300));
                    
                    scrollCount++;
                    
                    if (searchForText()) {
                        found = true;
                        break;
                    }
                    
                    // Check if we've reached the bottom
                    const newScrollTop = isRoot ? window.scrollY : container.scrollTop;
                    if (newScrollTop === oldScrollTop) {
                        break;
                    }
                }
                
                return {
                    found: found,
                    scrollCount: scrollCount,
                    message: found ? 
                        `Found '${text}' after ${scrollCount} scrolls` : 
                        `Text '${text}' not found after ${scrollCount} scrolls`
                };
            }
            """
            
            options = {
                "text": params.text,
                "maxScrolls": params.max_scrolls,
                "scrollAmount": params.scroll_amount,
                "containerSelector": params.container_selector
            }
            
            result = await page.evaluate(js_code, options)
            
            logger.info(result['message'])
            return ActionResult(
                data=result,
                extracted_content=result['message'],
                include_in_memory=True
            )
            
        except Exception as e:
            error_msg = f"Failed to scroll until visible: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg, include_in_memory=True)
    
    @controller.action(
        description="Handle infinite scroll pages by loading content progressively",
        param_model=InfiniteScrollAction
    )
    async def handle_infinite_scroll(params: InfiniteScrollAction, browser_session: BrowserSession) -> ActionResult:
        """Handle infinite scroll pages by scrolling and waiting for new content"""
        page = await browser_session.get_current_page()
        
        try:
            initial_count = 0
            if params.item_selector:
                initial_count = await page.evaluate(
                    f"document.querySelectorAll('{params.item_selector}').length"
                )
            
            total_scrolls = 0
            no_new_content_count = 0
            last_height = await page.evaluate("document.body.scrollHeight")
            
            while total_scrolls < params.max_scrolls:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Wait for new content
                await asyncio.sleep(params.wait_time)
                
                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                
                if params.item_selector:
                    current_count = await page.evaluate(
                        f"document.querySelectorAll('{params.item_selector}').length"
                    )
                    
                    if params.max_items and current_count >= params.max_items:
                        msg = f"🔄 Loaded {current_count} items (reached limit of {params.max_items})"
                        logger.info(msg)
                        return ActionResult(
                            data={"itemsLoaded": current_count, "scrollCount": total_scrolls},
                            extracted_content=msg,
                            include_in_memory=True
                        )
                
                if new_height == last_height:
                    no_new_content_count += 1
                    if no_new_content_count >= 3:
                        break
                else:
                    no_new_content_count = 0
                    last_height = new_height
                
                total_scrolls += 1
            
            # Final count
            final_count = initial_count
            if params.item_selector:
                final_count = await page.evaluate(
                    f"document.querySelectorAll('{params.item_selector}').length"
                )
            
            msg = f"🔄 Infinite scroll complete: {total_scrolls} scrolls"
            if params.item_selector:
                msg += f", loaded {final_count - initial_count} new items (total: {final_count})"
            
            logger.info(msg)
            return ActionResult(
                data={
                    "initialCount": initial_count,
                    "finalCount": final_count,
                    "newItems": final_count - initial_count,
                    "scrollCount": total_scrolls
                },
                extracted_content=msg,
                include_in_memory=True
            )
            
        except Exception as e:
            error_msg = f"Failed to handle infinite scroll: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg, include_in_memory=True)