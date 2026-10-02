"""Closed-choice wiring from constructed unknown candidates to frame terms.

The Resolver may select only terms already present in a candidate or the
question frame. Candidate provenance is returned separately and never enters
the ask. An adopted mapping is stored as testimony, not as semantic evidence.
"""
from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from threading import RLock
from types import ModuleType
import unicodedata
from typing import Any, Literal, Optional, Protocol

from .memory_frame import CodexAsker, Resolver
from .semantic_unknown import UnknownReport


Decision = Literal["ADOPT", "NONE", "UNRESOLVED"]
_ASKER_PROVENANCE = "verantyx.semantic_unknown_choice"
_LLM_ASKER_PROVENANCE = "llm-closed-choice"


class ClosedChoiceAsker(Protocol):
    """An injected closed-choice callback, including an external LLM asker."""

    def __call__(self, prompt: str) -> str: ...


# Preserve the old import while allowing this protocol to include the explicit
# LLM closed-choice path.
NonLLMAsker = ClosedChoiceAsker


def _contains_codex_asker(value: Any, seen: Optional[set[int]] = None) -> bool:
    """Find a CodexAsker wrapped by a callable, closure, or delegated object."""
    if value is CodexAsker or isinstance(value, CodexAsker):
        return True
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return False
    if isinstance(value, (ModuleType, type)):
        return False

    seen = seen if seen is not None else set()
    identity = id(value)
    if identity in seen:
        return False
    seen.add(identity)

    if isinstance(value, Mapping):
        return any(_contains_codex_asker(item, seen)
                   for pair in value.items() for item in pair)
    if isinstance(value, (tuple, list, set, frozenset)):
        return any(_contains_codex_asker(item, seen) for item in value)
    if isinstance(value, functools.partial):
        return (_contains_codex_asker(value.func, seen)
                or _contains_codex_asker(value.args, seen)
                or _contains_codex_asker(value.keywords, seen))
    if inspect.ismethod(value):
        return (_contains_codex_asker(value.__self__, seen)
                or _contains_codex_asker(value.__func__, seen))
    if inspect.isfunction(value):
        if any(_contains_codex_asker(cell.cell_contents, seen)
               for cell in (value.__closure__ or ())):
            return True
        return False

    try:
        state = vars(value)
    except TypeError:
        state = {}
    if any(_contains_codex_asker(item, seen) for item in state.values()):
        return True
    for cls in type(value).__mro__:
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            try:
                item = object.__getattribute__(value, name)
            except (AttributeError, TypeError):
                continue
            if _contains_codex_asker(item, seen):
                return True
    call_impl = getattr(type(value), "__call__", None)
    return call_impl is not None and _contains_codex_asker(call_impl, seen)


def _asker_provenance(asker: Any) -> str:
    if not callable(asker):
        raise TypeError("asker must be an injected closed-choice callable")
    if _contains_codex_asker(asker):
        return _LLM_ASKER_PROVENANCE
    # A caller-provided label is not proof of who answered. For unrecognized
    # injected callbacks, attribute the recorded protocol to this resolver.
    return _ASKER_PROVENANCE


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain(value: Any) -> Any:
    """Convert the typed provenance records to ordinary JSON-shaped values."""
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name))
                for name in value.__dataclass_fields__}
    return value


def _constructed(candidate: Any) -> bool:
    """Require a true construction marker, defaulting for legacy candidates."""
    return _get(candidate, "constructed", True) is True


