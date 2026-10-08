"""W6-a: the basis policy -- what a generated corpus may show a user, and under which type.

One typed table (pre-registered in ``docs/BASIS_POLICY.md``) decides. The inputs are

  (1) the kind of request (``factual`` asks for a fact; ``creative / paraphrase / style / example``
      do not claim one),
  (2) the origins of the cited basis (human-written / generated / none),
  (3) whether a human is present (``--human-present``),
  (4) whether the user switched the reference column on (``--show-generated-reference``, off by default).

The output is a closed type (``OUTCOMES``). Sentences a model wrote are never evidence for a fact:
they may only be (C) a phrasing for content a human source already carries, (E) material for a
request that claims no fact (typed ``constructed``), (D) a question put to the user whose "yes"
becomes a *human-written* record in the sovereign memory, or (B) a separate, opt-in reference
column. Nothing here reads a clock or a random source; every branch of ``decide`` is one table
lookup.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import ability_corpus

SCHEMA = "verantyx.basis_policy/1"
TABLE_VERSION = 1
#: W5-c: the 24-row table is unchanged (``TABLE_VERSION`` stays 1); the rules that sit beside it carry their
#: own versions (docs/BASIS_POLICY.md, sections ``prereg-w5c`` and ``prereg-w5c-r3``).
#: W5-e (A-3): version 4 -- ``human_confirmed`` is a human source only for ``family == "memory_sovereign"`` (docs/BASIS_POLICY.md, W5-e).
CLASSIFY_VERSION = 5
CONFIRM_ID_VERSION = 2
#: the basis of a source set that holds a source whose origin is unknown: not human, not (known to be) generated.
UNKNOWN_ORIGIN = "UNKNOWN_ORIGIN"
#: the closed vocabulary of ``origin`` values the product writes (a type declaration, not a list of words).
#: Only ``generated`` and ``human_confirmed`` classify a source; the other two are declared non-evidence.
DECLARED_NON_EVIDENCE = ("constructed", "testimony")
DECLARED_ORIGINS = ("generated", "human_confirmed") + DECLARED_NON_EVIDENCE

REQUEST_KINDS = ("factual", "creative", "paraphrase", "style", "example")
KIND_CLASS = {"factual": "FACTUAL", "creative": "NON_FACTUAL", "paraphrase": "NON_FACTUAL",
              "style": "NON_FACTUAL", "example": "NON_FACTUAL"}
BASES = ("HUMAN", "GENERATED", "NONE")
OUTCOMES = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "CONSTRUCTED",
            "CONFIRM_REQUEST", "REFERENCE_GENERATED", "ABSTAIN")

#: the kind of request each entrance assumes (the reading of a request's wording is a later ticket).
#: ``vera observe`` is not wired to the policy yet (it needs the W5-b integration first).
ENTRY_REQUEST_KIND = {"ask": "factual", "observe": "creative"}

#: copies of ``verantyx.one._REFUSAL_KINDS`` / ``_REFUSAL_PREFIXES``; a test keeps them equal.
REFUSAL_KINDS = ("unknown", "not_yet", "cannot", "unreadable")
REFUSAL_PREFIXES = ("UNKNOWN", "ABSTAIN", "AMBIGUOUS", "NOT_IN_DOCS",
                    "UNCONFIRMED", "TIED", "UNGROUNDED", "DOCUMENT_NOT_SPECIFIED")


# ------------------------------------------------------------------ the table (pre-registered)
def _rows() -> Dict[Tuple[str, str, bool, bool], Tuple[str, str]]:
    """The 24 rows of docs/BASIS_POLICY.md section 2, key = (class, basis, human, reference)."""
    out: Dict[Tuple[str, str, bool, bool], Tuple[str, str]] = {}

    def put(cls: str, basis: str, result: Tuple[str, str],
            overrides: Optional[Mapping[Tuple[bool, bool], Tuple[str, str]]] = None) -> None:
        for human in (False, True):
            for ref in (False, True):
                out[(cls, basis, human, ref)] = dict(overrides or {}).get((human, ref), result)

    put("FACTUAL", "HUMAN", ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED"))
    put("FACTUAL", "GENERATED", ("ABSTAIN", "ABSTAIN"), {
        (False, True): ("REFERENCE_GENERATED", "REFERENCE_GENERATED"),
        (True, False): ("CONFIRM_REQUEST", "CONFIRM_REQUEST"),
        (True, True): ("CONFIRM_REQUEST", "CONFIRM_REQUEST")})
    put("FACTUAL", "NONE", ("ABSTAIN", "ABSTAIN"))
    put("NON_FACTUAL", "HUMAN", ("CONSTRUCTED", "CONSTRUCTED"))
    put("NON_FACTUAL", "GENERATED", ("CONSTRUCTED", "CONSTRUCTED"))
    put("NON_FACTUAL", "NONE", ("ABSTAIN", "ABSTAIN"))
    return out


TABLE: Dict[Tuple[str, str, bool, bool], Tuple[str, str]] = _rows()


@dataclass(frozen=True)
class BasisDecision:
    outcome: str
    outcome_with_verified_form: str
    request_kind: Any
    kind_class: Optional[str]
    basis: Any
    human_present: Any
    show_reference: Any
    in_table: bool
    reason: Optional[str]
    table_version: int = TABLE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {"outcome": self.outcome, "outcome_with_verified_form": self.outcome_with_verified_form,
                "request_kind": self.request_kind, "kind_class": self.kind_class, "basis": self.basis,
                "human_present": self.human_present, "show_reference": self.show_reference,
                "in_table": self.in_table, "reason": self.reason, "table_version": self.table_version}


#: W5-c: the basis ``UNKNOWN_ORIGIN`` is outside the 24-row table (like ``MIXED``). Per class of request:
#: the table row whose basis it is read as (``None``: it abstains) and the reason it is not in the table.
_UNKNOWN_ORIGIN_COLUMN: Dict[str, Tuple[Optional[str], str]] = {
    "FACTUAL": (None, "NOT_IN_TABLE:UNKNOWN_ORIGIN_SOURCE"),
    "NON_FACTUAL": ("GENERATED", "UNKNOWN_ORIGIN_READ_AS_GENERATED")}


def decide(request_kind: Any, bases: Any, human_present: Any, show_reference: Any) -> BasisDecision:
    """Look the four inputs up in ``TABLE``. A key that cannot be formed abstains (never raises)."""
    basis = getattr(bases, "policy_basis", None) or getattr(bases, "basis", bases)
    kind_class = KIND_CLASS.get(request_kind) if isinstance(request_kind, str) else None
    bad: List[str] = []
    if kind_class is None:
        bad.append("request_kind")
    if basis == "MIXED":
        bad.append("BASIS_MIXED_NOT_IN_TABLE")
    elif basis == UNKNOWN_ORIGIN:
        pass                                       # outside the table, handled below
    elif not (isinstance(basis, str) and basis in BASES):
        bad.append("basis")
    if type(human_present) is not bool:
        bad.append("human_present")
    if type(show_reference) is not bool:
        bad.append("show_reference")
    if basis == UNKNOWN_ORIGIN and not bad:
        read_as, why = _UNKNOWN_ORIGIN_COLUMN[kind_class]
        row = ("ABSTAIN", "ABSTAIN") if read_as is None else TABLE[(kind_class, read_as, human_present,
                                                                    show_reference)]
        return BasisDecision(row[0], row[1], request_kind, kind_class, basis, human_present, show_reference,
                             False, why)
    row = None if bad else TABLE.get((kind_class, basis, human_present, show_reference))
    if row is None:
        reason = "NOT_IN_TABLE:" + (",".join(bad) if bad else "key")
        return BasisDecision("ABSTAIN", "ABSTAIN", request_kind, kind_class,
                             basis if isinstance(basis, str) else repr(basis), human_present,
                             show_reference, False, reason)
    return BasisDecision(row[0], row[1], request_kind, kind_class, basis, human_present,
                         show_reference, True, None)


# ---------------------------------------------------------------- classification of the basis
_CLASSES = ("human", "generated", "non_evidence", "request_text", "unreadable")


def _is_index_family(src: Mapping[str, Any]) -> bool:
    """The source names a family of the generated-corpus index (``ability_corpus.FAMILIES``, exact string)."""
    family = src.get("family")
    return isinstance(family, str) and family in ability_corpus.FAMILIES


def _document_text_holds(src: Mapping[str, Any], document_texts: Sequence[str]) -> bool:
    """W5-d (docs/BASIS_POLICY.md, W5-d): is this ``family == "document"`` source really in a document the caller handed over?
    (a) its ``text`` is a non-blank string and, under NFKC, a substring of the NFKC text of one of the documents; or
    (b) it has no ``text`` key and its ``sha256`` is that of the (utf-8) text of one of the documents (the form
    ``request_goal_route`` gives a source). A claim of the source alone (a non-empty ``--document`` argument, a ``family`` string) is nothing."""
    if "text" in src:
        text = src["text"]
        if not isinstance(text, str) or not text.strip():
            return False
        needle = unicodedata.normalize("NFKC", text)
        return any(needle in unicodedata.normalize("NFKC", body) for body in document_texts)
    digest = src.get("sha256")
    return isinstance(digest, str) and any(hashlib.sha256(body.encode("utf-8")).hexdigest() == digest
                                           for body in document_texts)


def _sovereign_ids_hold(src: Mapping[str, Any]) -> bool:
    store_id, confirm_id = src.get("store_id"), src.get("confirm_id")
    return (isinstance(store_id, str) and bool(store_id)
            and isinstance(confirm_id, str) and len(confirm_id) == 24
            and all(char in "0123456789abcdef" for char in confirm_id))


def _class_of(src: Any, user_documents: bool = False, document_texts: Optional[Sequence[str]] = None) -> str:
    """The class of one source: the rules of docs/BASIS_POLICY.md section prereg-w5c-r3 (the earliest rule that applies wins).

    A human source is one whose origin is declared human (``human_confirmed``) AND whose family is ``memory_sovereign`` (W5-f,
    version 5: nonempty ``store_id`` and a 24-character lowercase hexadecimal ``confirm_id``; a ``document`` source
    claiming it is checked in the documents like any other; any other family claiming it is ``unknown_origin``), the request text itself
    (``family == "user"``) and, only when ``user_documents`` is true (the caller handed these documents over in
    this very call), a ``family == "document"`` source with no origin WHOSE TEXT IS IN THOSE DOCUMENTS (W5-d: with
    ``document_texts``, the bodies of the documents handed over, it must be found in them -- ``_document_text_holds``;
    a document source not found there is ``unknown_origin``). ``document_texts is None`` is the older contract: the
    caller has checked it himself (the product never calls it so: ``apply_to_ask`` always passes the bodies).
    Everything else with no origin is ``unknown_origin``: it is not a human source and it is not known to be a
    generated one either (absent, ``None``, ``""``, a different spelling of a declared value, any unknown value,
    a family outside the index)."""
    if not isinstance(src, dict):
        return "unreadable"
    origin = src.get("origin")
    if origin == "generated":
        return "generated"
    if origin == "human_confirmed":
        if src.get("family") == "document" and user_documents \
                and (document_texts is None or _document_text_holds(src, document_texts)):
            return "human"
        if src.get("family") == "memory_sovereign":
            # W5-f (docs/BASIS_POLICY.md W5-f): labels need both identifier fields and the registered confirmation-id shape.
            return "human" if _sovereign_ids_hold(src) else "unknown_origin"
        return "unknown_origin"
    if _is_index_family(src) and not (isinstance(origin, str) and origin in DECLARED_NON_EVIDENCE):
        return "unknown_origin"
    if origin is not None:
        return "non_evidence"
    if src.get("family") == "user":
        return "request_text"
    if user_documents and src.get("family") == "document":
        if document_texts is None or _document_text_holds(src, document_texts):
            return "human"
        return "unknown_origin"
    return "unknown_origin"


def _unknown_value(src: Any) -> bool:
    """An ``origin`` that is present (not ``None``) and outside the closed vocabulary ``DECLARED_ORIGINS``."""
    if not isinstance(src, dict):
        return False
    origin = src.get("origin")
    return origin is not None and not (isinstance(origin, str) and origin in DECLARED_ORIGINS)


def _unknown_origin_sources(sources: Iterable[Any], user_documents: bool = False,
                            document_texts: Optional[Sequence[str]] = None) -> List[Mapping[str, Any]]:
    """The sources whose origin is unknown in either sense (class ``unknown_origin`` or an unknown value)."""
    return [s for s in sources if isinstance(s, dict)
            and (_class_of(s, user_documents, document_texts) == "unknown_origin" or _unknown_value(s))]


@dataclass(frozen=True)
class SourceClass:
    basis: str                      # HUMAN | GENERATED | MIXED | NONE | UNKNOWN_ORIGIN
    counts: Mapping[str, int]       # always the five keys of ``_CLASSES``
    cited: int                      # sources other than the request text itself
    non_evidence_by_origin: Mapping[str, int] = field(default_factory=dict)
    unknown_origin: int = 0                                           # class ``unknown_origin`` (not in counts)
    unknown_origin_by_family: Mapping[str, int] = field(default_factory=dict)
    unknown_origin_values: Mapping[str, int] = field(default_factory=dict)   # non_evidence with a value outside the vocabulary

    @property
    def policy_basis(self) -> str:
        """The basis the policy reads: ``UNKNOWN_ORIGIN`` as soon as one source's origin is unknown."""
        return UNKNOWN_ORIGIN if (self.unknown_origin or self.unknown_origin_values) else self.basis

    def to_dict(self) -> Dict[str, Any]:
        return {"basis": self.basis, "counts": dict(self.counts), "cited": self.cited,
                "non_evidence_by_origin": dict(self.non_evidence_by_origin),
                "unknown_origin": self.unknown_origin,
                "unknown_origin_by_family": dict(self.unknown_origin_by_family),
                "unknown_origin_values": dict(self.unknown_origin_values)}


