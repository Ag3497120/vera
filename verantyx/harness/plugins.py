"""Plugins: a small registry through the Python entry-point group `vera.plugins`.  The built-ins are registered the same way (the entry point `vera-builtin` of this package,
verantyx.harness.builtin_plugins:plugins); a plugin of your own is one more entry point.

Four kinds:

  backend         a model driver.  obj = factory(model, base_url, *, client=None, api_key_env=None, tool_choice="required", temperature=None) -> Backend  (see backends/base.py)
  gate            built-in: a `LoomGate` that selects one of the loom's evidence versions (evidence.v1 ... v6).  Yours: a GATE FILTER, a callable
                  (question: str, answer: str, sources: list[dict]) -> None | refusal code.  It runs on an answer the loom's own gate already passed, and it can only REFUSE
                  (a pure filter, like evidence.v6 over v2): the answer becomes 「分かりません」 with the reason `plugin_refused` and your code.  It cannot make Vera say more.
  memory_profile  a `MemoryProfile` (the loom's version bundle + the answer-run version) for `vera mem`.  It can only pick versions the loom itself implements.
  note_kind       a `NoteKind`: `annotate(sentences: list[dict]) -> list[{"sid": int, "text": str}]`, a read-only reader of the committed memory sentences; its notes are shown beside the
                  answer and never change it.  (The built-in kinds SAME_SEAT / UPDATE / REVERSAL_X / ENUMERATION are produced by the memory itself and are listed here with obj = None.)

The ledger records which plugins ran: the first `harness_meta` row of a run carries `plugins` = the canonical JSON of [{"kind", "name", "version"}], inside the hash chain.  `vera verify`
and `vera replay` compare that list with what is installed: a plugin that is not installed, or installed at another version, makes the result INPUTS (the replay cannot reproduce the
conditions), never a silent OK.  A broken plugin (an import error, a malformed object) is recorded in `Registry.errors` and does not take `vera` down; asking for it by name fails.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

GROUP = "vera.plugins"
KINDS = ("backend", "gate", "memory_profile", "note_kind")
BUILTIN_MODULE = "verantyx.harness.builtin_plugins"
_NAME_RX = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_VERSION_RX = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")
MANIFEST_MAX = 4000


class PluginError(Exception):
    """A typed refusal (`code` is a stable token): unknown_plugin, bad_plugin, duplicate_plugin, ..."""

    def __init__(self, msg: str, code: str = "plugin_error") -> None:
        super().__init__("%s: %s" % (code, msg))
        self.code = code


@dataclass(frozen=True)
class LoomGate:
    """A built-in gate: one of the loom's evidence versions ("v1" ... "v6")."""
    evidence: str


@dataclass(frozen=True)
class MemoryProfile:
    versions: Dict[str, str]
    answer_version: str
    profile: str = "mem.v4"


@dataclass(frozen=True)
class NoteKind:
    annotate: Optional[Callable[[Sequence[dict]], Sequence[dict]]] = None
    produced_by: str = "plugin"


@dataclass(frozen=True)
class Plugin:
    kind: str
    name: str
    version: str
    obj: Any
    description: str = ""
    builtin: bool = False
    origin: str = ""
    digest: str = ""                       # sha256 of the source of the module that provides the plugin (non-built-in plugins): the ledger records it, verify compares it

    def key(self) -> Tuple[str, str]:
        return (self.kind, self.name)

    def ref(self) -> Dict[str, str]:
        d = {"kind": self.kind, "name": self.name, "version": self.version}
        if self.digest:
            d["digest"] = self.digest
        return d


def _validate(p: Plugin) -> None:
    if not isinstance(p, Plugin):
        raise PluginError("an entry point must give Plugin objects, not %s" % type(p).__name__, "bad_plugin")
    if p.kind not in KINDS:
        raise PluginError("kind %r is not one of %s" % (p.kind, KINDS), "bad_plugin")
    if not isinstance(p.name, str) or not _NAME_RX.match(p.name):
        raise PluginError("name %r: lower-case letters, digits, . _ - (1 to 64, not starting with a symbol)" % (p.name,), "bad_plugin")
    if not isinstance(p.version, str) or not _VERSION_RX.match(p.version):
        raise PluginError("%s/%s: version %r is not a short version string" % (p.kind, p.name, p.version), "bad_plugin")
    o = p.obj
    if p.kind == "backend" and not callable(o):
        raise PluginError("%s/%s: a backend plugin's object is a factory (callable)" % (p.kind, p.name), "bad_plugin")
    if p.kind == "gate" and not (isinstance(o, LoomGate) or callable(o)):
        raise PluginError("%s/%s: a gate plugin's object is a LoomGate or a filter (callable)" % (p.kind, p.name), "bad_plugin")
    if p.kind == "memory_profile":
        if not isinstance(o, MemoryProfile) or not isinstance(o.versions, dict) or not isinstance(o.answer_version, str):
            raise PluginError("%s/%s: a memory_profile plugin's object is a MemoryProfile" % (p.kind, p.name), "bad_plugin")
    if p.kind == "note_kind" and not (isinstance(o, NoteKind) and (o.annotate is None or callable(o.annotate))):
        raise PluginError("%s/%s: a note_kind plugin's object is a NoteKind" % (p.kind, p.name), "bad_plugin")


