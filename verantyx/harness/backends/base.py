"""The backend protocol.

A backend turns ONE request (system prompt, the conversation so far, the tools of the loom or of the memory) into ONE assistant turn.  What the
driver (verantyx.loom.driver / memdriver, unchanged) reads from a turn is Anthropic-shaped: a list of content blocks (`text`, `thinking`, `tool_use`),
the usage the server reported, the model that answered and a stop reason.  Every backend returns exactly that (`Turn`), so the three of them (the
Anthropic API, any OpenAI-compatible server, a model with no tool calling) run through the SAME driver, the SAME loom / memory server and the SAME
ledger.  The guarantee does not live here:

  * a `text` block is never output: the driver drops it and writes its sha256 and length as a `free_text_dropped` row;
  * a `thinking` block is counted (hash + length) and dropped;
  * only `tool_use` blocks reach the server, and only the tools the server offered (`unknown_tool` otherwise, no row, no state);
  * the user sees only the text of a successful `emit` of a verified ledger, or an abstention with its typed reason.

`Backend.send` must not raise for a model that misbehaves (garbage tool arguments, prose instead of calls): that is a normal turn whose bad parts
are `text` blocks.  It raises for transport failures (the driver turns them into `abandoned api_error`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable

from verantyx.loom import driver as drv


class BackendError(Exception):
    """A typed refusal to build or use a backend (`code` is a stable token): sdk_missing, no_api_key, bad_backend, bad_base_url, ..."""

    def __init__(self, msg: str, code: str = "backend_error") -> None:
        super().__init__("%s: %s" % (code, msg))
        self.code = code


def text_block(text: str) -> Any:
    return SimpleNamespace(type="text", text=text)


def thinking_block(text: str) -> Any:
    return SimpleNamespace(type="thinking", thinking=text, signature="")


def tool_block(id_: str, name: str, inp: dict) -> Any:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


@dataclass
class Turn:
    content: List[Any] = field(default_factory=list)       # Anthropic-shaped blocks
    usage: Dict[str, int] = field(default_factory=dict)   # input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens (what the server reported: testimony)
    model: Optional[str] = None
    stop_reason: str = ""

    @property
    def tool_calls(self) -> List[Any]:
        return [b for b in self.content if getattr(b, "type", None) == "tool_use"]

    def as_response(self) -> Any:
        """The object `client.messages.create` returns (what driver.run_episode / memdriver.run_story_session read)."""
        return SimpleNamespace(content=list(self.content), stop_reason=self.stop_reason, model=self.model, usage=SimpleNamespace(**self.usage))


@runtime_checkable
class Backend(Protocol):
    name: str            # "anthropic" | "openai" | "json"
    model: str

    def send(self, *, system: str, messages: Sequence[dict], tools: Sequence[dict], max_tokens: int, tool_choice: Optional[dict] = None,
             extra: Optional[dict] = None) -> Turn: ...

    def ready(self) -> None:
        """Build the SDK client now (raises BackendError sdk_missing / no_api_key): a configuration error stops the command before a run exists."""
        ...

    def tool_choice(self) -> Tuple[dict, bool]:
        """(tool_choice, strict) this backend asks for: forced tool use where the server accepts it."""
        ...

    def describe(self) -> dict:
        """What the run folder records about the backend: name, model, base_url.  Never a key."""
        ...


class DriverClient:
    """`client.messages.create(**kw)`: the shape the loom drivers call, over a Backend.  Keyword arguments the drivers add (`extra_api`) are passed on as `extra`."""

    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        self.messages = SimpleNamespace(create=self._create)
        self.calls = 0

    def _create(self, **kw: Any) -> Any:
        self.calls += 1
        base = {"model", "max_tokens", "system", "tools", "tool_choice", "messages"}
        extra = {k: v for k, v in kw.items() if k not in base}
        t = self.backend.send(system=kw.get("system") or "", messages=kw.get("messages") or [], tools=kw.get("tools") or [], max_tokens=int(kw.get("max_tokens") or drv.MAX_TOKENS),
                              tool_choice=kw.get("tool_choice"), extra=extra or None)
        return t.as_response()


# -- helpers shared by the OpenAI-compatible and the JSON backends ------------------------------------------------------------
def get(b: Any, k: str, default: Any = None) -> Any:
    return b.get(k, default) if isinstance(b, dict) else getattr(b, k, default)


def jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def api_forced_choice(model: str, forced: bool = True) -> Tuple[dict, bool]:
    """The loom's rule for Claude ids that reject forced tool use (driver.FORCED_REJECTED); for every other model `any` unless the operator turned forcing off."""
    if not forced:
        return {"type": "auto"}, False
    return drv.tool_choice_for(model)
