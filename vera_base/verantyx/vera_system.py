"""One typed facade over Vera's semantic answer and construction paths.

Answers stay on the semantic producer/checker path.  Generation, outside
explanation, and project work are separate typed handoffs with their own
provenance and never become document answers or evidence.
"""
from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from .one import Vera
from .semantic_fast import SharedIndex
from .semantic_generate import GeneratedText, generate as generate_text
from .semantic_outside import OutsideResult, explain_outside


@dataclass(frozen=True)
class BandAnnotation:
    """Non-voting result of the independent semantic structure check."""

    status: str
    value: Any = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "value": _plain(self.value), "reason": self.reason}


@dataclass(frozen=True)
class RouteRefusal:
    """A closed-pattern chat refusal that says what would resolve the route."""

    kind: str
    verdict: str
    text: str
    missing: str
    answer: bool = False
    evidence: bool = False
    testimony: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "verdict": self.verdict,
            "text": self.text,
            "missing": self.missing,
            "answer": self.answer,
            "evidence": self.evidence,
            "testimony": self.testimony,
        }


@dataclass(frozen=True)
class VeraSystemResult:
    """A capability result with an explicit payload and provenance envelope."""

    capability: str
    payload: Any
    provenance: Any
    generated: bool = False
    band: Optional[BandAnnotation] = None

    @property
    def verdict(self) -> str:
        if isinstance(self.payload, RouteRefusal):
            return self.payload.verdict
        if self.capability == "conduct":
            return "COMPLETE" if bool(getattr(self.payload, "complete", False)) else "INCOMPLETE"
        if self.capability in {"say", "summarize", "explain"}:
            if isinstance(self.payload, GeneratedText) or isinstance(self.payload, OutsideResult):
                return "CONSTRUCTED"
            return str(getattr(self.payload, "reason", "REFUSED"))
        if isinstance(self.payload, Mapping):
            return str(self.payload.get("verdict", "UNKNOWN"))
        return str(getattr(self.payload, "verdict", "UNKNOWN"))

    @property
    def answer(self) -> bool:
        return self.capability == "ask" and self.verdict == "ANSWER"

    @property
    def evidence(self) -> Any:
        if self.capability == "ask" and isinstance(self.payload, Mapping):
            return self.payload.get("evidence", []) or []
        return False

    @property
    def testimony(self) -> bool:
        # Outside-choice testimony lives in its own payload field.  The
        # constructed surface itself never has testimony authority.
        return False

    @property
    def text(self) -> str:
        if isinstance(self.payload, Mapping):
            return str(self.payload.get("text", ""))
        return str(getattr(self.payload, "text", ""))

    @property
    def kind(self) -> str:
        if isinstance(self.payload, Mapping):
            return str(self.payload.get("kind", self.capability))
        return str(getattr(self.payload, "kind", self.capability))

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "kind": self.kind,
            "verdict": self.verdict,
            "text": self.text,
            "result": _plain(self.payload),
            "provenance": _plain(self.provenance),
            "generated": self.generated,
            "answer": self.answer,
            "evidence": _plain(self.evidence),
            "testimony": self.testimony,
            "band": self.band.as_dict() if self.band is not None else None,
        }

    to_dict = as_dict

    def __getitem__(self, key: str) -> Any:
        if key == "result":
            return self.payload
        if key == "provenance":
            return self.provenance
        if key == "band":
            return self.band
        if key in {"capability", "verdict", "text", "generated", "answer", "evidence", "testimony", "kind"}:
            return getattr(self, key)
        if isinstance(self.payload, Mapping):
            return self.payload[key]
        return self.as_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, TypeError):
            return default


def _plain(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return _plain(value.as_dict())
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name)) for name in value.__dataclass_fields__}
    return value


def _source_spans(value: Any) -> list[Any]:
    if isinstance(value, GeneratedText):
        rows = []
        for sentence in value.sentences:
            rows.extend(sentence.spans)
        for quote in value.quotes:
            rows.extend(quote.spans)
        return [_plain(span) for span in rows]
    if isinstance(value, OutsideResult) and value.construction is not None:
        return [_plain(item) for item in value.construction.provenance]
    spans = getattr(value, "spans", ())
    return [_plain(span) for span in spans]


