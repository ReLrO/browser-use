"""
Browser-use controller actions module.
This module contains additional actions that can be registered with a controller.
"""

from .enhanced_scroll import (
    ScrollDirection,
    ScrollStrategy,
    ScrollableAreaInfo,
    EnhancedScrollAction,
    ScrollToElementAction,
    ScrollUntilVisibleAction,
    InfiniteScrollAction,
    register_enhanced_scroll_actions,
)

__all__ = [
    "ScrollDirection",
    "ScrollStrategy",
    "ScrollableAreaInfo",
    "EnhancedScrollAction",
    "ScrollToElementAction",
    "ScrollUntilVisibleAction",
    "InfiniteScrollAction",
    "register_enhanced_scroll_actions",
]