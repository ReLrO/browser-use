"""Test the working agent"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.working_agent import WorkingAgent
from browser_use.browser.profile import BrowserProfile

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_working():
    """Test the working agent"""
    
    logger.info("=== Testing Working Agent ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-05-20",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent
    agent = WorkingAgent(llm, browser_profile=BrowserProfile(headless=False))
    
    try:
        await agent.initialize()
        
        # Test 1: Navigate
        logger.info("\n1. Navigate to Google")
        result = await agent.execute_task("Go to google.com")
        logger.info(f"Result: {result}")
        
        await asyncio.sleep(2)
        
        # Test 2: Search (single command)
        logger.info("\n2. Search")
        result = await agent.execute_task("Search for 'browser automation tools'")
        logger.info(f"Result: {result}")
        
        await asyncio.sleep(3)
        
        # Test 3: Click result
        logger.info("\n3. Click first result")
        result = await agent.execute_task("Click on the first search result")
        logger.info(f"Result: {result}")
        
        if result['success']:
            logger.info("✅ Successfully clicked search result!")
        else:
            logger.info("❌ Failed to click search result")
            
            # Try scrolling
            logger.info("\n4. Try scrolling")
            result = await agent.execute_task("Scroll down")
            logger.info(f"Scroll result: {result}")
            
            await asyncio.sleep(1)
            
            # Try again
            logger.info("\n5. Try clicking again")
            result = await agent.execute_task("Click on any blue link in search results")
            logger.info(f"Second attempt: {result}")
        
        await asyncio.sleep(5)
        
        # Test Amazon
        logger.info("\n\n=== Testing Amazon ===")
        
        result = await agent.execute_task("Go to amazon.com")
        logger.info(f"Navigate to Amazon: {result}")
        
        await asyncio.sleep(3)
        
        result = await agent.execute_task("Search for 'laptop'")
        logger.info(f"Search for laptop: {result}")
        
        await asyncio.sleep(3)
        
        result = await agent.execute_task("Click on the first product")
        logger.info(f"Click product: {result}")
        
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
    asyncio.run(test_working())