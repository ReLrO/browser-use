"""Debug element finding issues in next-gen system"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def debug_perception():
    """Debug what the perception system sees"""
    
    logger.info("=== Debugging Perception System ===")
    
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
        
        # Create a simple test page
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Test Page</h1>
                <input type="text" id="search-box" placeholder="Search here..." style="padding: 10px;">
                <button id="search-btn">Search</button>
                <div id="result"></div>
            </body>
            </html>
        """)
        
        logger.info("\n--- Getting Perception Data ---")
        
        # Get raw perception data
        perception_data = await agent._get_perception_data()
        
        # Log what we see
        logger.info(f"Perception data keys: {list(perception_data.keys())}")
        
        if 'perception_results' in perception_data:
            results = perception_data['perception_results']
            logger.info(f"Perception results keys: {list(results.keys())}")
            
            if 'dom' in results:
                dom_result = results['dom']
                logger.info(f"DOM result type: {type(dom_result)}")
                logger.info(f"DOM result: {dom_result}")
        
        # Try to access the element resolver directly
        logger.info("\n--- Testing Element Resolution ---")
        from browser_use.core.intent.views import ElementIntent
        
        element_intent = ElementIntent(
            description="Search input box",
            element_type="input"
        )
        
        # Get the resolver
        resolver = agent.element_resolver
        
        # Try to resolve
        try:
            resolved = await resolver.resolve_element(
                element_intent,
                perception_data,
                agent.current_page
            )
            
            if resolved:
                logger.info(f"Element resolved!")
                logger.info(f"Selector: {resolved.selector}")
                logger.info(f"Strategy: {resolved.strategy}")
                logger.info(f"Confidence: {resolved.confidence}")
            else:
                logger.error("Failed to resolve element")
                
        except Exception as e:
            logger.error(f"Resolution error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test the LLM element finder directly
        logger.info("\n--- Testing LLM Element Finder ---")
        from browser_use.core.resolver.llm_element_finder import LLMElementFinder
        
        llm_finder = LLMElementFinder(llm)
        
        # Extract elements
        elements = await llm_finder._extract_page_elements(agent.current_page, 50)
        logger.info(f"Found {len(elements)} elements on page")
        for i, elem in enumerate(elements[:5]):
            logger.info(f"Element {i}: {elem}")
        
        # Try to find the search box
        result = await llm_finder.find_element(
            agent.current_page,
            element_intent,
            max_elements=50
        )
        
        if result:
            logger.info("LLM finder found element!")
            logger.info(f"Selector: {result.selector}")
        else:
            logger.error("LLM finder failed")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_simple_action():
    """Test a simple action with debugging"""
    
    logger.info("=== Testing Simple Action ===")
    
    # Initialize LLM with rate limit handling
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        max_retries=3,
        request_timeout=30
    )
    
    # Create agent
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=False,
        use_accessibility=False,  # Disable to simplify
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Create a very simple page
        await agent.current_page.set_content("""
            <html>
            <body>
                <h1>Simple Test</h1>
                <button onclick="alert('Clicked!')">Click Me</button>
            </body>
            </html>
        """)
        
        await asyncio.sleep(1)
        
        # Try to click the button
        logger.info("\n--- Attempting to click button ---")
        result = await agent.execute_task("Click the button that says 'Click Me'")
        
        logger.info(f"Result: {result}")
        logger.info(f"Success: {result.get('success')}")
        
        if not result.get('success'):
            logger.error(f"Errors: {result.get('errors')}")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_direct_playwright():
    """Test with direct Playwright to verify it works"""
    
    logger.info("=== Testing Direct Playwright ===")
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Set content
        await page.set_content("""
            <html>
            <body>
                <h1>Direct Playwright Test</h1>
                <input type="text" id="test-input" placeholder="Type here">
                <button id="test-button">Click Me</button>
                <div id="result"></div>
            </body>
            </html>
        """)
        
        # Test typing
        await page.fill("#test-input", "Hello from Playwright")
        value = await page.evaluate('document.getElementById("test-input").value')
        logger.info(f"Input value: {value}")
        
        # Test clicking
        await page.evaluate("""
            document.getElementById('test-button').onclick = function() {
                document.getElementById('result').textContent = 'Button was clicked!';
            }
        """)
        
        await page.click("#test-button")
        result = await page.evaluate('document.getElementById("result").textContent')
        logger.info(f"Result: {result}")
        
        logger.info("\nPress Enter to close browser...")
        input()
        await browser.close()


async def main():
    """Run debug tests"""
    tests = [
        ("Debug Perception", debug_perception),
        ("Test Simple Action", test_simple_action),
        ("Test Direct Playwright", test_direct_playwright)
    ]
    
    print("\nSelect a debug test:")
    for i, (name, _) in enumerate(tests):
        print(f"{i+1}. {name}")
    
    choice = input("\nEnter your choice (1-3): ")
    
    try:
        choice = int(choice)
        if 1 <= choice <= len(tests):
            await tests[choice-1][1]()
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")


if __name__ == "__main__":
    # Add delay between API calls to avoid rate limiting
    asyncio.run(main())