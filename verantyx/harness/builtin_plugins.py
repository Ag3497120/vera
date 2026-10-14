"""The built-in plugins, registered through the same entry point group as any other (pyproject: `vera-builtin = "verantyx.harness.builtin_plugins:plugins"`)."""
from __future__ import annotations

from typing import List

from verantyx import __version__
from verantyx.harness.plugins import LoomGate, MemoryProfile, NoteKind, Plugin
from verantyx.loom import memanswer as ma
from verantyx.loom import memory as mem

GATE_DEFAULT = "evidence.v6"
MEMORY_PROFILE_DEFAULT = "m6d-v17"


def _backend_factory(kind: str):
    def factory(model, base_url=None, **kw):
        from verantyx.harness.backends import make_backend
        return make_backend(kind, model, base_url, **kw)
    factory.__name__ = "make_%s_backend" % kind
    return factory


def plugins() -> List[Plugin]:
    out: List[Plugin] = []
    for kind, desc in (("anthropic", "Anthropic Messages API (forced tool use)"), ("openai", "any OpenAI-compatible server: DeepSeek, Ollama, LM Studio, vLLM, MLX (tool calling forced)"),
                       ("json", "a model without tool calling: it answers with a JSON array of operations, everything else is dropped")):
        out.append(Plugin("backend", kind, __version__, _backend_factory(kind), desc))
    for n, why in ((1, "the first build"), (2, "v1 + a predicate question needs a subject, the answer is a whole word"), (3, "widened reach (not default)"), (4, "v3 without R7, with the subject-chain rule (not default)"),
                   (5, "v4 + SU + TW (not default)"), (6, "v2 + the refusal-only rules CH, SU, TW, NEG: a pure filter over v2 (default)")):
        out.append(Plugin("gate", "evidence.v%d" % n, "1", LoomGate("v%d" % n), "the loom's evidence gate v%d: %s" % (n, why)))
    out.append(Plugin("memory_profile", MEMORY_PROFILE_DEFAULT, "1", MemoryProfile(dict(mem.V4_VERSIONS_M6D), ma.ANSWER_V17), "mem.v4 with shape.v4 / qwords.v2 / ask.v3, answer run memanswer.v17 (default)"))
    out.append(Plugin("memory_profile", "m6c-v17", "1", MemoryProfile(dict(mem.V4_VERSIONS_M6C), ma.ANSWER_V17), "mem.v4 with shape.v3 (the table before 「へ」 was read like 「に」), memanswer.v17"))
    for name, why in (("same_seat", "two writes put different values on the same seat of the cross"), ("update", "a write that says it changes a value the memory holds"),
                      ("reversal_x", "a write that swaps the two sides of an earlier relation"), ("enumeration", "a list, not a contradiction")):
        out.append(Plugin("note_kind", name, "1", NoteKind(None, "loom"), "note %s: %s (produced by the memory itself)" % (name.upper(), why)))
    return out
