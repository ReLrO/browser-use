"""Token usage optimization for LLM interactions"""

import re
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import tiktoken
import zlib
import base64

from browser_use.core.intent.views import Intent, SubIntent
from browser_use.perception.base import PerceptionElement, BoundingBox


class CompressionStrategy(str, Enum):
	"""Token compression strategies"""
	NONE = "none"
	SUMMARIZE = "summarize"
	TRUNCATE = "truncate"
	SEMANTIC = "semantic"
	STRUCTURAL = "structural"
	HYBRID = "hybrid"


@dataclass
class TokenStats:
	"""Token usage statistics"""
	original_tokens: int
	compressed_tokens: int
	compression_ratio: float
	strategy_used: CompressionStrategy
	elements_removed: int = 0
	content_summarized: bool = False


class TokenOptimizer:
	"""Optimizes token usage for LLM interactions"""
	
	def __init__(self, model_name: str = "gpt-4"):
		self.model_name = model_name
		self.encoding = self._get_encoding(model_name)
		
		# Token limits by model
		self.model_limits = {
			"gpt-4": 8192,
			"gpt-4-32k": 32768,
			"gpt-3.5-turbo": 4096,
			"claude-3": 100000,
			"claude-2": 100000
		}
		
		# Target to stay under limit
		self.target_ratio = 0.7  # Use 70% of limit
		
		# Compression strategies
		self.strategies = {
			CompressionStrategy.SUMMARIZE: self._compress_by_summarization,
			CompressionStrategy.TRUNCATE: self._compress_by_truncation,
			CompressionStrategy.SEMANTIC: self._compress_by_semantic_filtering,
			CompressionStrategy.STRUCTURAL: self._compress_by_structural_reduction,
			CompressionStrategy.HYBRID: self._compress_hybrid
		}
	
	def _get_encoding(self, model_name: str):
		"""Get tiktoken encoding for model"""
		try:
			return tiktoken.encoding_for_model(model_name)
		except:
			# Fallback to cl100k_base
			return tiktoken.get_encoding("cl100k_base")
	
	def count_tokens(self, text: str) -> int:
		"""Count tokens in text"""
		return len(self.encoding.encode(text))
	
	def get_token_limit(self) -> int:
		"""Get token limit for current model"""
		for key in self.model_limits:
			if key in self.model_name.lower():
				return self.model_limits[key]
		return 4096  # Default limit
	
	def optimize_prompt(
		self,
		prompt: str,
		max_tokens: Optional[int] = None,
		strategy: CompressionStrategy = CompressionStrategy.HYBRID
	) -> Tuple[str, TokenStats]:
		"""Optimize a prompt to fit within token limits"""
		original_tokens = self.count_tokens(prompt)
		
		# Determine target token count
		if max_tokens is None:
			limit = self.get_token_limit()
			max_tokens = int(limit * self.target_ratio)
		
		# If already under limit, return as-is
		if original_tokens <= max_tokens:
			return prompt, TokenStats(
				original_tokens=original_tokens,
				compressed_tokens=original_tokens,
				compression_ratio=1.0,
				strategy_used=CompressionStrategy.NONE
			)
		
		# Apply compression strategy
		compression_func = self.strategies.get(strategy, self._compress_hybrid)
		compressed_prompt, elements_removed = compression_func(prompt, max_tokens)
		
		compressed_tokens = self.count_tokens(compressed_prompt)
		
		return compressed_prompt, TokenStats(
			original_tokens=original_tokens,
			compressed_tokens=compressed_tokens,
			compression_ratio=compressed_tokens / original_tokens,
			strategy_used=strategy,
			elements_removed=elements_removed
		)
	
	def optimize_perception_data(
		self,
		elements: List[PerceptionElement],
		max_tokens: int = 2000
	) -> Tuple[List[PerceptionElement], TokenStats]:
		"""Optimize perception element data for token efficiency"""
		# Calculate current token usage
		original_text = self._elements_to_text(elements)
		original_tokens = self.count_tokens(original_text)
		
		if original_tokens <= max_tokens:
			return elements, TokenStats(
				original_tokens=original_tokens,
				compressed_tokens=original_tokens,
				compression_ratio=1.0,
				strategy_used=CompressionStrategy.NONE
			)
		
		# Progressive filtering strategies
		filtered_elements = elements
		
		# 1. Remove non-interactive elements
		if self.count_tokens(self._elements_to_text(filtered_elements)) > max_tokens:
			filtered_elements = [e for e in filtered_elements if e.is_interactive]
		
		# 2. Remove invisible elements
		if self.count_tokens(self._elements_to_text(filtered_elements)) > max_tokens:
			filtered_elements = [e for e in filtered_elements if e.is_visible]
		
		# 3. Deduplicate similar elements
		if self.count_tokens(self._elements_to_text(filtered_elements)) > max_tokens:
			filtered_elements = self._deduplicate_elements(filtered_elements)
		
		# 4. Limit attributes
		if self.count_tokens(self._elements_to_text(filtered_elements)) > max_tokens:
			filtered_elements = self._minimize_element_attributes(filtered_elements)
		
		# 5. Spatial clustering
		if self.count_tokens(self._elements_to_text(filtered_elements)) > max_tokens:
			filtered_elements = self._cluster_nearby_elements(filtered_elements)
		
		# 6. Hard limit by importance
		if self.count_tokens(self._elements_to_text(filtered_elements)) > max_tokens:
			filtered_elements = self._select_most_important(filtered_elements, max_tokens)
		
		compressed_text = self._elements_to_text(filtered_elements)
		compressed_tokens = self.count_tokens(compressed_text)
		
		return filtered_elements, TokenStats(
			original_tokens=original_tokens,
			compressed_tokens=compressed_tokens,
			compression_ratio=compressed_tokens / original_tokens,
			strategy_used=CompressionStrategy.STRUCTURAL,
			elements_removed=len(elements) - len(filtered_elements)
		)
	
	def optimize_intent_context(
		self,
		intent: Intent,
		max_tokens: int = 1000
	) -> Tuple[Dict[str, Any], TokenStats]:
		"""Optimize intent context for token efficiency"""
		# Build minimal context
		context = {
			"goal": intent.primary_goal,
			"type": intent.type,
			"key_params": {p.name: p.value for p in intent.parameters if p.required}
		}
		
		# Add sub-intent summary if space allows
		if intent.sub_intents:
			sub_intent_summary = [
				{"desc": si.description[:50], "type": si.type}
				for si in intent.sub_intents[:5]  # Limit to 5
			]
			
			test_context = {**context, "sub_intents": sub_intent_summary}
			if self.count_tokens(json.dumps(test_context)) <= max_tokens:
				context = test_context
		
		# Add success criteria if space allows
		if intent.success_criteria:
			criteria_summary = [
				{"type": sc.type, "expected": str(sc.expected)[:30]}
				for sc in intent.success_criteria[:3]
			]
			
			test_context = {**context, "success_criteria": criteria_summary}
			if self.count_tokens(json.dumps(test_context)) <= max_tokens:
				context = test_context
		
		context_str = json.dumps(context)
		tokens = self.count_tokens(context_str)
		
		return context, TokenStats(
			original_tokens=self.count_tokens(json.dumps(intent.model_dump())),
			compressed_tokens=tokens,
			compression_ratio=tokens / self.count_tokens(json.dumps(intent.model_dump())),
			strategy_used=CompressionStrategy.SEMANTIC
		)
	
	# Compression strategies
	
	def _compress_by_summarization(self, text: str, max_tokens: int) -> Tuple[str, int]:
		"""Compress by summarizing sections"""
		# Split into sections
		sections = text.split('\n\n')
		
		compressed_sections = []
		elements_removed = 0
		
		for section in sections:
			if self.count_tokens(section) > 100:
				# Summarize long sections
				lines = section.split('\n')
				if len(lines) > 5:
					# Keep first 2 and last 1 lines
					summary = '\n'.join(lines[:2] + ['...'] + lines[-1:])
					compressed_sections.append(summary)
					elements_removed += len(lines) - 3
				else:
					compressed_sections.append(section)
			else:
				compressed_sections.append(section)
		
		compressed = '\n\n'.join(compressed_sections)
		
		# Further truncate if needed
		if self.count_tokens(compressed) > max_tokens:
			compressed, additional_removed = self._compress_by_truncation(compressed, max_tokens)
			elements_removed += additional_removed
		
		return compressed, elements_removed
	
	def _compress_by_truncation(self, text: str, max_tokens: int) -> Tuple[str, int]:
		"""Simple truncation strategy"""
		tokens = self.encoding.encode(text)
		
		if len(tokens) <= max_tokens:
			return text, 0
		
		# Truncate and decode
		truncated_tokens = tokens[:max_tokens]
		truncated_text = self.encoding.decode(truncated_tokens)
		
		# Count removed elements (approximate)
		removed_ratio = 1 - (max_tokens / len(tokens))
		elements_removed = int(text.count('\n') * removed_ratio)
		
		return truncated_text, elements_removed
	
	def _compress_by_semantic_filtering(self, text: str, max_tokens: int) -> Tuple[str, int]:
		"""Filter by semantic importance"""
		lines = text.split('\n')
		
		# Score lines by importance indicators
		scored_lines = []
		for line in lines:
			score = 0
			
			# High importance keywords
			if any(kw in line.lower() for kw in ['error', 'fail', 'success', 'submit', 'login', 'button']):
				score += 3
			
			# Medium importance
			if any(kw in line.lower() for kw in ['input', 'form', 'link', 'click']):
				score += 2
			
			# Has meaningful content
			if len(line.strip()) > 20:
				score += 1
			
			scored_lines.append((score, line))
		
		# Sort by importance
		scored_lines.sort(key=lambda x: x[0], reverse=True)
		
		# Take most important lines up to token limit
		selected_lines = []
		current_tokens = 0
		
		for score, line in scored_lines:
			line_tokens = self.count_tokens(line)
			if current_tokens + line_tokens <= max_tokens:
				selected_lines.append(line)
				current_tokens += line_tokens
			else:
				break
		
		compressed = '\n'.join(selected_lines)
		elements_removed = len(lines) - len(selected_lines)
		
		return compressed, elements_removed
	
	def _compress_by_structural_reduction(self, text: str, max_tokens: int) -> Tuple[str, int]:
		"""Reduce structural verbosity"""
		compressed = text
		
		# Remove redundant whitespace
		compressed = re.sub(r'\n\s*\n', '\n', compressed)
		compressed = re.sub(r'  +', ' ', compressed)
		
		# Shorten common patterns
		replacements = [
			(r'<.*?id="([^"]+)".*?>', r'#\1'),  # Simplify element descriptions
			(r'class="[^"]+"', ''),  # Remove class attributes
			(r'style="[^"]+"', ''),  # Remove style attributes
			(r'\s+', ' '),  # Normalize whitespace
		]
		
		for pattern, replacement in replacements:
			compressed = re.sub(pattern, replacement, compressed)
		
		# Count approximate removals
		elements_removed = text.count('\n') - compressed.count('\n')
		
		return compressed, elements_removed
	
	def _compress_hybrid(self, text: str, max_tokens: int) -> Tuple[str, int]:
		"""Hybrid compression using multiple strategies"""
		current_text = text
		total_removed = 0
		
		# Try strategies in order of preference
		strategies = [
			self._compress_by_structural_reduction,
			self._compress_by_semantic_filtering,
			self._compress_by_summarization,
			self._compress_by_truncation
		]
		
		for strategy in strategies:
			if self.count_tokens(current_text) <= max_tokens:
				break
			
			current_text, removed = strategy(current_text, max_tokens)
			total_removed += removed
		
		return current_text, total_removed
	
	# Helper methods for element optimization
	
	def _elements_to_text(self, elements: List[PerceptionElement]) -> str:
		"""Convert elements to text representation"""
		lines = []
		for i, elem in enumerate(elements):
			parts = [f"[{i}]", elem.type]
			
			if elem.text:
				parts.append(f'"{elem.text[:50]}"')
			
			if elem.selector:
				parts.append(elem.selector)
			
			lines.append(" ".join(parts))
		
		return "\n".join(lines)
	
	def _deduplicate_elements(self, elements: List[PerceptionElement]) -> List[PerceptionElement]:
		"""Remove duplicate elements"""
		seen = set()
		unique = []
		
		for elem in elements:
			# Create signature
			sig = (elem.type, elem.text[:20] if elem.text else "", elem.selector)
			
			if sig not in seen:
				seen.add(sig)
				unique.append(elem)
		
		return unique
	
	def _minimize_element_attributes(self, elements: List[PerceptionElement]) -> List[PerceptionElement]:
		"""Keep only essential attributes"""
		minimized = []
		
		for elem in elements:
			# Create minimal copy
			minimal = PerceptionElement(
				type=elem.type,
				text=elem.text[:50] if elem.text else None,
				selector=elem.selector,
				is_interactive=elem.is_interactive,
				is_visible=elem.is_visible
			)
			
			# Keep only essential attributes
			if elem.attributes:
				minimal.attributes = {
					k: v for k, v in elem.attributes.items()
					if k in ["href", "name", "value", "role"]
				}
			
			minimized.append(minimal)
		
		return minimized
	
	def _cluster_nearby_elements(
		self,
		elements: List[PerceptionElement],
		distance_threshold: float = 50
	) -> List[PerceptionElement]:
		"""Cluster nearby elements"""
		if not elements:
			return []
		
		# Group by proximity
		clusters = []
		used = set()
		
		for i, elem in enumerate(elements):
			if i in used or not elem.bounding_box:
				continue
			
			cluster = [elem]
			used.add(i)
			
			# Find nearby elements
			for j, other in enumerate(elements[i+1:], i+1):
				if j in used or not other.bounding_box:
					continue
				
				distance = self._calculate_distance(elem.bounding_box, other.bounding_box)
				if distance <= distance_threshold:
					cluster.append(other)
					used.add(j)
			
			# Keep most important from cluster
			if len(cluster) > 1:
				# Sort by importance
				cluster.sort(key=lambda e: (
					e.is_interactive,
					len(e.text or ""),
					e.type == "button"
				), reverse=True)
				
				clusters.append(cluster[0])  # Keep most important
			else:
				clusters.append(elem)
		
		# Add non-spatial elements
		for i, elem in enumerate(elements):
			if i not in used:
				clusters.append(elem)
		
		return clusters
	
	def _calculate_distance(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
		"""Calculate distance between bounding boxes"""
		center1_x = bbox1.x + bbox1.width / 2
		center1_y = bbox1.y + bbox1.height / 2
		center2_x = bbox2.x + bbox2.width / 2
		center2_y = bbox2.y + bbox2.height / 2
		
		return ((center2_x - center1_x) ** 2 + (center2_y - center1_y) ** 2) ** 0.5
	
	def _select_most_important(
		self,
		elements: List[PerceptionElement],
		max_tokens: int
	) -> List[PerceptionElement]:
		"""Select most important elements within token budget"""
		# Score elements
		scored = []
		for elem in elements:
			score = 0
			
			# Interactive elements are important
			if elem.is_interactive:
				score += 5
			
			# Buttons and inputs are very important
			if elem.type in ["button", "input", "select"]:
				score += 3
			
			# Links are moderately important
			if elem.type == "link":
				score += 2
			
			# Has text content
			if elem.text:
				score += 1
			
			scored.append((score, elem))
		
		# Sort by importance
		scored.sort(key=lambda x: x[0], reverse=True)
		
		# Select up to token limit
		selected = []
		current_tokens = 0
		
		for score, elem in scored:
			elem_text = self._elements_to_text([elem])
			elem_tokens = self.count_tokens(elem_text)
			
			if current_tokens + elem_tokens <= max_tokens:
				selected.append(elem)
				current_tokens += elem_tokens
		
		return selected


class MessageCompressor:
	"""Compress conversation messages for token efficiency"""
	
	def __init__(self, token_optimizer: TokenOptimizer):
		self.optimizer = token_optimizer
	
	def compress_messages(
		self,
		messages: List[Dict[str, Any]],
		max_tokens: int,
		keep_recent: int = 2
	) -> Tuple[List[Dict[str, Any]], TokenStats]:
		"""Compress message history to fit token limit"""
		# Always keep system message and recent messages
		if len(messages) <= keep_recent + 1:
			return messages, TokenStats(
				original_tokens=self._count_message_tokens(messages),
				compressed_tokens=self._count_message_tokens(messages),
				compression_ratio=1.0,
				strategy_used=CompressionStrategy.NONE
			)
		
		system_messages = [m for m in messages if m.get("role") == "system"]
		recent_messages = messages[-(keep_recent):]
		older_messages = messages[len(system_messages):-keep_recent]
		
		# Compress older messages
		compressed_older = []
		for msg in older_messages:
			if msg.get("role") == "assistant":
				# Summarize assistant responses
				compressed_content = self._summarize_message(msg["content"])
				compressed_older.append({
					"role": "assistant",
					"content": compressed_content
				})
			else:
				# Keep user messages but truncate if very long
				content = msg["content"]
				if self.optimizer.count_tokens(content) > 500:
					content = content[:500] + "..."
				compressed_older.append({
					"role": msg["role"],
					"content": content
				})
		
		# Combine messages
		compressed_messages = system_messages + compressed_older + recent_messages
		
		# Further compress if still over limit
		while self._count_message_tokens(compressed_messages) > max_tokens and len(compressed_older) > 0:
			compressed_older.pop(0)
			compressed_messages = system_messages + compressed_older + recent_messages
		
		original_tokens = self._count_message_tokens(messages)
		compressed_tokens = self._count_message_tokens(compressed_messages)
		
		return compressed_messages, TokenStats(
			original_tokens=original_tokens,
			compressed_tokens=compressed_tokens,
			compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
			strategy_used=CompressionStrategy.SUMMARIZE,
			content_summarized=True
		)
	
	def _count_message_tokens(self, messages: List[Dict[str, Any]]) -> int:
		"""Count total tokens in messages"""
		total = 0
		for msg in messages:
			total += self.optimizer.count_tokens(msg.get("content", ""))
		return total
	
	def _summarize_message(self, content: str) -> str:
		"""Summarize a message to key points"""
		lines = content.split('\n')
		
		# Extract key information
		key_lines = []
		for line in lines:
			if any(kw in line.lower() for kw in [
				'success', 'fail', 'error', 'complet',
				'found', 'click', 'type', 'navigat'
			]):
				key_lines.append(line.strip())
		
		if key_lines:
			return "Summary: " + "; ".join(key_lines[:3])
		else:
			return "Summary: " + content[:100] + "..."