def classify_sources(sources: Iterable[Any], *, user_documents: bool = False,
                     document_texts: Optional[Sequence[str]] = None) -> SourceClass:
    """Closed rules, the earliest that applies wins; the declared ``origin`` is the only evidence (no guessing).
    ``user_documents``: the caller handed documents over in this call (rule 7 of ``prereg-w5c-r3``);
    ``document_texts``: the bodies of those documents (W5-d: a document source counts as human only when its text is found in them)."""
    counts = {name: 0 for name in _CLASSES}
    by_origin: Dict[str, int] = {}
    unknown = 0
    unknown_by_family: Dict[str, int] = {}
    unknown_values: Dict[str, int] = {}
    for src in sources:
        cls = _class_of(src, user_documents, document_texts)
        if cls == "unknown_origin":
            unknown += 1
            fam = _family_of(src)
            unknown_by_family[fam] = unknown_by_family.get(fam, 0) + 1
            continue
        counts[cls] += 1
        if cls == "non_evidence":
            key = str(src.get("origin"))
            by_origin[key] = by_origin.get(key, 0) + 1
            if _unknown_value(src):
                unknown_values[key] = unknown_values.get(key, 0) + 1
    human, generated = counts["human"], counts["generated"]
    basis = (UNKNOWN_ORIGIN if unknown else "MIXED" if human and generated else "HUMAN" if human
             else "GENERATED" if generated else "NONE")
    cited = human + generated + counts["non_evidence"] + counts["unreadable"] + unknown
    return SourceClass(basis, counts, cited, dict(sorted(by_origin.items())), unknown,
                       dict(sorted(unknown_by_family.items())), dict(sorted(unknown_values.items())))


