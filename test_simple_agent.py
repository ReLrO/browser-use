"""Test the simple, direct agent"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.simple_agent import SimpleAgent

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_simple():
    """Test simple direct execution"""
    
    logger.info("=== Testing Simple Agent ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-05-20",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create simple agent
    agent = SimpleAgent(llm)
    
    try:
        await agent.initialize()
        
        # Test 1: Navigate
        logger.info("\n1. Navigate to Google")
        result = await agent.execute_task("Go to google.com")
        logger.info(f"Result: {result}")
        
        await asyncio.sleep(2)
        
        # Test 2: Type search
        logger.info("\n2. Type search query")
        result = await agent.execute_task("Type 'browser automation' in the search box")
        logger.info(f"Result: {result}")
        
        await asyncio.sleep(1)
        
        # Test 3: Submit search
        logger.info("\n3. Submit search")
        result = await agent.execute_task("Press Enter to search")
        logger.info(f"Result: {result}")
        
        await asyncio.sleep(3)
        
        # Test 4: Click result
        logger.info("\n4. Click first result")
        result = await agent.execute_task("Click the first search result")
        logger.info(f"Result: {result}")
        
        await asyncio.sleep(3)
        
        logger.info("\nDone! Simple and direct.")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(test_simple())