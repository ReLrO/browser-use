"""Debug intent decomposition"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


async def test_specific_intents():
	"""Test specific intent decomposition"""
	
	print("\n=== Testing Intent Decomposition ===")
	
	# Initialize components
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,
		use_accessibility=True,
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
				<h1>Simple Test Page</h1>
				<input type="text" id="search" placeholder="Search here..." style="padding: 10px;">
				<button id="btn" style="padding: 10px;">Click Me</button>
			</body>
			</html>
		""")
		
		print("\n--- Test 1: Simple Navigation ---")
		result = await agent.execute_task("Go to google.com")
		print(f"Success: {result['success']}")
		print(f"Result: {result}")
		
		# Go back to test page
		await page.go_back()
		await asyncio.sleep(1)
		
		print("\n--- Test 2: Type in Search Box ---")
		result = await agent.execute_task("Type 'hello world' in the search box")
		print(f"Success: {result['success']}")
		print(f"Result: {result}")
		
		# Check value
		value = await page.evaluate('document.getElementById("search").value')
		print(f"Actual value in search box: '{value}'")
		
		print("\n--- Test 3: Click Button ---")
		result = await agent.execute_task("Click the button")
		print(f"Success: {result['success']}")
		print(f"Result: {result}")
		
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
	print("Testing intent decomposition...")
	asyncio.run(test_specific_intents())