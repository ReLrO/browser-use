"""Streaming state management service"""

import asyncio
from typing import Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json
from playwright.async_api import Page, ConsoleMessage, Request, Response

from .views import (
	BrowserEvent, EventType, EventPriority, EventFilter,
	DOMChange, NetworkEvent, ConsoleEvent,
	StreamState, EventStreamConfig
)
from browser_use.utils import time_execution_async


class EventStream:
	"""Base class for event streams"""
	
	def __init__(self, config: EventStreamConfig):
		self.config = config
		self._events: deque[BrowserEvent] = deque(maxlen=config.max_event_queue_size)
		self._subscribers: list[asyncio.Queue] = []
		self._last_event_time = datetime.now()
		self._event_counts = defaultdict(int)
	
	async def add_event(self, event: BrowserEvent) -> None:
		"""Add an event to the stream"""
		# Rate limiting
		self._event_counts[event.type] += 1
		current_time = datetime.now()
		
		if (current_time - self._last_event_time).total_seconds() < 1:
			if self._event_counts[event.type] > self.config.max_events_per_second:
				return  # Drop event due to rate limit
		else:
			self._event_counts.clear()
			self._last_event_time = current_time
		
		# Score relevance if enabled
		if self.config.auto_score_relevance:
			event.relevance_score = self._calculate_relevance(event)
		
		# Add to queue
		self._events.append(event)
		
		# Notify subscribers
		for subscriber in self._subscribers:
			if not subscriber.full():
				await subscriber.put(event)
	
	async def get_events(self, filter: EventFilter) -> list[BrowserEvent]:
		"""Get events matching the filter"""
		events = list(self._events)
		
		# Apply filters
		if filter.event_types:
			events = [e for e in events if e.type in filter.event_types]
		
		if filter.priorities:
			events = [e for e in events if e.priority in filter.priorities]
		
		if filter.since_timestamp:
			events = [e for e in events if e.timestamp >= filter.since_timestamp]
		
		if filter.until_timestamp:
			events = [e for e in events if e.timestamp <= filter.until_timestamp]
		
		if filter.tab_ids:
			events = [e for e in events if e.tab_id in filter.tab_ids]
		
		if filter.tags:
			events = [e for e in events if any(tag in e.tags for tag in filter.tags)]
		
		if filter.min_relevance:
			events = [e for e in events if e.relevance_score >= filter.min_relevance]
		
		if filter.url_pattern and filter.url_pattern != "*":
			import re
			pattern = re.compile(filter.url_pattern.replace("*", ".*"))
			events = [e for e in events if e.page_url and pattern.match(e.page_url)]
		
		# Apply limit
		if filter.limit:
			events = events[-filter.limit:]
		
		return events
	
	async def subscribe(self) -> AsyncGenerator[BrowserEvent, None]:
		"""Subscribe to real-time events"""
		queue = asyncio.Queue(maxsize=1000)
		self._subscribers.append(queue)
		
		try:
			while True:
				event = await queue.get()
				yield event
		finally:
			self._subscribers.remove(queue)
	
	def _calculate_relevance(self, event: BrowserEvent) -> float:
		"""Calculate relevance score for an event"""
		base_score = 0.5
		
		# Adjust based on event type
		if event.type == EventType.ERROR:
			base_score = 0.9
		elif event.type == EventType.USER_INTERACTION:
			base_score = 0.8
		elif event.type == EventType.DOM_MUTATION:
			base_score = 0.6
		elif event.type == EventType.NETWORK_REQUEST:
			base_score = 0.4
		
		# Adjust based on priority
		if event.priority == EventPriority.CRITICAL:
			base_score = min(1.0, base_score + 0.3)
		elif event.priority == EventPriority.HIGH:
			base_score = min(1.0, base_score + 0.1)
		
		# Apply time decay
		age_minutes = (datetime.now() - event.timestamp).total_seconds() / 60
		decay_factor = self.config.relevance_decay_rate ** age_minutes
		
		return base_score * decay_factor
	
	async def cleanup_old_events(self) -> None:
		"""Remove events older than TTL"""
		cutoff_time = datetime.now() - timedelta(seconds=self.config.event_ttl_seconds)
		
		while self._events and self._events[0].timestamp < cutoff_time:
			self._events.popleft()


