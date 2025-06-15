"""Test intent analysis to see what the LLM generates"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.core.intent.service import IntentAnalyzer

# Enable debug logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


async def test_intent_analysis():
    """Test how different tasks are analyzed into intents"""
    
    print("\n=== Testing Intent Analysis ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create intent analyzer
    analyzer = IntentAnalyzer(llm)
    
    # Test different task types
    test_tasks = [
        "Click the button",
        "Type 'Hello World' in the input field",
        "Fill in 'John Doe' in the name field",
        "Enter my email address test@example.com",
        "Select 'Option 2' from the dropdown",
        "Check the checkbox",
        "Go to google.com"
    ]
    
    for task in test_tasks:
        print(f"\n--- Task: {task} ---")
        try:
            result = await analyzer.analyze(task)
            intent = result.intent
            
            print(f"Intent type: {intent.type}")
            print(f"Primary goal: {intent.primary_goal}")
            
            if intent.sub_intents:
                print("Sub-intents:")
                for i, sub in enumerate(intent.sub_intents):
                    print(f"  {i}: type={sub.type}, desc={sub.description}")
                    if sub.parameters:
                        print(f"     parameters: {[(p.name, p.value) for p in sub.parameters]}")
            
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    print("Testing intent analysis...")
    asyncio.run(test_intent_analysis())