"""Fusion layer for combining multi-modal perception results"""

import asyncio
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime
import numpy as np
from collections import defaultdict

from browser_use.perception.base import (
	PerceptionFusion, IPerceptionSystem, PerceptionElement,
	PerceptionResult, PerceptionQuery, BoundingBox
)
from browser_use.perception.vision.service import VisionEngine
from browser_use.perception.dom.service import IncrementalDOMProcessor
from browser_use.perception.accessibility.service import AccessibilityProcessor
from browser_use.utils import time_execution_async


class MultiModalPerceptionFusion(PerceptionFusion):
	"""Advanced fusion of vision, DOM, and accessibility perception"""
	
	def __init__(self):
		super().__init__()
		self._element_clusters: List[List[PerceptionElement]] = []
		self._fusion_weights = {
			"vision": 0.4,
			"dom": 0.35,
			"accessibility": 0.25
		}
		self._confidence_thresholds = {
			"high": 0.8,
			"medium": 0.6,
			"low": 0.4
		}
	
	@time_execution_async("perception_fusion")
	async def fuse_results(self, results: dict[str, PerceptionResult]) -> PerceptionResult:
		"""Intelligently fuse results from multiple perception systems"""
		
		# Collect all elements and errors
		all_elements = []
		all_errors = []
		processing_times = {}
		
		for system_name, result in results.items():
			all_elements.extend([(system_name, elem) for elem in result.elements])
			all_errors.extend(result.errors)
			processing_times[system_name] = result.processing_time_ms
		
		# Cluster similar elements
		clusters = self._cluster_elements(all_elements)
		
		# Fuse each cluster into a single element
		fused_elements = []
		for cluster in clusters:
			fused_element = self._fuse_cluster(cluster)
			if fused_element:
				fused_elements.append(fused_element)
		
		# Merge page context
		merged_context = self._merge_contexts(results)
		
		# Calculate total processing time
		total_time = sum(processing_times.values())
		
		# Add fusion metadata
		merged_context["fusion_metadata"] = {
			"systems_used": list(results.keys()),
			"processing_times": processing_times,
			"total_elements_before_fusion": sum(len(r.elements) for r in results.values()),
			"total_elements_after_fusion": len(fused_elements),
			"fusion_confidence": self._calculate_fusion_confidence(results)
		}
		
		return PerceptionResult(
			elements=fused_elements,
			page_context=merged_context,
			processing_time_ms=total_time,
			errors=all_errors
		)
	
	def _cluster_elements(self, elements: List[Tuple[str, PerceptionElement]]) -> List[List[Tuple[str, PerceptionElement]]]:
		"""Cluster similar elements from different systems"""
		clusters = []
		used = set()
		
		for i, (system1, elem1) in enumerate(elements):
			if i in used:
				continue
			
			cluster = [(system1, elem1)]
			used.add(i)
			
			for j, (system2, elem2) in enumerate(elements[i+1:], i+1):
				if j in used:
					continue
				
				if self._are_elements_similar(elem1, elem2):
					cluster.append((system2, elem2))
					used.add(j)
			
			clusters.append(cluster)
		
		return clusters
	
	def _are_elements_similar(self, elem1: PerceptionElement, elem2: PerceptionElement) -> bool:
		"""Check if two elements refer to the same UI element"""
		
		# Check spatial overlap if both have bounding boxes
		if elem1.bounding_box and elem2.bounding_box:
			overlap = self._calculate_bbox_overlap(elem1.bounding_box, elem2.bounding_box)
			if overlap > 0.7:  # 70% overlap threshold
				return True
		
		# Check selector match
		if elem1.selector and elem2.selector:
			if elem1.selector == elem2.selector:
				return True
		
		# Check text similarity
		if elem1.text and elem2.text:
			similarity = self._text_similarity(elem1.text, elem2.text)
			if similarity > 0.8:
				return True
		
		# Check label/role match
		if elem1.label and elem2.label:
			if elem1.label.lower() == elem2.label.lower():
				return True
		
		if elem1.role and elem2.role:
			if elem1.role == elem2.role:
				# Check if they're in similar location
				if elem1.bounding_box and elem2.bounding_box:
					distance = self._calculate_bbox_distance(elem1.bounding_box, elem2.bounding_box)
					if distance < 50:  # 50 pixels threshold
						return True
		
		return False
	
	def _fuse_cluster(self, cluster: List[Tuple[str, PerceptionElement]]) -> Optional[PerceptionElement]:
		"""Fuse a cluster of similar elements into one"""
		if not cluster:
			return None
		
		# If only one element, return it with adjusted confidence
		if len(cluster) == 1:
			system, element = cluster[0]
			element.confidence *= self._fusion_weights.get(system, 0.3)
			return element
		
		# Collect all properties
		systems = [system for system, _ in cluster]
		elements = [elem for _, elem in cluster]
		
		# Calculate fused confidence
		confidence = self._calculate_cluster_confidence(cluster)
		
		# Fuse bounding boxes
		bounding_box = self._fuse_bounding_boxes(elements)
		
		# Fuse text content
		text = self._fuse_text(elements)
		
		# Fuse attributes
		attributes = self._fuse_attributes(elements)
		
		# Determine type and role
		type_counts = defaultdict(int)
		role_counts = defaultdict(int)
		
		for elem in elements:
			if elem.type:
				type_counts[elem.type] += 1
			if elem.role:
				role_counts[elem.role] += 1
		
		element_type = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else "unknown"
		role = max(role_counts.items(), key=lambda x: x[1])[0] if role_counts else None
		
		# Get best selector (prefer DOM selector)
		selector = None
		for system, elem in cluster:
			if system == "dom" and elem.selector:
				selector = elem.selector
				break
		if not selector:
			selector = next((elem.selector for elem in elements if elem.selector), None)
		
		# Get best label (prefer accessibility label)
		label = None
		for system, elem in cluster:
			if system == "accessibility" and elem.label:
				label = elem.label
				break
		if not label:
			label = next((elem.label for elem in elements if elem.label), None)
		
		# Combine descriptions
		descriptions = [elem.description for elem in elements if elem.description]
		description = " | ".join(set(descriptions)) if descriptions else None
		
		# Determine states
		is_visible = any(elem.is_visible for elem in elements)
		is_interactive = any(elem.is_interactive for elem in elements)
		is_disabled = any(elem.is_disabled for elem in elements)
		is_focused = any(elem.is_focused for elem in elements)
		
		# Create fused element
		fused = PerceptionElement(
			type=element_type,
			confidence=confidence,
			bounding_box=bounding_box,
			selector=selector,
			text=text,
			attributes=attributes,
			role=role,
			label=label,
			description=description,
			is_visible=is_visible,
			is_interactive=is_interactive,
			is_disabled=is_disabled,
			is_focused=is_focused
		)
		
		# Add fusion metadata
		fused.attributes["_fusion_sources"] = systems
		fused.attributes["_fusion_count"] = len(cluster)
		
		return fused
	
	def _calculate_bbox_overlap(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
		"""Calculate IoU (Intersection over Union) for two bounding boxes"""
		# Calculate intersection
		x1 = max(bbox1.x, bbox2.x)
		y1 = max(bbox1.y, bbox2.y)
		x2 = min(bbox1.x + bbox1.width, bbox2.x + bbox2.width)
		y2 = min(bbox1.y + bbox1.height, bbox2.y + bbox2.height)
		
		if x2 < x1 or y2 < y1:
			return 0.0
		
		intersection = (x2 - x1) * (y2 - y1)
		
		# Calculate union
		area1 = bbox1.width * bbox1.height
		area2 = bbox2.width * bbox2.height
		union = area1 + area2 - intersection
		
		return intersection / union if union > 0 else 0.0
	
	def _calculate_bbox_distance(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
		"""Calculate distance between centers of two bounding boxes"""
		center1_x = bbox1.x + bbox1.width / 2
		center1_y = bbox1.y + bbox1.height / 2
		center2_x = bbox2.x + bbox2.width / 2
		center2_y = bbox2.y + bbox2.height / 2
		
		return np.sqrt((center2_x - center1_x) ** 2 + (center2_y - center1_y) ** 2)
	
	def _text_similarity(self, text1: str, text2: str) -> float:
		"""Calculate text similarity (simple version)"""
		if not text1 or not text2:
			return 0.0
		
		# Normalize
		text1 = text1.lower().strip()
		text2 = text2.lower().strip()
		
		if text1 == text2:
			return 1.0
		
		# Check if one contains the other
		if text1 in text2 or text2 in text1:
			return 0.9
		
		# Simple word overlap
		words1 = set(text1.split())
		words2 = set(text2.split())
		
		if not words1 or not words2:
			return 0.0
		
		intersection = len(words1 & words2)
		union = len(words1 | words2)
		
		return intersection / union if union > 0 else 0.0
	
	def _calculate_cluster_confidence(self, cluster: List[Tuple[str, PerceptionElement]]) -> float:
		"""Calculate confidence for a fused element"""
		if not cluster:
			return 0.0
		
		# Weighted average based on system weights
		total_weight = 0.0
		weighted_confidence = 0.0
		
		for system, elem in cluster:
			weight = self._fusion_weights.get(system, 0.3)
			total_weight += weight
			weighted_confidence += elem.confidence * weight
		
		base_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.5
		
		# Boost confidence based on number of agreeing systems
		agreement_boost = min(0.2, 0.1 * (len(cluster) - 1))
		
		return min(1.0, base_confidence + agreement_boost)
	
	def _fuse_bounding_boxes(self, elements: List[PerceptionElement]) -> Optional[BoundingBox]:
		"""Fuse multiple bounding boxes into one"""
		bboxes = [elem.bounding_box for elem in elements if elem.bounding_box]
		
		if not bboxes:
			return None
		
		if len(bboxes) == 1:
			return bboxes[0]
		
		# Calculate weighted average based on confidence
		total_weight = sum(elem.confidence for elem in elements if elem.bounding_box)
		
		if total_weight == 0:
			# Simple average
			x = sum(bbox.x for bbox in bboxes) / len(bboxes)
			y = sum(bbox.y for bbox in bboxes) / len(bboxes)
			width = sum(bbox.width for bbox in bboxes) / len(bboxes)
			height = sum(bbox.height for bbox in bboxes) / len(bboxes)
		else:
			# Weighted average
			x = sum(elem.bounding_box.x * elem.confidence for elem in elements if elem.bounding_box) / total_weight
			y = sum(elem.bounding_box.y * elem.confidence for elem in elements if elem.bounding_box) / total_weight
			width = sum(elem.bounding_box.width * elem.confidence for elem in elements if elem.bounding_box) / total_weight
			height = sum(elem.bounding_box.height * elem.confidence for elem in elements if elem.bounding_box) / total_weight
		
		return BoundingBox(x=x, y=y, width=width, height=height)
	
	def _fuse_text(self, elements: List[PerceptionElement]) -> str:
		"""Fuse text content from multiple elements"""
		texts = [elem.text for elem in elements if elem.text]
		
		if not texts:
			return ""
		
		# If all texts are similar, return the longest one
		if all(self._text_similarity(texts[0], text) > 0.8 for text in texts[1:]):
			return max(texts, key=len)
		
		# Otherwise, find the most common one
		text_counts = defaultdict(int)
		for text in texts:
			text_counts[text] += 1
		
		return max(text_counts.items(), key=lambda x: x[1])[0]
	
	def _fuse_attributes(self, elements: List[PerceptionElement]) -> dict[str, Any]:
		"""Fuse attributes from multiple elements"""
		all_attributes = {}
		
		# Collect all attributes with their sources
		for elem in elements:
			for key, value in elem.attributes.items():
				if key not in all_attributes:
					all_attributes[key] = []
				all_attributes[key].append(value)
		
		# Fuse each attribute
		fused_attributes = {}
		for key, values in all_attributes.items():
			# Remove None values
			values = [v for v in values if v is not None]
			
			if not values:
				continue
			
			if len(set(values)) == 1:
				# All agree
				fused_attributes[key] = values[0]
			else:
				# Take the most common value
				value_counts = defaultdict(int)
				for value in values:
					value_counts[str(value)] += 1
				
				most_common = max(value_counts.items(), key=lambda x: x[1])[0]
				
				# Try to convert back to original type
				sample_value = values[0]
				if isinstance(sample_value, bool):
					fused_attributes[key] = most_common.lower() == "true"
				elif isinstance(sample_value, (int, float)):
					try:
						fused_attributes[key] = type(sample_value)(most_common)
					except:
						fused_attributes[key] = most_common
				else:
					fused_attributes[key] = most_common
		
		return fused_attributes
	
	def _merge_contexts(self, results: dict[str, PerceptionResult]) -> dict[str, Any]:
		"""Merge page contexts from all systems"""
		merged = {}
		
		for system_name, result in results.items():
			for key, value in result.page_context.items():
				prefixed_key = f"{system_name}_{key}"
				merged[prefixed_key] = value
		
		# Add combined insights
		merged["combined_insights"] = self._generate_combined_insights(results)
		
		return merged
	
	def _generate_combined_insights(self, results: dict[str, PerceptionResult]) -> dict[str, Any]:
		"""Generate insights from combined perception results"""
		insights = {
			"page_complexity": "unknown",
			"accessibility_score": None,
			"visual_quality": None,
			"interaction_readiness": None
		}
		
		# Calculate page complexity
		total_elements = sum(len(r.elements) for r in results.values())
		if total_elements < 50:
			insights["page_complexity"] = "simple"
		elif total_elements < 200:
			insights["page_complexity"] = "moderate"
		else:
			insights["page_complexity"] = "complex"
		
		# Get accessibility score if available
		if "accessibility" in results:
			a11y_context = results["accessibility"].page_context
			if "landmarks" in a11y_context:
				# Simple scoring based on landmarks
				landmarks = a11y_context["landmarks"]
				score = 0
				if "main" in landmarks:
					score += 3
				if "navigation" in landmarks:
					score += 2
				if "banner" in landmarks:
					score += 1
				insights["accessibility_score"] = min(10, score * 1.5)
		
		# Visual quality from vision system
		if "vision" in results:
			vision_context = results["vision"].page_context
			if "visual_analysis_complete" in vision_context:
				insights["visual_quality"] = "analyzed"
		
		# Interaction readiness
		interactive_count = sum(
			sum(1 for e in r.elements if e.is_interactive)
			for r in results.values()
		)
		if interactive_count > 0:
			insights["interaction_readiness"] = "ready"
		else:
			insights["interaction_readiness"] = "no_interactive_elements"
		
		return insights
	
	def _calculate_fusion_confidence(self, results: dict[str, PerceptionResult]) -> float:
		"""Calculate overall confidence in the fusion result"""
		if not results:
			return 0.0
		
		# Check how many systems succeeded
		successful_systems = sum(1 for r in results.values() if not r.errors and r.elements)
		total_systems = len(results)
		
		# Base confidence on system agreement
		base_confidence = successful_systems / total_systems
		
		# Adjust based on element overlap
		if successful_systems > 1:
			# This is a simplified metric - in practice would be more sophisticated
			overlap_boost = min(0.2, successful_systems * 0.05)
			base_confidence += overlap_boost
		
		return min(1.0, base_confidence)