def _as_list(x: Any) -> List[Plugin]:
    if isinstance(x, Plugin):
        return [x]
    if callable(x):
        return _as_list(x())
    try:
        return list(x)
    except TypeError:
        raise PluginError("an entry point must be a Plugin, an iterable of Plugin or a callable returning them", "bad_plugin") from None


class Registry:
    def __init__(self) -> None:
        self._by_key: Dict[Tuple[str, str], Plugin] = {}
        self.errors: List[Dict[str, str]] = []

    def register(self, p: Plugin) -> None:
        _validate(p)
        old = self._by_key.get(p.key())
        if old is not None:
            raise PluginError("%s/%s is already registered (by %s); a plugin cannot replace another" % (p.kind, p.name, old.origin or "?"), "duplicate_plugin")
        self._by_key[p.key()] = p

    def load_provider(self, origin: str, provider: Any, builtin: bool = False) -> None:
        """Register everything one entry point provides; a failure is recorded (with the entry point's name), the rest still loads."""
        try:
            got = _as_list(provider() if callable(provider) and not isinstance(provider, Plugin) else provider)
        except Exception as e:                                         # a plugin must never take the command down
            self.errors.append({"origin": origin, "error": "%s: %s" % (type(e).__name__, e)})
            return
        for p in got:
            try:
                if not isinstance(p, Plugin):
                    raise PluginError("an entry point must give Plugin objects, not %s" % type(p).__name__, "bad_plugin")
                self.register(Plugin(p.kind, p.name, p.version, p.obj, p.description, builtin, origin, "" if builtin else p.digest or code_digest(provider, p.obj)))
            except PluginError as e:
                self.errors.append({"origin": origin, "error": str(e)})

    def get(self, kind: str, name: str) -> Optional[Plugin]:
        return self._by_key.get((kind, name))

    def require(self, kind: str, name: str) -> Plugin:
        p = self.get(kind, name)
        if p is None:
            known = ", ".join(sorted(self.names(kind))) or "none"
            raise PluginError("no %s plugin named %r (installed: %s)" % (kind, name, known), "unknown_plugin")
        return p

    def names(self, kind: str) -> List[str]:
        return sorted(n for (k, n) in self._by_key if k == kind)

    def all(self) -> List[Plugin]:
        return [self._by_key[k] for k in sorted(self._by_key)]

    def listing(self) -> List[Dict[str, Any]]:
        return [{"kind": p.kind, "name": p.name, "version": p.version, "builtin": p.builtin, "origin": p.origin, "description": p.description} for p in self.all()]


def code_digest(provider: Any, obj: Any) -> str:
    """sha256 of the source file of the module that defines the entry point (else the object): what the plugin IS, beyond its name and version.  "" when the source cannot be found."""
    import inspect
    import sys
    for o in (provider, obj):
        mod = sys.modules.get(getattr(o, "__module__", "") or "")
        try:
            f = inspect.getsourcefile(mod) if mod is not None else None
            if f:
                with open(f, "rb") as fh:
                    return hashlib.sha256(fh.read()).hexdigest()
        except (OSError, TypeError):
            continue
    return ""


class _EP:
    """An entry point given by name and an importable 'module:attr' (the shape tests and embedders use instead of installed metadata)."""

    def __init__(self, name: str, value: str) -> None:
        self.name, self.value = name, value

    def load(self) -> Any:
        mod, _, attr = self.value.partition(":")
        o = importlib.import_module(mod)
        for part in attr.split(".") if attr else []:
            o = getattr(o, part)
        return o


def installed_entry_points() -> List[Any]:
    from importlib import metadata
    try:
        return list(metadata.entry_points(group=GROUP))
    except TypeError:                                                  # Python 3.9-style API: not supported by this package (>= 3.10), kept harmless
        return list(metadata.entry_points().get(GROUP, []))


