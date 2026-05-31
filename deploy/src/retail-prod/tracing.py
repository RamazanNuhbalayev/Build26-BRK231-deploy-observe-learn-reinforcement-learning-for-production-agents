"""Tracing helpers for Azure OpenAI chat completions and agent invocations."""

from __future__ import annotations

import json
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind

_tracer = trace.get_tracer(__name__)

_GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
_GEN_AI_SYSTEM = "gen_ai.system"
_GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
_GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
_GEN_AI_RESPONSE_ID = "gen_ai.response.id"
_GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
_GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
_GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
_GEN_AI_TOOL_DEFINITIONS = "gen_ai.tool.definitions"


class GenAIMessageConverter:
    def input_messages(self, messages: list[dict]) -> str:
        return self._messages_json([self._input_message(message) for message in messages])

    def output_messages(self, response: Any) -> str:
        choice = response.choices[0]
        response_message = choice.message
        parts = self._text_parts(response_message.content)

        for tool_call in response_message.tool_calls or []:
            parts.append(self._tool_call_part(tool_call))

        output_message = {
            "role": response_message.role,
            "parts": parts,
            "finish_reason": "tool_call" if choice.finish_reason == "tool_calls" else choice.finish_reason,
        }
        if getattr(response_message, "name", None):
            output_message["name"] = response_message.name
        return self._messages_json([output_message])

    def _input_message(self, message: dict) -> dict:
        parts = self._text_parts(message.get("content"))

        for tool_call in message.get("tool_calls") or []:
            parts.append(self._tool_call_part(tool_call))

        if message.get("role") == "tool":
            parts = [{
                "type": "tool_call_response",
                "id": message.get("tool_call_id"),
                "response": message.get("content"),
            }]

        converted = {
            "role": message.get("role"),
            "parts": parts,
        }
        if message.get("name"):
            converted["name"] = message["name"]
        return converted

    def _text_parts(self, content: Any) -> list[dict]:
        if content is None:
            return []
        if isinstance(content, str):
            return [{"type": "text", "content": content}]
        if isinstance(content, list):
            return [self._content_part(part) for part in content]
        return [{"type": "text", "content": str(content)}]

    def _content_part(self, part: Any) -> dict:
        part = self._model_dump(part)
        if not isinstance(part, dict):
            return {"type": "text", "content": str(part)}
        if part.get("type") in {"text", "input_text", "output_text"}:
            return {"type": "text", "content": part.get("content") or part.get("text", "")}
        return part

    def _tool_call_part(self, tool_call: Any) -> dict:
        tool_call = self._model_dump(tool_call)
        function = tool_call.get("function") or {}
        return {
            "type": "tool_call",
            "id": tool_call.get("id"),
            "name": function.get("name") or tool_call.get("name"),
            "arguments": self._parse_json(function.get("arguments") or tool_call.get("arguments")),
        }

    @staticmethod
    def _model_dump(value: Any) -> dict:
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        return value

    @staticmethod
    def _parse_json(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @staticmethod
    def _messages_json(messages: list[dict]) -> str:
        return json.dumps(messages, separators=(",", ":"))


_message_converter = GenAIMessageConverter()


class ChatCompletionTrace:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_response(self, response: Any) -> None:
        if not self._span.is_recording():
            return

        self._span.set_attribute(
            _GEN_AI_OUTPUT_MESSAGES,
            _message_converter.output_messages(response),
        )

        if getattr(response, "id", None):
            self._span.set_attribute(_GEN_AI_RESPONSE_ID, response.id)
        if getattr(response, "model", None):
            self._span.set_attribute(_GEN_AI_RESPONSE_MODEL, response.model)


class AgentInvocationTrace:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_output(self, output: str) -> None:
        if not self._span.is_recording():
            return

        self._span.set_attribute(
            _GEN_AI_OUTPUT_MESSAGES,
            _message_converter.input_messages([{"role": "assistant", "content": output}]),
        )


@contextmanager
def trace_chat_completion(
    *,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> Iterator[ChatCompletionTrace]:
    """
    Context manager to trace a chat completion operation.
    """
    span_attributes = {
        _GEN_AI_OPERATION_NAME: "chat",
        _GEN_AI_SYSTEM: "azure_openai",
        _GEN_AI_PROVIDER_NAME: "azure_openai",
        _GEN_AI_REQUEST_MODEL: model,
        _GEN_AI_INPUT_MESSAGES: _message_converter.input_messages(messages),
    }
    if tools:
        span_attributes[_GEN_AI_TOOL_DEFINITIONS] = json.dumps(tools, separators=(",", ":"))

    with _tracer.start_as_current_span(
        f"chat {model or 'unknown'}",
        kind=SpanKind.CLIENT,
        attributes=span_attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as chat_span:
        yield ChatCompletionTrace(chat_span)


@contextmanager
def trace_agent_invocation(
    *,
    messages: list[dict],
) -> Iterator[AgentInvocationTrace]:
    """
    Context manager to trace an agent invocation operation.
    """
    span_attributes = {
        _GEN_AI_OPERATION_NAME: "invoke_agent",
        _GEN_AI_SYSTEM: "azure_openai",
        _GEN_AI_PROVIDER_NAME: "azure_openai",
        _GEN_AI_INPUT_MESSAGES: _message_converter.input_messages(messages),
    }

    with _tracer.start_as_current_span(
        "invoke_agent",
        kind=SpanKind.CLIENT,
        attributes=span_attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as agent_span:
        yield AgentInvocationTrace(agent_span)
