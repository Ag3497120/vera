"""Backends: the models Vera Harness can drive.  `make_backend` is the one place the CLI turns a name into a backend."""
from __future__ import annotations

from typing import Any, Optional

from verantyx.harness.backends.base import Backend, BackendError, DriverClient, Turn
from verantyx.harness.backends.claude import AnthropicBackend
from verantyx.harness.backends.json_ops import JsonOpsBackend
from verantyx.harness.backends.openai_compat import OpenAICompatBackend

BACKENDS = ("anthropic", "openai", "json")
DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5"}


def make_backend(kind: str, model: Optional[str] = None, base_url: Optional[str] = None, *, client: Any = None, api_key_env: Optional[str] = None,
                 tool_choice: str = "required", temperature: Optional[float] = None) -> Backend:
    """`client`: an SDK-like object for tests / embedders (anthropic: `.messages.create`; openai and json: `.chat.completions.create`); None = the real SDK, imported lazily."""
    if kind not in BACKENDS:
        raise BackendError("backend must be one of %s" % (BACKENDS,), "bad_backend")
    model = model or DEFAULT_MODELS.get(kind)
    if not model:
        raise BackendError("--model is required for the %s backend" % kind, "no_model")
    if base_url is not None:
        from urllib.parse import urlsplit
        u = urlsplit(base_url)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise BackendError("--base-url must be an http(s) URL", "bad_base_url")
        if u.username or u.password or "@" in u.netloc:
            raise BackendError("--base-url must not carry credentials (the run folder records the URL); use the key environment variable", "bad_base_url")
    if kind == "anthropic":
        return AnthropicBackend(model, client, api_key_env=api_key_env, base_url=base_url, forced=tool_choice != "auto")
    if kind == "openai":
        return OpenAICompatBackend(model, base_url, client, api_key_env=api_key_env, forced=tool_choice != "auto", temperature=temperature)
    return JsonOpsBackend(model, base_url, client=client, api_key_env=api_key_env, temperature=temperature)


__all__ = ["Backend", "BackendError", "DriverClient", "Turn", "AnthropicBackend", "OpenAICompatBackend", "JsonOpsBackend", "make_backend", "BACKENDS"]
