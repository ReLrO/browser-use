"""Test the robust agent"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.robust_agent import RobustBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Enable logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_robust_agent():
	"""Test the robust agent on various tasks"""
	
	logger.info("=== Testing Robust Agent ===")
	
	# Initialize LLM
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.5-flash-preview-05-20",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	# Create agent
	agent = RobustBrowserAgent(llm, browser_profile=BrowserProfile(headless=False))
	
	try:
		await agent.initialize()
		
		# Test 1: Google Search
		logger.info("\n=== Test 1: Google Search ===")
		
		result = await agent.execute_task("Go to google.com")
		logger.info(f"Navigate result: {result}")
		
		if result['success']:
			await asyncio.sleep(2)
			
			result = await agent.execute_task("Search for 'browser automation tools'")
			logger.info(f"Search result: {result}")
			
			if result['success']:
				await asyncio.sleep(3)
				
				result = await agent.execute_task("Click on the first search result")
				logger.info(f"Click result: {result}")
				
				if result['success']:
					logger.info("✅ Google search test PASSED!")
				else:
					logger.error("❌ Failed to click search result")
			else:
				logger.error("❌ Failed to search")
		else:
			logger.error("❌ Failed to navigate")
			
		await asyncio.sleep(3)
		
		# Test 2: Amazon Search
		logger.info("\n=== Test 2: Amazon Search ===")
		
		result = await agent.execute_task("Go to amazon.com")
		logger.info(f"Navigate to Amazon: {result}")
		
		if result['success']:
			await asyncio.sleep(3)
			
			result = await agent.execute_task("Search for 'laptop'")
			logger.info(f"Search for laptop: {result}")
			
			if result['success']:
				await asyncio.sleep(3)
				
				result = await agent.execute_task("Click on the first product")
				logger.info(f"Click product: {result}")
				
				if result['success']:
					logger.info("✅ Amazon search test PASSED!")
					
					# Extract product info
					result = await agent.execute_task("Extract the product title and price")
					logger.info(f"Extracted: {result}")
				else:
					logger.error("❌ Failed to click product")
			else:
				logger.error("❌ Failed to search on Amazon")
		else:
			logger.error("❌ Failed to navigate to Amazon")
			
		await asyncio.sleep(3)
		
		# Test 3: Complex task
		logger.info("\n=== Test 3: Complex Task ===")
		
		result = await agent.execute_task("Go to github.com and search for 'browser-use'")
		logger.info(f"Complex task result: {result}")
		
		if result['success']:
			logger.info("✅ Complex task PASSED!")
		else:
			logger.error("❌ Complex task failed")
			
	except Exception as e:
		logger.error(f"Test failed with exception: {e}")
		import traceback
		traceback.print_exc()
		
	finally:
		logger.info("\nPress Enter to close browser...")
		input()
		await agent.cleanup()


if __name__ == "__main__":
	asyncio.run(test_robust_agent())