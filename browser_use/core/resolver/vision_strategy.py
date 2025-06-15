"""Vision-based resolution strategy for universal UI understanding"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from playwright.async_api import Page

from browser_use.perception.base import PerceptionElement, BoundingBox
from browser_use.perception.vision.universal_ui_analyzer import VisionBasedUIAnalyzer
from browser_use.core.intent.views import ElementIntent
from browser_use.core.resolver.strategies import ResolutionStrategy

logger = logging.getLogger(__name__)


class VisionResolutionStrategy(ResolutionStrategy):
    """Resolution strategy that uses vision models to understand UI universally"""
    
    def __init__(self, llm):
        self.llm = llm
        self.ui_analyzer = VisionBasedUIAnalyzer(llm)
        self._element_cache = {}
    
    async def resolve(
        self,
        element_intent: ElementIntent,
        perception_data: Dict[str, Any],
        page: Page
    ) -> Optional[PerceptionElement]:
        """Resolve element using vision-based understanding"""
        
        logger.info(f"VisionResolutionStrategy resolving: {element_intent.description}")
        
        try:
            # Take screenshot if not available
            screenshot = None
            if 'screenshot' in perception_data:
                import base64
                screenshot = base64.b64decode(perception_data['screenshot'])
            else:
                screenshot = await page.screenshot()
            
            # Use vision to find the element
            result = await self.ui_analyzer.find_element_for_action(
                screenshot=screenshot,
                action_description=element_intent.description
            )
            
            if not result or not result.get('found'):
                logger.info("Vision could not find matching element")
                return None
            
            element_info = result['element']
            logger.info(f"Vision found element: {element_info['description']} with confidence {element_info['confidence']}")
            logger.debug(f"Reasoning: {element_info['reasoning']}")
            
            # Now we need to map the visual finding to an actual DOM element
            # We'll use a combination of the visual location and element matching
            
            # Get all interactive elements from the page
            elements = await self._get_page_elements(page)
            
            # Find best matching element based on vision description
            best_match = await self._match_visual_to_dom(
                visual_element=element_info,
                dom_elements=elements,
                page=page
            )
            
            if best_match:
                return best_match
            else:
                logger.warning("Could not map visual element to DOM element")
                # Try a more aggressive search based on the action description
                return await self._fallback_element_search(page, element_intent)
                
        except Exception as e:
            logger.error(f"Vision resolution strategy error: {e}")
            return None
    
    async def _fallback_element_search(self, page: Page, element_intent: ElementIntent) -> Optional[PerceptionElement]:
        """Fallback search when vision mapping fails"""
        logger.info(f"Trying fallback search for: {element_intent.description}")
        
        desc_lower = element_intent.description.lower()
        
        # For search results, try to find any substantial link
        if any(word in desc_lower for word in ['first', 'result', 'link', 'click', 'blue']):
            try:
                # Wait a bit for results to load
                await page.wait_for_timeout(1000)
                
                # Get all visible links
                all_links = await page.locator('a:visible').all()
                logger.info(f"Found {len(all_links)} visible links on page")
                
                # Find good candidates
                candidates = []
                for i, link in enumerate(all_links):
                    try:
                        text = await link.text_content()
                        if not text:
                            continue
                            
                        text = text.strip()
                        
                        # Get href to check if it's a real link
                        href = await link.get_attribute('href')
                        if not href or href == '#' or href.startswith('javascript:'):
                            continue
                        
                        # Get position
                        box = await link.bounding_box()
                        if not box:
                            continue
                        
                        # Score the link
                        score = 0
                        reasons = []
                        
                        # Length check - substantial text
                        if len(text) > 15:
                            score += 1
                            reasons.append("substantial_text")
                        
                        # Position check - not in header/footer
                        if box['y'] > 150 and box['y'] < 2000:
                            score += 1
                            reasons.append("good_position")
                        
                        # Not navigation
                        nav_words = ['sign in', 'log in', 'about', 'contact', 'privacy', 'terms', 'help', 'home']
                        if not any(nav in text.lower() for nav in nav_words):
                            score += 1
                            reasons.append("not_navigation")
                        
                        # Looks like a result (has descriptive text)
                        if len(text.split()) > 3:
                            score += 1
                            reasons.append("descriptive")
                        
                        if score >= 3:  # Good candidate
                            candidates.append({
                                'link': link,
                                'text': text,
                                'box': box,
                                'score': score,
                                'reasons': reasons,
                                'index': i
                            })
                    except:
                        continue
                
                if candidates:
                    # Sort by score and position
                    candidates.sort(key=lambda x: (-x['score'], x['box']['y']))
                    best = candidates[0]
                    
                    logger.info(f"Selected link: '{best['text'][:50]}...' at position {best['index']} with score {best['score']}")
                    
                    # Create element directly from the link
                    return PerceptionElement(
                        type='a',
                        text=best['text'],
                        selector=f"a:nth-of-type({best['index'] + 1})",
                        bounding_box=BoundingBox(**best['box']),
                        confidence=0.8,
                        is_interactive=True,
                        is_visible=True,
                        attributes={
                            'fallback_match': True,
                            'match_reasons': best['reasons']
                        }
                    )
                else:
                    logger.warning("No good link candidates found")
                    
            except Exception as e:
                logger.error(f"Fallback search error: {e}")
                import traceback
                traceback.print_exc()
        
        return None
    
    async def _get_page_elements(self, page: Page) -> List[Dict[str, Any]]:
        """Get all interactive elements from page"""
        
        elements = await page.evaluate("""() => {
            function describeLocation(rect) {
                const vpWidth = window.innerWidth;
                const vpHeight = window.innerHeight;
                const centerX = rect.x + rect.width / 2;
                const centerY = rect.y + rect.height / 2;
                
                let horizontal = '';
                if (centerX < vpWidth * 0.33) horizontal = 'left';
                else if (centerX > vpWidth * 0.67) horizontal = 'right';
                else horizontal = 'center';
                
                let vertical = '';
                if (centerY < vpHeight * 0.33) vertical = 'top';
                else if (centerY > vpHeight * 0.67) vertical = 'bottom';
                else vertical = 'middle';
                
                return vertical === 'middle' ? horizontal : `${vertical}-${horizontal}`;
            }
            
            const interactiveSelectors = [
                // Inputs
                'input[type="text"]', 'input[type="search"]', 'input[type="email"]', 
                'input[type="password"]', 'input[type="tel"]', 'input[type="url"]',
                'input:not([type="hidden"]):not([type="submit"]):not([type="button"])',
                'textarea', '[contenteditable="true"]',
                
                // Buttons and clickables
                'button', 'input[type="submit"]', 'input[type="button"]',
                '[role="button"]', '[role="tab"]', '[role="menuitem"]',
                
                // Links
                'a[href]', 'a[onclick]', '[role="link"]',
                
                // Dropdowns
                'select', '[role="combobox"]', '[role="listbox"]',
                
                // Generic clickables
                '[onclick]', '[ng-click]', '[data-click]',
                '[tabindex]:not([tabindex="-1"])',
                
                // Common clickable classes
                '.btn', '.button', '.link', '.clickable',
                '*[class*="button"]:not(script):not(style)',
                '*[class*="btn"]:not(script):not(style)'
            ];
            
            const elements = [];
            const seen = new Set();
            
            for (const selector of interactiveSelectors) {
                document.querySelectorAll(selector).forEach(el => {
                    if (seen.has(el) || !el.offsetParent) return;
                    seen.add(el);
                    
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    
                    // Build selector
                    let uniqueSelector = '';
                    if (el.id) {
                        uniqueSelector = '#' + el.id;
                    } else {
                        // Build a simple selector
                        uniqueSelector = el.tagName.toLowerCase();
                        if (el.className) {
                            const classes = el.className.split(' ').filter(c => c).slice(0, 2);
                            if (classes.length) {
                                uniqueSelector += '.' + classes.join('.');
                            }
                        }
                        // Add index if needed
                        const siblings = Array.from(el.parentElement?.children || []);
                        const index = siblings.indexOf(el);
                        if (index > 0) {
                            uniqueSelector += `:nth-child(${index + 1})`;
                        }
                    }
                    
                    elements.push({
                        selector: uniqueSelector,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || el.getAttribute('type') || '',
                        role: el.getAttribute('role') || '',
                        text: el.textContent.trim().substring(0, 100),
                        placeholder: el.placeholder || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        rect: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            top: rect.top,
                            bottom: rect.bottom,
                            left: rect.left,
                            right: rect.right
                        },
                        visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden',
                        // Location description
                        location: describeLocation(rect),
                        isInput: el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.getAttribute('role') === 'textbox' || el.getAttribute('role') === 'searchbox',
                        isButton: el.tagName === 'BUTTON' || el.getAttribute('role') === 'button',
                        isLink: el.tagName === 'A',
                        isSearchInput: el.type === 'search' || el.name?.includes('search') || el.id?.includes('search') || el.getAttribute('role') === 'searchbox'
                    });
                });
            }
            
            return elements;
        }""")
        
        return elements
    
    async def _match_visual_to_dom(
        self,
        visual_element: Dict[str, Any],
        dom_elements: List[Dict[str, Any]],
        page: Page
    ) -> Optional[PerceptionElement]:
        """Match visual description to actual DOM element - UNIVERSAL approach"""
        
        visual_location = visual_element.get('location', '').lower()
        visual_desc = visual_element.get('description', '').lower()
        visual_appearance = visual_element.get('visual_appearance', '').lower()
        
        logger.debug(f"Matching visual element: {visual_desc} at {visual_location}")
        
        # Universal scoring system - works for ANY element type
        scored_elements = []
        
        for elem in dom_elements:
            if not elem['visible']:
                continue
                
            score = 0.0
            reasons = []
            
            # 1. INTERACTIVE ELEMENT BONUS - any interactive element gets a base score
            if elem.get('isInput') or elem.get('isButton') or elem.get('isLink') or elem['tag'] in ['a', 'button', 'input', 'select', 'textarea']:
                score += 0.2
                reasons.append("interactive")
            
            # 2. TEXT MATCHING - most reliable signal
            elem_text = (elem.get('text', '') or '').lower().strip()
            elem_placeholder = (elem.get('placeholder', '') or '').lower()
            elem_aria = (elem.get('ariaLabel', '') or '').lower()
            elem_name = (elem.get('name', '') or '').lower()
            elem_id = (elem.get('id', '') or '').lower()
            
            # Combine all text sources
            all_elem_text = f"{elem_text} {elem_placeholder} {elem_aria} {elem_name} {elem_id}"
            
            # Check if visual description mentions any text from the element
            if elem_text and len(elem_text) > 5:  # Meaningful text
                # Direct text match
                if elem_text in visual_desc or visual_desc in elem_text:
                    score += 0.5
                    reasons.append(f"text_match: '{elem_text[:30]}'")
                # Partial word match
                elif any(word in elem_text.split() for word in visual_desc.split() if len(word) > 3):
                    score += 0.3
                    reasons.append("partial_text_match")
            
            # 3. ELEMENT TYPE MATCHING - flexible type detection
            elem_tag = elem.get('tag', '').lower()
            elem_type = elem.get('type', '').lower()
            elem_role = elem.get('role', '').lower()
            
            # Input/search field detection
            if any(word in visual_desc for word in ['input', 'field', 'text', 'search', 'type', 'enter', 'box']):
                if elem.get('isInput') or elem_tag in ['input', 'textarea'] or elem_role in ['textbox', 'searchbox']:
                    score += 0.4
                    reasons.append("input_match")
                    if 'search' in all_elem_text:
                        score += 0.2
                        reasons.append("search_specific")
            
            # Button detection
            elif any(word in visual_desc for word in ['button', 'submit', 'click']):
                if elem.get('isButton') or elem_tag == 'button' or elem_type in ['submit', 'button'] or elem_role == 'button':
                    score += 0.4
                    reasons.append("button_match")
            
            # Link/result detection
            elif any(word in visual_desc for word in ['link', 'result', 'navigate', 'click']):
                if elem_tag == 'a' or elem_role == 'link':
                    score += 0.4
                    reasons.append("link_match")
                    # Search result heuristics
                    if 'result' in visual_desc:
                        # Prefer links with substantial text
                        if len(elem_text) > 20:
                            score += 0.2
                            reasons.append("long_link_text")
                        # Avoid navigation/menu links
                        if not any(nav_word in elem_text for nav_word in ['home', 'about', 'contact', 'menu', 'sign in', 'log in']):
                            score += 0.1
                            reasons.append("non_nav_link")
            
            # Generic clickable detection
            elif 'click' in visual_desc:
                if elem_tag in ['a', 'button', 'div', 'span'] and (elem.get('onclick') or elem.get('style', '').get('cursor') == 'pointer'):
                    score += 0.3
                    reasons.append("clickable")
            
            # 4. LOCATION MATCHING - where on the page
            elem_location = elem.get('location', '').lower()
            if visual_location and elem_location:
                if elem_location == visual_location:
                    score += 0.2
                    reasons.append(f"exact_location: {elem_location}")
                elif any(part in elem_location for part in visual_location.split('-')):
                    score += 0.1
                    reasons.append(f"partial_location: {elem_location}")
            
            # 5. VISUAL PROMINENCE - larger/centered elements for main actions
            rect = elem.get('rect', {})
            if rect:
                width = rect.get('width', 0)
                height = rect.get('height', 0)
                x = rect.get('x', 0)
                y = rect.get('y', 0)
                
                # Size scoring
                if width > 300 and height > 30:  # Large element
                    score += 0.1
                    reasons.append("large_element")
                
                # Position scoring for search results (usually in center-left area)
                if 'result' in visual_desc and y > 200 and x < 800:
                    score += 0.1
                    reasons.append("result_position")
            
            # 6. FIRST/ORDINAL MATCHING
            if 'first' in visual_desc and elem_tag == 'a':
                # This will be handled by sorting later, just note it
                reasons.append("first_requested")
            
            # 7. NEGATIVE SCORING - avoid certain elements
            # Avoid ads
            if any(ad_word in all_elem_text for ad_word in ['ad', 'sponsored', 'promotion']):
                score -= 0.3
                reasons.append("likely_ad")
            
            # Avoid hidden or tiny elements
            if rect and (rect.get('width', 0) < 10 or rect.get('height', 0) < 10):
                score -= 0.2
                reasons.append("too_small")
            
            # Only consider elements with positive score
            if score > 0:
                scored_elements.append({
                    'score': score,
                    'elem': elem,
                    'reasons': reasons
                })
        
        # Sort by score
        scored_elements.sort(key=lambda x: x['score'], reverse=True)
        
        # If looking for "first" of something, filter and re-sort
        if 'first' in visual_desc and scored_elements:
            # Filter to only the type we want
            if 'result' in visual_desc:
                # Get all links that look like results
                result_elements = [se for se in scored_elements if se['elem']['tag'] == 'a' and se['score'] > 0.3]
                if result_elements:
                    # Sort by Y position to get the topmost
                    result_elements.sort(key=lambda x: x['elem']['rect'].get('y', 999999))
                    scored_elements = result_elements[:1]  # Take only the first
        
        # Log top candidates for debugging
        logger.debug(f"Top 3 candidates for '{visual_desc}':")
        for i, se in enumerate(scored_elements[:3]):
            elem = se['elem']
            logger.debug(f"  {i+1}. Score: {se['score']:.2f}, Tag: {elem['tag']}, Text: '{elem.get('text', '')[:50]}', Reasons: {se['reasons']}")
        
        # Return best match if score is good enough
        if scored_elements and scored_elements[0]['score'] > 0.2:  # Lower threshold for more matches
            best = scored_elements[0]
            best_elem = best['elem']
            
            logger.info(f"Selected element: {best_elem['tag']} with score {best['score']:.2f} - {best['reasons']}")
            
            # Try multiple methods to get the element
            element_handle = None
            
            # Method 1: Direct selector
            if best_elem.get('selector'):
                try:
                    element_handle = await page.query_selector(best_elem['selector'])
                except:
                    pass
            
            # Method 2: By text content
            if not element_handle and best_elem.get('text'):
                try:
                    text_to_find = best_elem['text'][:50].strip()
                    if text_to_find:
                        element_handle = await page.locator(f'text="{text_to_find}"').first.element_handle()
                except:
                    pass
            
            # Method 3: By attributes
            if not element_handle and best_elem['tag'] == 'a' and best_elem.get('text'):
                try:
                    # Find link with partial text match
                    element_handle = await page.locator(f'a:has-text("{best_elem["text"][:20]}")').first.element_handle()
                except:
                    pass
            
            if element_handle:
                # Get final bounding box
                box = await element_handle.bounding_box()
                bounding_box = None
                if box:
                    bounding_box = BoundingBox(
                        x=box['x'],
                        y=box['y'],
                        width=box['width'],
                        height=box['height']
                    )
                
                return PerceptionElement(
                    type=best_elem['tag'],
                    text=best_elem.get('text', ''),
                    selector=best_elem.get('selector'),
                    bounding_box=bounding_box,
                    confidence=min(visual_element['confidence'] * best['score'], 1.0),
                    is_interactive=True,
                    is_visible=True,
                    attributes={
                        'visual_match': visual_element['description'],
                        'match_reasons': best['reasons'],
                        'location': best_elem.get('location', '')
                    }
                )
            else:
                logger.warning(f"Could not get element handle for best match: {best_elem['tag']} - '{best_elem.get('text', '')[:30]}'")
        
        logger.warning(f"No suitable element found for: {visual_desc}")
        return None