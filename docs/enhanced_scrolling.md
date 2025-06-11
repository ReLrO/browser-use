# Enhanced Scrolling for Browser-Use

This document describes the enhanced scrolling capabilities added to browser-use, providing advanced scrolling features for complex web automation scenarios.

## Overview

The enhanced scrolling module extends browser-use with powerful scrolling capabilities:

- **Multi-directional scrolling** (up, down, left, right)
- **Multiple scrolling strategies** (pixels, viewport percentage, pages, scroll to end)
- **Smart container detection** (automatically finds the right element to scroll)
- **Scrollable area detection** (identify all scrollable areas on a page)
- **Content search while scrolling** (scroll until specific content is visible)
- **Infinite scroll handling** (load content progressively)
- **Element targeting** (scroll specific containers)

## Installation

The enhanced scrolling module is included in browser-use. To use it, simply import and register the actions:

```python
from browser_use import Agent, Controller
from browser_use.controller.actions.enhanced_scroll import register_enhanced_scroll_actions

# Create controller and register enhanced scroll actions
controller = Controller()
register_enhanced_scroll_actions(controller)

# Use with an agent
agent = Agent(
    task="Your task here",
    llm=your_llm,
    controller=controller
)
```

## Available Actions

### 1. `detect_scrollable_areas`

Identifies all scrollable areas on the current page.

**Usage:**
```python
# In agent task
"Use detect_scrollable_areas to understand the page structure"
```

**Returns:**
- Count of scrollable areas
- Details about each area (dimensions, scroll position, remaining content)
- Special detection for LinkedIn filter panels and dropdowns

### 2. `enhanced_scroll`

Advanced scrolling with multiple strategies and directions.

**Parameters:**
- `direction`: "up", "down", "left", "right" (default: "down")
- `amount`: Number of pixels to scroll (default: one viewport)
- `strategy`: "pixels", "viewport", "page", "to_end" (default: "pixels")
- `target_selector`: CSS selector of container to scroll (default: auto-detect)
- `smooth`: Use smooth scrolling animation (default: false)

**Examples:**
```python
# Scroll down 400 pixels
"Use enhanced_scroll with amount=400"

# Scroll 50% of viewport
"Use enhanced_scroll with strategy='viewport' and amount=50"

# Scroll to bottom
"Use enhanced_scroll with strategy='to_end' and direction='down'"

# Scroll specific container
"Use enhanced_scroll with target_selector='.my-container' and amount=300"

# Horizontal scrolling
"Use enhanced_scroll with direction='right' and amount=500"
```

### 3. `scroll_to_element`

Scroll to bring a specific element into view.

**Parameters:**
- `selector`: CSS selector of the element
- `alignment`: "start", "center", "end", or "nearest" (default: "center")
- `smooth`: Use smooth animation (default: true)

**Example:**
```python
"Use scroll_to_element with selector='#section-3' and alignment='start'"
```

### 4. `scroll_until_visible`

Scroll through page/container until specific text is found.

**Parameters:**
- `text`: Text to search for
- `max_scrolls`: Maximum scroll attempts (default: 10)
- `scroll_amount`: Pixels per scroll (default: 300)
- `container_selector`: Container to scroll (default: auto-detect)

**Example:**
```python
"Use scroll_until_visible to find 'Terms and Conditions' text"
```

### 5. `handle_infinite_scroll`

Handle pages with infinite scrolling by loading content progressively.

**Parameters:**
- `max_items`: Maximum items to load (default: no limit)
- `max_scrolls`: Maximum scroll attempts (default: 20)
- `wait_time`: Seconds to wait after each scroll (default: 2.0)
- `item_selector`: CSS selector to count items (optional)

**Example:**
```python
"Use handle_infinite_scroll with max_items=100 and item_selector='.post'"
```

## Real-World Examples

### LinkedIn Sales Navigator Filter Scrolling

```python
task = """
You are on LinkedIn Sales Navigator search page.

1. Use detect_scrollable_areas to identify all scrollable areas
2. If the filter panel is scrollable, note its selector (usually 'form.overflow-y-auto')
3. To find "Seniority Level" filter:
   - Use enhanced_scroll with target_selector='form.overflow-y-auto' and amount=400
   - Repeat until "Seniority Level" is visible
4. Click "Seniority Level" to open dropdown
5. Use detect_scrollable_areas again to check if dropdown is scrollable
6. If "CXO" option is not visible in dropdown:
   - Use enhanced_scroll with target_selector='.artdeco-typeahead__results-list' and amount=200
   - Or use scroll_until_visible with text='CXO' and container_selector='.artdeco-typeahead__results-list'
7. Click Include button for CXO
"""
```

### Research Paper Navigation

```python
task = """
1. Go to arxiv.org and search for "transformer architecture"
2. Click on the first paper
3. Use scroll_until_visible to find "References" section
4. Once there, use enhanced_scroll with strategy='to_end' to see all references
"""
```

### Social Media Feed Loading

```python
task = """
1. Go to a social media feed
2. Use handle_infinite_scroll with:
   - max_items: 50
   - item_selector: '.post' (adjust based on site)
3. Extract information from the loaded posts
"""
```

### Documentation Site Navigation

```python
task = """
1. Go to the Python documentation
2. Use detect_scrollable_areas to find the sidebar navigation
3. Use enhanced_scroll with target_selector='[sidebar selector]' to scroll through topics
4. Use scroll_to_element to jump to specific sections
"""
```

## Best Practices

1. **Always detect first**: Use `detect_scrollable_areas` before scrolling to understand the page structure.

2. **Target specific containers**: When dealing with multiple scrollable areas (like LinkedIn), use `target_selector` to scroll the right container.

3. **Use appropriate strategies**:
   - `pixels`: For precise control
   - `viewport`: For responsive scrolling
   - `page`: For paginated content
   - `to_end`: To quickly reach extremes

4. **Handle infinite scroll carefully**: Set reasonable limits with `max_items` and `max_scrolls` to avoid infinite loops.

5. **Combine with standard actions**: Enhanced scrolling works seamlessly with browser-use's built-in actions like `click`, `input_text`, etc.

## Troubleshooting

### "Container not found" errors
- The selector might be wrong or the element might not exist yet
- Try using `detect_scrollable_areas` first to get the correct selector

### Scrolling the wrong element
- Use `target_selector` to explicitly specify which element to scroll
- Some sites have nested scrollable containers - be specific

### Content not loading in infinite scroll
- Increase `wait_time` parameter to give the site more time to load
- Check if the site requires you to be near the bottom before loading more

### Scroll not working
- Some sites use custom scroll implementations
- Try different strategies or fall back to multiple smaller scrolls

## Implementation Details

The enhanced scrolling module:
- Uses Playwright's `evaluate` for JavaScript execution
- Leverages browser-use's existing `_scroll_container` for smart detection
- Implements proper error handling and logging
- Returns structured data for agent memory
- Supports both sync and async operations

The module is designed to be extensible - new scrolling strategies and actions can be easily added by following the established patterns.