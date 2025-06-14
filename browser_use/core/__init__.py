"""Core components for next-generation browser automation"""

from .intent.service import IntentAnalyzer, IntentManager
from .intent.views import (
	Intent, IntentType, IntentPriority,
	IntentParameter, IntentConstraint, SuccessCriteria,
	SubIntent, IntentAnalysisResult, IntentExecutionResult,
	ElementIntent
)

from .state.service import StreamingStateManager, EventStream
from .state.views import (
	BrowserEvent, EventType, EventPriority,
	EventFilter, StreamState, EventStreamConfig,
	DOMChange, NetworkEvent, ConsoleEvent
)

from .resolver.service import MultiStrategyElementResolver, ResolvedElement, ElementNotFoundError

from .orchestrator.service import ParallelActionOrchestrator, Action, ActionType, ActionResult, ExecutionPlan
from .orchestrator.intent_mapper import IntentToActionMapper, IntentPattern, PatternType
from .orchestrator.verification import IntentVerificationService, VerificationResult, VerificationType

__all__ = [
	# Intent system
	'IntentAnalyzer', 'IntentManager',
	'Intent', 'IntentType', 'IntentPriority',
	'IntentParameter', 'IntentConstraint', 'SuccessCriteria',
	'SubIntent', 'IntentAnalysisResult', 'IntentExecutionResult',
	'ElementIntent',
	
	# State management
	'StreamingStateManager', 'EventStream',
	'BrowserEvent', 'EventType', 'EventPriority',
	'EventFilter', 'StreamState', 'EventStreamConfig',
	'DOMChange', 'NetworkEvent', 'ConsoleEvent',
	
	# Element resolution
	'MultiStrategyElementResolver', 'ResolvedElement', 'ElementNotFoundError',
	
	# Action orchestration
	'ParallelActionOrchestrator', 'Action', 'ActionType', 'ActionResult', 'ExecutionPlan',
	'IntentToActionMapper', 'IntentPattern', 'PatternType',
	'IntentVerificationService', 'VerificationResult', 'VerificationType'
]