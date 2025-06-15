"""
Resolution strategies for element finding
"""

from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from browser_use.perception.base import PerceptionElement, PerceptionQuery
from browser_use.perception.dom.simple_element_finder import SimpleElementFinder
from browser_use.core.intent.views import ElementIntent
from browser_use.core.resolver.llm_element_finder import LLMElementFinder
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


class LLMFinderStrategy(ResolutionStrategy):
    """Strategy that uses LLM to find elements"""
    
    def __init__(self, llm):
        self.llm_finder = LLMElementFinder(llm)
    
    async def resolve(
        self, 
        element_intent: ElementIntent, 
        perception_data: Dict[str, Any],
        page: Page
    ) -> Optional[PerceptionElement]:
        """Resolve using LLM element finder"""
        
        logger.debug(f"LLMFinderStrategy resolving: {element_intent.description}")
        
        element = await self.llm_finder.find_element(
            page=page,
            element_intent=element_intent
        )
        
        if element:
            logger.debug(f"LLM found element: {element.selector}")
        else:
            logger.debug("LLM could not find element")
            
        return element