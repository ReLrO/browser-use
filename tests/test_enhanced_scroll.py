"""
Tests for enhanced scrolling functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from browser_use.controller.actions.enhanced_scroll import (
    ScrollDirection,
    ScrollStrategy,
    EnhancedScrollAction,
    ScrollToElementAction,
    ScrollUntilVisibleAction,
    InfiniteScrollAction,
    register_enhanced_scroll_actions,
)
from browser_use.controller.service import Controller
from browser_use.browser import BrowserSession


@pytest.fixture
def mock_browser_session():
    """Create a mock browser session"""
    session = MagicMock(spec=BrowserSession)
    page = AsyncMock()
    session.get_current_page = AsyncMock(return_value=page)
    return session, page


@pytest.fixture
def controller_with_scroll_actions():
    """Create a controller with enhanced scroll actions registered"""
    controller = Controller()
    register_enhanced_scroll_actions(controller)
    return controller


@pytest.mark.asyncio
async def test_enhanced_scroll_down_pixels(controller_with_scroll_actions, mock_browser_session):
    """Test basic downward scrolling by pixels"""
    session, page = mock_browser_session
    page.evaluate = AsyncMock(return_value={"scrolledY": 300, "hasMoreContent": {"down": True}})
    
    params = EnhancedScrollAction(
        direction=ScrollDirection.DOWN,
        amount=300,
        strategy=ScrollStrategy.PIXELS
    )
    
    result = await controller_with_scroll_actions.registry.actions["enhanced_scroll"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "Scrolled down by 300 pixels" in result.extracted_content
    page.evaluate.assert_called_once()


@pytest.mark.asyncio
async def test_enhanced_scroll_with_target_selector(controller_with_scroll_actions, mock_browser_session):
    """Test scrolling a specific container"""
    session, page = mock_browser_session
    page.evaluate = AsyncMock(return_value={
        "container": ".my-container",
        "scrolledY": 200,
        "hasMoreContent": {"down": False}
    })
    
    params = EnhancedScrollAction(
        direction=ScrollDirection.DOWN,
        amount=200,
        target_selector=".my-container"
    )
    
    result = await controller_with_scroll_actions.registry.actions["enhanced_scroll"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "in .my-container" in result.extracted_content
    assert "reached limit" in result.extracted_content


@pytest.mark.asyncio
async def test_detect_scrollable_areas(controller_with_scroll_actions, mock_browser_session):
    """Test detecting scrollable areas on a page"""
    session, page = mock_browser_session
    page.evaluate = AsyncMock(return_value={
        "count": 2,
        "elements": [
            {
                "description": "div.content-area",
                "isVisible": True,
                "scrollInfo": {"canScrollDown": True, "canScrollUp": False}
            },
            {
                "description": "ul.dropdown-menu (LinkedIn Dropdown)",
                "isVisible": True,
                "isDropdown": True,
                "scrollInfo": {"canScrollDown": True, "canScrollUp": False}
            }
        ],
        "summary": {
            "hasFilterPanel": False,
            "hasDropdown": True,
            "visibleScrollables": 2
        }
    })
    
    result = await controller_with_scroll_actions.registry.actions["detect_scrollable_areas"].function(
        browser_session=session
    )
    
    assert not result.error
    assert "Found 2 scrollable areas" in result.extracted_content
    assert "✓ Dropdown menu is scrollable" in result.extracted_content


@pytest.mark.asyncio
async def test_scroll_to_element(controller_with_scroll_actions, mock_browser_session):
    """Test scrolling to a specific element"""
    session, page = mock_browser_session
    page.evaluate = AsyncMock(return_value={
        "element": "#target",
        "wasVisible": False,
        "isNowVisible": True,
        "position": {"top": 100, "bottom": 200}
    })
    
    params = ScrollToElementAction(
        selector="#target",
        alignment="center",
        smooth=True
    )
    
    result = await controller_with_scroll_actions.registry.actions["scroll_to_element"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "Scrolled to element '#target'" in result.extracted_content


@pytest.mark.asyncio
async def test_scroll_until_visible(controller_with_scroll_actions, mock_browser_session):
    """Test scrolling until content is visible"""
    session, page = mock_browser_session
    page.evaluate = AsyncMock(return_value={
        "found": True,
        "scrollCount": 3,
        "message": "Found 'Legal issues' after 3 scrolls"
    })
    
    params = ScrollUntilVisibleAction(
        text="Legal issues",
        max_scrolls=10,
        scroll_amount=300
    )
    
    result = await controller_with_scroll_actions.registry.actions["scroll_until_visible"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "Found 'Legal issues' after 3 scrolls" in result.extracted_content


@pytest.mark.asyncio
async def test_handle_infinite_scroll(controller_with_scroll_actions, mock_browser_session):
    """Test handling infinite scroll pages"""
    session, page = mock_browser_session
    
    # Mock the sequence of evaluate calls
    page.evaluate = AsyncMock()
    page.evaluate.side_effect = [
        10,     # Initial item count
        1000,   # Initial page height
        # After first scroll
        2000,   # New page height
        20,     # New item count
        # After second scroll
        3000,   # New page height
        30,     # New item count
        # After third scroll
        3000,   # Same height (no new content)
        30,     # Same item count
        # Final count
        30      # Final item count
    ]
    
    params = InfiniteScrollAction(
        max_items=50,
        max_scrolls=5,
        wait_time=0.1,  # Short wait for testing
        item_selector=".item"
    )
    
    result = await controller_with_scroll_actions.registry.actions["handle_infinite_scroll"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "loaded 20 new items" in result.extracted_content
    assert result.data["finalCount"] == 30
    assert result.data["initialCount"] == 10


@pytest.mark.asyncio
async def test_scroll_to_end_strategy(controller_with_scroll_actions, mock_browser_session):
    """Test scrolling to end of container"""
    session, page = mock_browser_session
    page.evaluate = AsyncMock(return_value={
        "container": "window",
        "scrolledY": 5000,
        "hasMoreContent": {"down": False, "up": True}
    })
    
    params = EnhancedScrollAction(
        direction=ScrollDirection.DOWN,
        strategy=ScrollStrategy.TO_END
    )
    
    result = await controller_with_scroll_actions.registry.actions["enhanced_scroll"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "Scrolled to the down" in result.extracted_content
    assert "reached limit" in result.extracted_content


@pytest.mark.asyncio
async def test_multi_directional_scroll(controller_with_scroll_actions, mock_browser_session):
    """Test scrolling in different directions"""
    session, page = mock_browser_session
    
    # Test horizontal scrolling
    page.evaluate = AsyncMock(return_value={
        "container": "window",
        "scrolledX": 500,
        "scrolledY": 0,
        "hasMoreContent": {"right": True, "left": False}
    })
    
    params = EnhancedScrollAction(
        direction=ScrollDirection.RIGHT,
        amount=500
    )
    
    result = await controller_with_scroll_actions.registry.actions["enhanced_scroll"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "Scrolled right by 500 pixels" in result.extracted_content


@pytest.mark.asyncio
async def test_viewport_scroll_strategy(controller_with_scroll_actions, mock_browser_session):
    """Test scrolling by viewport percentage"""
    session, page = mock_browser_session
    
    # Mock viewport height
    page.evaluate.side_effect = [
        800,  # innerHeight
        {"container": "window", "scrolledY": 400, "hasMoreContent": {"down": True}}
    ]
    
    params = EnhancedScrollAction(
        direction=ScrollDirection.DOWN,
        amount=50,  # 50% of viewport
        strategy=ScrollStrategy.VIEWPORT
    )
    
    result = await controller_with_scroll_actions.registry.actions["enhanced_scroll"].function(
        params=params,
        browser_session=session
    )
    
    assert not result.error
    assert "using viewport strategy" in result.extracted_content
    assert "400 pixels" in result.extracted_content  # 50% of 800px viewport