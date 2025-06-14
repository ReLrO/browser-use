"""Multi-modal perception system for browser automation"""

from .base import (
	BoundingBox, PerceptionElement, PerceptionResult,
	PerceptionQuery, PerceptionCapability, IPerceptionSystem,
	PerceptionFusion
)
from .vision.service import VisionEngine
from .dom.service import IncrementalDOMProcessor
from .accessibility.service import AccessibilityProcessor
from .fusion.service import MultiModalPerceptionFusion

__all__ = [
	'BoundingBox', 'PerceptionElement', 'PerceptionResult',
	'PerceptionQuery', 'PerceptionCapability', 'IPerceptionSystem',
	'PerceptionFusion',
	'VisionEngine', 'IncrementalDOMProcessor', 
	'AccessibilityProcessor', 'MultiModalPerceptionFusion'
]