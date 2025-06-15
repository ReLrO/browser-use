"""Test NextGen with fixes applied"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Debug specific areas
logging.getLogger('browser_use.core.orchestrator.service').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.resolver.vision_strategy').setLevel(logging.INFO)


async def test_fixed():
    """Test with fixes applied"""
    
    logger.info("=== Testing NextGen with Fixes ===")
    
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
        use_vision=True,
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Test 1: Navigate
        logger.info("\n=== Test 1: Navigate to Google ===")
        result = await agent.execute_task("Go to google.com")
        logger.info(f"Result: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Test 2: Search (combined)
        logger.info("\n=== Test 2: Search for something ===")
        result = await agent.execute_task("Search for 'browser automation tools'")
        logger.info(f"Result: {result.get('success')}")
        
        await asyncio.sleep(5)
        
        # Test 3: Click result
        logger.info("\n=== Test 3: Click search result ===")
        result = await agent.execute_task("Click on the first search result")
        logger.info(f"Result: {result.get('success')}")
        
        if result.get('success'):
            logger.info("Successfully clicked a search result!")
        else:
            logger.info("Failed to click - trying alternative approach")
            # Try a more specific instruction
            result = await agent.execute_task("Click on any blue link in the search results")
            logger.info(f"Alternative result: {result.get('success')}")
        
        await asyncio.sleep(5)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(test_fixed())