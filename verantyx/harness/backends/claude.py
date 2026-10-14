"""The Anthropic backend: the Messages API with forced tool use (`tool_choice: any`, or `auto` + strict tools for the ids that reject forcing).

The `anthropic` SDK is imported here, lazily, and nowhere else.  The conversation is sent as the driver keeps it (the API's own blocks, unchanged);
the response blocks are returned as they are, so free text and thinking blocks reach the DRIVER, which hashes and drops them.  Nothing of them is read here.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from verantyx.harness import keys
from verantyx.harness.backends.base import BackendError, Turn, api_forced_choice, get


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, model: str, client: Any = None, *, api_key_env: Optional[str] = None, base_url: Optional[str] = None, forced: bool = True) -> None:
        self.model = model
        self.forced = forced
        self.base_url = base_url
        self.key_source: Optional[str] = None
        self._client = client
        self._api_key_env = api_key_env
        self.last_response_model: Optional[str] = None

    def client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise BackendError('the `anthropic` SDK is not installed (pip install "vera-harness[anthropic]")', "sdk_missing") from e
            key = keys.resolve_api_key("anthropic", self._api_key_env)
            if not key:
                raise BackendError("no API key: set ANTHROPIC_API_KEY or store one in the macOS Keychain (see verantyx.harness.keys)", "no_api_key")
            self.key_source = keys.key_source("anthropic", self._api_key_env)
            kw = {"api_key": key}
            if self.base_url:
                kw["base_url"] = self.base_url
            self._client = anthropic.Anthropic(**kw)
        return self._client

    def tool_choice(self) -> Tuple[dict, bool]:
        return api_forced_choice(self.model, self.forced)

    def send(self, *, system: str, messages: Sequence[dict], tools: Sequence[dict], max_tokens: int, tool_choice: Optional[dict] = None,
             extra: Optional[dict] = None) -> Turn:
        kw = dict(model=self.model, max_tokens=max_tokens, system=system, messages=list(messages))
        if tools:
            kw["tools"] = list(tools)
            if tool_choice is not None:
                kw["tool_choice"] = tool_choice
        if extra:
            kw.update(extra)
        resp = self.client().messages.create(**kw)
        us = get(resp, "usage")
        usage = {}
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            v = get(us, k) if us is not None else None
            if isinstance(v, int) and not isinstance(v, bool):
                usage[k] = v
        model = get(resp, "model")
        self.last_response_model = model
        return Turn(content=list(get(resp, "content", []) or []), usage=usage, model=model, stop_reason=str(get(resp, "stop_reason", "") or ""))

    def describe(self) -> dict:
        d = {"backend": self.name, "model": self.model}
        if self.base_url:
            d["base_url"] = self.base_url
        return d
