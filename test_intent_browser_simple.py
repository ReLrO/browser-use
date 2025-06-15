"""Simple integration test for the intent-driven browser-use implementation"""

import asyncio
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_real_browser_navigation():
	"""Test with real browser - navigate to example.com"""
	
	print("\n=== Testing Real Browser Navigation ===")
	
	# Initialize components
	import os
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	browser = Browser(config=BrowserConfig(headless=False))
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,
		use_accessibility=True,
		enable_streaming=True
	)
	
	try:
		# Initialize agent
		await agent.initialize()
		print("✓ Agent initialized")
		
		# Start the browser session
		await browser.start()
		
		# Create a new tab
		page = await browser.new_tab()
		
		# Set page on agent
		agent.current_page = page
		
		# Set the browser session properly
		agent.browser_session = browser
		
		# Initialize execution context
		agent._execution_context = {
			"page": page,
			"start_time": None
		}
		
		# Test 1: Navigate to example.com
		print("\n--- Test 1: Navigate to example.com ---")
		
		try:
			result = await agent.execute_task("Go to example.com")
			print(f"Navigation result: {result}")
		except Exception as e:
			print(f"Error during navigation: {e}")
			import traceback
			traceback.print_exc()
		
		# Wait to see the page
		await asyncio.sleep(2)
		
		# Check current URL
		current_url = page.url
		print(f"Current URL: {current_url}")
		
		# Test 2: Simple interaction
		print("\n--- Test 2: Test intent analysis and execution ---")
		
		# First, let's see what the intent analyzer produces
		try:
			analysis_result = await agent.intent_analyzer.analyze("Click on the 'More information' link")
			print(f"\nIntent analysis result:")
			print(f"  Primary goal: {analysis_result.intent.primary_goal}")
			print(f"  Type: {analysis_result.intent.type}")
			print(f"  Sub-intents: {len(analysis_result.intent.sub_intents)}")
			for i, sub in enumerate(analysis_result.intent.sub_intents):
				print(f"    {i+1}. {sub.description} (type: {sub.type})")
		except Exception as e:
			print(f"Error during intent analysis: {e}")
			import traceback
			traceback.print_exc()
		
		# Test 3: Direct intent execution
		print("\n--- Test 3: Test direct navigation ---")
		
		# Try to navigate directly using the page object
		try:
			await page.goto("https://example.com")
			print("✓ Direct navigation successful")
			await asyncio.sleep(2)
		except Exception as e:
			print(f"Error during direct navigation: {e}")
		
		print("\n✅ Tests completed!")
		
	except Exception as e:
		print(f"\n❌ Error: {e}")
		import traceback
		traceback.print_exc()
		
	finally:
		# Cleanup
		await browser.close()
		await agent.cleanup()
		print("\n✓ Cleanup complete")


async def test_minimal_intent_execution():
	"""Test minimal intent execution to debug issues"""
	
	print("\n=== Testing Minimal Intent Execution ===")
	
	import os
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(llm=llm, use_vision=False, use_accessibility=False)
	await agent.initialize()
	
	# Test just the intent analyzer
	print("\nTesting intent analyzer...")
	result = await agent.intent_analyzer.analyze("Navigate to https://google.com")
	print(f"Analysis complete: {result.intent.primary_goal}")
	
	# Test the orchestrator setup
	print("\nChecking orchestrator...")
	print(f"Orchestrator initialized: {agent.action_orchestrator is not None}")
	print(f"Element resolver initialized: {agent.element_resolver is not None}")
	
	await agent.cleanup()


if __name__ == "__main__":
	# Run tests
	asyncio.run(test_real_browser_navigation())
	asyncio.run(test_minimal_intent_execution())