# ================================================================== C: borrowing a phrasing
_GATE_REASONS = ("CAND_NOT_ONE_CROSS", "CAND_CENTER_DIFFERS", "CAND_ROLES_DIFFER",
                 "CAND_FILLER_SPAN_AMBIGUOUS", "CAND_REREAD_DIFFERS", "CAND_CONTENT_DIFFERS")
_CENTER_KEYS = ("predicate", "polarity", "tense", "modality", "voice")
#: parts of speech (UniDic ``pos1``) that carry no content of their own: a closed class of the
#: tagger, not a list of words.
_FUNCTION_POS = ("助詞", "助動詞", "補助記号", "記号", "空白")


@dataclass
class FormResult:
    """What ``borrow_form`` decided; ``state`` is FORM_BORROWED or the typed reason it is not."""

    state: str
    text: Optional[str] = None
    witnesses: List[Any] = field(default_factory=list)
    reasons: Dict[str, int] = field(default_factory=lambda: {r: 0 for r in _GATE_REASONS})
    families: Dict[str, str] = field(default_factory=dict)
    searched_rows: int = 0
    candidates: int = 0
    distinct_forms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"state": self.state, "reasons": dict(self.reasons), "families": dict(self.families),
                "searched_rows": self.searched_rows, "candidates": self.candidates,
                "distinct_forms": self.distinct_forms}


@dataclass(frozen=True)
class _Cross:
    center: Tuple[Any, ...]
    roles: Mapping[str, str]            # role -> the one filler's surface


def _one_cross(text: str) -> Optional[_Cross]:
    """The one event cross of a sentence whose every arm has exactly one filler, else None."""
    from .event_cross import read_events
    try:
        events = read_events(text)["events"]
        if events.get("status") != "CROSSED" or len(events.get("crosses") or []) != 1:
            return None
        cross = events["crosses"][0]
        roles: Dict[str, str] = {}
        for role, arm in cross["arms"].items():
            fillers = arm.get("fillers") or []
            if arm.get("kind") != "FILLER" or len(fillers) != 1:
                return None
            roles[role] = fillers[0]["surface"]
        if not roles:
            return None
        return _Cross(tuple(cross["center"].get(k) for k in _CENTER_KEYS), roles)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _stem(predicate: Any) -> str:
    """The leading run of characters that are not hiragana (a character class, not a word list)."""
    out = ""
    for ch in str(predicate or ""):
        if "぀" <= ch <= "ゟ":
            break
        out += ch
    return out


def _content_words(tagger: Any, text: str) -> frozenset:
    return frozenset((w.feature.pos1, w.feature.lemma or w.surface) for w in tagger(text)
                     if w.feature.pos1 not in _FUNCTION_POS)


