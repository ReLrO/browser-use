"""Simple test to demonstrate the intent-driven browser-use implementation"""

import asyncio
import pytest
from langchain_anthropic import ChatAnthropic
from browser_use.migration import create_enhanced_agent
from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext


async def test_basic_intent_driven_navigation():
	"""Test basic intent-driven navigation and interaction"""
	
	# Initialize LLM
	llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022", timeout=10)
	
	# Option 1: Using create_enhanced_agent helper
	print("\n=== Testing with create_enhanced_agent ===")
	try:
		agent = create_enhanced_agent(llm=llm)
		
		# Execute a high-level task
		result = await agent.execute_task(
			"Go to google.com and search for 'browser automation'",
			url="https://google.com"
		)
		
		print(f"Task completed: {result}")
	except Exception as e:
		print(f"Error with create_enhanced_agent: {e}")
	
	# Option 2: Direct NextGenBrowserAgent usage
	print("\n=== Testing with NextGenBrowserAgent directly ===")
	
	# Create browser instance
	browser = Browser(config=BrowserConfig(headless=False))
	
	# Create next-gen agent
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,
		use_accessibility=True,
		enable_streaming=True
	)
	
	try:
		# Initialize agent
		await agent.initialize()
		
		# Create browser context
		async with await browser.new_context() as context:
			page = await context.new_page()
			
			# Set the current page
			agent.current_page = page
			
			# Execute intent-based task
			result = await agent.execute_task(
				"Navigate to example.com and find the 'More information' link",
				context={
					"page": page,
					"url": "https://example.com"
				}
			)
			
			print(f"\nExecution result: {result}")
			
			# Wait a bit to see the result
			await asyncio.sleep(3)
			
	except Exception as e:
		print(f"Error: {e}")
		import traceback
		traceback.print_exc()
	finally:
		await agent.cleanup()
		await browser.close()


async def test_intent_analysis_only():
	"""Test just the intent analysis component"""
	print("\n=== Testing Intent Analysis Only ===")
	
	llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022", timeout=10)
	agent = NextGenBrowserAgent(llm=llm)
	
	await agent.initialize()
	
	# Test intent analysis
	test_tasks = [
		"Click the submit button",
		"Fill out the contact form with my information",
		"Find all product prices on the page and compare them",
		"Login with username test@example.com"
	]
	
	for task in test_tasks:
		print(f"\nAnalyzing: '{task}'")
		try:
			result = await agent.intent_analyzer.analyze(task)
			print(f"  Intent type: {result.intent.type}")
			print(f"  Primary goal: {result.intent.primary_goal}")
			print(f"  Confidence: {result.confidence}")
			if result.intent.sub_intents:
				print(f"  Sub-intents: {len(result.intent.sub_intents)}")
		except Exception as e:
			print(f"  Error: {e}")
	
	await agent.cleanup()


if __name__ == "__main__":
	# Run the tests
	asyncio.run(test_basic_intent_driven_navigation())
	asyncio.run(test_intent_analysis_only())