def _prompt_json(value: Any) -> str:
    """Serialize data while making invisible Unicode separators inert."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "".join(
        f"\\u{ord(char):04x}"
        if unicodedata.category(char) in ("Cf", "Zl", "Zp") else char
        for char in encoded
    )


class _JSONOptionResolver(Resolver):
    """Keep pre-serialized closed options and the queried word intact in Resolver's prompt.

    The queried word and every option reach this class already serialized by
    ``_prompt_json``; they are JSON text, not raw words. Escaping them again would
    double each backslash and show the model a string that is not the serialized
    data (the data would no longer be handed over verbatim).
    """

    @staticmethod
    def _escape(value: Any) -> str:
        """Escape a raw (not yet serialized) string such as the context text."""
        out = []
        for char in str(value):
            category = unicodedata.category(char)
            if char == "\\":
                out.append("\\\\")
            elif char in "「」" or category in ("Cc", "Cf", "Zl", "Zp"):
                out.append(f"\\u{ord(char):04x}")
            else:
                out.append(char)
        return "".join(out)

    @staticmethod
    def _inert_in_json(json_text: Any) -> str:
        """Make JSON text safe to show between 「」 without changing what it decodes to."""
        return "".join(
            f"\\u{ord(char):04x}"
            if char in "「」" or unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp") else char
            for char in str(json_text)
        )

    def _prompt(self, word, context, options, variant):
        head = (
            "次の語は、下の候補のどれに意味が最も近いですか。"
            if variant == 0 else
            "候補の中から、次の語を最も自然に言い換えられるものを1つだけ選んでください。どれも合わなければ null。"
        )
        # ``word`` is JSON text (see the class docstring). Inside a JSON string,
        # ``\uXXXX`` stands for the same character, so only the frame quotes and
        # characters that could break a line or hide (Cc, Cf, Zl, Zp: this also
        # covers U+0085 and U+007F, which json.dumps leaves raw) are rewritten
        # that way. Backslashes are left alone so ``json.loads`` returns the
        # original word.
        shown_word = self._inert_in_json(word)
        shown_context = self._escape(context)
        # Each option is already JSON-serialized, so escaping it again would
        # turn JSON escapes such as \u000a into literal backslash text.
        lines = "\n".join(f"{i}: {option}" for i, option in enumerate(options))
        return (
            f"{head}\n語: 「{shown_word}」\n使われた場面: {shown_context}\n候補:\n{lines}\n"
            f"答えは次のJSONだけを出力してください（説明は不要）: {{\"choice\": 番号 または null}}\n"
            f"候補以外を選んだり、新しい表現を作ったりしてはいけません。"
        )


def _as_terms(values: Iterable[Any]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise TypeError("frame_vocabulary must be an iterable of terms")
    terms: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("frame vocabulary terms must be strings")
        if value and value.strip() and value not in terms:
            terms.append(value)
    return terms


def _candidate_terms(candidate: Any, unknown: str) -> list[str]:
    terms: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value.strip() and value != unknown and value not in terms:
            terms.append(value)

    # A distinct candidate term is useful for alternate candidate types. The
    # current UnknownCandidate.term repeats the queried unknown and is omitted.
    add(_get(candidate, "term"))
    for unit in (_get(candidate, "units", ()) or ()):
        add(unit)
    for family in (_get(candidate, "families", ()) or ()):
        for member in (_get(family, "members", ()) or ()):
            add(member)
    for option in (_get(candidate, "options", ()) or ()):
        add(option)
    return terms


def _evidence(report: Any) -> list[dict[str, Any]]:
    result = []
    for index, candidate in enumerate(_get(report, "candidates", ()) or ()):
        result.append({
            "candidate_index": index,
            "kind": _get(candidate, "kind"),
            "constructed": _constructed(candidate),
            "counts_as_evidence": False,
            "provenance": _plain(_get(candidate, "provenance", ()) or ()),
        })
    return result


class SemanticUnknownChoice:
    """Resolve an unknown against constructed terms and a question frame.

    ``supersede_alias`` is the explicit correction path when a user or caller
    rejects an earlier adopted alias. All asks still go through Resolver.
    """

    def __init__(self, asker: ClosedChoiceAsker, seed: int = 7):
        _asker_provenance(asker)
        self.resolver = _JSONOptionResolver(asker, seed=seed)
        self._aliases: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        self._alias_history: list[dict[str, Any]] = []
        self._next_id = 1
        self._lock = RLock()

    @property
    def aliases(self) -> dict[tuple[str, tuple[str, ...]], dict[str, Any]]:
        """Return a snapshot so callers cannot mutate the active cache."""
        with self._lock:
            return deepcopy(self._aliases)

    @property
    def alias_history(self) -> list[dict[str, Any]]:
        """Return a snapshot so callers cannot mutate stored testimony."""
        with self._lock:
            return deepcopy(self._alias_history)

    @staticmethod
    def _options(report: Any, frame_vocabulary: Iterable[Any]) -> tuple[list[str], dict[str, list[str]]]:
        unknown = _get(report, "term", "")
        if not isinstance(unknown, str):
            raise TypeError("UnknownReport.term must be a string")
        candidates = _get(report, "candidates", ()) or ()
        origins: dict[str, list[str]] = {}
        for candidate in candidates:
            if not _constructed(candidate):
                continue
            for term in _candidate_terms(candidate, unknown):
                origins.setdefault(term, [])
                if "candidate" not in origins[term]:
                    origins[term].append("candidate")
        for term in _as_terms(frame_vocabulary):
            origins.setdefault(term, [])
            if "frame" not in origins[term]:
                origins[term].append("frame")
        return list(origins), origins

    @staticmethod
    def _key(report: Any, options: list[str]) -> tuple[str, tuple[str, ...]]:
        return str(_get(report, "term", "")), tuple(sorted(options))

    def choose(self, report: UnknownReport, frame_vocabulary: Iterable[str]) -> dict[str, Any]:
        """Return a typed decision, an adopted option if any, and provenance."""
        with self._lock:
            return self._choose(report, frame_vocabulary, supersedes=None, force=False)

    __call__ = choose

    def supersede_alias(self, report: UnknownReport,
                        frame_vocabulary: Iterable[str]) -> dict[str, Any]:
        """Re-ask after an adopted alias was judged wrong, linking its replacement."""
        with self._lock:
            frame_terms = _as_terms(frame_vocabulary)
            self._options(report, frame_terms)
            word = _get(report, "term", "")
            old = None
            for record in reversed(tuple(self._aliases.values())):
                if record.get("word") == word:
                    old = record
                    break
            # A correction retires prior choices for this unknown, including
            # choices made with an older candidate/frame inventory.
            for key, record in tuple(self._aliases.items()):
                if record.get("word") == word:
                    self._aliases.pop(key, None)
            return self._choose(report, frame_terms, supersedes=old, force=True)

    def _choose(self, report: UnknownReport, frame_vocabulary: Iterable[str], *,
                supersedes: Optional[dict[str, Any]], force: bool) -> dict[str, Any]:
        options, origins = self._options(report, frame_vocabulary)
        evidence = _evidence(report)
        key = self._key(report, options)

        if _get(report, "status") != "CANDIDATES":
            return {"decision": "NONE", "option": None,
                    "alias_record": None, "evidence": evidence}
        if not options:
            return {"decision": "NONE", "option": None,
                    "alias_record": None, "evidence": evidence}

        if not force and key in self._aliases:
            record = self._aliases[key]
            choice = record.get("choice")
            if (record.get("status") == "ADOPT" and isinstance(choice, str)
                    and choice in options):
                return {"decision": "ADOPT", "option": choice,
                        "alias_record": deepcopy(record), "evidence": evidence}
            # A corrupted or obsolete cache entry cannot widen the closed list.
            self._aliases.pop(key, None)

        # JSON strings keep untrusted line breaks and delimiters inside one
        # displayed list item. Source spans and candidate reasons are omitted.
        shown = [_prompt_json({"term": term, "from": origins[term]}) for term in options]
        query = _prompt_json(_get(report, "term", ""))
        source = _asker_provenance(self.resolver.asker)
        result = self.resolver.resolve(
            query, shown,
            "Choose only among these constructed terms and question-frame terms.",
        )
        shown_choice = result.get("choice")
        reverse = dict(zip(shown, options))
        option = (reverse.get(shown_choice)
                  if result.get("status") == "ADOPT" and isinstance(shown_choice, str)
                  else None)
        decision: Decision
        if result.get("status") == "ADOPT" and option is not None:
            decision = "ADOPT"
        else:
            # A null choice is not evidence that no relation exists; abstain.
            decision = "UNRESOLVED"
            option = None

        record = {
            "id": f"semantic-unknown-alias-{self._next_id}",
            "op": "alias",
            "scope": "semantic_unknown",
            "word": _get(report, "term", ""),
            "choice": option,
            "status": decision,
            "asks": _plain(result.get("asks", [])),
            "by": source,
            "support": "testimony",
            "supersedes": supersedes.get("id") if supersedes else None,
        }
        self._next_id += 1
        self._alias_history.append(deepcopy(record))
        if decision == "ADOPT":
            self._aliases[key] = deepcopy(record)

        return {"decision": decision, "option": option,
                "alias_record": deepcopy(record), "evidence": evidence}


def choose_unknown(report: UnknownReport, frame_vocabulary: Iterable[str],
                   asker: ClosedChoiceAsker, *, seed: int = 7) -> dict[str, Any]:
    """One-shot convenience wrapper; use SemanticUnknownChoice to reuse aliases."""
    return SemanticUnknownChoice(asker, seed=seed).choose(report, frame_vocabulary)
