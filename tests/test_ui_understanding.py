"""Test UI/UX understanding capabilities"""

import asyncio
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile
from browser_use.core.caching import rate_limiter

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_search_patterns():
    """Test understanding of common search UI patterns"""
    
    logger.info("=== Testing Search UI Pattern Understanding ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=False,
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Test 1: Search with icon button
        logger.info("\n--- Test 1: Search with Icon Button ---")
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px; font-family: Arial;">
                <h1>Search Test - Icon Button</h1>
                <div style="display: flex; align-items: center; max-width: 500px;">
                    <input type="search" id="search" placeholder="Search..." style="flex: 1; padding: 10px;">
                    <button style="padding: 10px; margin-left: 5px;" title="Search">
                        <svg width="20" height="20" viewBox="0 0 24 24">
                            <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                        </svg>
                    </button>
                </div>
                <div id="results" style="margin-top: 20px; padding: 10px; background: #f0f0f0;">
                    Results will appear here...
                </div>
                <script>
                    document.querySelector('button').onclick = () => {
                        const query = document.getElementById('search').value;
                        document.getElementById('results').textContent = 'Searched for: ' + query;
                    };
                    document.getElementById('search').addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') {
                            document.querySelector('button').click();
                        }
                    });
                </script>
            </body>
            </html>
        """)
        
        result = await agent.execute_task("Search for 'test query'")
        logger.info(f"Search result: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Verify
        results = await agent.current_page.evaluate('document.getElementById("results").textContent')
        logger.info(f"Results: {results}")
        
        # Test 2: Submit form with Enter key
        logger.info("\n--- Test 2: Submit with Enter Key ---")
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Login Form</h1>
                <form id="loginForm">
                    <div style="margin: 10px 0;">
                        <input type="text" id="username" placeholder="Username" style="padding: 8px; width: 200px;">
                    </div>
                    <div style="margin: 10px 0;">
                        <input type="password" id="password" placeholder="Password" style="padding: 8px; width: 200px;">
                    </div>
                    <button type="submit" style="padding: 8px 20px;">Login</button>
                </form>
                <div id="message" style="margin-top: 20px;"></div>
                <script>
                    document.getElementById('loginForm').onsubmit = (e) => {
                        e.preventDefault();
                        const user = document.getElementById('username').value;
                        document.getElementById('message').textContent = 'Logged in as: ' + user;
                    };
                </script>
            </body>
            </html>
        """)
        
        # Type username
        result = await agent.execute_task("Type 'alice' in the username field")
        logger.info(f"Type username: {result.get('success')}")
        
        await asyncio.sleep(1)
        
        # Type password
        result = await agent.execute_task("Type 'secret123' in the password field")
        logger.info(f"Type password: {result.get('success')}")
        
        await asyncio.sleep(1)
        
        # Submit with Enter
        result = await agent.execute_task("Press Enter to submit the login form")
        logger.info(f"Submit with Enter: {result.get('success')}")
        
        # Verify
        message = await agent.current_page.evaluate('document.getElementById("message").textContent')
        logger.info(f"Login message: {message}")
        
        # Test 3: Complex search interface
        logger.info("\n--- Test 3: Complex Search Interface ---")
        await agent.current_page.set_content("""
            <html>
            <body style="padding: 20px;">
                <h1>Advanced Search</h1>
                <div style="border: 1px solid #ccc; padding: 20px; max-width: 600px;">
                    <div style="margin-bottom: 15px;">
                        <input type="text" id="mainSearch" placeholder="What are you looking for?" 
                               style="width: 70%; padding: 10px; font-size: 16px;">
                        <button id="searchBtn" style="padding: 10px 20px; margin-left: 10px;">
                            Search
                        </button>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <label>Category:</label>
                        <select id="category" style="margin-left: 10px; padding: 5px;">
                            <option value="all">All Categories</option>
                            <option value="electronics">Electronics</option>
                            <option value="books">Books</option>
                        </select>
                    </div>
                    <div>
                        <label>
                            <input type="checkbox" id="inStock"> In Stock Only
                        </label>
                    </div>
                </div>
                <div id="searchResults" style="margin-top: 20px; padding: 10px; background: #f5f5f5;">
                    No search performed yet.
                </div>
                <script>
                    function performSearch() {
                        const query = document.getElementById('mainSearch').value;
                        const category = document.getElementById('category').value;
                        const inStock = document.getElementById('inStock').checked;
                        document.getElementById('searchResults').innerHTML = 
                            `<strong>Search Results:</strong><br>
                             Query: "${query}"<br>
                             Category: ${category}<br>
                             In Stock Only: ${inStock}`;
                    }
                    document.getElementById('searchBtn').onclick = performSearch;
                    document.getElementById('mainSearch').addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') performSearch();
                    });
                </script>
            </body>
            </html>
        """)
        
        # Perform complex search
        result = await agent.execute_task("Search for 'laptop' in Electronics category with in-stock items only")
        logger.info(f"Complex search: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Verify
        results = await agent.current_page.evaluate('document.getElementById("searchResults").innerHTML')
        logger.info(f"Search results: {results}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


async def test_modern_ui_patterns():
    """Test understanding of modern UI patterns"""
    
    logger.info("=== Testing Modern UI Pattern Understanding ===")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Create agent
    agent = NextGenBrowserAgent(
        llm=llm,
        browser_profile=BrowserProfile(headless=False),
        use_vision=False,
        use_accessibility=True,
        enable_streaming=False
    )
    
    try:
        await agent.initialize()
        await agent._start_browser()
        
        # Test: Toggle switches, tabs, modals
        logger.info("\n--- Test: Modern UI Elements ---")
        await agent.current_page.set_content("""
            <html>
            <head>
                <style>
                    .toggle-switch {
                        position: relative;
                        width: 60px;
                        height: 30px;
                        background: #ccc;
                        border-radius: 15px;
                        cursor: pointer;
                        transition: 0.3s;
                    }
                    .toggle-switch.active {
                        background: #4CAF50;
                    }
                    .toggle-slider {
                        position: absolute;
                        top: 3px;
                        left: 3px;
                        width: 24px;
                        height: 24px;
                        background: white;
                        border-radius: 50%;
                        transition: 0.3s;
                    }
                    .toggle-switch.active .toggle-slider {
                        left: 33px;
                    }
                    .tab {
                        padding: 10px 20px;
                        background: #f0f0f0;
                        border: none;
                        cursor: pointer;
                    }
                    .tab.active {
                        background: #007bff;
                        color: white;
                    }
                    .tab-content {
                        display: none;
                        padding: 20px;
                        border: 1px solid #ddd;
                    }
                    .tab-content.active {
                        display: block;
                    }
                </style>
            </head>
            <body style="padding: 20px;">
                <h1>Modern UI Elements</h1>
                
                <div style="margin: 20px 0;">
                    <h3>Settings</h3>
                    <div style="display: flex; align-items: center; margin: 10px 0;">
                        <span>Enable Notifications:</span>
                        <div class="toggle-switch" id="notifToggle" style="margin-left: 10px;">
                            <div class="toggle-slider"></div>
                        </div>
                        <span id="notifStatus" style="margin-left: 10px;">OFF</span>
                    </div>
                </div>
                
                <div style="margin: 20px 0;">
                    <h3>Content Tabs</h3>
                    <div>
                        <button class="tab active" data-tab="1">Overview</button>
                        <button class="tab" data-tab="2">Details</button>
                        <button class="tab" data-tab="3">Reviews</button>
                    </div>
                    <div class="tab-content active" id="tab1">Overview content here</div>
                    <div class="tab-content" id="tab2">Details content here</div>
                    <div class="tab-content" id="tab3">Reviews content here</div>
                </div>
                
                <div id="status" style="margin-top: 20px; padding: 10px; background: #f0f0f0;"></div>
                
                <script>
                    // Toggle switch
                    document.getElementById('notifToggle').onclick = function() {
                        this.classList.toggle('active');
                        const isActive = this.classList.contains('active');
                        document.getElementById('notifStatus').textContent = isActive ? 'ON' : 'OFF';
                        document.getElementById('status').textContent = 
                            'Notifications ' + (isActive ? 'enabled' : 'disabled');
                    };
                    
                    // Tabs
                    document.querySelectorAll('.tab').forEach(tab => {
                        tab.onclick = function() {
                            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                            this.classList.add('active');
                            document.getElementById('tab' + this.dataset.tab).classList.add('active');
                            document.getElementById('status').textContent = 
                                'Switched to ' + this.textContent + ' tab';
                        };
                    });
                </script>
            </body>
            </html>
        """)
        
        # Test toggle switch
        result = await agent.execute_task("Enable notifications")
        logger.info(f"Toggle notifications: {result.get('success')}")
        
        await asyncio.sleep(2)
        
        # Test tab switching
        result = await agent.execute_task("Switch to the Reviews tab")
        logger.info(f"Switch tab: {result.get('success')}")
        
        # Verify
        status = await agent.current_page.evaluate('document.getElementById("status").textContent')
        logger.info(f"Status: {status}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await agent.cleanup()


if __name__ == "__main__":
    print("\nSelect test:")
    print("1. Search UI patterns")
    print("2. Modern UI patterns")
    print("3. Run all tests")
    
    choice = input("\nChoice (1-3): ")
    
    if choice == "1":
        asyncio.run(test_search_patterns())
    elif choice == "2":
        asyncio.run(test_modern_ui_patterns())
    elif choice == "3":
        asyncio.run(test_search_patterns())
        asyncio.run(test_modern_ui_patterns())
    else:
        print("Invalid choice")