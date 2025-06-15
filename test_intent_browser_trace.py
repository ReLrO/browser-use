"""Trace test to find where the Page serialization error occurs"""

import asyncio
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig


async def test_with_detailed_trace():
	"""Test with detailed error tracing"""
	
	print("\n=== Testing with Detailed Trace ===")
	
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
		use_vision=False,
		use_accessibility=False,
		enable_streaming=False
	)
	
	try:
		await agent.initialize()
		await browser.start()
		page = await browser.new_tab()
		
		agent.current_page = page
		agent.browser_session = browser
		agent._execution_context = {
			"page": page,
			"start_time": None
		}
		
		# Patch execute_task to add more debugging
		original_execute_task = agent.execute_task
		
		async def debug_execute_task(task, url=None, context=None):
			try:
				print(f"\n[DEBUG] Starting execute_task for: '{task}'")
				
				# Analyze intent
				print("[DEBUG] Analyzing intent...")
				analysis_result = await agent.intent_analyzer.analyze(task)
				intent = analysis_result.intent
				print(f"[DEBUG] Intent analyzed: {intent.primary_goal}")
				
				# Register intent
				print("[DEBUG] Registering intent...")
				await agent.intent_manager.register_intent(intent)
				
				# Get perception data
				print("[DEBUG] Getting perception data...")
				perception_data = await agent._get_perception_data()
				print(f"[DEBUG] Perception data keys: {list(perception_data.keys())}")
				
				# Check if Page is in perception data
				if "page" in perception_data:
					print("[DEBUG] WARNING: Page object found in perception_data!")
				
				agent._execution_context["perception_data"] = perception_data
				
				# Execute intent
				print("[DEBUG] Executing intent...")
				execution_result = await agent.action_orchestrator.execute_intent(
					intent,
					agent.current_page,
					agent._execution_context
				)
				print(f"[DEBUG] Execution result type: {type(execution_result)}")
				print(f"[DEBUG] Execution success: {execution_result.success}")
				
				# Try to convert to dict
				print("[DEBUG] Building response dict...")
				response = {
					"success": execution_result.success,
					"intent_id": intent.id,
					"actions_taken": len(execution_result.actions_taken),
					"duration_seconds": execution_result.duration_seconds,
					"tokens_used": execution_result.tokens_used,
					"verification": {
						"criteria_met": execution_result.criteria_met,
						"screenshot": execution_result.verification_screenshot
					},
					"errors": execution_result.errors,
					"data": getattr(execution_result, 'extracted_data', {})
				}
				
				print("[DEBUG] Response dict created successfully")
				return response
				
			except Exception as e:
				print(f"\n[DEBUG] Exception caught: {type(e).__name__}: {e}")
				print("[DEBUG] Full traceback:")
				traceback.print_exc()
				
				# Check what's causing the serialization error
				import json
				print("\n[DEBUG] Checking what can't be serialized...")
				
				if 'execution_result' in locals():
					print("[DEBUG] Checking execution_result...")
					for field_name in execution_result.__fields__:
						try:
							field_value = getattr(execution_result, field_name)
							json.dumps({"test": field_value})
						except Exception as serialize_error:
							print(f"[DEBUG] Field '{field_name}' can't be serialized: {serialize_error}")
				
				return {
					"success": False,
					"error": str(e),
					"error_type": type(e).__name__
				}
		
		agent.execute_task = debug_execute_task
		
		# Run the test
		result = await agent.execute_task("Navigate to https://example.com")
		print(f"\nFinal result: {result}")
		
		# Check URL
		await asyncio.sleep(1)
		print(f"Current URL: {page.url}")
		
	except Exception as e:
		print(f"\n❌ Outer Error: {e}")
		traceback.print_exc()
	
	finally:
		await browser.close()
		await agent.cleanup()
		print("\n✓ Cleanup complete")


if __name__ == "__main__":
	asyncio.run(test_with_detailed_trace())