class DOMEventStream(EventStream):
	"""Stream for DOM mutation events"""
	
	def __init__(self, config: EventStreamConfig):
		super().__init__(config)
		self._mutation_buffer: list[dict] = []
		self._last_flush = datetime.now()
	
	async def setup_page_listeners(self, page: Page, tab_id: str) -> None:
		"""Set up DOM mutation observer on the page"""
		if not self.config.collect_dom_mutations:
			return
		
		# Inject mutation observer script
		await page.evaluate("""
			(() => {
				if (window.__domEventStream) return;
				
				window.__domEventStream = {
					mutations: [],
					observer: new MutationObserver((mutations) => {
						for (const mutation of mutations) {
							const record = {
								type: mutation.type,
								targetTag: mutation.target.tagName,
								targetId: mutation.target.id,
								targetClass: mutation.target.className,
								attributeName: mutation.attributeName,
								oldValue: mutation.oldValue,
								addedNodes: Array.from(mutation.addedNodes).map(n => ({
									tag: n.tagName,
									id: n.id,
									class: n.className
								})),
								removedNodes: Array.from(mutation.removedNodes).map(n => ({
									tag: n.tagName,
									id: n.id,
									class: n.className
								}))
							};
							window.__domEventStream.mutations.push(record);
						}
					})
				};
				
				window.__domEventStream.observer.observe(document.body, {
					childList: true,
					attributes: true,
					characterData: true,
					subtree: true,
					attributeOldValue: true,
					characterDataOldValue: true
				});
			})();
		""")
		
		# Start periodic collection
		asyncio.create_task(self._collect_mutations_periodically(page, tab_id))
	
	async def _collect_mutations_periodically(self, page: Page, tab_id: str) -> None:
		"""Periodically collect DOM mutations from the page"""
		while True:
			try:
				await asyncio.sleep(self.config.dom_mutation_throttle_ms / 1000)
				
				# Get mutations from page
				mutations = await page.evaluate("window.__domEventStream.mutations.splice(0)")
				
				if mutations:
					# Process mutations
					for mutation in mutations:
						dom_change = DOMChange(
							type=mutation["type"],
							target_selector=self._build_selector(mutation),
							attribute_name=mutation.get("attributeName"),
							old_value=mutation.get("oldValue"),
							added_nodes=mutation.get("addedNodes", []),
							removed_nodes=mutation.get("removedNodes", [])
						)
						
						event = BrowserEvent(
							type=EventType.DOM_MUTATION,
							dom_change=dom_change,
							page_url=page.url,
							tab_id=tab_id,
							priority=self._get_mutation_priority(mutation)
						)
						
						await self.add_event(event)
				
			except Exception as e:
				# Page might be closed or navigated
				break
	
	def _build_selector(self, mutation: dict) -> str:
		"""Build a CSS selector for the mutated element"""
		parts = []
		
		if mutation.get("targetTag"):
			parts.append(mutation["targetTag"].lower())
		
		if mutation.get("targetId"):
			parts.append(f"#{mutation['targetId']}")
		
		if mutation.get("targetClass"):
			classes = mutation["targetClass"].strip().split()
			for cls in classes[:2]:  # Limit to 2 classes
				if cls:
					parts.append(f".{cls}")
		
		return "".join(parts) or "*"
	
	def _get_mutation_priority(self, mutation: dict) -> EventPriority:
		"""Determine priority of a DOM mutation"""
		# High priority for form elements
		if mutation.get("targetTag") in ["INPUT", "BUTTON", "FORM", "SELECT", "TEXTAREA"]:
			return EventPriority.HIGH
		
		# Medium for interactive elements
		if mutation.get("targetTag") in ["A", "DIV", "SPAN"] and (
			mutation.get("addedNodes") or mutation.get("removedNodes")
		):
			return EventPriority.MEDIUM
		
		return EventPriority.LOW


class NetworkEventStream(EventStream):
	"""Stream for network events"""
	
	async def setup_page_listeners(self, page: Page, tab_id: str) -> None:
		"""Set up network event listeners"""
		if not self.config.collect_network:
			return
		
		# Request listener
		async def on_request(request: Request):
			# Check if should ignore
			url = request.url
			if any(pattern in url for pattern in self.config.ignored_network_patterns):
				return
			
			network_event = NetworkEvent(
				url=url,
				method=request.method,
				resource_type=request.resource_type,
				headers=dict(request.headers),
				is_navigation=request.is_navigation_request()
			)
			
			event = BrowserEvent(
				type=EventType.NETWORK_REQUEST,
				network_event=network_event,
				page_url=page.url,
				tab_id=tab_id,
				priority=EventPriority.HIGH if request.is_navigation_request() else EventPriority.LOW
			)
			
			await self.add_event(event)
		
		# Response listener
		async def on_response(response: Response):
			# Check if should ignore
			url = response.url
			if any(pattern in url for pattern in self.config.ignored_network_patterns):
				return
			
			network_event = NetworkEvent(
				url=url,
				method=response.request.method,
				status=response.status,
				resource_type=response.request.resource_type,
				headers=dict(response.headers)
			)
			
			event = BrowserEvent(
				type=EventType.NETWORK_RESPONSE,
				network_event=network_event,
				page_url=page.url,
				tab_id=tab_id,
				priority=EventPriority.HIGH if response.status >= 400 else EventPriority.LOW
			)
			
			await self.add_event(event)
		
		page.on("request", on_request)
		page.on("response", on_response)


