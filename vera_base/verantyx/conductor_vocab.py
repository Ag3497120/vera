"""Finite vocabulary annotations for :mod:`verantyx.conductor` questions.

The project frame supplies the only terms a resolver may select.  The
meaning-assets alias and sense indexes can narrow that list and name why a
term is present, but a shelf redirect is never an adopted project alias.
Only an exact frame term, an active testimony alias, or two agreeing closed
choice asks can resolve an option.  Every other case escalates.
"""
from __future__ import annotations

import hashlib
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

from . import memory_frame
from .memory_frame import WriteRejected, normalize_np


ResolutionStatus = Literal["EXACT", "ALIAS", "ADOPTED", "ESCALATE"]
_UNSET = object()


@dataclass(frozen=True)
class VocabularyCandidate:
    """One frame term and the finite, named records that made it eligible."""

    term: str
    frame_record_ids: tuple[str, ...] = ()
    lexical_refs: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class VocabularyResolution:
    """A non-voting annotation for one option in an agent question."""

    surface: str
    status: ResolutionStatus
    canonical: Optional[str] = None
    candidates: tuple[VocabularyCandidate, ...] = ()
    record_ids: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    asset_status: tuple[str, ...] = ()
    reason: str = ""


def _key(value: str) -> str:
    return normalize_np(unicodedata.normalize("NFKC", value).strip()).casefold()


def _get(mapping: Any, key: str) -> Any:
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        try:
            return mapping[key]
        except (KeyError, TypeError):
            return None


