"""Minimal test to verify basic functionality works"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_navigation_only():
    """Test just navigation which seems to work"""
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent with minimal config
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=False,
        use_accessibility=False,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Test 1: Navigate to a simple site
        logger.info("Test 1: Navigate to example.com")
        result = await agent.execute_task("Go to example.com")
        logger.info(f"Success: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Test 2: Navigate to another site
        logger.info("\nTest 2: Navigate to wikipedia.org")
        result = await agent.execute_task("Navigate to wikipedia.org")
        logger.info(f"Success: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Test 3: Check current URL
        current_url = agent.current_page.url
        logger.info(f"\nCurrent URL: {current_url}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_with_delays():
    """Test with delays to avoid rate limiting"""
    
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
        use_accessibility=False,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Create test page
        await agent.current_page.goto("data:text/html,<h1>Test Page</h1><button>Click Me</button>")
        
        # Wait to avoid rate limit
        logger.info("Waiting 10 seconds to avoid rate limit...")
        await asyncio.sleep(10)
        
        # Try clicking
        logger.info("Attempting to click button...")
        result = await agent.execute_task("Click the button")
        logger.info(f"Result: {result}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_direct_action():
    """Test executing actions directly without LLM intent analysis"""
    
    from browser_use.core.intent.views import Intent, SubIntent, IntentType, IntentParameter
    from browser_use.core.orchestrator.service import ActionType
    
    # Initialize LLM (still needed for element finding)
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
        use_accessibility=False,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Navigate directly
        intent = Intent(
            task_description="Navigate to example.com",
            type=IntentType.NAVIGATION,
            primary_goal="Go to example.com",
            sub_intents=[
                SubIntent(
                    description="Navigate to example.com",
                    type=IntentType.NAVIGATION,
                    parameters=[
                        IntentParameter(
                            name="url",
                            value="https://example.com",
                            type="string",
                            required=True
                        )
                    ]
                )
            ]
        )
        
        logger.info("Executing navigation intent directly...")
        result = await agent.execute_intent_directly(intent)
        logger.info(f"Result: {result}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    print("Select test:")
    print("1. Navigation only (works)")
    print("2. Test with delays")
    print("3. Direct action execution")
    
    choice = input("Choice (1-3): ")
    
    if choice == "1":
        asyncio.run(test_navigation_only())
    elif choice == "2":
        asyncio.run(test_with_delays())
    elif choice == "3":
        asyncio.run(test_direct_action())
    else:
        print("Invalid choice")