def _replace_by_spans(text: str, spans: Sequence[Tuple[int, int, str]]) -> str:
    out, pos = [], 0
    for start, end, new in spans:
        out.append(text[pos:start])
        out.append(new)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def borrow_form(source_text: str, *, corpus: Optional[ability_corpus.Corpus] = None,
                limit: int = 200) -> FormResult:
    """Borrow the *phrasing* for a human source sentence from generated sentences of the same cross.

    The content (centre and every role's filler) is the human sentence's; a generated sentence only
    lends the words around the fillers. A role the human source lacks is never added. If the search
    of any family was cut off by ``limit`` nothing is borrowed (a row never seen might disagree),
    and two different phrasings are a tie: nothing is borrowed.
    """
    h = _one_cross(source_text) if isinstance(source_text, str) else None
    if h is None:
        return FormResult("FORM_SOURCE_NOT_ONE_CROSS")
    term = _stem(h.center[0])
    if not term:
        return FormResult("FORM_NOT_SEARCHED")
    corpus = corpus if corpus is not None else ability_corpus.Corpus(ability_corpus.default_root())
    res = FormResult("FORM_NO_CANDIDATE")
    rows: List[Tuple[int, Any]] = []
    truncated = False
    for order, family in enumerate(ability_corpus.FAMILIES):
        hits = corpus.search(term, family, limit + 1)
        res.families[family] = hits.state
        if hits.state.startswith("UNKNOWN_"):
            continue
        if len(hits) > limit:
            res.families[family] = "FORM_SEARCH_TRUNCATED"
            truncated = True
            continue
        rows.extend((order, w) for w in hits)
    res.searched_rows = len(rows)
    if truncated:
        res.state = "FORM_SEARCH_TRUNCATED"
        return res
    if not rows and all(s.startswith("UNKNOWN_") for s in res.families.values()):
        states = sorted(set(res.families.values()))
        res.state = states[0] if len(states) == 1 else "UNKNOWN_INDEX_MIXED"
        return res
    try:
        import fugashi
        tagger = fugashi.Tagger()
    except ImportError:
        res.state = "UNKNOWN_NO_TOKENIZER"
        return res
    source_content = _content_words(tagger, source_text)
    passed: Dict[str, List[Tuple[int, Any]]] = {}
    for order, row in rows:
        g = _one_cross(row.text)
        if g is None:
            res.reasons["CAND_NOT_ONE_CROSS"] += 1
            continue
        if g.center != h.center:
            res.reasons["CAND_CENTER_DIFFERS"] += 1
            continue
        if set(g.roles) != set(h.roles):
            res.reasons["CAND_ROLES_DIFFER"] += 1
            continue
        spans = sorted((row.text.find(surface), role, surface) for role, surface in g.roles.items())
        placed = [(start, start + len(surface), h.roles[role])
                  for start, role, surface in spans]
        if (any(row.text.count(surface) != 1 for _s, _r, surface in spans)
                or any(a[1] > b[0] for a, b in zip(placed, placed[1:]))):
            res.reasons["CAND_FILLER_SPAN_AMBIGUOUS"] += 1
            continue
        new_text = _replace_by_spans(row.text, placed)
        again = _one_cross(new_text)
        if again is None or again.center != h.center or dict(again.roles) != dict(h.roles):
            res.reasons["CAND_REREAD_DIFFERS"] += 1
            continue
        if _content_words(tagger, new_text) != source_content:
            res.reasons["CAND_CONTENT_DIFFERS"] += 1
            continue
        passed.setdefault(new_text, []).append((order, row))
    res.candidates = sum(len(v) for v in passed.values())
    res.distinct_forms = len(passed)
    if len(passed) == 1:
        (new_text, witnesses), = passed.items()
        res.state = "FORM_BORROWED"
        res.text = new_text
        res.witnesses = [w for _o, w in sorted(witnesses, key=lambda p: (p[0], p[1].id))]
    elif len(passed) > 1:
        res.state = "FORM_TIE"
    return res


# ============================================================ the entrance (`vera ask`)
_CONFIRM_ANSWERS = ("yes", "no")
_NOT_RECORDED = "UNKNOWN_NOT_RECORDED"
_STATUS_YES, _STATUS_NO = "HUMAN_CONFIRMED", "REJECTED_GENERATED"
_WITHDRAWN_TEXT = {
    "UNKNOWN_GENERATED_BASIS_ONLY": "人が書いた出所に根拠が見つかりません。",
    "UNKNOWN_GENERATED_REJECTED_BY_USER": "生成コーパスの文は、利用者が正しくないと答えています。",
    "UNKNOWN_BASIS_NOT_IN_TABLE": "出所の組合せが方針の表にないため、答えません。",
    "UNKNOWN_NO_HUMAN_BASIS": "人が書いた出所に根拠が見つかりません。",
    "AMBIGUOUS_CONFIRMED_RECORDS": "確認済みの記録が食い違っているため、答えません。",
    "UNKNOWN_ORIGIN_SOURCE": "出所の分からない出典があるため、答えません。",
}


@dataclass(frozen=True)
class AskPolicy:
    """What the entrance knows besides the question: the kind of request, a human, the column, a yes/no."""

    request_kind: str = ENTRY_REQUEST_KIND["ask"]
    human_present: bool = False
    show_reference: bool = False
    confirm: Optional[Tuple[str, str]] = None

    @classmethod
    def from_args(cls, args: Any) -> "AskPolicy | Dict[str, Any]":
        """The policy of an ``ask`` command line, or a typed error dict (exit code 2)."""
        kind = getattr(args, "request_kind", None) or ENTRY_REQUEST_KIND["ask"]
        if kind not in REQUEST_KINDS:
            return {"kind": "unknown", "verdict": "UNKNOWN_BAD_REQUEST_KIND", "request_kind": str(kind),
                    "want": list(REQUEST_KINDS)}
        raw = getattr(args, "confirm", None)
        confirm: Optional[Tuple[str, str]] = None
        if raw is not None:
            if (not isinstance(raw, (list, tuple)) or len(raw) != 2 or not isinstance(raw[0], str)
                    or not raw[0] or raw[1] not in _CONFIRM_ANSWERS):
                return {"kind": "unknown", "verdict": "UNKNOWN_BAD_CONFIRM_ARGUMENT",
                        "reason": "--confirm takes an id and yes|no", "want": list(_CONFIRM_ANSWERS)}
            if KIND_CLASS[kind] != "FACTUAL":
                return {"kind": "unknown", "verdict": "UNKNOWN_CONFIRM_REQUIRES_FACTUAL",
                        "reason": "--confirm settles a question about a fact; "
                                  "it cannot be combined with a request that claims none"}
            confirm = (raw[0], raw[1])
        return cls(kind, bool(getattr(args, "human_present", False)) or confirm is not None,
                   bool(getattr(args, "show_generated_reference", False)), confirm)


def _is_refused(result: Mapping[str, Any]) -> bool:
    verdict = result.get("verdict")
    return (result.get("kind") in REFUSAL_KINDS
            or (isinstance(verdict, str) and verdict.startswith(REFUSAL_PREFIXES)))


