"""Finite vocabulary annotations for :mod:`verantyx.conductor` questions.

The project frame supplies the only terms a resolver may select.  The
meaning-assets alias and sense indexes can narrow that list and name why a
term is present, but a shelf redirect is never an adopted project alias.
Only an exact frame term, an active testimony alias, or two agreeing closed
choice asks can resolve an option.  Every other case escalates.

An optional ``chooser`` (``verantyx.llm_choice.LLMChooser``) can be passed, or
set on the frame as ``vocab_chooser``.  It is never used by default.  With a
chooser the candidates are narrowed by role (only terms that can be an option
answer), a single candidate is still asked twice, and an adopted mapping is
recorded as non-evidence testimony that cites its ledger decision.
"""
from __future__ import annotations

import hashlib
import sqlite3
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping, Optional

from . import memory_frame
from .memory_frame import WriteRejected, normalize_np


ResolutionStatus = Literal["EXACT", "ALIAS", "ADOPTED", "ESCALATE"]
_UNSET = object()

# Which (record kind, slot) pairs can be the target of an agent option mapping.
# ``conductor.ProjectFrame._answer_choice`` compares an option's canonical term
# with POLICY.answer (backed by a DECISION), and only for these three question
# kinds.  Every other question kind has no option-mapping role.
_OPTION_SLOT_ROLES = frozenset({("DECISION", "choice"), ("POLICY", "answer")})
_OPTION_ROLES: dict[str, frozenset] = {
    "CHOICE": _OPTION_SLOT_ROLES,
    "DESIGN_PREFERENCE": _OPTION_SLOT_ROLES,
    "FEATURE_SELECTION": _OPTION_SLOT_ROLES,
}
LLM_CHOICE_BY = "llm-choice"
LLM_MAPPING_TYPE = "LLM_TESTIMONY_MAPPING"


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
    support: str = ""            # "frame" (exact) or "testimony" (alias / adopted)
    outcome: str = ""            # typed outcome of the LLM path, "" when it was not used
    ledger_ids: tuple[str, ...] = ()
    chooser_source: str = ""     # "argument" / "frame" / "" (no chooser)
    question_kind: str = ""
    question_kind_source: str = ""   # "explicit" / "classified" / ""


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
        chooser: Any = None,
    ):
        self.frame = frame
        self._chooser = chooser
        self._aliases = aliases
        self._senses = senses
        self._asset_errors: dict[str, str] = {}

    @property
    def memory(self) -> Any:
        return self.frame.memory

    def effective_chooser(self) -> tuple[Any, str]:
        """(chooser, source).  ``(None, "")`` is the default: no model is ever asked."""
        if self._chooser is not None:
            return self._chooser, "argument"
        framed = getattr(self.frame, "vocab_chooser", None)
        if framed is not None:
            return framed, "frame"
        return None, ""

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

    def _frame_term_roles(self) -> dict[str, set[tuple[str, str]]]:
        """Normalized term -> the (record kind, slot) pairs it occupies in the active frame."""
        roles: dict[str, set[tuple[str, str]]] = {}
        for record in self._active_records():
            if record.get("kind") == "ALIAS":
                continue
            kind = str(record.get("kind", ""))
            for slot, value in record.get("slots", {}).items():
                if isinstance(value, str) and value.strip():
                    key = _key(value)
                    if key:
                        roles.setdefault(key, set()).add((kind, str(slot)))
        return roles

    def role_candidates(self, surface: str, question_kind: str) -> tuple[VocabularyCandidate, ...]:
        """``candidates()`` narrowed to terms whose frame role can answer this question kind."""
        allowed = _OPTION_ROLES.get(question_kind, frozenset())
        if not allowed:
            return ()
        roles = self._frame_term_roles()
        return tuple(c for c in self.candidates(surface) if roles.get(_key(c.term), set()) & allowed)

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

    def resolve(self, surface: str, context: str = "", *, question_kind: Optional[str] = None) -> VocabularyResolution:
        """Resolve one option using exact match, adopted alias, then closed choice."""
        return self._resolve(surface, context, question_kind, None)

    def _resolve(self, surface: str, context: str, question_kind: Optional[str],
                 options: Optional[list[str]]) -> VocabularyResolution:
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
                                         asset_status=statuses, support="frame")

        prior, found = self._matching_alias(raw)
        if found:
            if prior.status == "ALIAS":
                prior = replace(prior, support="testimony")
            return prior  # active or attempted testimony always precedes another ask

        candidates = self.candidates(raw)
        statuses = self._asset_status()
        if not candidates:
            return VocabularyResolution(raw, "ESCALATE", asset_status=statuses,
                                        reason="no frame terms match the attested lexical entry")
        chooser, chooser_source = self.effective_chooser()
        if chooser is not None:
            return self._resolve_with_chooser(raw, context, question_kind, options, chooser, chooser_source,
                                              statuses)
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

    def resolve_options(self, options: list[str], context: str = "", *,
                        question_kind: Optional[str] = None) -> tuple[VocabularyResolution, ...]:
        """Annotate each supplied option; this method never selects an option."""
        return tuple(self._resolve(option, context, question_kind, list(options)) for option in options)

    def _resolve_with_chooser(self, raw: str, context: str, question_kind: Optional[str],
                              options: Optional[list[str]], chooser: Any, chooser_source: str,
                              statuses: tuple[str, ...]) -> VocabularyResolution:
        """Opt-in path: role-narrowed candidates, then an LLM closed choice (testimony, not evidence)."""
        from .llm_choice import ChoiceCandidate

        if question_kind is not None:
            kind, kind_source = str(question_kind), "explicit"
        else:
            from .conductor import classify_question

            kind, kind_source = classify_question(context, options), "classified"
        meta = dict(asset_status=statuses, chooser_source=chooser_source, question_kind=kind,
                    question_kind_source=kind_source)
        candidates = self.role_candidates(raw, kind)
        if not candidates:
            why = ("question kind has no option-mapping role" if kind not in _OPTION_ROLES
                   else "no frame term in an option-answer role matches the attested lexical entry")
            return VocabularyResolution(raw, "ESCALATE", reason=why, outcome="NO_ROLE_CANDIDATES", **meta)

        refs = _unique(ref for c in candidates for ref in c.lexical_refs)
        sentences = {str(r.get("id", "")): str(r.get("sentence", "")) for r in self._active_records()}
        asked = [ChoiceCandidate(c.term, tuple(s for s in (sentences.get(i, "") for i in c.frame_record_ids) if s))
                 for c in candidates]
        decision = chooser.choose(raw, asked, question=context)
        ledger_ids = tuple(x for x in (decision.decision_id, *decision.ask_ids, decision.reuse_decision_id) if x)

        if decision.status == "ADOPTED":
            witness = {
                "kind": "testimony", "by": LLM_CHOICE_BY, "scope": "agent-option", "word": raw,
                "asks": [dict(a) for a in decision.asks], "support": "testimony",
                "protocol": "llm_choice/v1", "counts_as_evidence": False, "mapping_type": LLM_MAPPING_TYPE,
                "ledger_decision_id": decision.decision_id,
                "candidate_terms": [c.term for c in candidates],
                "vocabulary_refs": list(refs),
                "frame_record_ids": list(_unique(rid for c in candidates for rid in c.frame_record_ids)),
            }
            record = self.adopt_alias(raw, str(decision.choice), witness=witness)
            return VocabularyResolution(
                raw, "ADOPTED", str(decision.choice), candidates, (record["id"],), refs, statuses,
                support="testimony", outcome="LLM_ADOPTED_CACHED" if decision.cached else "LLM_ADOPTED",
                ledger_ids=ledger_ids, chooser_source=chooser_source, question_kind=kind,
                question_kind_source=kind_source)

        reason = f"{decision.status}: {decision.reason}" + (f" ({decision.detail})" if decision.detail else "")
        if decision.status == "ABSTAINED":
            # An abstention is a recorded attempt; a failure or refusal is not (it must stay retryable).
            self._append_llm_alias_event(raw, decision, candidates)
        return VocabularyResolution(raw, "ESCALATE", candidates=candidates, source_refs=refs, reason=reason,
                                    outcome=f"LLM_{decision.status}:{decision.reason}", ledger_ids=ledger_ids,
                                    **meta)

    def _append_llm_alias_event(self, surface: str, decision: Any,
                                candidates: tuple[VocabularyCandidate, ...]) -> None:
        self.memory._append({
            "op": "alias", "scope": "agent-option", "word": surface, "choice": None,
            "status": "NONE" if decision.reason == "NONE_SELECTED" else "UNRESOLVED",
            "asks": [dict(a) for a in decision.asks], "by": LLM_CHOICE_BY, "support": "testimony",
            "candidate_terms": [c.term for c in candidates],
            "vocabulary_refs": list(_unique(ref for c in candidates for ref in c.lexical_refs)),
            "record_id": None, "ledger_decision_id": decision.decision_id, "reason": decision.reason,
            "ts": self.memory.now(),
        })

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
        elif by == LLM_CHOICE_BY:
            self._validate_llm_choice(witness, raw, target[0])
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
        if by == LLM_CHOICE_BY:
            # typed as constructed testimony whatever the caller wrote
            provenance.update({"counts_as_evidence": False, "mapping_type": LLM_MAPPING_TYPE})
        record = self.memory.write("ALIAS", "vocabulary testimony", witness=provenance,
                                   supersedes=supersedes, subject=alias_key, value=target[0])
        event = {
            "op": "alias", "scope": "agent-option", "word": raw,
            "choice": target[0], "status": "ADOPT", "asks": provenance.get("asks", []),
            "by": by, "support": "testimony",
            "candidate_terms": list(provenance.get("candidate_terms", [target[0]])),
            "vocabulary_refs": list(provenance.get("vocabulary_refs", [])),
            "record_id": record["id"], "supersedes": supersedes, "ts": self.memory.now(),
        }
        if "ledger_decision_id" in provenance:
            event["ledger_decision_id"] = provenance["ledger_decision_id"]
            event["mapping_type"] = provenance.get("mapping_type")
            event["counts_as_evidence"] = False
        self.memory._append(event)
        return record

    def _validate_llm_choice(self, witness: Mapping[str, Any], word: str, canonical: str) -> None:
        """An ``llm-choice`` witness is only as good as the ledger decision it cites."""
        chooser, _source = self.effective_chooser()
        ledger = getattr(chooser, "ledger", None)
        verify = getattr(ledger, "verify_adoption", None)
        if verify is None:
            raise WriteRejected("llm-choice testimony needs a chooser with a ledger to check it against")
        decision_id = witness.get("ledger_decision_id")
        terms = witness.get("candidate_terms")
        if not isinstance(decision_id, str) or not decision_id or not isinstance(terms, (list, tuple)) or not terms:
            raise WriteRejected("llm-choice testimony must cite a ledger decision and its candidate terms")
        if not verify(decision_id, word, canonical, list(terms)):
            raise WriteRejected("the ledger holds no ADOPTED decision matching this word, choice and candidates")

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
