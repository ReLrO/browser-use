"""Test vision-based element resolution strategy"""

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


async def test_vision_strategy():
    """Test vision-based resolution on various scenarios"""
    
    logger.info("=== Testing Vision-Based Resolution Strategy ===")
    
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
        use_vision=True,  # Enable vision
        use_accessibility=True,
        enable_streaming=False
    )
    
    test_cases = [
        {
            "name": "Amazon Filter Test",
            "url": "amazon.com",
            "tasks": [
                "Search for 'laptop'",
                "Filter by '4 stars and up' customer rating",
                "Sort by price from low to high"
            ]
        },
        {
            "name": "CNN Article Test",
            "url": "cnn.com",
            "tasks": [
                "Find an article about technology",
                "Enter it and read it",
                "Extract the main points"
            ]
        },
        {
            "name": "Wikipedia Search Test",
            "url": "wikipedia.org",
            "tasks": [
                "Search for 'Artificial Intelligence'",
                "Click on the first search result",
                "Extract the first paragraph"
            ]
        }
    ]
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        for test in test_cases:
            logger.info(f"\n--- Running: {test['name']} ---")
            
            # Navigate to site
            result = await agent.execute_task(f"Go to {test['url']}")
            logger.info(f"Navigation: {result.get('success')}")
            
            await asyncio.sleep(3)
            
            # Store context for "it" references
            context = {"previous_task": None}
            
            # Execute tasks
            for task in test['tasks']:
                logger.info(f"\nTask: {task}")
                
                # Update context with previous task
                if context['previous_task']:
                    agent._execution_context['previous_task'] = context['previous_task']
                
                result = await agent.execute_task(task)
                success = result.get('success', False)
                logger.info(f"Result: {success}")
                
                if result.get('data'):
                    logger.info(f"Data: {result['data']}")
                
                # Update context for next task
                context['previous_task'] = {
                    'task': task,
                    'success': success,
                    'result': result.get('data')
                }
                
                await asyncio.sleep(2)
            
            logger.info(f"\n{test['name']} completed")
            await asyncio.sleep(3)
    
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_specific_vision_case():
    """Test a specific case with vision resolution"""
    
    logger.info("=== Testing Specific Vision Case ===")
    
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
        
        # Test Amazon filters which were failing
        logger.info("\nNavigating to Amazon...")
        await agent.execute_task("Go to amazon.com")
        await asyncio.sleep(3)
        
        logger.info("\nSearching for laptops...")
        result = await agent.execute_task("Search for 'laptop'")
        logger.info(f"Search result: {result.get('success')}")
        await asyncio.sleep(5)
        
        logger.info("\nTrying to filter by rating...")
        result = await agent.execute_task("Filter by '4 stars and up' customer rating if available")
        logger.info(f"Filter result: {result.get('success')}")
        
        if not result.get('success'):
            logger.info("Filter failed, taking screenshot for debugging...")
            screenshot = await agent.current_page.screenshot(path="debug_filter_fail.png")
            logger.info("Screenshot saved as debug_filter_fail.png")
        
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
    print("\nSelect test:")
    print("1. Test vision strategy on multiple sites")
    print("2. Test specific vision case (Amazon filters)")
    
    choice = input("\nChoice (1-2): ")
    
    if choice == "1":
        asyncio.run(test_vision_strategy())
    elif choice == "2":
        asyncio.run(test_specific_vision_case())
    else:
        print("Invalid choice")