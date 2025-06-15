"""
Resolution strategies for element finding
"""

from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from browser_use.perception.base import PerceptionElement, PerceptionQuery
from browser_use.perception.dom.simple_element_finder import SimpleElementFinder
from browser_use.core.intent.views import ElementIntent
from playwright.async_api import Page
import logging

logger = logging.getLogger(__name__)


class ResolutionStrategy(ABC):
    """Base class for resolution strategies"""
    
    @abstractmethod
    async def resolve(
        self, 
        element_intent: ElementIntent, 
        perception_data: Dict[str, Any],
        page: Page
    ) -> Optional[PerceptionElement]:
        """Resolve element using this strategy"""
        pass


class SimpleFinderStrategy(ResolutionStrategy):
    """Strategy that uses SimpleElementFinder directly"""
    
    async def resolve(
        self, 
        element_intent: ElementIntent, 
        perception_data: Dict[str, Any],
        page: Page
    ) -> Optional[PerceptionElement]:
        """Resolve using SimpleElementFinder"""
        
        logger.debug(f"SimpleFinderStrategy resolving: {element_intent.description}")
        
        # Use SimpleElementFinder directly
        element = await SimpleElementFinder.find_element_by_description(
            page=page,
            description=element_intent.description,
            element_type=element_intent.element_type,
            attributes=element_intent.attributes
        )
        
        if element:
            logger.debug(f"Found element: {element.selector}")
        else:
            logger.debug("No element found")
            
        return element


class DOMProcessorStrategy(ResolutionStrategy):
    """Strategy that uses DOM processor"""
    
    def __init__(self, dom_processor):
        self.dom_processor = dom_processor
    
    async def resolve(
        self, 
        element_intent: ElementIntent, 
        perception_data: Dict[str, Any],
        page: Page
    ) -> Optional[PerceptionElement]:
        """Resolve using DOM processor"""
        
        if not self.dom_processor:
            return None
            
        query = PerceptionQuery(
            description=element_intent.description,
            element_type=element_intent.element_type,
            attributes=element_intent.attributes,
            context={"page": page}
        )
        
        elements = await self.dom_processor.find_elements(query)
        return elements[0] if elements else None