def discover(entry_points: Optional[Iterable[Any]] = None) -> Registry:
    """Build a registry: the built-ins first (the package's own entry point, or - when the package metadata is not installed, as in a source checkout - the same provider imported
    directly), then every other entry point of the group, in the order of their names."""
    reg = Registry()
    eps = list(installed_entry_points() if entry_points is None else entry_points)
    builtin = [e for e in eps if str(getattr(e, "value", "")).startswith(BUILTIN_MODULE)]
    others = sorted((e for e in eps if e not in builtin), key=lambda e: str(getattr(e, "name", "")))
    if builtin:
        for e in builtin:
            _load_ep(reg, e, True)
    else:
        from verantyx.harness import builtin_plugins
        reg.load_provider("builtin", builtin_plugins.plugins, True)
    for e in others:
        _load_ep(reg, e, False)
    return reg


def _load_ep(reg: Registry, ep: Any, builtin: bool) -> None:
    origin = "%s=%s" % (getattr(ep, "name", "?"), getattr(ep, "value", "?"))
    try:
        provider = ep.load()
    except Exception as e:
        reg.errors.append({"origin": origin, "error": "%s: %s" % (type(e).__name__, e)})
        return
    reg.load_provider(origin, provider, builtin)


_REGISTRY: Optional[Registry] = None


def registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = discover()
    return _REGISTRY


def set_registry(reg: Optional[Registry]) -> None:
    """For tests and embedders: use `reg` from now on (None: discover again on the next call)."""
    global _REGISTRY
    _REGISTRY = reg


# ------------------------------------------------------------------------------------------------------------
# the manifest a ledger carries
# ------------------------------------------------------------------------------------------------------------
def manifest(used: Sequence[Plugin]) -> str:
    """The canonical JSON of the plugins that run, sorted, without duplicates: the string of the `plugins` key of the first harness_meta row."""
    refs = sorted({(p.kind, p.name, p.version, p.digest) for p in used})
    s = json.dumps([dict({"kind": k, "name": n, "version": v}, **({"digest": d} if d else {})) for k, n, v, d in refs], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(s) > MANIFEST_MAX:
        raise PluginError("too many plugins for one ledger row", "bad_plugin")
    return s


def parse_manifest(s: Any) -> Optional[List[Dict[str, str]]]:
    """The declared plugins, or None when the string is not a well-formed manifest."""
    try:
        v = json.loads(s)
    except (TypeError, ValueError):
        return None
    if not isinstance(v, list):
        return None
    out = []
    for e in v:
        if not (isinstance(e, dict) and set(e) in ({"kind", "name", "version"}, {"kind", "name", "version", "digest"}) and all(isinstance(x, str) for x in e.values())):
            return None
        out.append(e)
    return out


def mismatch(declared: Optional[Sequence[Dict[str, str]]], reg: Optional[Registry] = None) -> Optional[str]:
    """None when every declared plugin is installed at the declared version, else a typed token: unknown_plugin:<kind>/<name>, plugin_version:<kind>/<name>:<declared>!=<installed>,
    plugins_malformed.  `declared` None (a ledger that declares nothing: made before plugins, or by the loom directly) is not a mismatch."""
    if declared is None:
        return None
    reg = reg or registry()
    for e in declared:
        p = reg.get(e["kind"], e["name"])
        if p is None:
            return "unknown_plugin:%s/%s" % (e["kind"], e["name"])
        if p.version != e["version"]:
            return "plugin_version:%s/%s:%s!=%s" % (e["kind"], e["name"], e["version"], p.version)
        if e.get("digest") and p.digest != e["digest"]:
            return "plugin_code:%s/%s:the installed source is not the source that ran" % (e["kind"], e["name"])
    return None


def apply_gate_filters(question: str, answer: str, sources: Sequence[dict], filters: Sequence[Plugin]) -> Optional[Tuple[Plugin, str]]:
    """The first gate filter that refuses: (plugin, code), else None.  A filter that raises, or returns anything but None / a string, refuses (fail closed)."""
    for f in filters:
        if isinstance(f.obj, LoomGate):
            continue
        try:
            code = f.obj(question, answer, list(sources))
        except Exception as e:
            return f, "filter_error:%s" % type(e).__name__
        if code is None:
            continue
        if not isinstance(code, str) or not code:
            return f, "filter_bad_result"
        return f, re.sub(r"[^0-9A-Za-z._:-]", "_", code)[:60]
    return None
