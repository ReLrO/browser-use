from __future__ import annotations

from typing import TYPE_CHECKING, Any
from warnings import filterwarnings

from langchain_core._api import LangChainBetaWarning
from langchain_core.load import dumpd, load
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

filterwarnings('ignore', category=LangChainBetaWarning)

if TYPE_CHECKING:
	from browser_use.agent.views import AgentOutput


class MessageMetadata(BaseModel):
	"""Metadata for a message"""

	tokens: int = 0
	message_type: str | None = None


class ManagedMessage(BaseModel):
	"""A message with its metadata"""

	message: BaseMessage
	metadata: MessageMetadata = Field(default_factory=MessageMetadata)

	model_config = ConfigDict(arbitrary_types_allowed=True)

	# https://github.com/pydantic/pydantic/discussions/7558
	@model_serializer(mode='wrap')
	def to_json(self, original_dump):
		"""
		Returns the JSON representation of the model.

		It uses langchain's `dumps` function to serialize the `message`
		property before encoding the overall dict with json.dumps.
		"""
		data = original_dump(self)

		# NOTE: We override the message field to use langchain JSON serialization.
		data['message'] = dumpd(self.message)

		return data

	@model_validator(mode='before')
	@classmethod
	def validate(
		cls,
		value: Any,
		*,
		strict: bool | None = None,
		from_attributes: bool | None = None,
		context: Any | None = None,
	) -> Any:
		"""
		Custom validator that uses langchain's `loads` function
		to parse the message if it is provided as a JSON string.
		"""
		if isinstance(value, dict) and 'message' in value:
			# NOTE: We use langchain's load to convert the JSON string back into a BaseMessage object.
			filterwarnings('ignore', category=LangChainBetaWarning)
			value['message'] = load(value['message'])
		return value


class MessageHistory(BaseModel):
	"""History of messages with metadata"""

	messages: list[ManagedMessage] = Field(default_factory=list)
	current_tokens: int = 0

	model_config = ConfigDict(arbitrary_types_allowed=True)

	def add_message(self, message: BaseMessage, metadata: MessageMetadata, position: int | None = None) -> None:
		"""Add message with metadata to history"""
		if position is None:
			self.messages.append(ManagedMessage(message=message, metadata=metadata))
		else:
			self.messages.insert(position, ManagedMessage(message=message, metadata=metadata))
		self.current_tokens += metadata.tokens

	def add_model_output(self, output: AgentOutput) -> None:
		"""Add model output as AI message"""
		tool_calls = [
			{
				'name': 'AgentOutput',
				'args': output.model_dump(mode='json', exclude_unset=True),
				'id': '1',
				'type': 'tool_call',
			}
		]

		msg = AIMessage(
			content='',
			tool_calls=tool_calls,
		)
		self.add_message(msg, MessageMetadata(tokens=100))  # Estimate tokens for tool calls

		# Empty tool response
		tool_message = ToolMessage(content='', tool_call_id='1')
		self.add_message(tool_message, MessageMetadata(tokens=10))  # Estimate tokens for empty response

	def get_messages(self) -> list[BaseMessage]:
		"""Get all messages"""
		return [m.message for m in self.messages]

	def get_total_tokens(self) -> int:
		"""Get total tokens in history"""
		return self.current_tokens

	def remove_oldest_message(self) -> None:
		"""Remove oldest non-system message"""
		for i, msg in enumerate(self.messages):
			if not isinstance(msg.message, SystemMessage):
				self.current_tokens -= msg.metadata.tokens
				self.messages.pop(i)
				break

	def remove_last_state_message(self) -> None:
		"""Remove last state message from history"""
		if len(self.messages) > 2 and isinstance(self.messages[-1].message, HumanMessage):
			self.current_tokens -= self.messages[-1].metadata.tokens
			self.messages.pop()
	
	def apply_sliding_window(self, max_tokens: int, preserve_recent: int = 3) -> None:
		"""Apply sliding window to compress history while preserving important messages
		
		Args:
			max_tokens: Maximum allowed tokens
			preserve_recent: Number of recent messages to always preserve
		"""
		if self.current_tokens <= max_tokens:
			return
		
		# Always preserve system messages and recent messages
		preserved_indices = set()
		
		# Mark system messages for preservation
		for i, msg in enumerate(self.messages):
			if isinstance(msg.message, SystemMessage):
				preserved_indices.add(i)
		
		# Mark recent messages for preservation
		if len(self.messages) > preserve_recent:
			for i in range(len(self.messages) - preserve_recent, len(self.messages)):
				preserved_indices.add(i)
		
		# Remove messages from oldest to newest until under token limit
		i = 0
		while self.current_tokens > max_tokens and i < len(self.messages):
			if i not in preserved_indices:
				self.current_tokens -= self.messages[i].metadata.tokens
				self.messages.pop(i)
				# Adjust preserved indices after removal
				preserved_indices = {idx - 1 if idx > i else idx for idx in preserved_indices}
			else:
				i += 1
	
	def compress_history(self, max_tokens: int) -> str | None:
		"""Compress history by summarizing older messages
		
		Returns:
			Summary of compressed messages if any were compressed, None otherwise
		"""
		if self.current_tokens <= max_tokens:
			return None
		
		# Find messages to compress (older than last 5, non-system)
		messages_to_compress = []
		indices_to_remove = []
		
		for i, msg in enumerate(self.messages[:-5]):  # Keep last 5 messages
			if not isinstance(msg.message, SystemMessage):
				messages_to_compress.append(msg)
				indices_to_remove.append(i)
		
		if not messages_to_compress:
			return None
		
		# Create summary of compressed messages
		summary_parts = []
		for msg in messages_to_compress[:5]:  # Summarize up to 5 messages
			if isinstance(msg.message, AIMessage) and msg.message.tool_calls:
				# Extract action from tool calls
				tool_call = msg.message.tool_calls[0]
				if 'args' in tool_call and 'action' in tool_call['args']:
					actions = tool_call['args']['action']
					if isinstance(actions, list) and actions:
						action_name = next(iter(actions[0].keys())) if isinstance(actions[0], dict) else str(actions[0])
						summary_parts.append(f"• Executed: {action_name}")
			elif isinstance(msg.message, HumanMessage):
				content = str(msg.message.content)[:100] + '...' if len(str(msg.message.content)) > 100 else str(msg.message.content)
				summary_parts.append(f"• State: {content}")
		
		if len(messages_to_compress) > 5:
			summary_parts.append(f"• ... and {len(messages_to_compress) - 5} more actions")
		
		summary = "Previous actions summary:\n" + "\n".join(summary_parts)
		
		# Remove compressed messages
		tokens_removed = 0
		for i in reversed(indices_to_remove):  # Remove from end to preserve indices
			tokens_removed += self.messages[i].metadata.tokens
			self.messages.pop(i)
		
		self.current_tokens -= tokens_removed
		
		return summary


class MessageManagerState(BaseModel):
	"""Holds the state for MessageManager"""

	history: MessageHistory = Field(default_factory=MessageHistory)
	tool_id: int = 1

	model_config = ConfigDict(arbitrary_types_allowed=True)
