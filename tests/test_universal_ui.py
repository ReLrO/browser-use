"""Test universal UI understanding on various websites"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile
from browser_use.core.caching import rate_limiter

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_any_website(url: str, tasks: list):
    """Test UI understanding on any website with given tasks"""
    
    logger.info(f"\n=== Testing {url} ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-05-20",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=False,
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Navigate to the website
        logger.info(f"\n--- Navigating to {url} ---")
        result = await agent.execute_task(f"Go to {url}")
        logger.info(f"Navigation: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Execute each task
        for i, task in enumerate(tasks, 1):
            logger.info(f"\n--- Task {i}: {task} ---")
            logger.info(f"Rate limit status: {rate_limiter.get_remaining_calls()} calls remaining")
            
            result = await agent.execute_task(task)
            logger.info(f"Result: {result.get('success')}")
            
            if result.get('data'):
                logger.info(f"Data: {result['data']}")
            
            # Wait between tasks
            await asyncio.sleep(2)
        
        # Take screenshot at the end
        logger.info("\n--- Final State ---")
        current_url = agent.current_page.url
        page_title = await agent.current_page.title()
        logger.info(f"Final URL: {current_url}")
        logger.info(f"Page title: {page_title}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to continue...")
        input()
        await agent.cleanup()


async def run_website_tests():
    """Run tests on various websites"""
    
    # Test configurations for different websites
    test_configs = [
        {
            "url": "wikipedia.org",
            "tasks": [
                "Search for 'Artificial Intelligence'",
                "Click on the first search result",
                "Extract the first paragraph of the article"
            ]
        },
        {
            "url": "google.com",
            "tasks": [
                "Search for 'weather forecast'",
                "Click on the 'News' tab if available"
            ]
        },
        {
            "url": "github.com",
            "tasks": [
                "Search for 'browser automation'",
                "Filter results by 'Repositories' if possible",
                "Click on the first repository result"
            ]
        },
        {
            "url": "amazon.com",
            "tasks": [
                "Search for 'laptop'",
                "Filter by '4 stars and up' customer rating if available",
                "Sort by price from low to high if possible"
            ]
        },
        {
            "url": "reddit.com",
            "tasks": [
                "Search for 'programming'",
                "Click on the first post",
                "Go back to search results"
            ]
        }
    ]
    
    # Let user choose which test to run
    print("\nAvailable website tests:")
    for i, config in enumerate(test_configs):
        print(f"{i+1}. {config['url']}")
    print("0. Run all tests")
    
    choice = input("\nSelect test (0-5): ")
    
    try:
        choice = int(choice)
        if choice == 0:
            # Run all tests
            for config in test_configs:
                await test_any_website(config["url"], config["tasks"])
        elif 1 <= choice <= len(test_configs):
            # Run selected test
            config = test_configs[choice - 1]
            await test_any_website(config["url"], config["tasks"])
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")


async def test_custom_website():
    """Test a custom website with custom tasks"""
    
    url = input("Enter website URL (e.g., example.com): ").strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print("\nEnter tasks to perform (one per line, empty line to finish):")
    tasks = []
    while True:
        task = input(f"Task {len(tasks)+1}: ").strip()
        if not task:
            break
        tasks.append(task)
    
    if tasks:
        await test_any_website(url, tasks)
    else:
        print("No tasks entered")


async def test_ui_patterns():
    """Test specific UI patterns across different sites"""
    
    logger.info("=== Testing Common UI Patterns ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-05-20",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=False,
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Test search pattern on different sites
        search_tests = [
            ("google.com", "machine learning"),
            ("youtube.com", "python tutorial"),
            ("twitter.com", "#programming"),
        ]
        
        for site, query in search_tests:
            logger.info(f"\n--- Testing search on {site} ---")
            
            # Navigate
            result = await agent.execute_task(f"Go to {site}")
            await asyncio.sleep(3)
            
            # Search
            result = await agent.execute_task(f"Search for '{query}'")
            logger.info(f"Search on {site}: {result.get('success')}")
            
            await asyncio.sleep(3)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    print("\n=== Universal UI Understanding Test Suite ===")
    print("\nSelect test mode:")
    print("1. Test predefined websites")
    print("2. Test custom website")
    print("3. Test UI patterns across sites")
    
    mode = input("\nChoice (1-3): ")
    
    if mode == "1":
        asyncio.run(run_website_tests())
    elif mode == "2":
        asyncio.run(test_custom_website())
    elif mode == "3":
        asyncio.run(test_ui_patterns())
    else:
        print("Invalid choice")