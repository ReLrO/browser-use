"""Test individual actions to debug issues"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent

# Enable debug logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


async def test_actions():
    """Test each action individually"""
    
    print("\n=== Testing Individual Actions ===")
    
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
    
    try:
        # Initialize agent
        await agent.initialize()
        
        # Let the agent manage its own browser
        await agent._start_browser()
        
        print("✓ Browser and agent initialized")
        
        # Test 1: Click action on a simple page
        print("\n--- Test 1: Click Action ---")
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Click Test</h1>
                <button id="test-button" onclick="document.getElementById('result').textContent = 'Button clicked!'">
                    Click Me
                </button>
                <div id="result"></div>
            </body>
            </html>
        """)
        
        try:
            result = await agent.execute_task("Click the button that says 'Click Me'")
            print(f"Click Success: {result.get('success', False)}")
            
            # Check if button was clicked
            result_text = await agent.current_page.evaluate('document.getElementById("result").textContent')
            print(f"Result after click: '{result_text}'")
        except Exception as e:
            print(f"Click Error: {e}")
        
        # Test 2: Type action
        print("\n--- Test 2: Type Action ---")
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Type Test</h1>
                <input type="text" id="test-input" placeholder="Type here..." style="padding: 10px;">
                <div id="typed-result"></div>
            </body>
            </html>
        """)
        
        try:
            print("Calling execute_task for type action...")
            result = await agent.execute_task("Type 'Hello World' in the input field")
            print(f"Result returned: {result}")
            print(f"Type Success: {result.get('success', False)}")
            
            # Check if text was typed
            input_value = await agent.current_page.evaluate('document.getElementById("test-input").value')
            print(f"Input value: '{input_value}'")
        except Exception as e:
            print(f"Type Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Select from dropdown
        print("\n--- Test 3: Select Action ---")
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Select Test</h1>
                <select id="test-select">
                    <option value="">Choose an option</option>
                    <option value="option1">Option 1</option>
                    <option value="option2">Option 2</option>
                    <option value="option3">Option 3</option>
                </select>
                <div id="select-result"></div>
            </body>
            </html>
        """)
        
        try:
            print("Calling execute_task for select action...")
            result = await agent.execute_task("Select 'Option 2' from the dropdown")
            print(f"Result returned: {result}")
            print(f"Select Success: {result.get('success', False)}")
            
            # Check if option was selected
            select_value = await agent.current_page.evaluate('document.getElementById("test-select").value')
            print(f"Selected value: '{select_value}'")
        except Exception as e:
            print(f"Select Error: {e}")
            import traceback
            traceback.print_exc()
        
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
    print("Testing individual actions...")
    asyncio.run(test_actions())