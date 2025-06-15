"""Test the NextGen fixes"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Enable detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also enable debug for specific modules to see the fixes in action
logging.getLogger('browser_use.core.resolver.service').setLevel(logging.INFO)
logging.getLogger('browser_use.core.resolver.llm_element_finder').setLevel(logging.INFO)
logging.getLogger('browser_use.core.orchestrator.service').setLevel(logging.INFO)


async def test_nextgen_fixes():
    """Test the fixes with a simple search task"""
    
    logger.info("=== Testing NextGen Fixes ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-05-20",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent with vision enabled
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=True,  # Vision enabled!
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Test 1: Navigate to Google
        logger.info("\n=== Test 1: Navigation ===")
        result = await agent.execute_task("Go to google.com")
        logger.info(f"Navigation result: {result.get('success')}")
        
        # Add delay to avoid rate limits
        logger.info("Waiting 3 seconds to avoid rate limits...")
        await asyncio.sleep(3)
        
        # Test 2: Search with typing and Enter key
        logger.info("\n=== Test 2: Search with Enter key ===")
        result = await agent.execute_task("Type 'browser automation' in the search box and press Enter")
        logger.info(f"Search result: {result.get('success')}")
        
        # Add delay to avoid rate limits
        logger.info("Waiting 5 seconds to avoid rate limits...")
        await asyncio.sleep(5)
        
        # Test 3: Click on a result
        logger.info("\n=== Test 3: Click on search result ===")
        result = await agent.execute_task("Click on the first search result")
        logger.info(f"Click result: {result.get('success')}")
        
        await asyncio.sleep(5)
        
        logger.info("\n=== All tests completed ===")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    # Test our fixes
    asyncio.run(test_nextgen_fixes())