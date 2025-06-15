"""Comprehensive test of the intent-driven browser-use implementation"""

import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig


async def test_comprehensive_intent_features():
	"""Test various features of the intent-driven browser implementation"""
	
	print("\n=== Comprehensive Intent-Driven Browser Test ===")
	
	# Initialize components
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=False,  # Disable vision for faster testing
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
		
		# Test 1: Simple Navigation
		print("\n--- Test 1: Simple Navigation ---")
		result = await agent.execute_task(
			"Navigate to https://example.com"
		)
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		print(f"Current URL: {page.url}")
		assert "example.com" in page.url, f"Expected to be on example.com, but URL is {page.url}"
		print("✅ Navigation test passed!")
		
		# Test 2: Complex Task with Sub-intents
		print("\n--- Test 2: Complex Task Decomposition ---")
		result = await agent.execute_task(
			"Go to Wikipedia and search for 'artificial intelligence'"
		)
		print(f"Success: {result['success']}")
		print(f"Intent ID: {result.get('intent_id', 'N/A')}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
		
		if result.get('errors'):
			print(f"Errors: {result['errors']}")
		
		# Test 3: Direct Intent Execution
		print("\n--- Test 3: Direct Intent Execution ---")
		# First, analyze a task into an intent
		analysis_result = await agent.intent_analyzer.analyze(
			"Click on the first link on the page"
		)
		print(f"Intent type: {analysis_result.intent.type}")
		print(f"Primary goal: {analysis_result.intent.primary_goal}")
		print(f"Sub-intents: {len(analysis_result.intent.sub_intents)}")
		
		# Execute the intent directly
		result = await agent.execute_intent_directly(analysis_result.intent)
		print(f"Direct execution success: {result.get('success', False)}")
		
		# Test 4: Intent History
		print("\n--- Test 4: Intent History ---")
		history = await agent.get_intent_history(limit=5)
		print(f"Recent intents executed: {len(history)}")
		for i, intent in enumerate(history[:3]):
			print(f"  {i+1}. {intent.primary_goal} (Status: {intent.status})")
		
		# Test 5: Current State
		print("\n--- Test 5: Current State ---")
		state = await agent.get_current_state()
		print(f"Current URL: {state.get('url', 'N/A')}")
		print(f"Perception systems active: {list(state.get('perception_results', {}).keys())}")
		
		# Test 6: Multiple Tabs
		print("\n--- Test 6: Multiple Tabs ---")
		new_page = await agent.new_tab()
		print("✓ New tab created")
		
		await agent.switch_tab(new_page)
		print("✓ Switched to new tab")
		
		result = await agent.execute_task(
			"Navigate to https://google.com",
			url="https://google.com"
		)
		print(f"Navigation in new tab success: {result['success']}")
		print(f"New tab URL: {new_page.url}")
		
		# Test 7: Performance Metrics
		print("\n--- Test 7: Performance Metrics ---")
		total_duration = sum(intent.duration_seconds for intent in history if hasattr(intent, 'duration_seconds'))
		total_tokens = sum(intent.tokens_used for intent in history if hasattr(intent, 'tokens_used'))
		print(f"Total execution time: {total_duration:.2f}s")
		print(f"Total tokens used: {total_tokens}")
		
		print("\n✅ All tests completed successfully!")
		
	except Exception as e:
		print(f"\n❌ Test failed: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		await browser.close()
		await agent.cleanup()
		print("\n✓ Cleanup complete")


async def test_error_handling():
	"""Test error handling in the intent-driven implementation"""
	
	print("\n=== Testing Error Handling ===")
	
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
	
	browser = Browser(config=BrowserConfig(headless=True))
	
	try:
		await agent.initialize()
		await browser.start()
		
		page = await browser.new_tab()
		agent.current_page = page
		agent.browser_session = browser
		
		# Test invalid URL
		print("\n--- Testing Invalid URL ---")
		result = await agent.execute_task(
			"Navigate to invalid://not-a-real-url"
		)
		print(f"Success: {result['success']}")
		print(f"Errors: {result.get('errors', 'None')}")
		
		# Test ambiguous task
		print("\n--- Testing Ambiguous Task ---")
		result = await agent.execute_task(
			"Do something with the page"
		)
		print(f"Success: {result['success']}")
		if result.get('requires_clarification'):
			print("Clarification requested:")
			for q in result.get('clarification_questions', []):
				print(f"  - {q}")
		
		print("\n✅ Error handling tests completed!")
		
	except Exception as e:
		print(f"\n❌ Error handling test failed: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		await browser.close()
		await agent.cleanup()


if __name__ == "__main__":
	print("Testing comprehensive intent-driven browser-use implementation...")
	
	# Run comprehensive feature test
	asyncio.run(test_comprehensive_intent_features())
	
	print("\n" + "="*50 + "\n")
	
	# Run error handling test
	asyncio.run(test_error_handling())