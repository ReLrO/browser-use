"""Simple test for next-gen browser automation"""

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


async def test_simple_navigation():
    """Test basic navigation and interaction"""
    
    logger.info("=== Testing Simple Navigation ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Configure browser
    profile = BrowserProfile(
        headless=False,
        viewport={"width": 1280, "height": 720}
    )
    
    # Create agent
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=profile,
        use_vision=False,
        use_accessibility=False,
        enable_streaming=False
    )
    
    try:
        # Initialize
        await agent.initialize()
        await agent._start_browser()
        logger.info("✓ Agent initialized")
        
        # Test 1: Simple navigation
        logger.info("\n--- Test 1: Navigate to Wikipedia ---")
        result = await agent.execute_task("Go to wikipedia.org")
        logger.info(f"Navigation result: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Test 2: Search on Wikipedia
        logger.info("\n--- Test 2: Search on Wikipedia ---")
        result = await agent.execute_task(
            "Search for 'Python programming language' using the search box"
        )
        logger.info(f"Search result: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Test 3: Extract information
        logger.info("\n--- Test 3: Extract Information ---")
        result = await agent.execute_task(
            "Extract the first paragraph of the article"
        )
        logger.info(f"Extraction result: {result.get('success')}")
        if result.get('success'):
            data = result.get('data', {})
            logger.info(f"Extracted text: {str(data)[:200]}...")
        
        # Test 4: Click a link
        logger.info("\n--- Test 4: Click a Link ---")
        result = await agent.execute_task(
            "Click on the 'History' section link if available"
        )
        logger.info(f"Click result: {result.get('success')}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_form_interaction():
    """Test form filling"""
    
    logger.info("=== Testing Form Interaction ===")
    
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
        
        # Create a test form
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px; font-family: Arial;">
                <h1>Test Form</h1>
                <form>
                    <div style="margin: 10px 0;">
                        <label for="name">Name:</label><br>
                        <input type="text" id="name" name="name" placeholder="Enter your name">
                    </div>
                    <div style="margin: 10px 0;">
                        <label for="email">Email:</label><br>
                        <input type="email" id="email" name="email" placeholder="Enter your email">
                    </div>
                    <div style="margin: 10px 0;">
                        <label for="message">Message:</label><br>
                        <textarea id="message" name="message" rows="4" cols="50" placeholder="Enter your message"></textarea>
                    </div>
                    <div style="margin: 10px 0;">
                        <label for="country">Country:</label><br>
                        <select id="country" name="country">
                            <option value="">Select a country</option>
                            <option value="us">United States</option>
                            <option value="uk">United Kingdom</option>
                            <option value="ca">Canada</option>
                        </select>
                    </div>
                    <button type="submit">Submit</button>
                </form>
                <div id="result" style="margin-top: 20px; padding: 10px; background: #f0f0f0;"></div>
            </body>
            </html>
        """)
        
        # Test form filling
        logger.info("\n--- Testing Form Fill ---")
        result = await agent.execute_task(
            "Fill the form with: Name: 'John Doe', Email: 'john@example.com', Message: 'This is a test message', Country: 'United States'"
        )
        logger.info(f"Form fill result: {result.get('success')}")
        
        # Verify values
        await asyncio.sleep(1)
        name_value = await agent.current_page.evaluate('document.getElementById("name").value')
        email_value = await agent.current_page.evaluate('document.getElementById("email").value')
        message_value = await agent.current_page.evaluate('document.getElementById("message").value')
        country_value = await agent.current_page.evaluate('document.getElementById("country").value')
        
        logger.info(f"Verification:")
        logger.info(f"  Name: {name_value}")
        logger.info(f"  Email: {email_value}")
        logger.info(f"  Message: {message_value}")
        logger.info(f"  Country: {country_value}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_element_interaction():
    """Test various element interactions"""
    
    logger.info("=== Testing Element Interactions ===")
    
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
        
        # Create interactive test page
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px; font-family: Arial;">
                <h1>Interactive Elements Test</h1>
                
                <div style="margin: 20px 0;">
                    <h2>Buttons</h2>
                    <button id="btn1" onclick="document.getElementById('output').textContent='Button 1 clicked'">
                        Click Me
                    </button>
                    <button id="btn2" onclick="document.getElementById('output').textContent='Button 2 clicked'">
                        Another Button
                    </button>
                </div>
                
                <div style="margin: 20px 0;">
                    <h2>Checkboxes</h2>
                    <label>
                        <input type="checkbox" id="check1" name="options" value="option1">
                        Option 1
                    </label><br>
                    <label>
                        <input type="checkbox" id="check2" name="options" value="option2">
                        Option 2
                    </label>
                </div>
                
                <div style="margin: 20px 0;">
                    <h2>Radio Buttons</h2>
                    <label>
                        <input type="radio" name="choice" value="a" id="radio1">
                        Choice A
                    </label><br>
                    <label>
                        <input type="radio" name="choice" value="b" id="radio2">
                        Choice B
                    </label>
                </div>
                
                <div style="margin: 20px 0;">
                    <h2>Links</h2>
                    <a href="#" onclick="document.getElementById('output').textContent='Link 1 clicked'; return false;">
                        Test Link 1
                    </a> | 
                    <a href="#" onclick="document.getElementById('output').textContent='Link 2 clicked'; return false;">
                        Test Link 2
                    </a>
                </div>
                
                <div id="output" style="margin-top: 20px; padding: 10px; background: #f0f0f0; min-height: 30px;">
                    Output will appear here
                </div>
            </body>
            </html>
        """)
        
        # Test 1: Click button
        logger.info("\n--- Test 1: Click Button ---")
        result = await agent.execute_task("Click the button that says 'Click Me'")
        logger.info(f"Result: {result.get('success')}")
        output = await agent.current_page.evaluate('document.getElementById("output").textContent')
        logger.info(f"Output: {output}")
        
        await asyncio.sleep(1)
        
        # Test 2: Check checkboxes
        logger.info("\n--- Test 2: Check Checkboxes ---")
        result = await agent.execute_task("Check both Option 1 and Option 2 checkboxes")
        logger.info(f"Result: {result.get('success')}")
        check1 = await agent.current_page.evaluate('document.getElementById("check1").checked')
        check2 = await agent.current_page.evaluate('document.getElementById("check2").checked')
        logger.info(f"Checkbox states: Option 1={check1}, Option 2={check2}")
        
        await asyncio.sleep(1)
        
        # Test 3: Select radio button
        logger.info("\n--- Test 3: Select Radio Button ---")
        result = await agent.execute_task("Select Choice B radio button")
        logger.info(f"Result: {result.get('success')}")
        radio2 = await agent.current_page.evaluate('document.getElementById("radio2").checked')
        logger.info(f"Choice B selected: {radio2}")
        
        await asyncio.sleep(1)
        
        # Test 4: Click link
        logger.info("\n--- Test 4: Click Link ---")
        result = await agent.execute_task("Click on Test Link 2")
        logger.info(f"Result: {result.get('success')}")
        output = await agent.current_page.evaluate('document.getElementById("output").textContent')
        logger.info(f"Output: {output}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def main():
    """Run all tests"""
    tests = [
        ("Simple Navigation", test_simple_navigation),
        ("Form Interaction", test_form_interaction),
        ("Element Interaction", test_element_interaction)
    ]
    
    print("Select a test to run:")
    for i, (name, _) in enumerate(tests):
        print(f"{i+1}. {name}")
    print("0. Run all tests")
    
    choice = input("\nEnter your choice (0-3): ")
    
    try:
        choice = int(choice)
        if choice == 0:
            for name, test_func in tests:
                print(f"\n{'='*60}")
                print(f"Running: {name}")
                print('='*60)
                await test_func()
        elif 1 <= choice <= len(tests):
            await tests[choice-1][1]()
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")


if __name__ == "__main__":
    asyncio.run(main())