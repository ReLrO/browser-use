"""Comprehensive test of NextGen browser-use"""

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

# Debug specific modules
logging.getLogger('browser_use.core.resolver.vision_strategy').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.orchestrator.service').setLevel(logging.INFO)


async def test_comprehensive():
    """Test various scenarios comprehensively"""
    
    logger.info("=== Comprehensive NextGen Test ===")
    
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
        
        # Test 1: Amazon Search (the original failing test)
        logger.info("\n=== Test 1: Amazon Search ===")
        
        # Navigate
        result = await agent.execute_task("Go to amazon.com")
        logger.info(f"Navigate to Amazon: {result.get('success')}")
        await asyncio.sleep(3)
        
        # Search
        result = await agent.execute_task("Search for 'laptop'")
        logger.info(f"Search for laptop: {result.get('success')}")
        await asyncio.sleep(5)
        
        # Click result - with better description
        result = await agent.execute_task("Click on the first product in the search results (not an ad)")
        logger.info(f"Click product: {result.get('success')}")
        
        if not result.get('success'):
            # Try scrolling and clicking again
            logger.info("First click failed, trying to scroll...")
            result = await agent.execute_task("Scroll down to see more products")
            await asyncio.sleep(2)
            
            result = await agent.execute_task("Click on any laptop product link")
            logger.info(f"Second click attempt: {result.get('success')}")
        
        await asyncio.sleep(5)
        
        # Test 2: Google Search (simpler case)
        logger.info("\n=== Test 2: Google Search ===")
        
        result = await agent.execute_task("Go to google.com")
        logger.info(f"Navigate to Google: {result.get('success')}")
        await asyncio.sleep(3)
        
        result = await agent.execute_task("Search for 'OpenAI GPT-4'")
        logger.info(f"Search on Google: {result.get('success')}")
        await asyncio.sleep(5)
        
        result = await agent.execute_task("Click the first search result")
        logger.info(f"Click Google result: {result.get('success')}")
        await asyncio.sleep(5)
        
        # Test 3: Form Filling
        logger.info("\n=== Test 3: Form Filling ===")
        
        result = await agent.execute_task("Go to github.com/login")
        logger.info(f"Navigate to GitHub login: {result.get('success')}")
        await asyncio.sleep(3)
        
        result = await agent.execute_task("Type 'testuser' in the username field")
        logger.info(f"Type username: {result.get('success')}")
        await asyncio.sleep(2)
        
        result = await agent.execute_task("Type 'testpass' in the password field")
        logger.info(f"Type password: {result.get('success')}")
        
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
    asyncio.run(test_comprehensive())