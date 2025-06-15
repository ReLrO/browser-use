"""Debug why type actions aren't working"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


async def test_type_isolated():
    """Test type action in isolation"""
    
    print("\n=== Testing Type Action in Isolation ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent - let it manage its own browser
    agent = NextGenBrowserAgent(
        llm=llm,
        use_vision=False,
        use_accessibility=False,
        enable_streaming=False
    )
    
    try:
        # Initialize agent (this will set up all components)
        await agent.initialize()
        
        # Let the agent start its own browser
        # This ensures browser_session is properly set up
        await agent._start_browser()
        
        print("✓ Agent and browser initialized")
        
        # Create a simple test page
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Type Test</h1>
                <input type="text" id="test-input" placeholder="Type here..." style="padding: 10px;">
                <div id="result"></div>
            </body>
            </html>
        """)
        
        print("\n--- Testing Type Action ---")
        print("Current page URL:", agent.current_page.url)
        
        # Execute the type task
        result = await agent.execute_task("Type 'Hello World' in the input field")
        
        print(f"\nResult: {result}")
        print(f"Success: {result.get('success', False)}")
        
        # Check if text was typed
        input_value = await agent.current_page.evaluate('document.getElementById("test-input").value')
        print(f"Input value after typing: '{input_value}'")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nPress Enter to close browser...")
        input()
        await agent.cleanup()
        print("✓ Cleanup complete")


if __name__ == "__main__":
    print("Testing type action in isolation...")
    asyncio.run(test_type_isolated())