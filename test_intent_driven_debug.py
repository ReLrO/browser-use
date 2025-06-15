"""Debug test for intent-driven browser-use implementation"""

import asyncio
import logging
from langchain_anthropic import ChatAnthropic
from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig
from browser_use.core import Intent, IntentType, SubIntent, IntentParameter

# Setup logging to see what's happening
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_step_by_step():
	"""Test the intent-driven implementation step by step"""
	
	print("\n=== Step 1: Initialize Components ===")
	
	# Initialize LLM
	llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022", timeout=10)
	
	# Create browser
	browser = Browser(config=BrowserConfig(headless=False))
	
	# Create agent
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,
		use_accessibility=True,
		enable_streaming=True
	)
	
	try:
		# Initialize agent
		print("Initializing agent...")
		await agent.initialize()
		print("✓ Agent initialized")
		
		# Create browser context
		print("\n=== Step 2: Create Browser Context ===")
		context = await browser.new_context()
		page = await context.new_page()
		agent.current_page = page
		print("✓ Browser context created")
		
		# Test 1: Simple navigation
		print("\n=== Test 1: Simple Navigation ===")
		
		# Create a simple navigation intent manually
		nav_intent = Intent(
			task_description="Navigate to example.com",
			type=IntentType.NAVIGATION,
			primary_goal="Go to example.com",
			parameters=[
				IntentParameter(name="url", value="https://example.com", type="string", required=True)
			],
			sub_intents=[
				SubIntent(
					id="nav_1",
					description="Navigate to https://example.com",
					type=IntentType.NAVIGATION,
					parameters=[
						IntentParameter(name="url", value="https://example.com", type="string", required=True)
					]
				)
			]
		)
		
		print(f"Created intent: {nav_intent.primary_goal}")
		
		# Execute the intent directly
		result = await agent.execute_intent_directly(nav_intent)
		print(f"Result: {result}")
		
		# Wait to see the result
		await asyncio.sleep(2)
		
		# Test 2: Using execute_task
		print("\n=== Test 2: Using execute_task ===")
		
		try:
			result = await agent.execute_task(
				"Click on the 'More information' link",
				context={"page": page}
			)
			print(f"Task result: {result}")
		except Exception as e:
			print(f"Error with execute_task: {e}")
			import traceback
			traceback.print_exc()
		
		# Wait a bit
		await asyncio.sleep(3)
		
		# Test 3: Test intent analysis only
		print("\n=== Test 3: Intent Analysis ===")
		
		test_tasks = [
			"Search for 'Python tutorials'",
			"Fill out the contact form",
			"Login with username test@example.com and password mypassword"
		]
		
		for task in test_tasks:
			print(f"\nAnalyzing: '{task}'")
			try:
				result = await agent.intent_analyzer.analyze(task)
				print(f"  Intent: {result.intent}")
				print(f"  Type: {result.intent.type}")
				print(f"  Sub-intents: {len(result.intent.sub_intents)}")
				if result.intent.parameters:
					print(f"  Parameters: {[(p.name, p.value[:20] + '...' if len(p.value) > 20 else p.value) for p in result.intent.parameters]}")
			except Exception as e:
				print(f"  Error: {e}")
				import traceback
				traceback.print_exc()
		
	except Exception as e:
		print(f"\nError: {e}")
		import traceback
		traceback.print_exc()
	finally:
		print("\n=== Cleanup ===")
		await agent.cleanup()
		await browser.close()
		print("✓ Cleanup complete")


async def test_minimal_working():
	"""Test the absolute minimal working example"""
	
	print("\n=== Minimal Working Test ===")
	
	# Check if the modules are loading correctly
	try:
		from browser_use.core import IntentAnalyzer, IntentManager
		from browser_use.perception import VisionEngine, IncrementalDOMProcessor
		print("✓ Core modules imported successfully")
	except Exception as e:
		print(f"✗ Failed to import core modules: {e}")
		return
	
	# Test basic initialization
	llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022", timeout=10)
	
	try:
		analyzer = IntentAnalyzer(llm)
		print("✓ IntentAnalyzer created")
		
		# Test basic analysis
		result = await analyzer.analyze("Go to google.com")
		print(f"✓ Basic analysis works: {result}")
		
	except Exception as e:
		print(f"✗ Error: {e}")
		import traceback
		traceback.print_exc()


if __name__ == "__main__":
	# Run minimal test first
	asyncio.run(test_minimal_working())
	
	# Then run full test
	asyncio.run(test_step_by_step())