class ConsoleEventStream(EventStream):
	"""Stream for console events"""
	
	async def setup_page_listeners(self, page: Page, tab_id: str) -> None:
		"""Set up console event listeners"""
		if not self.config.collect_console:
			return
		
		async def on_console(msg: ConsoleMessage):
			# Check if should collect this level
			if msg.type not in self.config.console_levels:
				return
			
			console_event = ConsoleEvent(
				level=msg.type,
				message=msg.text,
				args=[str(arg) for arg in msg.args]
			)
			
			event = BrowserEvent(
				type=EventType.CONSOLE_LOG,
				console_event=console_event,
				page_url=page.url,
				tab_id=tab_id,
				priority=EventPriority.HIGH if msg.type == "error" else EventPriority.MEDIUM
			)
			
			await self.add_event(event)
		
		page.on("console", on_console)


class StreamingStateManager:
	"""Manages browser state through event streams"""
	
	def __init__(self, config: Optional[EventStreamConfig] = None):
		self.config = config or EventStreamConfig()
		self.event_streams = {
			'dom': DOMEventStream(self.config),
			'network': NetworkEventStream(self.config),
			'console': ConsoleEventStream(self.config)
		}
		self._stream_states: dict[str, StreamState] = {}
		self._cleanup_task: Optional[asyncio.Task] = None
	
	async def start(self) -> None:
		"""Start the streaming state manager"""
		# Start cleanup task
		self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
	
	async def stop(self) -> None:
		"""Stop the streaming state manager"""
		if self._cleanup_task:
			self._cleanup_task.cancel()
			try:
				await self._cleanup_task
			except asyncio.CancelledError:
				pass
	
	async def setup_page_monitoring(self, page: Page, tab_id: str) -> None:
		"""Set up monitoring for a page"""
		# Initialize state for tab
		self._stream_states[tab_id] = StreamState(
			current_url=page.url,
			page_title=await page.title() if page.url != "about:blank" else None
		)
		
		# Set up event listeners for each stream
		for stream in self.event_streams.values():
			await stream.setup_page_listeners(page, tab_id)
		
		# Navigation listener
		if self.config.collect_navigation:
			async def on_navigation():
				event = BrowserEvent(
					type=EventType.NAVIGATION,
					page_url=page.url,
					tab_id=tab_id,
					priority=EventPriority.HIGH
				)
				await self.event_streams['dom'].add_event(event)
				
				# Update state
				if tab_id in self._stream_states:
					self._stream_states[tab_id].current_url = page.url
					self._stream_states[tab_id].page_title = await page.title()
			
			page.on("load", on_navigation)
	
	@time_execution_async("get_relevant_state")
	async def get_relevant_state(
		self,
		intent: Any,  # Will be Intent type when integrated
		since: Optional[datetime] = None,
		tab_id: Optional[str] = None
	) -> dict[str, Any]:
		"""Get state relevant to an intent"""
		if not since:
			since = datetime.now() - timedelta(seconds=30)
		
		# Build filter based on intent
		filter = EventFilter(
			since_timestamp=since,
			tab_ids=[tab_id] if tab_id else None,
			min_relevance=0.3
		)
		
		# Get events from all streams
		relevant_events = {}
		for stream_name, stream in self.event_streams.items():
			if self._is_stream_relevant_to_intent(stream_name, intent):
				events = await stream.get_events(filter)
				if events:
					relevant_events[stream_name] = events
		
		# Get current state
		current_state = self._stream_states.get(tab_id) if tab_id else None
		
		# Build summary
		summary = self._summarize_events(relevant_events, current_state)
		
		return {
			"events": relevant_events,
			"current_state": current_state.model_dump() if current_state else None,
			"summary": summary
		}
	
	def _is_stream_relevant_to_intent(self, stream_name: str, intent: Any) -> bool:
		"""Check if a stream is relevant to an intent"""
		# TODO: Implement intent-based filtering when Intent type is available
		# For now, return all streams
		return True
	
	def _summarize_events(self, events: dict[str, list[BrowserEvent]], state: Optional[StreamState]) -> dict:
		"""Create a summary of events"""
		summary = {
			"total_events": sum(len(e) for e in events.values()),
			"events_by_type": {},
			"recent_errors": [],
			"key_changes": []
		}
		
		# Count events by type
		for stream_events in events.values():
			for event in stream_events:
				summary["events_by_type"][event.type] = summary["events_by_type"].get(event.type, 0) + 1
				
				# Collect errors
				if event.type == EventType.ERROR or (
					event.console_event and event.console_event.level == "error"
				):
					summary["recent_errors"].append({
						"message": event.console_event.message if event.console_event else "Unknown error",
						"timestamp": event.timestamp.isoformat()
					})
		
		# Identify key changes
		dom_events = events.get("dom", [])
		if dom_events:
			recent_mutations = [e for e in dom_events if e.dom_change]
			if recent_mutations:
				summary["key_changes"].append(f"{len(recent_mutations)} DOM mutations detected")
		
		return summary
	
	async def _periodic_cleanup(self) -> None:
		"""Periodically clean up old events"""
		while True:
			try:
				await asyncio.sleep(60)  # Run every minute
				
				for stream in self.event_streams.values():
					await stream.cleanup_old_events()
				
			except asyncio.CancelledError:
				break
			except Exception as e:
				# Log error but continue
				pass