def _unique(values: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _sense_rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        value = value.get("senses", (value,))
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(row for row in value if isinstance(row, Mapping))


class ConductorVocabulary:
    """Resolve agent option spellings against one frame's closed vocabulary.

    ``aliases`` and ``senses`` are keyed lookups from ``meaning_assets``;
    pass small mappings to make a pinned/demo shelf.  Missing sidecars are
    reported and do not stop exact frame matching.  A unique shelf redirect
    is still only a candidate annotation: it must not create an ``ALIAS``
    record or silently select a project option.
    """

    def __init__(
        self,
        frame: Any,
        *,
        aliases: Any = _UNSET,
        senses: Any = _UNSET,
    ):
        self.frame = frame
        self._aliases = aliases
        self._senses = senses
        self._asset_errors: dict[str, str] = {}

    @property
    def memory(self) -> Any:
        return self.frame.memory

    def _load(self, name: str) -> Any:
        attr = "_" + name
        value = getattr(self, attr)
        if value is not _UNSET:
            return value
        try:
            from . import meaning_assets

            value = getattr(meaning_assets, name)()
        except (OSError, ValueError, KeyError, RuntimeError, ImportError, sqlite3.Error) as exc:
            self._asset_errors[name] = type(exc).__name__
            value = {}
        setattr(self, attr, value)
        return value

    def _asset_status(self) -> tuple[str, ...]:
        out = []
        for name in ("aliases", "senses"):
            if name in self._asset_errors:
                out.append(f"{name}:ASSET_MISSING")
            elif getattr(self, "_" + name) is _UNSET:
                out.append(f"{name}:NOT_LOADED")
            else:
                out.append(f"{name}:AVAILABLE")
        return tuple(out)

    def _active_records(self) -> list[dict[str, Any]]:
        active = getattr(self.frame, "_active", None)
        if callable(active):
            return list(active())
        return list(self.memory.active(require_fresh=True))

    def _frame_terms(self) -> dict[str, tuple[str, tuple[str, ...]]]:
        terms: dict[str, tuple[str, list[str]]] = {}
        for record in self._active_records():
            if record.get("kind") == "ALIAS":
                # ALIAS.subject is an internal stable key.  Its target is not
                # allowed to keep a superseded frame term alive by itself.
                continue
            rid = str(record.get("id", ""))
            slots = record.get("slots", {})
            for value in slots.values():
                if not isinstance(value, str) or not value.strip():
                    continue
                key = _key(value)
                if not key:
                    continue
                if key not in terms:
                    terms[key] = (value.strip(), [])
                if rid:
                    terms[key][1].append(rid)
        return {key: (value, _unique(ids)) for key, (value, ids) in terms.items()}

    def frame_terms(self) -> tuple[str, ...]:
        """Return the frame's canonical terms in stable display order."""
        values = {value for value, _ids in self._frame_terms().values()}
        return tuple(sorted(values, key=lambda value: (_key(value), value)))

    def candidates(self, surface: str) -> tuple[VocabularyCandidate, ...]:
        """Build finite candidates from frame terms plus keyed lexical hints.

        All sense rows are retained.  Context is intentionally not used to
        pick one: an ambiguous shelf term remains a set of candidates for the
        closed-choice asker or a typed escalation.
        """
        terms = self._frame_terms()
        alias_map = self._load("aliases")
        sense_map = self._load("senses")
        evidence: dict[str, dict[str, set[str]]] = {}
        lexical_entry = False

        def add(term: Any, ref: str, domain: str = "") -> None:
            if not isinstance(term, str):
                return
            hit = terms.get(_key(term))
            if hit is None:
                return
            key = _key(hit[0])
            row = evidence.setdefault(key, {"refs": set(), "domains": set()})
            row["refs"].add(ref)
            if domain:
                row["domains"].add(domain)

        alias_target = _get(alias_map, surface)
        if isinstance(alias_target, str) and alias_target.strip():
            lexical_entry = True
            add(alias_target, f"jawiki:alias:{surface}")

        rows = _sense_rows(_get(sense_map, surface))
        if rows:
            lexical_entry = True
            for row in rows:
                add(row.get("core"), f"jawiki:senses:{surface}", str(row.get("domain_tag", "")))

        # Known lexical entries that do not touch this frame produce no
        # candidates.  Unknown surfaces may still be asked against the whole
        # frame vocabulary, which remains finite and is never extended.
        if lexical_entry:
            selected = evidence
        else:
            selected = {
                key: {"refs": set(), "domains": set()}
                for key in terms
            }

        out = []
        for key in sorted(selected, key=lambda k: (_key(terms[k][0]), terms[k][0])):
            value, ids = terms[key]
            detail = selected[key]
            out.append(VocabularyCandidate(
                value, ids, tuple(sorted(detail["refs"])), tuple(sorted(detail["domains"]))))
        return tuple(out)

    def _matching_alias(self, surface: str) -> tuple[Optional[VocabularyResolution], bool]:
        active = [record for record in self._active_records()
                  if record.get("kind") == "ALIAS"
                  and (record.get("witness") or {}).get("scope") == "agent-option"
                  and (record.get("witness") or {}).get("word") == surface]
        events = getattr(self.memory, "aliases", {})
        event = events.get(("agent-option", surface)) if hasattr(events, "get") else None
        if not active:
            if event is None:
                return None, False
            return VocabularyResolution(
                surface, "ESCALATE", asset_status=self._asset_status(),
                reason=f"prior alias attempt is {event.get('status', 'inconsistent')} without an active testimony record"), True

        values = {_key(str(record.get("slots", {}).get("value", ""))) for record in active}
        if len(values) != 1:
            return VocabularyResolution(
                surface, "ESCALATE", record_ids=_unique(r.get("id") for r in active),
                asset_status=self._asset_status(), reason="active testimony aliases conflict"), True
        target_key = next(iter(values))
        terms = self._frame_terms()
        target = terms.get(target_key)
        if target is None:
            return VocabularyResolution(
                surface, "ESCALATE", record_ids=_unique(r.get("id") for r in active),
                asset_status=self._asset_status(), reason="adopted alias target is outside the active frame vocabulary"), True
        if event is None or event.get("status") != "ADOPT" or _key(str(event.get("choice", ""))) != target_key:
            return VocabularyResolution(
                surface, "ESCALATE", record_ids=_unique(r.get("id") for r in active),
                asset_status=self._asset_status(), reason="alias event and typed testimony disagree"), True
        return VocabularyResolution(
            surface, "ALIAS", target[0], record_ids=_unique(r.get("id") for r in active),
            source_refs=("frame:ALIAS testimony",), asset_status=self._asset_status()), True

    def resolve(self, surface: str, context: str = "") -> VocabularyResolution:
        """Resolve one option using exact match, adopted alias, then closed choice."""
        raw = surface.strip() if isinstance(surface, str) else ""
        statuses = self._asset_status()
        if not raw:
            return VocabularyResolution(surface or "", "ESCALATE", asset_status=statuses,
                                        reason="option is empty")

        terms = self._frame_terms()
        exact = terms.get(_key(raw))
        if exact is not None:
            ids = exact[1]
            candidate = VocabularyCandidate(exact[0], ids)
            return VocabularyResolution(raw, "EXACT", exact[0], (candidate,), ids,
                                         asset_status=statuses)

        prior, found = self._matching_alias(raw)
        if found:
            return prior  # active or attempted testimony always precedes another ask

        candidates = self.candidates(raw)
        statuses = self._asset_status()
        if not candidates:
            return VocabularyResolution(raw, "ESCALATE", asset_status=statuses,
                                        reason="no frame terms match the attested lexical entry")
        resolver = getattr(self.memory, "resolver", None)
        if resolver is None:
            return VocabularyResolution(raw, "ESCALATE", candidates=candidates,
                                        asset_status=statuses, reason="no closed-choice asker is configured")
        if len(candidates) < 2:
            refs = _unique(ref for candidate in candidates for ref in candidate.lexical_refs)
            return VocabularyResolution(raw, "ESCALATE", candidates=candidates, source_refs=refs,
                                        asset_status=statuses,
                                        reason="a single lexical candidate cannot adopt a project alias")

        options = [candidate.term for candidate in candidates]
        result = self._closed_choice(raw, context, options, resolver)
        if result["status"] != "ADOPT":
            self._append_alias_event(raw, result, candidates)
            return VocabularyResolution(raw, "ESCALATE", candidates=candidates,
                                        source_refs=_unique(ref for c in candidates for ref in c.lexical_refs),
                                        asset_status=statuses,
                                        reason=result.get("why", result["status"]))

        witness = {
            "kind": "testimony", "by": "llm-closed-choice", "scope": "agent-option",
            "word": raw, "asks": result["asks"], "support": "testimony",
            "candidate_terms": options,
            "vocabulary_refs": list(_unique(ref for c in candidates for ref in c.lexical_refs)),
            "frame_record_ids": list(_unique(rid for c in candidates for rid in c.frame_record_ids)),
        }
        record = self.adopt_alias(raw, str(result["choice"]), witness=witness)
        return VocabularyResolution(raw, "ADOPTED", str(result["choice"]), candidates,
                                    (record["id"],),
                                    _unique(ref for c in candidates for ref in c.lexical_refs), statuses)

    def resolve_options(self, options: list[str], context: str = "") -> tuple[VocabularyResolution, ...]:
        """Annotate each supplied option; this method never selects an option."""
        return tuple(self.resolve(option, context) for option in options)

    def adopt_alias(
        self,
        surface: str,
        canonical: str,
        *,
        witness: Mapping[str, Any],
        supersedes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record a testimony alias to an active frame term, optionally correcting one.

        Human testimony may explicitly correct an earlier alias.  A
        ``llm-closed-choice`` witness must carry two differently ordered,
        independently worded asks that select the same supplied candidate.
        Shelf aliases alone are never accepted as adoption provenance.
        """
        if not isinstance(surface, str) or not surface.strip():
            raise WriteRejected("alias surface must be a nonempty string")
        raw = surface.strip()
        terms = self._frame_terms()
        target = terms.get(_key(canonical))
        if target is None:
            raise WriteRejected("alias target is outside the active frame vocabulary")
        if _key(raw) in terms:
            raise WriteRejected("an exact frame term cannot be replaced by an alias")
        if not isinstance(witness, Mapping) or witness.get("kind") != "testimony":
            raise WriteRejected("adopted aliases require typed testimony provenance")
        by = str(witness.get("by", ""))
        if by == "llm-closed-choice":
            self._validate_closed_choice(witness, target[0])
        elif not by.startswith("human:"):
            raise WriteRejected("alias adoption must cite closed-choice asks or an identified human")

        active_aliases = [record for record in self._active_records()
                          if record.get("kind") == "ALIAS"
                          and (record.get("witness") or {}).get("scope") == "agent-option"
                          and (record.get("witness") or {}).get("word") == raw]
        active_ids = {str(record.get("id")) for record in active_aliases}
        if active_aliases and supersedes not in active_ids:
            raise WriteRejected("correcting an active alias must supersede its testimony record")
        if not active_aliases and supersedes:
            raise WriteRejected("supersession target is not an active alias for this surface")
        if supersedes and supersedes not in active_ids:
            raise WriteRejected("supersession target is not an active alias for this surface")

        alias_key = "term" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        provenance = dict(witness)
        provenance.update({"kind": "testimony", "scope": "agent-option", "word": raw,
                           "support": "testimony", "canonical": target[0]})
        record = self.memory.write("ALIAS", "vocabulary testimony", witness=provenance,
                                   supersedes=supersedes, subject=alias_key, value=target[0])
        self.memory._append({
            "op": "alias", "scope": "agent-option", "word": raw,
            "choice": target[0], "status": "ADOPT", "asks": provenance.get("asks", []),
            "by": by, "support": "testimony",
            "candidate_terms": list(provenance.get("candidate_terms", [target[0]])),
            "vocabulary_refs": list(provenance.get("vocabulary_refs", [])),
            "record_id": record["id"], "supersedes": supersedes, "ts": self.memory.now(),
        })
        return record

    @staticmethod
    def _validate_closed_choice(witness: Mapping[str, Any], canonical: str) -> None:
        options = witness.get("candidate_terms")
        asks = witness.get("asks")
        if not isinstance(options, (list, tuple)) or len(options) < 2 or not isinstance(asks, list) or len(asks) != 2:
            raise WriteRejected("closed-choice testimony needs two asks over at least two frame candidates")
        if canonical not in options:
            raise WriteRejected("closed-choice testimony selected a term outside its candidate list")
        variants = set()
        orders = []
        picks = []
        for ask in asks:
            if not isinstance(ask, Mapping):
                raise WriteRejected("closed-choice ask provenance is malformed")
            variant = ask.get("variant")
            order = ask.get("order")
            picked = ask.get("picked")
            if variant not in (0, 1) or not isinstance(order, list) or sorted(order) != list(range(len(options))):
                raise WriteRejected("closed-choice ask order is malformed")
            if not isinstance(picked, int) or isinstance(picked, bool) or not 0 <= picked < len(options):
                raise WriteRejected("closed-choice ask did not return a valid candidate index")
            variants.add(variant)
            orders.append(order)
            picks.append(picked)
        if variants != {0, 1} or picks[0] != picks[1] or options[picks[0]] != canonical:
            raise WriteRejected("the independent closed-choice asks do not agree on this alias")
        if orders[0] == orders[1]:
            raise WriteRejected("the closed-choice asks did not use independent candidate orders")

    def _closed_choice(self, surface: str, context: str, options: list[str], resolver: Any) -> dict[str, Any]:
        asks = []
        for variant in (0, 1):
            order = list(range(len(options)))
            if variant:
                order.reverse()
            shown = [options[i] for i in order]
            prompt = resolver._prompt(surface, context, shown, variant)
            reply = resolver.asker(prompt)
            picked = memory_frame.parse_choice(reply, len(shown))
            real = False if picked is False else (None if picked is None else order[picked])
            asks.append({"variant": variant, "order": order, "reply": (reply or "")[:200], "picked": real})
        a, b = asks[0]["picked"], asks[1]["picked"]
        if a is False or b is False:
            return {"status": "UNRESOLVED", "why": "invalid closed-choice answer", "choice": None, "asks": asks}
        if a is None and b is None:
            return {"status": "NONE", "why": "no listed frame term was selected", "choice": None, "asks": asks}
        if a == b:
            return {"status": "ADOPT", "choice": options[a], "asks": asks}
        return {"status": "UNRESOLVED", "why": "the two closed-choice asks disagree", "choice": None, "asks": asks}

    def _append_alias_event(
        self,
        surface: str,
        result: Mapping[str, Any],
        candidates: tuple[VocabularyCandidate, ...],
    ) -> None:
        self.memory._append({
            "op": "alias", "scope": "agent-option", "word": surface,
            "choice": result.get("choice"), "status": result.get("status"),
            "asks": result.get("asks", []), "by": "llm-closed-choice",
            "support": "testimony", "candidate_terms": [c.term for c in candidates],
            "vocabulary_refs": list(_unique(ref for c in candidates for ref in c.lexical_refs)),
            "record_id": result.get("record_id"), "ts": self.memory.now(),
        })


__all__ = ["ConductorVocabulary", "VocabularyCandidate", "VocabularyResolution"]
