"""Test next-gen intent-driven extraction on real websites"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use.agent.next_gen_agent import NextGenBrowserAgent
from browser_use.browser.profile import BrowserProfile

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebsiteExtractionTest:
    """Test extraction capabilities on real websites"""
    
    def __init__(self):
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Configure browser profile
        self.profile = BrowserProfile(
            disable_security=True,
            wait_for_network_idle_page_load_time=1,
            headless=False,  # Set to True for CI/CD
            viewport={"width": 1920, "height": 1080}
        )
        
        # Create agent
        self.agent = NextGenBrowserAgent(
            llm=self.llm,
            browser_profile=self.profile,
            use_vision=False,  # Disable vision for faster extraction
            use_accessibility=True,
            enable_streaming=False
        )
        
        self.results = []
    
    async def setup(self):
        """Initialize agent and browser"""
        await self.agent.initialize()
        await self.agent._start_browser()
        logger.info("✓ Agent and browser initialized")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.agent.cleanup()
        logger.info("✓ Cleanup complete")
    
    async def test_amazon_search(self):
        """Test product extraction from Amazon search results"""
        logger.info("\n=== Testing Amazon Product Search ===")
        
        try:
            # Navigate to Amazon
            result = await self.agent.execute_task(
                "Go to amazon.com",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to navigate: {result}")
                return
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Search for laptops
            result = await self.agent.execute_task(
                "Search for 'laptop' using the search box",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to search: {result}")
                return
            
            # Wait for results
            await asyncio.sleep(3)
            
            # Extract product information
            logger.info("Extracting product data...")
            result = await self.agent.execute_task(
                """Extract the following information for the first 5 products:
                - Product title
                - Price
                - Rating (stars)
                - Number of reviews
                - Prime eligible (yes/no)
                """,
                context={
                    "extraction_format": "structured",
                    "max_items": 5
                }
            )
            
            if result['success']:
                products = result.get('data', {}).get('products', [])
                logger.info(f"✓ Extracted {len(products)} products")
                
                for i, product in enumerate(products, 1):
                    logger.info(f"\nProduct {i}:")
                    logger.info(f"  Title: {product.get('title', 'N/A')[:60]}...")
                    logger.info(f"  Price: {product.get('price', 'N/A')}")
                    logger.info(f"  Rating: {product.get('rating', 'N/A')} stars")
                    logger.info(f"  Reviews: {product.get('reviews', 'N/A')}")
                    logger.info(f"  Prime: {product.get('prime', 'N/A')}")
                
                self.results.append({
                    "site": "Amazon",
                    "task": "Product Search",
                    "success": True,
                    "items_extracted": len(products)
                })
            else:
                logger.error(f"Extraction failed: {result.get('errors', 'Unknown error')}")
                self.results.append({
                    "site": "Amazon",
                    "task": "Product Search",
                    "success": False,
                    "error": str(result.get('errors', []))
                })
                
        except Exception as e:
            logger.error(f"Amazon test failed: {e}")
            self.results.append({
                "site": "Amazon",
                "task": "Product Search",
                "success": False,
                "error": str(e)
            })
    
    async def test_reddit_posts(self):
        """Test post extraction from Reddit"""
        logger.info("\n=== Testing Reddit Post Extraction ===")
        
        try:
            # Navigate to Reddit
            result = await self.agent.execute_task(
                "Go to reddit.com",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to navigate: {result}")
                return
            
            # Wait for content to load
            await asyncio.sleep(2)
            
            # Extract post information
            logger.info("Extracting Reddit posts...")
            result = await self.agent.execute_task(
                """Extract information from the first 5 posts on the page:
                - Post title
                - Subreddit name
                - Number of upvotes
                - Number of comments
                - Posted time (e.g., "2 hours ago")
                """,
                context={
                    "extraction_format": "structured",
                    "max_items": 5
                }
            )
            
            if result['success']:
                posts = result.get('data', {}).get('posts', [])
                logger.info(f"✓ Extracted {len(posts)} posts")
                
                for i, post in enumerate(posts, 1):
                    logger.info(f"\nPost {i}:")
                    logger.info(f"  Title: {post.get('title', 'N/A')[:60]}...")
                    logger.info(f"  Subreddit: {post.get('subreddit', 'N/A')}")
                    logger.info(f"  Upvotes: {post.get('upvotes', 'N/A')}")
                    logger.info(f"  Comments: {post.get('comments', 'N/A')}")
                    logger.info(f"  Posted: {post.get('posted_time', 'N/A')}")
                
                self.results.append({
                    "site": "Reddit",
                    "task": "Post Extraction",
                    "success": True,
                    "items_extracted": len(posts)
                })
            else:
                logger.error(f"Extraction failed: {result.get('errors', 'Unknown error')}")
                self.results.append({
                    "site": "Reddit",
                    "task": "Post Extraction",
                    "success": False,
                    "error": str(result.get('errors', []))
                })
                
        except Exception as e:
            logger.error(f"Reddit test failed: {e}")
            self.results.append({
                "site": "Reddit",
                "task": "Post Extraction",
                "success": False,
                "error": str(e)
            })
    
    async def test_github_repos(self):
        """Test repository information extraction from GitHub"""
        logger.info("\n=== Testing GitHub Repository Extraction ===")
        
        try:
            # Navigate to GitHub trending
            result = await self.agent.execute_task(
                "Go to github.com/trending",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to navigate: {result}")
                return
            
            # Extract repository information
            logger.info("Extracting repository data...")
            result = await self.agent.execute_task(
                """Extract information about the first 5 trending repositories:
                - Repository name (owner/repo)
                - Description
                - Programming language
                - Number of stars
                - Number of forks
                - Stars gained today
                """,
                context={
                    "extraction_format": "structured",
                    "max_items": 5
                }
            )
            
            if result['success']:
                repos = result.get('data', {}).get('repositories', [])
                logger.info(f"✓ Extracted {len(repos)} repositories")
                
                for i, repo in enumerate(repos, 1):
                    logger.info(f"\nRepository {i}:")
                    logger.info(f"  Name: {repo.get('name', 'N/A')}")
                    logger.info(f"  Description: {repo.get('description', 'N/A')[:60]}...")
                    logger.info(f"  Language: {repo.get('language', 'N/A')}")
                    logger.info(f"  Stars: {repo.get('stars', 'N/A')}")
                    logger.info(f"  Forks: {repo.get('forks', 'N/A')}")
                    logger.info(f"  Stars today: {repo.get('stars_today', 'N/A')}")
                
                self.results.append({
                    "site": "GitHub",
                    "task": "Trending Repos",
                    "success": True,
                    "items_extracted": len(repos)
                })
            else:
                logger.error(f"Extraction failed: {result.get('errors', 'Unknown error')}")
                self.results.append({
                    "site": "GitHub",
                    "task": "Trending Repos",
                    "success": False,
                    "error": str(result.get('errors', []))
                })
                
        except Exception as e:
            logger.error(f"GitHub test failed: {e}")
            self.results.append({
                "site": "GitHub",
                "task": "Trending Repos",
                "success": False,
                "error": str(e)
            })
    
    async def test_google_search(self):
        """Test search result extraction from Google"""
        logger.info("\n=== Testing Google Search Extraction ===")
        
        try:
            # Navigate to Google first
            result = await self.agent.execute_task(
                "Go to google.com",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to navigate: {result}")
                return
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Now perform the search
            result = await self.agent.execute_task(
                "Type 'browser automation tools' in the search box and press Enter",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to search: {result}")
                return
            
            # Wait for results to load
            await asyncio.sleep(3)
            
            # Extract search results
            logger.info("Extracting search results...")
            result = await self.agent.execute_task(
                """Extract information from the first 5 search results:
                - Title
                - URL
                - Description snippet
                - Is it an ad? (yes/no)
                """,
                context={
                    "extraction_format": "structured",
                    "max_items": 5,
                    "exclude_ads": False  # Include ads in extraction
                }
            )
            
            if result['success']:
                results_data = result.get('data', {}).get('search_results', [])
                logger.info(f"✓ Extracted {len(results_data)} search results")
                
                for i, item in enumerate(results_data, 1):
                    logger.info(f"\nResult {i}:")
                    logger.info(f"  Title: {item.get('title', 'N/A')}")
                    logger.info(f"  URL: {item.get('url', 'N/A')}")
                    logger.info(f"  Snippet: {item.get('snippet', 'N/A')[:80]}...")
                    logger.info(f"  Is Ad: {item.get('is_ad', 'N/A')}")
                
                self.results.append({
                    "site": "Google",
                    "task": "Search Results",
                    "success": True,
                    "items_extracted": len(results_data)
                })
            else:
                logger.error(f"Extraction failed: {result.get('errors', 'Unknown error')}")
                self.results.append({
                    "site": "Google",
                    "task": "Search Results",
                    "success": False,
                    "error": str(result.get('errors', []))
                })
                
        except Exception as e:
            logger.error(f"Google test failed: {e}")
            self.results.append({
                "site": "Google",
                "task": "Search Results",
                "success": False,
                "error": str(e)
            })
    
    async def test_complex_interaction(self):
        """Test complex interaction with form filling and extraction"""
        logger.info("\n=== Testing Complex Interaction (Amazon Filter) ===")
        
        try:
            # Navigate to Amazon laptops
            result = await self.agent.execute_task(
                "Go to amazon.com and search for gaming laptops",
                context={"timeout": 30}
            )
            
            if not result['success']:
                logger.error(f"Failed to search: {result}")
                return
            
            # Apply filters
            logger.info("Applying filters...")
            result = await self.agent.execute_task(
                """Apply the following filters:
                1. Price range: Under $1,500
                2. Customer rating: 4 stars & up
                3. Brand: Select ASUS if available
                Then extract the first 3 products that match these criteria
                """,
                context={
                    "wait_after_filter": 2,
                    "extraction_format": "structured"
                }
            )
            
            if result['success']:
                filtered_products = result.get('data', {}).get('products', [])
                logger.info(f"✓ Found {len(filtered_products)} filtered products")
                
                for i, product in enumerate(filtered_products, 1):
                    logger.info(f"\nFiltered Product {i}:")
                    logger.info(f"  Title: {product.get('title', 'N/A')[:60]}...")
                    logger.info(f"  Price: {product.get('price', 'N/A')}")
                    logger.info(f"  Rating: {product.get('rating', 'N/A')}")
                    logger.info(f"  Brand: {product.get('brand', 'N/A')}")
                
                self.results.append({
                    "site": "Amazon",
                    "task": "Filtered Search",
                    "success": True,
                    "items_extracted": len(filtered_products)
                })
            else:
                logger.error(f"Filter/extraction failed: {result.get('errors', 'Unknown error')}")
                self.results.append({
                    "site": "Amazon",
                    "task": "Filtered Search",
                    "success": False,
                    "error": str(result.get('errors', []))
                })
                
        except Exception as e:
            logger.error(f"Complex interaction test failed: {e}")
            self.results.append({
                "site": "Amazon",
                "task": "Filtered Search",
                "success": False,
                "error": str(e)
            })
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        
        logger.info(f"\nTotal tests run: {total_tests}")
        logger.info(f"Successful: {successful_tests}")
        logger.info(f"Failed: {total_tests - successful_tests}")
        logger.info(f"Success rate: {(successful_tests/total_tests*100):.1f}%")
        
        logger.info("\nDetailed Results:")
        for result in self.results:
            status = "✓" if result['success'] else "✗"
            logger.info(f"\n{status} {result['site']} - {result['task']}")
            if result['success']:
                logger.info(f"  Items extracted: {result.get('items_extracted', 0)}")
            else:
                logger.info(f"  Error: {result.get('error', 'Unknown')}")
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"extraction_test_results_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            f.write("Next-Gen Extraction Test Results\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write("="*60 + "\n\n")
            
            for result in self.results:
                f.write(f"{result['site']} - {result['task']}\n")
                f.write(f"Success: {result['success']}\n")
                if result['success']:
                    f.write(f"Items extracted: {result.get('items_extracted', 0)}\n")
                else:
                    f.write(f"Error: {result.get('error', 'Unknown')}\n")
                f.write("-"*40 + "\n")
        
        logger.info(f"\nResults saved to: {filename}")


async def run_extraction_tests():
    """Run all extraction tests"""
    test = WebsiteExtractionTest()
    
    try:
        await test.setup()
        
        # Run individual tests
        tests = [
            test.test_google_search,
            test.test_amazon_search,
            test.test_reddit_posts,
            test.test_github_repos,
            test.test_complex_interaction
        ]
        
        for test_func in tests:
            try:
                await test_func()
                await asyncio.sleep(2)  # Brief pause between tests
            except Exception as e:
                logger.error(f"Test {test_func.__name__} failed: {e}")
                continue
        
        # Print summary
        test.print_summary()
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await test.cleanup()


async def run_single_test():
    """Run a single test for debugging"""
    test = WebsiteExtractionTest()
    
    try:
        await test.setup()
        
        # Run just one test
        await test.test_amazon_search()
        
        test.print_summary()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("\nPress Enter to close browser...")
        input()
        await test.cleanup()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "single":
        # Run single test: python nextgen_extraction_test.py single
        asyncio.run(run_single_test())
    else:
        # Run all tests: python nextgen_extraction_test.py
        asyncio.run(run_extraction_tests())