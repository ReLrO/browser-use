"""
Example demonstrating enhanced scrolling capabilities in browser-use.
This shows how to use the advanced scrolling features for complex web interactions.
"""

import asyncio
from typing import Optional

from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller
from browser_use.controller.actions.enhanced_scroll import register_enhanced_scroll_actions


async def detect_and_scroll_example():
    """Example: Detect scrollable areas and perform targeted scrolling"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    
    agent = Agent(
        task="Navigate to a page with multiple scrollable areas and demonstrate scrolling",
        llm=ChatOpenAI(model="gpt-4o"),
        controller=controller,
    )
    
    # Example task that uses scrollable area detection
    result = await agent.run("""
    1. Go to https://www.linkedin.com/sales/search/people
    2. First, use detect_scrollable_areas to understand the page structure
    3. If there's a filter panel, use enhanced_scroll to scroll it down by 400 pixels
    4. If you find any dropdown menus, detect if they're scrollable
    5. Report what scrollable areas you found
    """)
    
    print("Scrollable areas detected and scrolled!")


async def scroll_to_content_example():
    """Example: Scroll until specific content is found"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    
    agent = Agent(
        task="Find specific content by scrolling",
        llm=ChatOpenAI(model="gpt-4o"),
        controller=controller,
    )
    
    result = await agent.run("""
    1. Go to https://en.wikipedia.org/wiki/Web_scraping
    2. Use scroll_until_visible to find the text "Legal issues"
    3. Once found, report the section content
    """)
    
    print("Found content by scrolling!")


async def infinite_scroll_example():
    """Example: Handle infinite scroll pages"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    
    agent = Agent(
        task="Load content from infinite scroll page",
        llm=ChatOpenAI(model="gpt-4o"),
        controller=controller,
    )
    
    result = await agent.run("""
    1. Go to https://infinite-scroll.com/demo/masonry
    2. Use handle_infinite_scroll with:
       - max_items: 50
       - item_selector: '.grid-item'
    3. Report how many items were loaded
    """)
    
    print("Handled infinite scroll!")


async def linkedin_filter_scrolling():
    """Example: LinkedIn-specific scrolling for filters and dropdowns"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    
    agent = Agent(
        task="Navigate LinkedIn filters with advanced scrolling",
        llm=ChatOpenAI(model="gpt-4o"),
        controller=controller,
    )
    
    result = await agent.run("""
    You are on LinkedIn Sales Navigator search page.
    
    1. Use detect_scrollable_areas to identify all scrollable areas
    2. Look for the filter panel (usually has class 'scaffold-layout__aside')
    3. If "Seniority Level" filter is not visible:
       - Use enhanced_scroll with target_selector='form.overflow-y-auto' to scroll down 400 pixels
       - Repeat until "Seniority Level" is visible
    4. Click on "Seniority Level" to open the dropdown
    5. Use detect_scrollable_areas again to check if the dropdown is scrollable
    6. If the dropdown is scrollable and "CXO" is not visible:
       - Use enhanced_scroll with target_selector='.artdeco-typeahead__results-list' to scroll
       - Or use scroll_until_visible to find "CXO" option
    7. Click the Include button for CXO
    """)
    
    print("LinkedIn filters navigated with scrolling!")


async def multi_directional_scroll_example():
    """Example: Scroll in different directions"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    
    agent = Agent(
        task="Demonstrate multi-directional scrolling",
        llm=ChatOpenAI(model="gpt-4o"),
        controller=controller,
    )
    
    result = await agent.run("""
    1. Go to https://www.google.com/maps
    2. Search for "New York City"
    3. Use enhanced_scroll with:
       - direction: "right", amount: 500
       - direction: "down", amount: 300
       - direction: "left", amount: 500
       - direction: "up", amount: 300
    4. You should have made a rectangle with your scrolling
    """)
    
    print("Multi-directional scrolling complete!")


async def scroll_strategies_example():
    """Example: Different scrolling strategies"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    
    agent = Agent(
        task="Demonstrate different scrolling strategies",
        llm=ChatOpenAI(model="gpt-4o"),
        controller=controller,
    )
    
    result = await agent.run("""
    1. Go to https://en.wikipedia.org/wiki/Python_(programming_language)
    2. Demonstrate different scroll strategies:
       - Use enhanced_scroll with strategy="viewport" and amount=50 (scroll 50% of viewport)
       - Use enhanced_scroll with strategy="page" (scroll exactly one page)
       - Use enhanced_scroll with strategy="to_end" and direction="down" (scroll to bottom)
       - Use enhanced_scroll with strategy="to_end" and direction="up" (scroll to top)
    3. Report the differences you observed
    """)
    
    print("Scroll strategies demonstrated!")


if __name__ == "__main__":
    # Run examples
    print("Enhanced Scrolling Examples\n")
    
    # Uncomment the example you want to run:
    
    # asyncio.run(detect_and_scroll_example())
    # asyncio.run(scroll_to_content_example())
    # asyncio.run(infinite_scroll_example())
    asyncio.run(linkedin_filter_scrolling())
    # asyncio.run(multi_directional_scroll_example())
    # asyncio.run(scroll_strategies_example())