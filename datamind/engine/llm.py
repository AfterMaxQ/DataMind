"""LLM client abstraction layer (Layer 1).

Provides:

- :class:`LLMResponse` — unified response dataclass
- :class:`BaseLLMClient` — abstract interface for LLM providers
- :class:`OpenAIClient` — OpenAI-compatible client with retry + streaming
- :class:`OllamaClient` — Ollama client with auto-discovery + OpenAI delegation
"""

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator

from datamind.config import LLM_MAX_RETRIES, LLM_RETRYABLE_STATUSES


@dataclass
class LLMResponse:
    """Unified response from any LLM client."""

    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""
    finish_reason: str = "stop"


class BaseLLMClient(ABC):
    """Abstract base for all LLM provider clients."""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> "LLMResponse | Iterator[LLMResponse]":
        """Send a chat completion request and return the response."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return a list of available model names."""
        ...


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible API client with retry logic and streaming support.

    Uses lazy initialisation of the ``openai.OpenAI`` client so that
    importing this module does not fail when ``openai`` is not installed.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        api_url: str = "https://api.openai.com/v1",
        max_retries: int = LLM_MAX_RETRIES,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        self.api_url = api_url
        self.max_retries = max_retries
        self._extra_kwargs = kwargs
        self._client: Any = None  # Lazy initialised

    def _get_client(self) -> Any:
        """Lazily create and return the OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_url,
                **self._extra_kwargs,
            )
        return self._client

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> "LLMResponse | Iterator[LLMResponse]":
        """Send a chat completion request.

        Retries on retryable status codes (429, 502, 503, 504) with
        exponential backoff.
        """
        client = self._get_client()

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            request_kwargs["tools"] = tools
        request_kwargs.update(kwargs)

        if stream:
            return self._stream(client, request_kwargs)
        return self._sync(client, request_kwargs)

    def _sync(self, client: Any, kwargs: dict[str, Any]) -> LLMResponse:
        """Execute a synchronous chat completion with retry logic."""
        last_exception: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.chat.completions.create(**kwargs)
                return self._parse_response(response)
            except Exception as exc:
                last_exception = exc
                if not self._is_retryable(exc):
                    raise
                if attempt >= self.max_retries:
                    raise
                delay = (2 ** attempt) * 0.5 + 0.1
                time.sleep(delay)
        raise last_exception  # type: ignore[misc]

    def _stream(
        self, client: Any, kwargs: dict[str, Any]
    ) -> Iterator[LLMResponse]:
        """Stream completion chunks, yielding an LLMResponse per chunk.

        Each yielded LLMResponse contains the *delta* content, if any.
        Tool calls are accumulated across chunks and emitted on the
        chunk where the tool call data first appears.
        """
        accumulated_content: list[str] = []
        accumulated_tool_calls: dict[int, dict[str, Any]] = {}
        model = self.model
        finish_reason = "stop"
        usage = {}

        for chunk in client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            delta_content = getattr(delta, "content", None) or ""
            if delta_content:
                accumulated_content.append(delta_content)

            # Accumulate tool call deltas
            delta_tool_calls = getattr(delta, "tool_calls", None) or []
            for tc in delta_tool_calls:
                idx = getattr(tc, "index", 0)
                if idx not in accumulated_tool_calls:
                    accumulated_tool_calls[idx] = {
                        "id": getattr(tc, "id", "") or "",
                        "type": getattr(tc, "type", "function") or "function",
                        "name": "",
                        "arguments": "",
                    }
                existing = accumulated_tool_calls[idx]
                if hasattr(tc, "id") and tc.id:
                    existing["id"] = tc.id
                if hasattr(tc, "function") and tc.function:
                    if hasattr(tc.function, "name") and tc.function.name:
                        existing["name"] = tc.function.name
                    if hasattr(tc.function, "arguments") and tc.function.arguments:
                        existing["arguments"] += tc.function.arguments

            choice_finish = getattr(chunk.choices[0], "finish_reason", None) if chunk.choices else None
            if choice_finish:
                finish_reason = choice_finish

            if hasattr(chunk, "model") and chunk.model:
                model = chunk.model

            if hasattr(chunk, "usage") and chunk.usage:
                usage = _usage_to_dict(chunk.usage)

            # Yield a response with this chunk's delta content
            yield LLMResponse(
                content=delta_content,
                tool_calls=(
                    list(accumulated_tool_calls.values())
                    if accumulated_tool_calls
                    else []
                ),
                usage=usage,
                model=model,
                finish_reason=finish_reason,
            )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse an OpenAI API response into an :class:`LLMResponse`."""
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", None) or ""

        tool_calls: list[dict] = []
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        for tc in raw_tool_calls:
            tool_calls.append({
                "id": getattr(tc, "id", ""),
                "type": getattr(tc, "type", "function"),
                "name": getattr(tc.function, "name", ""),
                "arguments": getattr(tc.function, "arguments", ""),
            })

        usage = _usage_to_dict(getattr(response, "usage", None))
        model = getattr(response, "model", self.model)
        finish_reason = getattr(choice, "finish_reason", "stop") or "stop"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=model,
            finish_reason=finish_reason,
        )

    def _is_retryable(self, exc: Exception) -> bool:
        """Return True if *exc* represents a retryable HTTP error."""
        return (
            hasattr(exc, "status_code")
            and getattr(exc, "status_code") in LLM_RETRYABLE_STATUSES
        )

    def list_models(self) -> list[str]:
        """Return model names available via the OpenAI API."""
        client = self._get_client()
        try:
            models = client.models.list()
            return [m.id for m in models]
        except Exception:
            # If we can't list models, at least return our own
            return [self.model]


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client.

    Discovers locally available models by running ``ollama list`` (cached
    with TTL).  Chat requests delegate to an OpenAI-compatible client
    pointed at the Ollama API endpoint.
    """

    DEFAULT_API_URL = "http://localhost:11434/v1"

    def __init__(
        self,
        model: str,
        api_url: str = DEFAULT_API_URL,
        auto_discover: bool = True,
        discovery_ttl: int = 300,
        manual_models: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, **kwargs)
        self.api_url = api_url
        self.auto_discover = auto_discover
        self.discovery_ttl = discovery_ttl
        self.manual_models = manual_models or []

        self._discovery_cache: list[str] | None = None
        self._discovery_timestamp: float = 0.0

        # The underlying OpenAI-compatible client (lazy, shared)
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily create the OpenAI-compatible client pointed at Ollama."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key="ollama",  # Ollama doesn't require a real key
                base_url=self.api_url,
            )
        return self._client

    def _discover_models(self) -> list[str]:
        """Run ``ollama list`` and parse model names from the output.

        Cached per *discovery_ttl* seconds.
        """
        now = time.time()
        if (
            self._discovery_cache is not None
            and (now - self._discovery_timestamp) < self.discovery_ttl
        ):
            return self._discovery_cache

        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())

            models: list[str] = []
            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                parts = line.split()
                if parts:
                    models.append(parts[0])
            self._discovery_cache = models
            self._discovery_timestamp = now
            return models
        except Exception:
            # Fall back to cache (even if stale) or manual models
            if self._discovery_cache is not None:
                return self._discovery_cache
            return list(self.manual_models)

    def list_models(self) -> list[str]:
        """Return discovered or manually configured model names."""
        if self.auto_discover:
            discovered = self._discover_models()
            if discovered:
                return discovered
        return list(self.manual_models)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> "LLMResponse | Iterator[LLMResponse]":
        """Delegate chat to the OpenAI-compatible client."""
        client = self._get_client()

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            request_kwargs["tools"] = tools
        request_kwargs.update(kwargs)

        # Use a short-lived delegate for consistency with the _sync/_stream helpers
        delegate = OpenAIClient(
            api_key="ollama",
            model=self.model,
            api_url=self.api_url,
            max_retries=1,
        )
        delegate._client = client

        if stream:
            return delegate._stream(client, request_kwargs)
        return delegate._sync(client, request_kwargs)


def _usage_to_dict(usage: Any) -> dict[str, int]:
    """Convert an OpenAI usage object to a plain dict."""
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