class VeraSystem:
    """Facade over semantic asking, verified construction, and a project frame.

    ``documents`` accepts a source-to-text mapping, a path, or an iterable of
    document paths.  A frame can be a parsed spec, compiled frame, project
    frame, DSL text, or a path to the DSL.  If a raw frame has no supplied
    memory, a private temporary memory directory is kept until ``close``.
    """

    _ASK_PREFIX = re.compile(r"^\s*ask\s*[: ]\s*(.+?)\s*$", re.IGNORECASE)
    _SAY_PREFIX = re.compile(r"^\s*say\s*[: ]\s*(.+?)\s*$", re.IGNORECASE)
    _EXPLAIN_PREFIX = re.compile(r"^\s*explain\s*[: ]\s*(.+?)\s*$", re.IGNORECASE)
    _SUMMARY_PREFIX = re.compile(r"^\s*(?:summarize|summary)\s*[: ]\s*(.+?)\s*$", re.IGNORECASE)
    _CONDUCT_PREFIX = re.compile(r"^\s*(?:conduct|run\s+project)\b", re.IGNORECASE)
    _PLAIN_QUESTION = re.compile(r"(?:[?？]|か[。．]?)\s*$|(?:何|誰|だれ|どこ|いつ|なぜ|どうして|どう|どの|いくつ|いくら).*[。．?？]?\s*$")
    _JP_SUMMARY = re.compile(r"^\s*(.+?)(?:について)?(?:要約|まとめ)(?:して|て|を)?[。！!？?]*\s*$")

    def __init__(self, documents: Any, frame: Any = None, memory: Any = None,
                 asker: Any = None):
        if isinstance(documents, Mapping):
            if not all(isinstance(key, str) and isinstance(value, str)
                       for key, value in documents.items()):
                raise TypeError("documents mapping must contain string source names and text")
            self.vera = Vera.from_texts(dict(documents), mode="semantic")
        else:
            paths = [documents] if isinstance(documents, (str, os.PathLike)) else list(documents)
            self.vera = Vera.from_texts({}, mode="semantic")
            if paths:
                self.vera.load_documents(paths)

        self.asker = asker
        self._tempdir: Optional[tempfile.TemporaryDirectory[str]] = None
        self.frame_spec = None
        self.frame_compilation = None
        self.project_frame = None
        self.memory = memory
        if frame is not None:
            self._prepare_frame(frame, memory)

        self.shared_index: Optional[SharedIndex] = None
        self._indexed_view = None
        self._ensure_shared_index()

    @property
    def view(self) -> Any:
        bot = getattr(self.vera, "bot", None)
        if bot is not None and getattr(self.vera, "_semantic_generation", None) != getattr(bot, "_semantic_generation", 0):
            self.vera._make_semantic_view()
        return getattr(self.vera, "_semantic_view", None)

    def _prepare_frame(self, frame: Any, memory: Any) -> None:
        from . import project_frame

        if isinstance(frame, project_frame.Compilation):
            self.frame_compilation = frame
            self.project_frame = frame.conductor
            self.frame_spec = frame.spec
            self.memory = frame.memory
            return
        if isinstance(frame, project_frame.ProjectFrameSpec):
            spec = frame
        elif isinstance(frame, (str, os.PathLike)):
            frame_path = Path(frame)
            if frame_path.is_file():
                spec = project_frame.load_frame(frame_path)
            else:
                spec = project_frame.parse_frame(str(frame), source="<frame>")
        elif (hasattr(frame, "memory") and hasattr(frame, "answer")
              and callable(getattr(frame, "_active", None))):
            self.project_frame = frame
            self.memory = frame.memory
            return
        else:
            raise TypeError("frame must be a ProjectFrameSpec, compiled frame, ProjectFrame, DSL text, or path")

        selected_memory = memory
        if selected_memory is None:
            self._tempdir = tempfile.TemporaryDirectory(prefix=".vera-system-", dir=os.getcwd())
            selected_memory = str(Path(self._tempdir.name) / "memory.jsonl")
        self.frame_compilation = project_frame.compile_frame(spec, selected_memory)
        self.frame_spec = spec
        self.project_frame = self.frame_compilation.conductor
        self.memory = self.frame_compilation.memory

    def _ensure_shared_index(self) -> Optional[SharedIndex]:
        view = self.view
        if view is None:
            self.shared_index = None
            self._indexed_view = None
            return None
        if self.shared_index is None or self._indexed_view is not view:
            self.shared_index = SharedIndex(view)
            self._indexed_view = view
        elif not self.shared_index.is_current(view):
            self.shared_index.refresh(view)
        return self.shared_index

    def _index_context(self, *, terms: Iterable[str] = (), kind: str = "terms") -> dict[str, Any]:
        index = self._ensure_shared_index()
        if index is None:
            return {"available": False, "authority": "navigation_only"}
        terms = tuple(term for term in terms if isinstance(term, str) and term)
        if kind == "summary":
            clauses = index.summary.clauses(terms)
            docs = index.realize.documents_for_clauses(clauses)
        elif kind == "units":
            clauses = index.unknown.unit_clauses(terms)
            docs = index.realize.documents_for_clauses(clauses)
        else:
            clauses = index.clauses_for_terms(terms)
            docs = index.realize.documents_for_clauses(clauses)
        return {
            "available": True,
            "authority": "navigation_only_not_evidence",
            "terms": list(terms),
            "candidate_clause_ids": [str(getattr(clause, "id", "")) for clause in clauses],
            "candidate_sources": list(docs),
            "index_stats": index.stats(),
        }

    def ask(self, text: str) -> VeraSystemResult:
        """Answer through the semantic route and add a non-voting band annotation."""
        if not isinstance(text, str):
            raise TypeError("question must be text")
        from . import question, semantic_band

        raw = dict(self.vera.ask(text, mode="semantic"))
        band_value = None
        if raw.get("verdict") == "ANSWER":
            request = question.read_semantic(text).value
            band_value = semantic_band.band(self.view, request, raw)
            if band_value is None:
                annotation = BandAnnotation(
                    "ABSTAINED", None,
                    "no audited independent semantic structure is available",
                )
            else:
                annotation = BandAnnotation("AVAILABLE", band_value)
        else:
            annotation = BandAnnotation("NOT_APPLICABLE", None, "the semantic path did not verify an ANSWER")
        raw["band"] = annotation.as_dict()
        trace = list(raw.get("trace", ()))
        trace.append({
            "part": "semantic_band.band",
            "status": "abstained" if annotation.status == "ABSTAINED" else "ran",
            "reason": annotation.reason,
            "non_voting": True,
        })
        raw["trace"] = trace
        provenance = {
            "route": "Vera(mode='semantic')",
            "sources": raw.get("sources", []) or [],
            "evidence": raw.get("evidence", []) or [],
            "trace": trace,
            "shared_index": (self.shared_index.stats() if self.shared_index is not None else None),
        }
        return VeraSystemResult("ask", raw, provenance, band=annotation)

    def say(self, request: str, style: str = "plain") -> VeraSystemResult:
        """Generate only source-checked text, optionally from a verified answer."""
        asked = self.ask(request)
        view = self.view
        index_context = self._index_context(terms=(request,), kind="terms")
        generated = generate_text(view, {"kind": "answer", "result": asked.payload}, style=style)
        source_refs = list((asked.payload.get("sources", []) or []))
        provenance = {
            "source_spans": _source_spans(generated),
            "verified_answer_verdict": asked.verdict,
            "source_refs": source_refs,
            "shared_index": index_context,
            "authority": "constructed_verified_text_not_answer_testimony_or_evidence",
        }
        return VeraSystemResult("say", generated, provenance, generated=isinstance(generated, GeneratedText))

    def explain(self, term: str) -> VeraSystemResult:
        """Construct a marked outside-closure explanation with optional testimony."""
        if not isinstance(term, str):
            raise TypeError("term must be text")
        view = self.view
        if view is None:
            refusal = RouteRefusal(
                "outside_refusal", "NO_SOURCE_VIEW", "構成的説明を作れません。",
                "load source documents so the outside-closure route has a View",
            )
            return VeraSystemResult(
                "explain", refusal,
                {"term": term, "source_view": None, "missing": refusal.missing},
            )
        value = explain_outside(view, term, asker=self.asker)
        index_context = self._index_context(terms=(term,), kind="units")
        provenance = {
            "candidate_provenance": _source_spans(value),
            "view_sources_consulted": sorted((getattr(view, "sources", {}) or {}).keys()),
            "shared_index": index_context,
            "authority": "constructed_outside_explanation_not_answer_or_evidence",
        }
        return VeraSystemResult("explain", value, provenance, generated=True)

    def summarize(self, entity: str, *, limit: int = 8, style: str = "plain") -> VeraSystemResult:
        """Assemble a provenance-bearing summary from verified source clauses."""
        if not isinstance(entity, str):
            raise TypeError("summary entity must be text")
        stripped = entity.strip()
        index_context = self._index_context(terms=(stripped,), kind="summary")
        if ("について" in stripped and any(mark in stripped for mark in ("要約", "まとめ"))):
            generated = generate_text(self.view, stripped, style=style)
        else:
            generated = generate_text(
                self.view,
                {"kind": "summary", "entity": stripped, "limit": limit},
                style=style,
            )
        provenance = {
            "source_spans": _source_spans(generated),
            "source_refs": (sorted((getattr(self.view, "sources", {}) or {}).keys())
                            if self.view is not None else []),
            "shared_index": index_context,
            "authority": "constructed_verified_summary_not_answer_testimony_or_evidence",
        }
        return VeraSystemResult("summarize", generated, provenance, generated=isinstance(generated, GeneratedText))

    def conduct(self, adapter: Any = None, **kwargs: Any) -> VeraSystemResult:
        """Run the compiled human frame through the supplied work adapter."""
        from . import conductor_run

        if self.project_frame is None:
            refusal = RouteRefusal(
                "conductor_refusal", "NO_FRAME", "Project conduct is unavailable.",
                "supply a parsed or compiled human project frame",
            )
            return VeraSystemResult("conduct", refusal, {"frame": None})
        if adapter is None:
            refusal = RouteRefusal(
                "conductor_refusal", "NO_ADAPTER", "Project conduct is unavailable.",
                "supply an adapter implementing start, poll, send, and stop",
            )
            return VeraSystemResult("conduct", refusal, {"frame": _frame_provenance(self)})
        result = conductor_run.run_project(self.project_frame, adapter, **kwargs)
        provenance = {
            "frame": _frame_provenance(self),
            "outcomes": _plain(result.outcomes),
            "handoffs": _plain(result.handoffs),
            "agent_output_is_evidence": False,
        }
        return VeraSystemResult("conduct", result, provenance)

    def dispatch(self, line: str, *, adapter: Any = None) -> VeraSystemResult:
        """Route only recognized closed patterns to a facade capability."""
        if not isinstance(line, str):
            raise TypeError("chat line must be text")
        value = line.strip()
        if not value:
            return self._route_refusal("", "write a capability prefix and its request")
        match = self._SAY_PREFIX.match(value)
        if match:
            return self.say(match.group(1))
        match = self._EXPLAIN_PREFIX.match(value)
        if match:
            return self.explain(match.group(1))
        match = self._SUMMARY_PREFIX.match(value)
        if match:
            return self.summarize(match.group(1))
        if self._CONDUCT_PREFIX.match(value):
            return self.conduct(adapter)
        match = self._ASK_PREFIX.match(value)
        if match:
            return self.ask(match.group(1))
        japanese_summary = self._JP_SUMMARY.match(value)
        if japanese_summary:
            return self.summarize(japanese_summary.group(1).strip())
        if self._PLAIN_QUESTION.search(value):
            return self.ask(value)
        return self._route_refusal(value, "prefix with ask:, say:, explain:, summarize:, or conduct:")

    def _route_refusal(self, line: str, missing: str) -> VeraSystemResult:
        refusal = RouteRefusal(
            "route_refusal", "UNCLASSIFIABLE", "入力の機能を分類できません。", missing,
        )
        return VeraSystemResult(
            "route_refusal", refusal,
            {"classifier": "closed_patterns_v1", "input": line, "missing": missing},
        )

    def close(self) -> None:
        self.vera.close()
        if self._tempdir is not None:
            self._tempdir.cleanup()
            self._tempdir = None

    def __enter__(self) -> "VeraSystem":
        return self

    def __exit__(self, _kind: Any, _value: Any, _traceback: Any) -> None:
        self.close()


def _frame_provenance(system: VeraSystem) -> dict[str, Any]:
    frame = system.project_frame
    if frame is None:
        return {"present": False, "record_ids": []}
    if system.frame_compilation is not None:
        records = system.frame_compilation.records
    else:
        try:
            records = frame.memory.active(require_fresh=True)
        except (AttributeError, OSError, ValueError):
            records = []
    return {
        "present": True,
        "source": getattr(system.frame_spec, "source", "compiled-frame"),
        "record_ids": [str(row.get("id", "")) for row in records if isinstance(row, Mapping)],
    }


__all__ = ["BandAnnotation", "RouteRefusal", "VeraSystem", "VeraSystemResult"]
