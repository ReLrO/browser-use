"""Test Wikipedia search with improved UI understanding"""

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


async def test_wikipedia_search():
    """Test Wikipedia search with different approaches"""
    
    logger.info("=== Testing Wikipedia Search ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
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
        
        # Navigate to Wikipedia
        logger.info("\n--- Navigate to Wikipedia ---")
        result = await agent.execute_task("Go to wikipedia.org")
        logger.info(f"Navigation: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Approach 1: Type and click search button
        logger.info("\n--- Approach 1: Type and Click Search ---")
        
        # Type in search box
        result = await agent.execute_task("Type 'Python programming language' in the search input")
        logger.info(f"Type: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Click search button (with better description)
        result = await agent.execute_task("Click the search button next to the search input")
        logger.info(f"Click search: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Check if we're on the article page
        current_url = agent.current_page.url
        logger.info(f"Current URL: {current_url}")
        
        if "Python" not in current_url:
            # Try alternative approach
            logger.info("\n--- Approach 2: Use Enter Key ---")
            
            # Go back to main page
            await agent.execute_task("Go to wikipedia.org")
            await asyncio.sleep(2)
            
            # Type and press Enter
            result = await agent.execute_task("Type 'Python programming language' in the search box and press Enter")
            logger.info(f"Type and Enter: {result.get('success')}")
            
            await asyncio.sleep(3)
            
            current_url = agent.current_page.url
            logger.info(f"Current URL after Enter: {current_url}")
        
        # Extract first paragraph
        logger.info("\n--- Extract Information ---")
        result = await agent.execute_task("Extract the first paragraph from the article")
        logger.info(f"Extraction: {result.get('success')}")
        
        if result.get('data'):
            logger.info(f"Extracted text: {str(result['data'])[:200]}...")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_direct_search():
    """Test with direct search task"""
    
    logger.info("=== Testing Direct Search Task ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
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
        
        # Single task that combines navigation and search
        logger.info("\n--- Combined Task ---")
        result = await agent.execute_task(
            "Go to wikipedia.org and search for 'Artificial Intelligence'"
        )
        logger.info(f"Combined task: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Check result
        current_url = agent.current_page.url
        page_title = await agent.current_page.title()
        logger.info(f"Current URL: {current_url}")
        logger.info(f"Page title: {page_title}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    print("\nSelect test:")
    print("1. Wikipedia search with multiple approaches")
    print("2. Direct combined search task")
    print("3. Run both tests")
    
    choice = input("\nChoice (1-3): ")
    
    if choice == "1":
        asyncio.run(test_wikipedia_search())
    elif choice == "2":
        asyncio.run(test_direct_search())
    elif choice == "3":
        asyncio.run(test_wikipedia_search())
        print("\n" + "="*60 + "\n")
        asyncio.run(test_direct_search())
    else:
        print("Invalid choice")