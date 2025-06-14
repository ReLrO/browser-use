"""Intent analysis and management service"""

import asyncio
from typing import Any, Optional
from datetime import datetime
import json
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from .views import (
	Intent, IntentType, IntentPriority, IntentParameter,
	IntentConstraint, SuccessCriteria, SubIntent,
	IntentAnalysisResult
)
from browser_use.utils import time_execution_async


class IntentAnalyzer:
	"""Converts user tasks into semantic intents that can be executed"""
	
	def __init__(self, llm: BaseChatModel):
		self.llm = llm
		self._intent_patterns = self._load_intent_patterns()
	
	def _load_intent_patterns(self) -> dict[str, dict]:
		"""Load common intent patterns for quick matching"""
		return {
			"login": {
				"keywords": ["login", "sign in", "authenticate", "log in"],
				"type": IntentType.AUTHENTICATION,
				"typical_parameters": ["username", "password", "provider"]
			},
			"search": {
				"keywords": ["search", "find", "look for", "query"],
				"type": IntentType.SEARCH,
				"typical_parameters": ["query", "filters", "sort_by"]
			},
			"fill_form": {
				"keywords": ["fill", "complete", "submit form", "enter information"],
				"type": IntentType.FORM_FILL,
				"typical_parameters": ["form_data", "submit_after"]
			},
			"navigate": {
				"keywords": ["go to", "navigate", "open", "visit"],
				"type": IntentType.NAVIGATION,
				"typical_parameters": ["url", "wait_for"]
			},
			"extract": {
				"keywords": ["get", "extract", "scrape", "collect", "download"],
				"type": IntentType.EXTRACTION,
				"typical_parameters": ["data_type", "format", "save_to"]
			}
		}
	
	@time_execution_async("intent_analysis")
	async def analyze(self, task: str, context: Optional[dict[str, Any]] = None) -> IntentAnalysisResult:
		"""Analyze a user task and convert it into executable intents"""
		
		# Quick pattern matching for common intents
		quick_match = self._quick_match_intent(task)
		
		# Use LLM for detailed analysis
		system_prompt = self._build_analysis_prompt()
		user_prompt = self._build_user_prompt(task, context, quick_match)
		
		messages = [
			SystemMessage(content=system_prompt),
			HumanMessage(content=user_prompt)
		]
		
		try:
			response = await self.llm.ainvoke(messages)
			analysis = self._parse_llm_response(response.content)
			
			# Enhance with quick match if available
			if quick_match:
				analysis.intent.type = quick_match["type"]
			
			return analysis
			
		except Exception as e:
			# Fallback to basic intent
			return self._create_fallback_intent(task, str(e))
	
	def _quick_match_intent(self, task: str) -> Optional[dict]:
		"""Quick pattern matching for common intents"""
		task_lower = task.lower()
		
		for pattern_name, pattern_data in self._intent_patterns.items():
			if any(keyword in task_lower for keyword in pattern_data["keywords"]):
				return pattern_data
		
		return None
	
	def _build_analysis_prompt(self) -> str:
		"""Build the system prompt for intent analysis"""
		return """You are an expert at understanding user intents for browser automation tasks.

Analyze the user's task and decompose it into a structured intent with:
1. Primary goal - what the user ultimately wants to achieve
2. Sub-intents - smaller tasks that need to be completed
3. Parameters - specific values needed for execution
4. Constraints - limitations or requirements
5. Success criteria - how to verify the task was completed

Respond with a JSON object following this structure:
{
  "primary_goal": "Main objective",
  "intent_type": "navigation|form_fill|authentication|search|interaction|extraction|verification|composite|custom",
  "priority": "critical|high|medium|low",
  "sub_intents": [
    {
      "description": "What this step does",
      "type": "intent_type",
      "parameters": [{"name": "param_name", "value": "param_value", "type": "string", "required": true}],
      "dependencies": ["previous_sub_intent_id"]
    }
  ],
  "parameters": [
    {"name": "param_name", "value": "param_value", "type": "string", "required": true, "sensitive": false}
  ],
  "constraints": [
    {"type": "constraint_type", "value": "constraint_value", "description": "explanation"}
  ],
  "success_criteria": [
    {"type": "criteria_type", "expected": "expected_value", "description": "what to check"}
  ],
  "confidence": 0.95,
  "requires_clarification": false,
  "clarification_questions": []
}

Be specific and actionable in your analysis."""
	
	def _build_user_prompt(self, task: str, context: Optional[dict], quick_match: Optional[dict]) -> str:
		"""Build the user prompt with task and context"""
		prompt = f"Task: {task}\n\n"
		
		if context:
			prompt += f"Context:\n{json.dumps(context, indent=2)}\n\n"
		
		if quick_match:
			prompt += f"Initial classification: {quick_match['type']}\n"
			prompt += f"Typical parameters: {quick_match['typical_parameters']}\n\n"
		
		prompt += "Please analyze this task and provide a structured intent."
		
		return prompt
	
	def _parse_llm_response(self, response: str) -> IntentAnalysisResult:
		"""Parse the LLM response into an IntentAnalysisResult"""
		try:
			# Extract JSON from response
			import re
			json_match = re.search(r'\{[\s\S]*\}', response)
			if json_match:
				data = json.loads(json_match.group())
			else:
				data = json.loads(response)
			
			# Create sub-intents
			sub_intents = []
			for idx, sub_data in enumerate(data.get("sub_intents", [])):
				sub_intent = SubIntent(
					description=sub_data["description"],
					type=IntentType(sub_data["type"]),
					parameters=[IntentParameter(**p) for p in sub_data.get("parameters", [])],
					dependencies=sub_data.get("dependencies", []),
					optional=sub_data.get("optional", False)
				)
				sub_intents.append(sub_intent)
			
			# Create main intent
			intent = Intent(
				task_description=data.get("task_description", ""),
				type=IntentType(data["intent_type"]),
				priority=IntentPriority(data.get("priority", "medium")),
				primary_goal=data["primary_goal"],
				sub_intents=sub_intents,
				parameters=[IntentParameter(**p) for p in data.get("parameters", [])],
				constraints=[IntentConstraint(**c) for c in data.get("constraints", [])],
				success_criteria=[SuccessCriteria(**s) for s in data.get("success_criteria", [])]
			)
			
			return IntentAnalysisResult(
				intent=intent,
				confidence=data.get("confidence", 0.8),
				requires_clarification=data.get("requires_clarification", False),
				clarification_questions=data.get("clarification_questions", [])
			)
			
		except Exception as e:
			raise ValueError(f"Failed to parse LLM response: {e}")
	
	def _create_fallback_intent(self, task: str, error: str) -> IntentAnalysisResult:
		"""Create a basic fallback intent when analysis fails"""
		intent = Intent(
			task_description=task,
			type=IntentType.CUSTOM,
			priority=IntentPriority.MEDIUM,
			primary_goal=task,
			sub_intents=[],
			context={"error": error, "fallback": True}
		)
		
		return IntentAnalysisResult(
			intent=intent,
			confidence=0.3,
			requires_clarification=True,
			clarification_questions=["Could you please provide more details about what you want to accomplish?"]
		)


