"""Test the intent-driven browser with actual element interaction"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('browser_use.core.orchestrator').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.intent').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.resolver').setLevel(logging.DEBUG)


async def test_search_interaction():
	"""Test searching on a website - requires element recognition"""
	
	print("\n=== Testing Search Interaction ===")
	
	# Initialize components
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=False,  # Start without vision to see if DOM is enough
		use_accessibility=True,  # Enable accessibility for better element finding
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
		
		# Test 1: Search on DuckDuckGo (simpler than Google)
		print("\n--- Test 1: Search on DuckDuckGo ---")
		result = await agent.execute_task(
			"Go to duckduckgo.com and search for 'OpenAI GPT-4'"
		)
		
		print(f"\nTask result:")
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
		
		if result.get('errors'):
			print(f"Errors: {result['errors']}")
		
		# Wait a bit to see results
		await asyncio.sleep(3)
		print(f"Current URL: {page.url}")
		
		# Test 2: Click on a result
		print("\n--- Test 2: Click on first search result ---")
		result = await agent.execute_task(
			"Click on the first search result"
		)
		
		print(f"\nTask result:")
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		
		await asyncio.sleep(2)
		print(f"Current URL after click: {page.url}")
		
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


async def test_form_filling():
	"""Test form filling - requires finding and interacting with form elements"""
	
	print("\n=== Testing Form Filling ===")
	
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=False,
		use_accessibility=True,
		enable_streaming=False
	)
	
	browser = Browser(config=BrowserConfig(headless=False))
	
	try:
		await agent.initialize()
		await browser.start()
		
		page = await browser.new_tab()
		agent.current_page = page
		agent.browser_session = browser
		
		# Create a simple HTML form for testing
		await page.set_content("""
			<html>
			<body>
				<h1>Test Form</h1>
				<form>
					<label for="name">Name:</label>
					<input type="text" id="name" name="name"><br><br>
					
					<label for="email">Email:</label>
					<input type="email" id="email" name="email"><br><br>
					
					<label for="message">Message:</label>
					<textarea id="message" name="message"></textarea><br><br>
					
					<button type="submit">Submit</button>
				</form>
			</body>
			</html>
		""")
		
		print("✓ Test form loaded")
		
		# Test form filling
		print("\n--- Testing form filling ---")
		result = await agent.execute_task(
			"Fill out the form with name 'John Doe', email 'john@example.com', and message 'This is a test message'"
		)
		
		print(f"\nTask result:")
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		
		# Verify form values
		await asyncio.sleep(1)
		name_value = await page.evaluate('document.getElementById("name").value')
		email_value = await page.evaluate('document.getElementById("email").value')
		message_value = await page.evaluate('document.getElementById("message").value')
		
		print(f"\nForm values after filling:")
		print(f"Name: {name_value}")
		print(f"Email: {email_value}")
		print(f"Message: {message_value}")
		
		# Test clicking submit
		print("\n--- Testing form submission ---")
		result = await agent.execute_task(
			"Click the submit button"
		)
		
		print(f"\nSubmit result:")
		print(f"Success: {result['success']}")
		
	except Exception as e:
		print(f"\n❌ Test failed: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		print("\nPress Enter to close browser...")
		input()
		await browser.close()
		await agent.cleanup()


async def test_wikipedia_interaction():
	"""Test interacting with Wikipedia - real world example"""
	
	print("\n=== Testing Wikipedia Interaction ===")
	
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,  # Enable vision for complex pages
		use_accessibility=True,
		enable_streaming=False
	)
	
	browser = Browser(config=BrowserConfig(headless=False))
	
	try:
		await agent.initialize()
		await browser.start()
		
		page = await browser.new_tab()
		agent.current_page = page
		agent.browser_session = browser
		
		print("✓ Browser initialized with vision enabled")
		
		# Navigate to Wikipedia
		print("\n--- Going to Wikipedia ---")
		result = await agent.execute_task(
			"Go to Wikipedia and search for 'Artificial Intelligence'"
		)
		
		print(f"\nNavigation result:")
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		
		await asyncio.sleep(3)
		
		# Try to click on a specific section
		print("\n--- Clicking on History section ---")
		result = await agent.execute_task(
			"Click on the 'History' section in the table of contents"
		)
		
		print(f"\nClick result:")
		print(f"Success: {result['success']}")
		print(f"Current URL: {page.url}")
		
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
	print("Testing interactive capabilities of intent-driven browser...")
	
	# Run tests one by one
	asyncio.run(test_search_interaction())
	
	print("\n" + "="*50 + "\n")
	
	asyncio.run(test_form_filling())
	
	print("\n" + "="*50 + "\n")
	
	asyncio.run(test_wikipedia_interaction())