def _source_list(result: Mapping[str, Any]) -> List[Any]:
    """Every source the result cites: the top-level ``sources``, the sources of its ``lines`` that the
    top level does not already hold, and one phantom generated source when the result declares
    ``basis_origin: "generated"`` yet shows none (a generated basis is never invisible to the policy)."""
    sources = result.get("sources")
    out: List[Any] = [] if sources is None else (list(sources) if isinstance(sources, (list, tuple))
                                                  else [sources])
    for line in (result.get("lines") if isinstance(result.get("lines"), (list, tuple)) else []):
        nested = line.get("sources") if isinstance(line, dict) else None
        for src in (nested if isinstance(nested, (list, tuple)) else []):
            if src not in out:
                out.append(src)
    if result.get("basis_origin") == "generated" and not any(
            isinstance(s, dict) and s.get("origin") == "generated" for s in out):
        out.append({"family": "(declared basis_origin)", "origin": "generated", "text": "",
                    "source": "(declared)"})
    return out


def _text_of(src: Mapping[str, Any]) -> str:
    return src["text"] if isinstance(src.get("text"), str) else ""


def _family_of(src: Mapping[str, Any]) -> str:
    family = src.get("family")
    return family if isinstance(family, str) else "(none)"


def _source_id(src: Mapping[str, Any]) -> str:
    return f"{_family_of(src)}:{src.get('source_file', '')}:{src.get('line', '')}"


def _generated_sources(sources: Sequence[Any]) -> List[Mapping[str, Any]]:
    out, seen = [], set()
    for s in sources:
        if isinstance(s, dict) and s.get("origin") == "generated":
            key = (_source_id(s), s.get("sha"), _text_of(s))
            if key not in seen:
                seen.add(key)
                out.append(s)
    return out


def _confirm_id(query: str, claim: str, generated: Sequence[Mapping[str, Any]],
                destination: Optional[Mapping[str, Any]] = None) -> str:
    """The id of one question (``CONFIRM_ID_VERSION`` 2). With a ``destination`` (the sovereign it is put for:
    ``{"store_id", "structure_ref"}``) the id also depends on it; without one the key is absent, so the value is
    the one version 1 computed."""
    cited = sorted([_family_of(s), str(s.get("source_file", "")),
                    s["line"] if isinstance(s.get("line"), int) else -1, str(s.get("sha", ""))]
                   for s in generated)
    body: Dict[str, Any] = {"query": query, "claim": claim, "generated": cited}
    if destination is not None:
        body["destination"] = {"store_id": destination.get("store_id"),
                               "structure_ref": destination.get("structure_ref")}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


# ------------------------------------------------------------------ the sovereign (read only)
@dataclass
class _SovereignView:
    state: str
    root: Optional[str] = None
    store_id: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    detail: Optional[str] = None
    destination: Optional[Dict[str, Any]] = None     # {"store_id", "structure_ref"}; only for an ACTIVE sovereign


def _read_sovereign(consult: bool) -> _SovereignView:
    """Where the human records live (``VERA_SOVEREIGN_ROOT`` + ``VERA_SOVEREIGN_STORE``); read only."""
    if not consult:
        return _SovereignView("NOT_CONSULTED")
    root = os.environ.get("VERA_SOVEREIGN_ROOT") or None
    sid = os.environ.get("VERA_SOVEREIGN_STORE") or None
    if root is None and sid is None:
        return _SovereignView("UNKNOWN_NO_SOVEREIGN")
    if root is None or sid is None:
        return _SovereignView("UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE", root, sid)
    from . import sovereign as sov
    try:
        info = sov.describe(root, sid)
        if info.status != "ACTIVE":
            return _SovereignView(info.status, root, sid)
        events = list(sov.open_ledger(root, sid).events())
    except sov.SovereignUnavailable as exc:
        return _SovereignView(exc.verdict, root, sid)
    except Exception as exc:          # a memory that cannot be read is typed, never a crash of the ask
        return _SovereignView("UNKNOWN_SOVEREIGN_UNREADABLE", root, sid, detail=type(exc).__name__)
    try:
        destination = sov.basis_confirmation_destination(root, sid)
    except Exception as exc:
        return _SovereignView("UNKNOWN_SOVEREIGN_UNREADABLE", root, sid, detail=type(exc).__name__)
    if info.consent.get("promote") is not True:
        return _SovereignView("ACTIVE_NO_CONSENT", root, sid, destination=destination)
    return _SovereignView("ACTIVE_CONSENTED", root, sid, events, destination=destination)


