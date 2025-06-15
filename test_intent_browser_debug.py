"""Debug test for the intent-driven browser-use implementation"""

import asyncio
import logging
import json
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging for specific modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('browser_use.core.orchestrator').setLevel(logging.DEBUG)
logging.getLogger('browser_use.core.intent').setLevel(logging.DEBUG)


async def test_navigation_step_by_step():
	"""Test navigation with detailed debugging"""
	
	print("\n=== Testing Navigation Step by Step ===")
	
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
		use_vision=False,  # Disable vision to simplify
		use_accessibility=False,  # Disable accessibility to simplify
		enable_streaming=False  # Disable streaming to simplify
	)
	
	try:
		# Initialize agent
		await agent.initialize()
		print("✓ Agent initialized")
		
		# Start the browser session
		await browser.start()
		print("✓ Browser started")
		
		# Create a new tab
		page = await browser.new_tab()
		print(f"✓ New tab created, URL: {page.url}")
		
		# Set page on agent
		agent.current_page = page
		agent.browser_session = browser
		agent._execution_context = {
			"page": page,
			"start_time": None
		}
		
		# Step 1: Analyze the intent
		print("\n--- Step 1: Analyze Intent ---")
		analysis_result = await agent.intent_analyzer.analyze("Navigate to https://example.com")
		print(f"Primary goal: {analysis_result.intent.primary_goal}")
		print(f"Intent type: {analysis_result.intent.type}")
		print(f"Sub-intents: {len(analysis_result.intent.sub_intents)}")
		
		for i, sub in enumerate(analysis_result.intent.sub_intents):
			print(f"  {i+1}. {sub.description} (type: {sub.type})")
			if sub.parameters:
				for param in sub.parameters:
					print(f"     - {param.name}: {param.value}")
		
		# Step 2: Try to execute the intent directly
		print("\n--- Step 2: Execute Intent Directly ---")
		intent = analysis_result.intent
		
		# Register intent
		await agent.intent_manager.register_intent(intent)
		print("✓ Intent registered")
		
		# Get perception data
		perception_data = await agent._get_perception_data()
		print(f"✓ Perception data gathered (keys: {list(perception_data.keys())})")
		
		# Try to execute
		print("\nExecuting intent through orchestrator...")
		try:
			execution_result = await agent.action_orchestrator.execute_intent(
				intent,
				page,
				agent._execution_context
			)
			print(f"✓ Execution result: success={execution_result.success}")
			print(f"  Duration: {execution_result.duration_seconds}s")
			print(f"  Actions taken: {len(execution_result.actions_taken)}")
			
			# Check if we navigated
			await asyncio.sleep(1)
			print(f"\nCurrent URL: {page.url}")
			
		except Exception as e:
			print(f"✗ Execution failed: {e}")
			import traceback
			traceback.print_exc()
		
		# Step 3: Test raw navigation
		print("\n--- Step 3: Test Raw Navigation ---")
		try:
			await page.goto("https://example.com")
			print(f"✓ Raw navigation successful, URL: {page.url}")
		except Exception as e:
			print(f"✗ Raw navigation failed: {e}")
		
	except Exception as e:
		print(f"\n❌ Error: {e}")
		import traceback
		traceback.print_exc()
		
	finally:
		# Cleanup
		await browser.close()
		await agent.cleanup()
		print("\n✓ Cleanup complete")


if __name__ == "__main__":
	asyncio.run(test_navigation_step_by_step())