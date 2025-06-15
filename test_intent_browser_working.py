"""Test the intent-driven browser-use implementation after fixing JSON serialization"""

import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.migration import create_enhanced_agent


async def test_intent_driven_navigation():
	"""Test that the intent-driven implementation works end-to-end"""
	
	print("\n=== Testing Intent-Driven Browser Navigation ===")
	
	# Initialize the enhanced agent
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = create_enhanced_agent(llm=llm)
	
	try:
		# Test 1: Simple navigation
		print("\n--- Test 1: Navigate to example.com ---")
		result = await agent.execute_task(
			"Navigate to https://example.com",
			url="https://example.com"
		)
		
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
		
		if result.get('errors'):
			print(f"Errors: {result['errors']}")
		
		# Test 2: More complex task
		print("\n--- Test 2: Search on a website ---")
		result = await agent.execute_task(
			"Go to https://en.wikipedia.org and search for 'artificial intelligence'",
			url="https://en.wikipedia.org"
		)
		
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
		
		if result.get('errors'):
			print(f"Errors: {result['errors']}")
		
		# Test 3: Extract data
		print("\n--- Test 3: Extract page title ---")
		result = await agent.execute_task(
			"Get the page title from the current page"
		)
		
		print(f"Success: {result['success']}")
		print(f"Extracted data: {result.get('data', {})}")
		
		print("\n✅ All tests completed!")
		
	except Exception as e:
		print(f"\n❌ Test failed: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		# Cleanup
		await agent.cleanup()
		print("\n✓ Cleanup complete")


async def test_direct_agent_usage():
	"""Test using NextGenBrowserAgent directly"""
	
	print("\n=== Testing Direct Agent Usage ===")
	
	from browser_use.agent.next_gen_agent import NextGenBrowserAgent
	from browser_use.browser import Browser, BrowserConfig
	
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
		
		# Test navigation
		print("\n--- Testing navigation ---")
		result = await agent.execute_task(
			"Navigate to https://example.com"
		)
		
		print(f"Result: {result}")
		print(f"Success: {result['success']}")
		print(f"Current URL: {page.url}")
		
		# Verify we actually navigated
		assert "example.com" in page.url, f"Expected to be on example.com, but URL is {page.url}"
		print("✅ Navigation successful!")
		
	except Exception as e:
		print(f"\n❌ Error: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		await browser.close()
		await agent.cleanup()
		print("\n✓ Cleanup complete")


if __name__ == "__main__":
	print("Testing intent-driven browser-use implementation...")
	
	# Run both test approaches
	asyncio.run(test_intent_driven_navigation())
	print("\n" + "="*50 + "\n")
	asyncio.run(test_direct_agent_usage())