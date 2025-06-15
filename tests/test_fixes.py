"""Test the fixes to the next-gen system"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile
from browser_use.core.caching import rate_limiter

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_functionality():
    """Test basic clicking and typing with fixes"""
    
    logger.info("=== Testing Basic Functionality with Fixes ===")
    
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
        logger.info("✓ Agent initialized")
        
        # Create test page
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px; font-family: Arial;">
                <h1>Test Page - With Fixes</h1>
                
                <div style="margin: 20px 0;">
                    <input type="text" id="name-input" placeholder="Enter your name" style="padding: 8px;">
                    <button id="greet-btn" onclick="greet()">Say Hello</button>
                </div>
                
                <div id="output" style="margin-top: 20px; padding: 10px; background: #f0f0f0; min-height: 50px;">
                    Results will appear here...
                </div>
                
                <script>
                    function greet() {
                        const name = document.getElementById('name-input').value;
                        const output = document.getElementById('output');
                        if (name) {
                            output.textContent = 'Hello, ' + name + '!';
                        } else {
                            output.textContent = 'Please enter a name first.';
                        }
                    }
                </script>
            </body>
            </html>
        """)
        
        logger.info("\n--- Test 1: Type in input field ---")
        logger.info(f"Rate limiter status: {rate_limiter.get_remaining_calls()} calls remaining")
        
        result = await agent.execute_task("Type 'Alice' in the name input field")
        logger.info(f"Type result: {result.get('success')}")
        
        # Verify
        value = await agent.current_page.evaluate('document.getElementById("name-input").value')
        logger.info(f"Input value: '{value}'")
        
        await asyncio.sleep(2)
        
        logger.info("\n--- Test 2: Click button ---")
        logger.info(f"Rate limiter status: {rate_limiter.get_remaining_calls()} calls remaining")
        
        result = await agent.execute_task("Click the 'Say Hello' button")
        logger.info(f"Click result: {result.get('success')}")
        
        # Verify
        output = await agent.current_page.evaluate('document.getElementById("output").textContent')
        logger.info(f"Output text: '{output}'")
        
        await asyncio.sleep(2)
        
        # Test caching
        logger.info("\n--- Test 3: Repeat action (should use cache) ---")
        result = await agent.execute_task("Type 'Bob' in the name input field")
        logger.info(f"Type result (cached): {result.get('success')}")
        
        value = await agent.current_page.evaluate('document.getElementById("name-input").value')
        logger.info(f"New input value: '{value}'")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_real_website():
    """Test on a real website"""
    
    logger.info("=== Testing Real Website ===")
    
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
        
        # Test Wikipedia
        logger.info("\n--- Navigate to Wikipedia ---")
        result = await agent.execute_task("Go to wikipedia.org")
        logger.info(f"Navigation: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        logger.info("\n--- Search on Wikipedia ---")
        logger.info(f"Rate limiter: {rate_limiter.get_remaining_calls()} calls remaining")
        
        result = await agent.execute_task("Type 'Python programming' in the search box")
        logger.info(f"Type result: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Press Enter to search
        result = await agent.execute_task("Press Enter to search")
        logger.info(f"Search result: {result.get('success')}")
        
        await asyncio.sleep(3)
        
        # Extract some data
        logger.info("\n--- Extract data ---")
        result = await agent.execute_task("Extract the first paragraph of the article")
        logger.info(f"Extraction result: {result.get('success')}")
        
        if result.get('data'):
            logger.info(f"Extracted: {str(result['data'])[:200]}...")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_form_filling():
    """Test form filling capabilities"""
    
    logger.info("=== Testing Form Filling ===")
    
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
        
        # Create form page
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px; font-family: Arial;">
                <h1>Registration Form</h1>
                <form id="test-form">
                    <div style="margin: 10px 0;">
                        <label for="firstName">First Name:</label><br>
                        <input type="text" id="firstName" name="firstName" required>
                    </div>
                    
                    <div style="margin: 10px 0;">
                        <label for="lastName">Last Name:</label><br>
                        <input type="text" id="lastName" name="lastName" required>
                    </div>
                    
                    <div style="margin: 10px 0;">
                        <label for="email">Email:</label><br>
                        <input type="email" id="email" name="email" required>
                    </div>
                    
                    <div style="margin: 10px 0;">
                        <label for="country">Country:</label><br>
                        <select id="country" name="country">
                            <option value="">Select a country</option>
                            <option value="us">United States</option>
                            <option value="uk">United Kingdom</option>
                            <option value="ca">Canada</option>
                            <option value="au">Australia</option>
                        </select>
                    </div>
                    
                    <div style="margin: 10px 0;">
                        <label>
                            <input type="checkbox" id="newsletter" name="newsletter">
                            Subscribe to newsletter
                        </label>
                    </div>
                    
                    <button type="submit">Submit</button>
                </form>
                
                <div id="result" style="margin-top: 20px; padding: 10px; background: #f0f0f0;">
                    Form not submitted yet
                </div>
                
                <script>
                    document.getElementById('test-form').addEventListener('submit', (e) => {
                        e.preventDefault();
                        const formData = new FormData(e.target);
                        const data = Object.fromEntries(formData);
                        document.getElementById('result').innerHTML = 
                            '<h3>Form Submitted!</h3>' + 
                            '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    });
                </script>
            </body>
            </html>
        """)
        
        logger.info("\n--- Fill the form ---")
        logger.info(f"Rate limiter: {rate_limiter.get_remaining_calls()} calls remaining")
        
        # Test individual field filling with delays
        tasks = [
            ("Type 'John' in the first name field", 2),
            ("Type 'Doe' in the last name field", 2),
            ("Type 'john.doe@example.com' in the email field", 2),
            ("Select 'United States' from the country dropdown", 2),
            ("Check the newsletter subscription checkbox", 2),
            ("Click the Submit button", 3)
        ]
        
        for task, delay in tasks:
            logger.info(f"\n{task}")
            result = await agent.execute_task(task)
            logger.info(f"Result: {result.get('success')}")
            await asyncio.sleep(delay)
        
        # Check final result
        result_text = await agent.current_page.evaluate('document.getElementById("result").textContent')
        logger.info(f"\nFinal result: {result_text}")
        
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
    print("1. Basic functionality (type and click)")
    print("2. Real website (Wikipedia)")
    print("3. Form filling")
    
    choice = input("\nChoice (1-3): ")
    
    if choice == "1":
        asyncio.run(test_basic_functionality())
    elif choice == "2":
        asyncio.run(test_real_website())
    elif choice == "3":
        asyncio.run(test_form_filling())
    else:
        print("Invalid choice")