class IntentManager:
	"""Manages intent lifecycle and execution tracking"""
	
	def __init__(self):
		self._active_intents: dict[str, Intent] = {}
		self._intent_history: list[Intent] = []
		self._execution_lock = asyncio.Lock()
	
	async def register_intent(self, intent: Intent) -> None:
		"""Register a new intent for execution"""
		async with self._execution_lock:
			self._active_intents[intent.id] = intent
	
	async def update_intent_status(self, intent_id: str, status: str, error: Optional[str] = None) -> None:
		"""Update the status of an intent"""
		async with self._execution_lock:
			if intent_id in self._active_intents:
				intent = self._active_intents[intent_id]
				intent.status = status
				intent.attempts += 1
				
				if error:
					intent.last_error = error
				
				if status in ["completed", "failed", "cancelled"]:
					self._intent_history.append(intent)
					del self._active_intents[intent_id]
	
	async def get_intent(self, intent_id: str) -> Optional[Intent]:
		"""Get an intent by ID"""
		async with self._execution_lock:
			return self._active_intents.get(intent_id)
	
	async def get_active_intents(self) -> list[Intent]:
		"""Get all active intents"""
		async with self._execution_lock:
			return list(self._active_intents.values())
	
	async def get_intent_history(self, limit: int = 10) -> list[Intent]:
		"""Get recent intent history"""
		async with self._execution_lock:
			return self._intent_history[-limit:]
	
	def can_execute_parallel(self, intent1: Intent, intent2: Intent) -> bool:
		"""Check if two intents can be executed in parallel"""
		# Check if intents have conflicting parameters or constraints
		param_names1 = {p.name for p in intent1.parameters}
		param_names2 = {p.name for p in intent2.parameters}
		
		# If they share sensitive parameters, don't parallelize
		sensitive1 = {p.name for p in intent1.parameters if p.sensitive}
		sensitive2 = {p.name for p in intent2.parameters if p.sensitive}
		
		if sensitive1 & sensitive2:
			return False
		
		# If they're both navigation intents, don't parallelize
		if intent1.type == IntentType.NAVIGATION and intent2.type == IntentType.NAVIGATION:
			return False
		
		# Check for explicit dependencies
		for sub1 in intent1.sub_intents:
			for sub2 in intent2.sub_intents:
				if sub1.id in sub2.dependencies or sub2.id in sub1.dependencies:
					return False
		
		return True