def _effective_records(events: Sequence[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    """The last (highest seq) well-formed basis confirmation per confirm_id; a correction is a later record."""
    out: Dict[str, Mapping[str, Any]] = {}
    for e in events:
        p = e.get("payload")
        if (e.get("kind") == "decision" and isinstance(p, dict) and p.get("record") == "basis_confirmation"
                and p.get("status") in (_STATUS_YES, _STATUS_NO) and isinstance(p.get("confirm_id"), str)
                and isinstance(p.get("query"), str)):
            out[p["confirm_id"]] = e
    return out


# ------------------------------------------------------------------------- output pieces
def _trace(orig: Mapping[str, Any], outcome: Any) -> List[Dict[str, Any]]:
    steps = [{k: t[k] for k in ("part", "status") if k in t}
             for t in (orig.get("trace") if isinstance(orig.get("trace"), list) else [])
             if isinstance(t, dict)]
    return steps + [{"part": "basis_policy.apply", "status": "ran", "outcome": outcome}]


def _n_unknown(sc: SourceClass) -> int:
    """The sources whose origin is unknown, counted from the classification (it knows ``user_documents``)."""
    return sc.unknown_origin + sum(sc.unknown_origin_values.values())


def _withheld(orig: Mapping[str, Any], sources: Sequence[Any], n_generated: int, n_unknown: int) -> Dict[str, Any]:
    return {"verdict": orig.get("verdict"), "kind": orig.get("kind"), "door": orig.get("door"),
            "basis_origin": orig.get("basis_origin"), "generated_source_count": n_generated,
            "unknown_origin_source_count": n_unknown,
            "families": sorted({_family_of(s) for s in sources if isinstance(s, dict)})}


_CONFIRM_VERDICT = "CONFIRM_REQUEST"


def abstention_kind(kind: Any) -> str:
    """The ``kind`` of an output the policy builds anew: the original one only when it is itself a refusal
    kind, else ``unknown`` (a ``kind`` on the answer side must never survive a withdrawal)."""
    return kind if isinstance(kind, str) and kind in REFUSAL_KINDS else "unknown"


def abstention_verdict(verdict: Any, fallback: str) -> str:
    """The ``verdict`` of an output the policy builds anew: the original one only when it is a refusal
    (``REFUSAL_PREFIXES``) or the question put back; ``ANSWER`` / ``CREATED`` / ``PARTIAL`` / ``None`` /
    anything else becomes ``fallback``. Together with ``abstention_kind`` both halves of the type say
    "abstain", so a scorer that reads the answer side first still reads an abstention."""
    if isinstance(verdict, str) and (verdict.startswith(REFUSAL_PREFIXES) or verdict == _CONFIRM_VERDICT):
        return verdict
    return fallback


def _unknown_dict(orig: Mapping[str, Any], sources: Sequence[Any], n_generated: int, verdict: Any,
                  text: str, outcome: Any, kind: Any = "unknown",
                  fallback: str = "UNKNOWN_NO_HUMAN_BASIS", n_unknown: int = 0) -> Dict[str, Any]:
    """Every output the policy builds for a withdrawn answer goes through here: both halves of its type are
    normalised to the abstain side, and no marker of a partial answer (``status``) is carried."""
    return {"kind": abstention_kind(kind), "verdict": abstention_verdict(verdict, fallback), "text": text,
            "sources": [], "evidence": [], "withheld": _withheld(orig, sources, n_generated, n_unknown),
            "door": orig.get("door"), "trace": _trace(orig, outcome)}


def _payload(status: str, confirm_id: str, query: str, claim: str,
             generated: Sequence[Mapping[str, Any]],
             destination: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    p: Dict[str, Any] = {
        "record": "basis_confirmation", "status": status, "witness": "user_confirmation",
        "confirm_id": confirm_id, "query": query, "claim": claim,
        "generated_sources": [{"family": _family_of(s), "source_id": _source_id(s), "sha": s.get("sha")}
                              for s in generated],
        "table_version": TABLE_VERSION}
    if status == _STATUS_YES:
        p["origin"] = "human_confirmed"
    if destination is not None:
        p["destination"] = {"store_id": destination.get("store_id"),
                            "structure_ref": destination.get("structure_ref")}
    return dict(sorted(p.items()))


def _confirm_block(query: str, claim: str, generated: Sequence[Mapping[str, Any]], confirm_id: str,
                   view: _SovereignView) -> Dict[str, Any]:
    return {
        "id": confirm_id,
        "question": f"生成コーパスの文にもとづくと「{claim}」となります"
                    "（生成された文であり、事実の証拠ではありません）。この内容は正しいですか？ はい／いいえ",
        "claim": claim,
        "generated_sentences": [{"text": _text_of(s), "family": _family_of(s), "source_id": _source_id(s),
                                 "sha": s.get("sha"), "source_file": s.get("source_file"),
                                 "line": s.get("line")} for s in generated],
        "draft_record": {"kind": "decision",
                         "payload": _payload(_STATUS_YES, confirm_id, query, claim, generated, view.destination)},
        "destination": {"state": view.state, "store_id": view.store_id,
                        "structure_ref": (view.destination or {}).get("structure_ref")},
        "how_to_answer": f"vera ask <query> --human-present --confirm {confirm_id} yes|no"}


def _reference(generated: Sequence[Mapping[str, Any]], rejected: bool) -> List[Dict[str, Any]]:
    return [{"text": _text_of(s), "family": _family_of(s), "source_id": _source_id(s),
             "model": _NOT_RECORDED, "effort": _NOT_RECORDED, "rejected_by_user": rejected}
            for s in generated]


def _document_texts(documents: Sequence[Any]) -> List[str]:
    """The bodies of the documents the caller handed over, read the way ``one.Vera.load_documents`` reads them (``document_loaders``:
    a directory by ``load_directory``, a file by ``load_paths``). A path that cannot be read gives no body (so nothing is found in it)."""
    from .document_loaders import load_directory, load_paths
    bodies: List[str] = []
    for item in documents:
        try:
            path = Path(item)
            result = load_directory(str(path)) if path.is_dir() else load_paths([str(path)])
        except (OSError, ValueError, TypeError):
            continue
        bodies.extend(doc.text for doc in result["documents"] if isinstance(doc.text, str))
    return bodies


def apply_to_ask(result: Any, policy: AskPolicy, *, query: str, mode: str,
                 documents: Sequence[str]) -> Tuple[Any, int]:
    """Pass one ``vera ask`` result through the policy; returns (output, exit code).

    The input is never modified. Only a result that cites no source other than the request text
    itself (a sum, a greeting) is passed through untouched (and says so); anything that cites a
    generated sentence is always judged.
    """
    if not isinstance(result, dict):
        return result, 0
    orig = copy.deepcopy(result)
    sources = _source_list(orig)
    user_documents = mode == "round5" and bool(documents)
    document_texts = _document_texts(documents) if user_documents else None      # W5-d: what was really handed over
    sc = classify_sources(sources, user_documents=user_documents, document_texts=document_texts)
    n_unknown = _n_unknown(sc)
    refused = _is_refused(orig)
    kind = policy.request_kind
    factual = KIND_CLASS.get(kind) == "FACTUAL"
    human = policy.human_present or policy.confirm is not None
    b0 = "NONE" if refused else sc.policy_basis
    has_unknown = sc.policy_basis == UNKNOWN_ORIGIN
    generated = _generated_sources(sources)
    claim = orig.get("text") if isinstance(orig.get("text"), str) and orig.get("text") else ""
    view = _read_sovereign(factual or policy.confirm is not None)
    confirm_id = _confirm_id(query, claim, generated, view.destination) if (b0 == "GENERATED" and claim) else None
    notes: Dict[str, Any] = {"records_read": 0, "rejected_by_user": 0, "confirmed_records_used": 0,
                             "confirmed_records_not_used": 0, "ambiguous": False}
    basis = b0
    record: Optional[Mapping[str, Any]] = None
    rejected = False
    if factual and view.state == "ACTIVE_CONSENTED":
        effective = _effective_records(view.events)
        notes["records_read"] = len(effective)
        mine = [e for e in effective.values() if e["payload"]["query"] == query
                and e["payload"]["status"] == _STATUS_YES and isinstance(e["payload"].get("claim"), str)
                and e["payload"]["claim"]]
        if b0 == "GENERATED" and confirm_id in effective and effective[confirm_id]["payload"]["status"] == _STATUS_NO:
            basis, rejected = "NONE", True
            notes["rejected_by_user"] = 1
        if b0 == "GENERATED" and mine and not has_unknown:
            claims = {e["payload"]["claim"] for e in mine}
            if len(claims) > 1:                      # contradicting confirmations are looked at BEFORE the comparison with the present claim
                basis = "NONE"
                notes["ambiguous"] = True
            elif claims == {claim}:                  # W5-d (D1): the very sentence now generated -- string equality, nothing normalized
                basis = "HUMAN"
                record = max(mine, key=lambda e: e["seq"])
                notes["confirmed_records_used"] = 1
            else:                                    # a yes for another sentence is not a yes for this one
                notes["confirmed_records_not_used"] = len(mine)
                notes["confirmed_records_claim_differs"] = len(mine)
        elif mine:
            notes["confirmed_records_not_used"] = len(mine)
    sovereign_note = {"state": view.state, "store_id": view.store_id, **notes}
    if view.detail is not None:
        sovereign_note["detail"] = view.detail

    d = decide(kind, basis, human, policy.show_reference)
    passthrough = (not refused and sc.cited == 0 and record is None and not notes["ambiguous"])
    outcome: Optional[str] = None if passthrough else d.outcome
    form: Dict[str, Any] = {"state": "NOT_ATTEMPTED_OUTCOME"}
    withdrawn_verdict: Optional[str] = None
    downgraded: Optional[str] = None

    if passthrough:
        out: Dict[str, Any] = orig
    elif d.outcome == "ANSWER_HUMAN_BASIS":
        if record is not None:
            payload = record["payload"]
            text = payload["claim"]
            out = {"kind": "answer", "verdict": "ANSWER", "text": text, "values": [text], "evidence": [text],
                   "sources": [{"family": "memory_sovereign", "source": record["id"], "text": text,
                                "origin": "human_confirmed", "store_id": view.store_id,
                                "confirm_id": payload["confirm_id"]}],
                   "door": orig.get("door"), "trace": _trace(orig, d.outcome)}
            form = {"state": "NOT_ATTEMPTED_RECORD"}
        else:
            out = orig
            if mode != "round5" or not documents:
                form = {"state": "NOT_ATTEMPTED_ROUTE"}
            else:
                texts = {_text_of(s) for s in sources if isinstance(s, dict) and s.get("origin") is None
                         and s.get("family") != "user"}
                if len(texts) != 1 or "" in texts:
                    form = {"state": "FORM_SOURCE_NOT_ONE_CLAUSE"}
                else:
                    got = borrow_form(next(iter(texts)))
                    form = got.to_dict()
                    if got.state == "FORM_BORROWED":
                        outcome = d.outcome_with_verified_form
                        out = {**orig, "form_text": got.text, **ability_corpus.form_mark(got.witnesses)}
    elif d.outcome == "CONSTRUCTED":
        out = {**orig, "constructed": True}
    elif d.outcome == "CONFIRM_REQUEST":
        if confirm_id is None:
            outcome, downgraded = "ABSTAIN", "CONFIRM_NOT_POSSIBLE_NO_CLAIM_TEXT"
            withdrawn_verdict = "UNKNOWN_GENERATED_BASIS_ONLY"
            out = {}
        else:
            block = _confirm_block(query, claim, generated, confirm_id, view)
            out = _unknown_dict(orig, sources, sc.counts["generated"], "CONFIRM_REQUEST", block["question"], outcome,
                                n_unknown=n_unknown)
            out["confirm"] = block
    else:                                    # REFERENCE_GENERATED and ABSTAIN
        if refused and not sc.counts["generated"] and not has_unknown:
            out = orig
        else:
            if d.reason == "NOT_IN_TABLE:UNKNOWN_ORIGIN_SOURCE" or has_unknown:
                withdrawn_verdict = "UNKNOWN_ORIGIN_SOURCE"
            elif d.reason is not None:
                withdrawn_verdict = "UNKNOWN_BASIS_NOT_IN_TABLE"
            elif notes["ambiguous"]:
                withdrawn_verdict = "AMBIGUOUS_CONFIRMED_RECORDS"
            elif rejected:
                withdrawn_verdict = "UNKNOWN_GENERATED_REJECTED_BY_USER"
            elif basis == "GENERATED":
                withdrawn_verdict = "UNKNOWN_GENERATED_BASIS_ONLY"
            else:
                withdrawn_verdict = "UNKNOWN_NO_HUMAN_BASIS"
            out = {}
    if withdrawn_verdict is not None:
        if refused:
            # a refusal keeps its own type where that type is a refusal on both halves; the bodies it
            # carried are dropped, and so is its own text when that text quotes a generated sentence
            own = orig.get("text") if isinstance(orig.get("text"), str) else ""
            quoted = any(b and b in own for b in (_text_of(g) for g in list(generated)
                                                  + _unknown_origin_sources(sources, user_documents, document_texts)))
            out = _unknown_dict(orig, sources, sc.counts["generated"], orig.get("verdict"),
                                _WITHDRAWN_TEXT[withdrawn_verdict] if quoted else own, outcome,
                                kind=orig.get("kind"), fallback=withdrawn_verdict, n_unknown=n_unknown)
        else:
            out = _unknown_dict(orig, sources, sc.counts["generated"], withdrawn_verdict,
                                _WITHDRAWN_TEXT[withdrawn_verdict], outcome, n_unknown=n_unknown)

    rc = 0
    if policy.confirm is not None:
        out, rc = _settle_confirmation(policy.confirm, confirm_id, query, claim, generated, view, orig,
                                       sources, sc, outcome)
    if policy.show_reference:
        out["reference_generated"] = _reference(generated, rejected)
        out["reference_state"] = "FOUND" if generated else "NO_GENERATED_SOURCES"
    note: Dict[str, Any] = {
        "schema": SCHEMA, "table_version": TABLE_VERSION, "applied": not passthrough}
    if passthrough:
        note["reason"] = "NO_CITED_SOURCES"
    note.update({
        "request_kind": kind, "kind_class": d.kind_class, "basis": basis, "basis_original": b0,
        "human_present": human, "show_reference": policy.show_reference, "outcome": outcome,
        "in_table": d.in_table if not passthrough else None,
        "counts": {**sc.counts, "non_evidence_by_origin": dict(sc.non_evidence_by_origin),
                   "unknown_origin": sc.unknown_origin,
                   "unknown_origin_by_family": dict(sc.unknown_origin_by_family),
                   "unknown_origin_values": dict(sc.unknown_origin_values)},
        "classify_version": CLASSIFY_VERSION, "confirm_id_version": CONFIRM_ID_VERSION,
        "sovereign": sovereign_note, "form": form})
    if d.reason is not None and not passthrough:
        note["reason"] = d.reason
    if downgraded is not None:
        note["downgraded"] = downgraded
    if policy.confirm is not None:
        note["confirm"] = {"id": policy.confirm[0], "answer": policy.confirm[1], "result": out.get("verdict")}
    out.pop("basis_policy", None)
    out["basis_policy"] = note
    return out, rc




# ------------------------------------------------------------------ --confirm (W5-c: bound to a destination)
def _destination_key(d: Optional[Mapping[str, Any]]) -> str:
    return json.dumps(None if d is None else {"store_id": d.get("store_id"), "structure_ref": d.get("structure_ref")},
                      sort_keys=True, ensure_ascii=False)


def _candidate_destinations(view: _SovereignView) -> Tuple[List[Optional[Dict[str, Any]]], Optional[str]]:
    """The destinations an id for this question could have been issued for: the current one, none, and every
    store the current root registered (each with that root's ``structure_ref``). An id issued under another root
    is not here (its destination cannot be told from this root). The returned reason is a typed value when the
    enumeration of the root could not be completed."""
    found: List[Optional[Dict[str, Any]]] = [view.destination, None]
    state: Optional[str] = None
    if view.root is not None:
        from . import sovereign as sov
        try:
            for sid in sov.basis_confirmation_store_ids(view.root):
                try:
                    found.append(sov.basis_confirmation_destination(view.root, sid))
                except sov.SovereignUnavailable:
                    state = "UNKNOWN_CANDIDATES_PARTIAL"
        except Exception:
            state = "UNKNOWN_CANDIDATES_UNREADABLE"
    unique: Dict[str, Optional[Dict[str, Any]]] = {}
    for d in found:
        unique.setdefault(_destination_key(d), d)
    return list(unique.values()), state


def _settle_confirmation(confirm: Tuple[str, str], confirm_id: Optional[str], query: str, claim: str,
                         generated: Sequence[Mapping[str, Any]], view: _SovereignView,
                         orig: Mapping[str, Any], sources: Sequence[Any],
                         sc: SourceClass, outcome: Any) -> Tuple[Dict[str, Any], int]:
    """``--confirm ID yes|no``: write only if ID is an id of this very question *for this very sovereign* and the
    sovereign consents. The order (docs/BASIS_POLICY.md, prereg-w5c section 4), the earliest that applies ends it:
    (1) the question has no id, (2) ID is none of the ids this question can have, (3) the sovereign is not ACTIVE,
    (4) it does not consent, (5) ID was issued for another destination, (6) write. Only (6) writes."""
    given, answer = confirm
    base = {"door": orig.get("door"), "trace": _trace(orig, outcome), "sources": [], "evidence": []}

    def unknown_id(why: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        out = {"kind": "unknown", "verdict": "UNKNOWN_CONFIRM_ID",
               "text": "この確認の id は、いまの問いのものではありません。何も書いていません。",
               "wrote": 0, **base}
        if why is not None:
            out["candidates_state"] = why
        return out, 1

    if confirm_id is None:                                                           # (1)
        return unknown_id()
    candidates, candidates_state = _candidate_destinations(view)
    matched = {_destination_key(d): d for d in candidates if _confirm_id(query, claim, generated, d) == given}
    if len(matched) != 1:                                                            # (2) none, or a tie
        return unknown_id(candidates_state)
    issued = next(iter(matched.values()))
    if view.state not in ("ACTIVE_CONSENTED", "ACTIVE_NO_CONSENT"):                  # (3)
        block = _confirm_block(query, claim, generated, confirm_id, view)
        return {**_unknown_dict(orig, sources, sc.counts["generated"], "CONFIRM_REQUEST", block["question"],
                                outcome, n_unknown=_n_unknown(sc)), "confirm": block, "wrote": 0}, 1

    def not_saved(verdict: Any) -> Tuple[Dict[str, Any], int]:
        # the sovereign's own typed refusal is kept; ``kind: unknown`` makes it an abstention to a scorer, and a
        # verdict that is not a string becomes a typed UNKNOWN_*
        return {"kind": "unknown", "verdict": verdict if isinstance(verdict, str) else "UNKNOWN_CONFIRM_NOT_SAVED",
                "text": "確認を保存できませんでした。何も書いていません。", "wrote": 0,
                "confirm": {"id": confirm_id, "answer": answer, "destination": view.state}, **base}, 1

    if view.state == "ACTIVE_NO_CONSENT":                                            # (4) the door is not called
        return not_saved("NO_CONSENT")
    if issued != view.destination:                                                   # (5)
        return {"kind": "unknown", "verdict": "CONFIRM_TARGET_MISMATCH",
                "text": "この確認の id は、別の宛先に出した問いのものです。何も書いていません。", "wrote": 0,
                "confirm": {"id": given, "answer": answer,
                            "issued_for": dict(issued) if issued is not None else {"state": "NO_DESTINATION"},
                            "destination": {"state": view.state, **(view.destination or {})}}, **base}, 1
    from . import sovereign as sov                                                   # (6)
    status = _STATUS_YES if answer == "yes" else _STATUS_NO
    res = sov.append_basis_confirmation(view.root, view.store_id,
                                        _payload(status, confirm_id, query, claim, generated, view.destination))
    if res.get("verdict") != "APPENDED":
        return not_saved(res.get("verdict"))
    verdict = "CONFIRMED_HUMAN_RECORD" if status == _STATUS_YES else "REJECTED_GENERATED_RECORDED"
    return {"kind": "confirmation", "verdict": verdict,
            "text": "確認を、人が書いた記録として保存しました。" if status == _STATUS_YES
            else "正しくないという確認を、記録として追記しました（文は消していません）。",
            "event_id": res["event_id"], "confirm_id": confirm_id, "store_id": res["store_id"], "wrote": 1,
            "confirm": {"id": confirm_id, "answer": answer, "claim": claim}, **base}, 0
