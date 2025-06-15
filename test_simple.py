"""Simple test to check each functionality"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


async def test_each_action():
    """Test each action type separately"""
    
    print("\n=== Testing Each Action Type ===")
    
    # Initialize components
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    agent = NextGenBrowserAgent(
        llm=llm,
        use_vision=False,  # Disable vision to reduce complexity
        use_accessibility=False,
        enable_streaming=False
    )
    
    browser = Browser(config=BrowserConfig(headless=False))
    
    try:
        # Initialize and start browser
        await agent.initialize()
        await browser.start()
        
        # Set up agent with browser
        page = await browser.new_tab()
        agent.current_page = page
        agent.browser_session = browser
        
        print("✓ Browser and agent initialized")
        
        # Create a simple test page
        await page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Test Page</h1>
                <input type="text" id="test-input" placeholder="Type here..." style="padding: 10px;">
                <button id="test-button" style="padding: 10px;">Click Me</button>
                <div id="result"></div>
            </body>
            </html>
        """)
        
        print("\n--- Test 1: Navigation (WORKING) ---")
        try:
            result = await agent.execute_task("Go to example.com")
            print(f"Success: {result.get('success', False)}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Go back to test page
        await page.go_back()
        await asyncio.sleep(1)
        
        print("\n--- Test 2: Click Action ---")
        try:
            result = await agent.execute_task("Click the button")
            print(f"Success: {result.get('success', False)}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n--- Test 3: Type Action ---")
        try:
            result = await agent.execute_task("Type 'Hello World' in the input field")
            print(f"Success: {result.get('success', False)}")
            
            # Check if text was actually typed
            value = await page.evaluate('document.getElementById("test-input").value')
            print(f"Actual value: '{value}'")
        except Exception as e:
            print(f"Error: {e}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nPress Enter to close browser...")
        input()
        await browser.close()
        await agent.cleanup()
        print("✓ Cleanup complete")


if __name__ == "__main__":
    print("Running simple action tests...")
    asyncio.run(test_each_action())