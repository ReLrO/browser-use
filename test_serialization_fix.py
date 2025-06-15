"""Test to identify the JSON serialization issue"""

import asyncio
import os
import logging
import json
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


async def test_serialization():
    """Test to find where JSON serialization fails"""
    
    print("\n=== Testing JSON Serialization ===")
    
    # Initialize components
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    agent = NextGenBrowserAgent(
        llm=llm,
        use_vision=False,
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
        
        # Create a test page
        await page.set_content("""
            <html>
            <body>
                <button>Test Button</button>
            </body>
            </html>
        """)
        
        # Get perception data
        print("\n--- Getting perception data ---")
        perception_data = await agent._get_perception_data()
        
        # Try to serialize it
        print("\n--- Checking what can be serialized ---")
        for key, value in perception_data.items():
            try:
                json.dumps({key: value})
                print(f"✓ {key}: serializable")
            except Exception as e:
                print(f"✗ {key}: NOT serializable - {type(value).__name__} - {e}")
                
                # If it's a dict, check its contents
                if isinstance(value, dict):
                    for k, v in value.items():
                        try:
                            json.dumps({k: v})
                            print(f"  ✓ {key}.{k}: serializable")
                        except Exception as e2:
                            print(f"  ✗ {key}.{k}: NOT serializable - {type(v).__name__} - {e2}")
        
        # Now try to execute a task
        print("\n--- Executing task ---")
        try:
            result = await agent.execute_task("Click the button")
            print(f"Success: {result.get('success', False)}")
        except Exception as e:
            print(f"Error during task execution: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nPress Enter to close browser...")
        input()
        await browser.close()
        await agent.cleanup()


if __name__ == "__main__":
    print("Testing JSON serialization...")
    asyncio.run(test_serialization())