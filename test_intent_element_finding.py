"""Test element finding with LLM assistance"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser import Browser, BrowserConfig

# Enable debug logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_llm_element_finding():
	"""Test if the LLM can find elements through the intent system"""
	
	print("\n=== Testing LLM Element Finding ===")
	
	# Initialize components
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,  # Enable vision for better element finding
		use_accessibility=True,
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
		
		print("✓ Browser and agent initialized with vision enabled")
		
		# Create a test page with various elements
		await page.set_content("""
			<html>
			<head><title>Element Finding Test</title></head>
			<body style="padding: 20px;">
				<h1>Test Page for Element Finding</h1>
				
				<div style="margin: 20px 0;">
					<h2>Search Section</h2>
					<input type="text" placeholder="Search for something..." style="padding: 5px;">
					<button onclick="alert('Search clicked!')">Search</button>
				</div>
				
				<div style="margin: 20px 0;">
					<h2>Navigation Links</h2>
					<a href="#about">About Us</a> | 
					<a href="#contact">Contact</a> | 
					<a href="#products">Products</a>
				</div>
				
				<div style="margin: 20px 0;">
					<h2>Action Buttons</h2>
					<button style="background: green; color: white; padding: 10px;">Buy Now</button>
					<button style="background: blue; color: white; padding: 10px;">Learn More</button>
					<button style="background: red; color: white; padding: 10px;">Cancel</button>
				</div>
				
				<div style="margin: 20px 0;">
					<h2>Form Elements</h2>
					<label>Your Name: <input type="text" name="fullname"></label><br><br>
					<label>Comments: <textarea name="comments" rows="3" cols="30"></textarea></label><br><br>
					<label><input type="checkbox"> I agree to terms</label><br><br>
					<select name="country">
						<option>Select Country</option>
						<option>USA</option>
						<option>UK</option>
						<option>Canada</option>
					</select>
				</div>
			</body>
			</html>
		""")
		
		print("✓ Test page loaded with various elements")
		
		# Test 1: Find and click specific button by color
		print("\n--- Test 1: Click the green button ---")
		result = await agent.execute_task(
			"Click the green 'Buy Now' button"
		)
		print(f"Success: {result['success']}")
		print(f"Actions taken: {result.get('actions_taken', 0)}")
		
		# Test 2: Fill search box
		print("\n--- Test 2: Use the search box ---")
		result = await agent.execute_task(
			"Type 'artificial intelligence' in the search box"
		)
		print(f"Success: {result['success']}")
		
		# Verify the value
		search_value = await page.evaluate('document.querySelector("input[placeholder*=Search]").value')
		print(f"Search box value: {search_value}")
		
		# Test 3: Click navigation link
		print("\n--- Test 3: Click on Products link ---")
		result = await agent.execute_task(
			"Click on the Products navigation link"
		)
		print(f"Success: {result['success']}")
		
		# Test 4: Fill form fields
		print("\n--- Test 4: Fill the form ---")
		result = await agent.execute_task(
			"Fill in 'John Smith' for the name field and 'This is a test comment' in the comments area"
		)
		print(f"Success: {result['success']}")
		
		# Verify form values
		name_value = await page.evaluate('document.querySelector("input[name=fullname]").value')
		comments_value = await page.evaluate('document.querySelector("textarea[name=comments]").value')
		print(f"Name field: {name_value}")
		print(f"Comments: {comments_value}")
		
		# Test 5: Select from dropdown
		print("\n--- Test 5: Select from dropdown ---")
		result = await agent.execute_task(
			"Select 'Canada' from the country dropdown"
		)
		print(f"Success: {result['success']}")
		
		# Test 6: Check checkbox
		print("\n--- Test 6: Check the agreement checkbox ---")
		result = await agent.execute_task(
			"Check the 'I agree to terms' checkbox"
		)
		print(f"Success: {result['success']}")
		
		# Get a screenshot to see final state
		await page.screenshot(path="element_finding_test.png")
		print("\n✓ Screenshot saved as element_finding_test.png")
		
	except Exception as e:
		print(f"\n❌ Test failed: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		print("\nPress Enter to close browser...")
		input()
		await browser.close()
		await agent.cleanup()
		print("✓ Cleanup complete")


async def test_real_website():
	"""Test on a real website"""
	
	print("\n=== Testing on Real Website (Hacker News) ===")
	
	llm = ChatGoogleGenerativeAI(
		model="gemini-2.0-flash-exp",
		temperature=0,
		google_api_key=os.getenv("GOOGLE_API_KEY")
	)
	
	agent = NextGenBrowserAgent(
		llm=llm,
		use_vision=True,
		use_accessibility=True,
		enable_streaming=False
	)
	
	browser = Browser(config=BrowserConfig(headless=False))
	
	try:
		await agent.initialize()
		await browser.start()
		
		page = await browser.new_tab()
		agent.current_page = page
		agent.browser_session = browser
		
		# Go to Hacker News
		print("\n--- Navigating to Hacker News ---")
		result = await agent.execute_task(
			"Go to news.ycombinator.com"
		)
		print(f"Navigation success: {result['success']}")
		
		await asyncio.sleep(2)
		
		# Click on the first article
		print("\n--- Clicking first article ---")
		result = await agent.execute_task(
			"Click on the first news article title"
		)
		print(f"Click success: {result['success']}")
		print(f"Current URL: {page.url}")
		
		await asyncio.sleep(2)
		
		# Go back and try comments
		print("\n--- Going back to main page ---")
		await page.go_back()
		await asyncio.sleep(2)
		
		print("\n--- Clicking comments of first article ---")
		result = await agent.execute_task(
			"Click on the comments link of the first article"
		)
		print(f"Comments click success: {result['success']}")
		
	except Exception as e:
		print(f"\n❌ Test failed: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		print("\nPress Enter to close browser...")
		input()
		await browser.close()
		await agent.cleanup()


if __name__ == "__main__":
	print("Testing LLM-based element finding...")
	
	# Test custom page with various elements
	asyncio.run(test_llm_element_finding())
	
	print("\n" + "="*50 + "\n")
	
	# Test real website
	asyncio.run(test_real_website())