"""Debug Google search functionality"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Focus on specific modules
logging.getLogger('browser_use.core.resolver.service').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.resolver.vision_strategy').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.orchestrator.service').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.intent.service').setLevel(logging.INFO)


async def test_google_search():
    """Test Google search with detailed debugging"""
    
    logger.info("=== Testing Google Search Debug ===")
    
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
        
        # Step 1: Navigate
        logger.info("\n=== Step 1: Navigate to Google ===")
        result = await agent.execute_task("Go to google.com")
        logger.info(f"Navigation result: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Step 2: Type search query
        logger.info("\n=== Step 2: Type search query ===")
        result = await agent.execute_task("Type 'browser automation tools' in the search box")
        logger.info(f"Type result: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Step 3: Submit search
        logger.info("\n=== Step 3: Submit search ===")
        result = await agent.execute_task("Press Enter to submit the search")
        logger.info(f"Submit result: {result.get('success')}")
        
        await asyncio.sleep(5)
        
        # Step 4: Debug - what's on the page?
        logger.info("\n=== Step 4: Debug page state ===")
        
        # Get perception data to see what the system sees
        perception_data = await agent._get_perception_data()
        
        # Check if we have search results
        if 'page_elements' in perception_data:
            elements = perception_data['page_elements']
            logger.info(f"Found {len(elements)} elements on page")
            
            # Look for links that might be search results
            links = [el for el in elements if el.get('tag') == 'a' and el.get('text')]
            logger.info(f"Found {len(links)} links with text")
            
            # Show first few links
            for i, link in enumerate(links[:5]):
                logger.info(f"Link {i}: {link.get('text', '')[:100]}")
        
        # Step 5: Try to click first result with more specific instruction
        logger.info("\n=== Step 5: Click first search result ===")
        result = await agent.execute_task("Click on the first blue link in the search results (not an ad)")
        logger.info(f"Click result: {result.get('success')}")
        
        if not result.get('success'):
            # Try scrolling first
            logger.info("\n=== Step 6: Try scrolling ===")
            result = await agent.execute_task("Scroll down to see more results")
            logger.info(f"Scroll result: {result.get('success')}")
            
            await asyncio.sleep(2)
            
            # Try clicking again
            result = await agent.execute_task("Click on any search result link")
            logger.info(f"Second click attempt: {result.get('success')}")
        
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
    asyncio.run(test_google_search())