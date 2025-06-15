"""Test Amazon search functionality"""

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


async def test_amazon_search():
    """Test searching on Amazon"""
    
    logger.info("=== Testing Amazon Search ===")
    
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
        use_vision=True,  # Enable vision for true understanding
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Navigate to Amazon
        logger.info("\nStep 1: Navigating to Amazon...")
        result = await agent.execute_task("Go to amazon.com")
        logger.info(f"Navigation result: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Search for laptop
        logger.info("\nStep 2: Searching for laptop...")
        result = await agent.execute_task("Search for 'laptop'")
        logger.info(f"Search result: {result.get('success')}")
        
        if not result.get('success'):
            logger.error(f"Search failed: {result.get('errors')}")
            
            # Debug - get page elements
            logger.info("\nDebugging - checking page elements...")
            perception_data = await agent._get_perception_data()
            elements = perception_data.get('page_elements', [])
            
            # Look for search inputs
            search_inputs = [el for el in elements if el.get('isSearchInput') or (el.get('isInput') and 'search' in str(el).lower())]
            logger.info(f"Found {len(search_inputs)} potential search inputs")
            
            for i, el in enumerate(search_inputs[:3]):
                logger.info(f"Search input {i}: id={el.get('id')}, name={el.get('name')}, placeholder={el.get('placeholder')}")
        
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
    asyncio.run(test_amazon_search())