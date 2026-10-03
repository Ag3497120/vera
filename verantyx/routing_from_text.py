"""Routing from a human's free-text explanation (W2-h2).

    explanation text
      -> (1) segment      lines and sentence ends -> units (the form of the text only; no topic word is looked at)
      -> (2) read         each unit through the reading entry (semantic_read) and the event cross (event_cross)
      -> (3) extract      the centre (predicate class, polarity, modality, comparison) and the arms (roles, fillers)
                          fall into a CLOSED set of relations (RELATION_KINDS)
      -> (4) records      relations -> AgentRecord / RoutingRule / RoutingPrecedence / LineageRelation
                          (basis = Basis.text(source, [the sentences it was read from]))
      -> (5) gate         ONE unit that could not be read and mapped (UNIT_STATUSES) -> no job is routed (typed abstention)
      -> (6) table        build_routing_table (the record layer's own checks; a refusal is an abstention, never repaired)
      -> (7) route        agent_routing.route(table, request), called as it is (no chooser: no run-time LLM)
      -> (8) constraints  what the records cannot hold (a prohibition, "a human does it", "wait", the independence of two
                          roles other than implement/verify) may only turn a decision into "not routed"; they never pick a
                          different agent and never turn "not routed" into a route.

What this module never does: it holds no topic regular expression and no match of the explanation's own words (the only tables
are the closed constants below, every entry of which is listed with its reason in docs/ROUTING_FROM_TEXT.md), it builds a
RoutingTable only through build_routing_table, it passes the router ``used_agents`` only, it sets no lineage label
(``AgentRecord.lineage`` is always None: a label is a split the producer declares and a free text cannot), it writes no
``independent_of`` condition, it makes no fallback rule the human did not state, and it breaks no tie by position.

Matching is by exact equality with what the reader returned (the predicate's dictionary form, a filler's string) after NFKC and
case folding, or with the morphemes of a filler.  The explanation's raw string is not searched with a pattern.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from . import agent_routing as ar

SCHEMA = "verantyx.routing_from_text/1"

# ---------------------------------------------------------------------------------------------------------------------------------
# closed lists (docs/ROUTING_FROM_TEXT.md lists every one of them)
# ---------------------------------------------------------------------------------------------------------------------------------
# EXCEPTION, CONDITION and OVERRIDE of the ticket are not kinds of their own in this version: an exception is a narrower
# SUITABILITY / PROHIBITION (the router looks at a conditional rule before the role's fallback), a condition is the ``work`` scope of
# a relation (role / kind / size), and an override is a flag of the unit that replaces a relation of exactly the same scope.
RELATION_KINDS = ("SUITABILITY", "PROHIBITION", "COMPARISON", "COMPARISON_ONLY", "INDEPENDENCE", "QUANTITY", "PRECEDENCE",
                  "ALIAS", "HUMAN", "WAIT")
UNIT_STATUSES = ("MAPPED", "COMPARISON_ONLY", "UNREAD", "PREDICATE_CLASS_UNKNOWN", "WORK_TERM_UNKNOWN", "NAME_UNRESOLVED",
                 "AMBIGUOUS_RELATION", "CONTRADICTION", "UNREPRESENTABLE")
PASSING_STATUSES = ("MAPPED", "COMPARISON_ONLY")     # the only states that do not stop the gate
ABSTENTION_TYPES = ("INCOMPLETE_READING", "NO_CONTENT", "RECORD_REFUSED", "TASK_NAME_UNKNOWN", "PROHIBITION_VETO",
                    "INDEPENDENCE_VETO", "CONSTRAINT_CONFLICT", "ROUTER_UNEXPECTED")
CONSTRAINT_KINDS = ("prohibit", "human", "wait", "independent")
UNDECIDED_OUT = ("NOT_COVERED", "TIE", "ALL_EXCLUDED", "WAIT", "HUMAN", "ABSTAINED")
BASIS_KINDS_OUT = ("explicit", "comparison", "negation", "condition", "independence", "precedence", "quantity", "combination",
                   "silence")
PREDICATE_CLASS_NAMES = ("ASSIGN", "PERFORM", "SUIT", "ROLE_VERB", "CREATE_VERB", "PREFER", "WAIT", "CALL", "COPULA", "RUN")
USED_TASK_FIELDS = ("role", "kind", "size", "already_used", "running")
IGNORED_FIELDS = ("touches", "used_today", "files", "date")     # known fields the router has no place for (NOT_USED_BY_ROUTER)
LOOKUP_ID_STUB = "stub-no-placement/1"

# ---------------------------------------------------------------------------------------------------------------------------------
# constant tables.  Written BEFORE the test data was opened (artifacts/w2-h2/constants_frozen.txt holds their hash and time).
# The coarse placement (W3-a2) is not integrated, so a predicate's class and a filler's type cannot be asked of it: these hand tables
# are the whole of it.  An entry is a word of the CLOSED vocabulary of docs/AGENT_ROUTING.md section 2 (ROLES / TASK_KINDS / SIZES)
# or a construction word (a copula, an anaphor, an honorific); a word whose meaning is not one-to-one with that vocabulary is left
# out on purpose (leaving it out makes the unit abstain, never a wrong route).
# ---------------------------------------------------------------------------------------------------------------------------------
# (language, dictionary form of the reader's predicate) -> class.  The reader decides the dictionary form; the table only classes it.
PREDICATE_CLASSES: Dict[Tuple[str, str], str] = {
    # ASSIGN: someone gives a work to a recipient (the recipient is the agent)
    ("ja", "任せる"): "ASSIGN",       # delegate
    ("ja", "頼む"): "ASSIGN",         # ask someone to do
    ("ja", "回す"): "ASSIGN",         # pass a job on to
    ("ja", "割り当てる"): "ASSIGN",   # assign
    ("en", "assign"): "ASSIGN",       # assign
    ("en", "delegate"): "ASSIGN",     # delegate
    # PERFORM: the agent does the work (the work is the object)
    ("ja", "やる"): "PERFORM",        # do
    ("ja", "行う"): "PERFORM",        # carry out
    ("ja", "受け持つ"): "PERFORM",    # take charge of
    ("en", "do"): "PERFORM",          # do
    ("en", "handle"): "PERFORM",      # handle
    # SUIT: the agent suits the work (also the only class a comparison of agents can route through)
    ("ja", "向く"): "SUIT",           # be suited to
    ("ja", "適する"): "SUIT",         # be suitable for
    ("en", "suit"): "SUIT",           # suit
    # ROLE_VERB: the verb itself names the work (VERB_WORK); its object adds nothing (GENERIC_OBJECTS)
    ("ja", "確かめる"): "ROLE_VERB",  # check -> verify
    ("ja", "読む"): "ROLE_VERB",      # read -> read
    ("ja", "答える"): "ROLE_VERB",    # answer -> answer
    ("en", "check"): "ROLE_VERB",     # check -> verify
    ("en", "verify"): "ROLE_VERB",    # verify -> verify
    ("en", "review"): "ROLE_VERB",    # review -> review
    ("en", "read"): "ROLE_VERB",      # read -> read
    ("en", "answer"): "ROLE_VERB",    # answer -> answer
    ("en", "attack"): "ROLE_VERB",    # attack -> the kind attack
    # CREATE_VERB: the verb makes something; the object says what (WORK_TERMS), a generic object means the verb's default
    ("ja", "書く"): "CREATE_VERB",    # write
    ("ja", "作る"): "CREATE_VERB",    # make
    ("en", "write"): "CREATE_VERB",   # write
    ("en", "implement"): "CREATE_VERB",   # implement
    ("en", "build"): "CREATE_VERB",   # build
    # PREFER: one is preferred over another
    ("ja", "優先する"): "PREFER",     # give priority to
    ("en", "prefer"): "PREFER",       # prefer
    # WAIT: hold the work until told
    ("ja", "待つ"): "WAIT",           # wait
    ("en", "hold"): "WAIT",           # hold
    ("en", "wait"): "WAIT",           # wait
    # CALL: a name for a name
    ("ja", "呼ぶ"): "CALL",           # call
    ("en", "call"): "CALL",           # call
    # COPULA: A is B (an alias, an identity of lineage, or a work that is a name's)
    ("ja", "だ"): "COPULA",           # be
    ("en", "be"): "COPULA",           # be
    # RUN: how many of the agent run at once
    ("ja", "動かす"): "RUN",          # run (transitive)
    ("ja", "走らせる"): "RUN",        # make run
    ("en", "run"): "RUN",             # run
}

# What the verb itself names, for ROLE_VERB and for the default of CREATE_VERB: (field, value) of the closed vocabulary.
VERB_WORK: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("ja", "確かめる"): ("role", "verify"),       # to check is to verify
    ("ja", "読む"): ("role", "read"),             # to read is the role read
    ("ja", "答える"): ("role", "answer"),         # to answer is the role answer
    ("en", "check"): ("role", "verify"),          # check
    ("en", "verify"): ("role", "verify"),         # verify
    ("en", "review"): ("role", "review"),         # review
    ("en", "read"): ("role", "read"),             # read
    ("en", "answer"): ("role", "answer"),         # answer
    ("en", "attack"): ("kind", "attack"),         # attack is a kind of job, not a role
    ("ja", "書く"): ("role", "implement"),        # to write (with no object that says more) is to implement
    ("ja", "作る"): ("role", "implement"),        # to make (the same)
    ("en", "write"): ("role", "implement"),       # write (the same)
    ("en", "implement"): ("role", "implement"),   # implement
    ("en", "build"): ("role", "implement"),       # build (the same)
}

# (language, the work as a phrase without a size word) -> (field, value).  Only a word that is one-to-one with ROLES / TASK_KINDS.
WORK_TERMS: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("ja", "実装"): ("role", "implement"),                # implementation
    ("ja", "検証"): ("role", "verify"),                   # verification
    ("ja", "レビュー"): ("role", "review"),               # review
    ("ja", "生成"): ("role", "generate"),                 # generation
    ("ja", "読解"): ("role", "read"),                     # reading
    ("ja", "読み込み"): ("role", "read"),                 # reading in
    ("ja", "回答"): ("role", "answer"),                   # answering
    ("ja", "攻撃"): ("kind", "attack"),                   # attack
    ("ja", "テスト"): ("kind", "test_authoring"),         # tests (the work of writing them)
    ("ja", "新機能"): ("kind", "feature"),                # a new feature
    ("ja", "修正"): ("kind", "small_fix"),                # a fix
    ("ja", "リファクタリング"): ("kind", "large_refactor"),   # refactoring (concatenated: fugashi cuts it in two)
    ("ja", "リファクタ"): ("kind", "large_refactor"),     # refactoring (short form)
    ("en", "implementation"): ("role", "implement"),      # implementation
    ("en", "verification"): ("role", "verify"),           # verification
    ("en", "review"): ("role", "review"),                 # review
    ("en", "reviews"): ("role", "review"),                # reviews
    ("en", "generation"): ("role", "generate"),           # generation
    ("en", "reading"): ("role", "read"),                  # reading
    ("en", "attack"): ("kind", "attack"),                 # attack
    ("en", "attacks"): ("kind", "attack"),                # attacks
    ("en", "test"): ("kind", "test_authoring"),           # a test
    ("en", "tests"): ("kind", "test_authoring"),          # tests
    ("en", "feature"): ("kind", "feature"),               # a feature
    ("en", "features"): ("kind", "feature"),              # features
    ("en", "new feature"): ("kind", "feature"),           # a new feature
    ("en", "new features"): ("kind", "feature"),          # new features
    ("en", "fix"): ("kind", "small_fix"),                 # a fix
    ("en", "fixes"): ("kind", "small_fix"),               # fixes
    ("en", "refactor"): ("kind", "large_refactor"),       # a refactor
    ("en", "refactors"): ("kind", "large_refactor"),      # refactors
    ("en", "refactoring"): ("kind", "large_refactor"),    # refactoring
    ("en", "bulk generation"): ("kind", "bulk_generation"),   # bulk generation
}

# A size word that stands in front of the head of a work phrase -> a SIZES value.
SIZE_TERMS: Dict[Tuple[str, str], str] = {
    ("ja", "大きな"): "large", ("ja", "大きい"): "large", ("ja", "大規模な"): "large",    # big
    ("ja", "小さな"): "small", ("ja", "小さい"): "small", ("ja", "小規模な"): "small",    # small
    ("ja", "中規模な"): "medium",                                                          # middle-sized
    ("en", "large"): "large", ("en", "big"): "large",                                      # big
    ("en", "small"): "small", ("en", "tiny"): "small", ("en", "minor"): "small",          # small
    ("en", "medium"): "medium",                                                            # middle-sized
}

# An identity word of a lineage phrase ("same company", "different lab") -> same | different.
IDENTITY_TERMS: Dict[Tuple[str, str], str] = {
    ("ja", "同じ"): "same", ("ja", "同一"): "same",            # the same
    ("ja", "別"): "different", ("ja", "異なる"): "different",  # another / different
    ("en", "same"): "same",                                     # the same
    ("en", "different"): "different", ("en", "separate"): "different",   # different
}

# The head noun of a lineage phrase: what two agents can be "the same" or "different" in.
LINEAGE_HEADS: Dict[Tuple[str, str], str] = {
    ("ja", "会社"): "organisation", ("ja", "系列"): "lineage", ("ja", "系統"): "lineage",   # company / series / lineage
    ("ja", "ベンダー"): "organisation", ("ja", "ラボ"): "organisation",                     # vendor / lab
    ("en", "company"): "organisation", ("en", "family"): "lineage", ("en", "lineage"): "lineage",   # company / family
    ("en", "lab"): "organisation", ("en", "vendor"): "organisation", ("en", "provider"): "organisation",   # lab / vendor
}

# A noun that names a ROLE of an agent ("the one who made it", "the verifier"), for the independence of two roles.
ROLE_NOUNS: Dict[Tuple[str, str], str] = {
    ("ja", "作った者"): "implement", ("ja", "実装した者"): "implement", ("ja", "確かめる者"): "verify", ("ja", "検証する者"): "verify",
    ("en", "implementer"): "implement", ("en", "verifier"): "verify", ("en", "reviewer"): "review",
}

# The agent of a sentence is a person, not one of the agents (the work is for a human).
HUMAN_TERMS: Dict[str, frozenset] = {
    "ja": frozenset({"人", "人間", "私", "自分", "人手"}),    # a person / human / I / myself / by hand
    "en": frozenset({"human", "a human", "i", "me", "a person", "people"}),   # human / I / person
}

# A scope that means "the rest": only the router's NOT_COVERED may be replaced by it.
RESIDUAL_TERMS: Dict[str, frozenset] = {
    "ja": frozenset({"それ以外", "それ以外の仕事", "それ以外のもの", "上記以外", "どれにも当てはまらない仕事"}),   # everything else
    "en": frozenset({"anything else", "everything else", "otherwise", "any other job", "any other work", "the rest"}),
}

# A label that opens a line and says the line changes what was said before (matched as a whole word, never as a part of a word).
OVERRIDE_MARKERS: frozenset = frozenset({"追記", "追伸", "訂正", "更新", "p.s.", "ps", "update", "edit", "correction", "addendum"})

# Of the labels above, the ones that ADD to what was said before ("an addendum", "a postscript").  A line that opens with one of these replaces an
# earlier statement only when its own sentence says so (REPLACEMENT_MARKERS below); the other labels (訂正 / 更新 / update / edit / correction)
# replace as before.  Without a marker the two statements both stand and the router's own handling of two candidates decides (W5-b, A02).
ADDITION_LABELS: frozenset = frozenset({"追記", "追伸", "p.s.", "ps", "addendum"})

# A word that says the sentence takes the place of an earlier one.  Japanese entries are compared as a part of the NFKC text, English entries as
# whole words after case folding.  A sentence with one of these, under an ADDITION_LABELS label, replaces; without one it adds.
REPLACEMENT_MARKERS: Dict[str, frozenset] = {
    "ja": frozenset({"やっぱり", "ではなく"}),
    "en": frozenset({"instead", "replace"}),
}

# A word that points at something said before.  A filler that is one of these is not a name (the antecedent is not read).
ANAPHORS: Dict[str, frozenset] = {
    "ja": frozenset({"前者", "後者", "それ", "これ", "あれ", "彼", "彼女", "同上", "上記", "そちら", "こちら"}),
    "en": frozenset({"the former", "the latter", "it", "they", "them", "he", "she", "this", "that", "former", "latter",
                     "the same one"}),
}

# A word that adds nothing as the object of a verb that already names its work ("check the code", "review the work").
GENERIC_OBJECTS: Dict[str, frozenset] = {
    "ja": frozenset({"コード", "作業", "仕事", "もの", "ファイル", "変更"}),
    "en": frozenset({"code", "work", "job", "task", "file", "files", "change", "changes"}),
}

# An honorific that makes a filler a person's name as a form of address (the person is not an agent name).
HONORIFICS: frozenset = frozenset({"さん", "氏", "君", "様"})
# An English word that, at the head of a filler, makes it a description and not a name.
EN_DETERMINERS: frozenset = frozenset({"the", "a", "an", "this", "that", "these", "those", "my", "our"})
# Morphological classes (fugashi pos1) that cannot be part of a plain name.
NON_NAME_POS: frozenset = frozenset({"形容詞", "連体詞", "動詞", "助詞", "助動詞", "副詞", "接続詞", "代名詞", "感動詞"})

# Form of the text (no word of any topic).
SENTENCE_ENDS: frozenset = frozenset({"。", "．", "！", "？", "!", "?"})    # '.' counts only when blank or the end follows it
CLOSERS: frozenset = frozenset({"」", "』", "）", ")", "\"", "'"})            # stay with the sentence they close
LIST_MARKERS: frozenset = frozenset({"-", "*", "・", "•", "●", "○"})
MARKUP_CHARS: frozenset = frozenset({"-", "=", "_", "|", ":", "*", "#", "─", "—", "―", "~", "+"})

# the constants that the freeze hash covers (artifacts/w2-h2/constants_frozen.txt), in this order
CONSTANT_NAMES = ("PREDICATE_CLASSES", "VERB_WORK", "WORK_TERMS", "SIZE_TERMS", "IDENTITY_TERMS", "LINEAGE_HEADS", "ROLE_NOUNS",
                  "HUMAN_TERMS", "RESIDUAL_TERMS", "OVERRIDE_MARKERS", "ADDITION_LABELS", "REPLACEMENT_MARKERS", "ANAPHORS", "GENERIC_OBJECTS", "HONORIFICS",
                  "EN_DETERMINERS", "NON_NAME_POS", "SENTENCE_ENDS", "CLOSERS", "LIST_MARKERS", "MARKUP_CHARS")


# ---------------------------------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------------------------------
def _norm(text: str) -> str:
    """The key by which two strings are the same: NFKC, case folded, no surrounding blanks."""
    return unicodedata.normalize("NFKC", text).strip().casefold()


def _ja_tokens(text: str) -> List[Tuple[str, str]]:
    """The morphemes of a Japanese string as (surface, pos1).  The tagger is the one the rest of Vera uses."""
    from .typed_edges import _tagger     # inside the function: fugashi is loaded only when a Japanese filler is looked at
    return [(word.surface, word.feature.pos1) for word in _tagger()(unicodedata.normalize("NFKC", text).strip())]


def _display(items: Iterable[Any]) -> List[Any]:
    return sorted(set(items))      # a stable listing for people; never used to choose


# ---------------------------------------------------------------------------------------------------------------------------------
# (1) segment: the form of the text only
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Unit:
    index: int
    text: str          # what the reader is given (the marker and an override label taken off)
    witness: str       # a substring of the explanation (the line as written, only blanks taken off at both ends)
    marker: str        # the list marker / heading / table bar that was taken off ("" when none)
    override: bool     # the line opened with an override label (OVERRIDE_MARKERS)
    line: int          # 1-based line number
    label: str = ""    # that label, in the form it is compared in (_norm); "" when the line has none.  Every sentence of the line carries it


def _is_markup(stripped: str) -> bool:
    return all(ch in MARKUP_CHARS or ch.isspace() for ch in stripped)


def _marker(line: str) -> Tuple[str, int]:
    """(the marker, the offset in ``line`` where the body starts)."""
    body = line.lstrip()
    lead = len(line) - len(body)
    if body.startswith("#"):
        k = 0
        while k < len(body) and body[k] == "#":
            k += 1
        return "#" * k, lead + k
    if body and body[0] in LIST_MARKERS and (len(body) == 1 or body[1].isspace() or body[0] in "・•●○"):
        return body[0], lead + 1
    k = 0
    while k < len(body) and body[k].isdigit():
        k += 1
    if 0 < k < len(body) and body[k] in ".)）．" and (k + 1 >= len(body) or body[k + 1].isspace()):
        return body[:k + 1], lead + k + 1
    return "", lead


def _override_label(body: str) -> Optional[Tuple[int, str]]:
    """(the offset in ``body`` where the sentences begin, the label in its compared form), when the line opens with an override label
    ("追記（翌日）：", "P.S. ", "Update:"); else None.  The head word is compared as a whole with OVERRIDE_MARKERS (never as a part of a word)."""
    n, i = len(body), 0
    while i < n and not body[i].isspace() and body[i] not in "（(：:":
        i += 1
    label = _norm(body[:i])
    if label not in OVERRIDE_MARKERS:
        return None
    j = i
    if j < n and body[j] in "（(":
        close = body.find("）" if body[j] == "（" else ")", j)     # the matching bracket of the label
        if close < 0:
            return None
        j = close + 1
    if j < n and body[j] in "：:":
        return j + 1, label
    if j < n and body[j].isspace():
        return j, label
    return None


def segment_with_counts(text: str) -> Tuple[List[Unit], int]:
    """Units and the number of lines that were only markup (a blank line, ``---``, a table's separator row)."""
    units: List[Unit] = []
    skipped = 0
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.rstrip("\r")
        stripped = line.strip()
        if _is_markup(stripped):
            skipped += 1
            continue
        if stripped.startswith("|"):          # a table row is one unit (the table is not interpreted in this version)
            units.append(Unit(len(units), stripped, stripped, "|", False, number))
            continue
        marker, offset = _marker(line)
        found = _override_label(line[offset:])
        label_end, label = (found if found is not None else (None, ""))
        start = offset + (label_end or 0)
        spans: List[Tuple[int, int]] = []
        i, first, n = start, start, len(line)
        while i < n:
            ch = line[i]
            if ch in SENTENCE_ENDS or (ch == "." and (i + 1 >= n or line[i + 1].isspace())):
                j = i + 1
                while j < n and (line[j] in SENTENCE_ENDS or line[j] in CLOSERS):
                    j += 1
                spans.append((first, j))
                first, i = j, j
            else:
                i += 1
        if line[first:].strip():
            spans.append((first, n))
        made = 0
        for begin, end in spans:
            sentence = line[begin:end].strip()
            if not sentence or all(ch in SENTENCE_ENDS or ch in CLOSERS or ch.isspace() for ch in sentence):
                continue
            witness = line[:end].strip() if made == 0 else sentence     # the first sentence keeps the marker / label it came with
            units.append(Unit(len(units), sentence, witness, marker, label_end is not None, number, label))
            made += 1
        if made == 0:
            skipped += 1
    return units, skipped


def segment(text: str) -> List[Unit]:
    return segment_with_counts(text)[0]


# ---------------------------------------------------------------------------------------------------------------------------------
# (2) read: the reading entry and the event cross, one unit at a time
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass
class UnitReading:
    unit: Unit
    status: str                       # CROSSED | ABSTAINED | INPUT_REJECTED | ERROR
    lang: Optional[str] = None
    crosses: List[dict] = field(default_factory=list)
    relations: List[dict] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    lookup_id: Optional[str] = None
    part_places: Dict[str, Any] = field(default_factory=dict)   # W5-d2 (D2-2): compared name of each part of a parallel Japanese filler -> the placement answer for it
    marker_head: Optional["UnitReading"] = None      # W5-d (R-J2): the fragment between a replacement marker and the next clause break, read by the same reader


def read_units(units: Iterable[Unit], reader: Optional[Callable[[str], Mapping[str, Any]]] = None,
               lookup: Any = None) -> List[UnitReading]:
    """Read each unit.  ``reader`` maps one sentence to a reading-entry output (the schema of docs/READING_CONVENTIONS.md);
    the default is ``semantic_read.read``.  A refusal or an exception of the reader is kept as ``ERROR`` with its type (never
    swallowed: the unit is counted and the gate stops)."""
    from . import event_cross
    if reader is None:
        from . import semantic_read
        reader = semantic_read.read
    done: List[UnitReading] = []
    if lookup is None:      # W5-d2: resolved once (what ``attach_events`` resolved for every unit): the reading of a unit and the questions about the parts of its names use the same lookup
        lookup = event_cross.default_lookup()
    for unit in units:
        reading = _read_one(unit, reader, lookup, event_cross)
        if _replaces_by_marker(unit):
            head = _marker_head(unit.text)
            if head is not None:      # W5-d (R-J2): the marker is followed by a fragment of its own: read it as it stands (same reader, same lookup)
                reading.marker_head = _read_one(Unit(unit.index, head, unit.witness, "", False, unit.line), reader, lookup, event_cross)
        done.append(reading)
    return done


def _read_one(unit: Unit, reader: Callable[[str], Mapping[str, Any]], lookup: Any, event_cross: Any) -> UnitReading:
    """One unit through the reader and the event cross (the body of ``read_units``)."""
    try:
        raw = reader(unit.text)
        out = event_cross.attach_events(raw, lookup)
    except Exception as exc:     # ReadError and anything else: typed, counted, never hidden
        return UnitReading(unit, "ERROR", None, [], [], ["READER_ERROR:" + str(getattr(exc, "type", type(exc).__name__))])
    events = out.get("events") or {}
    status = events.get("status")
    lang = raw.get("lang") if isinstance(raw, Mapping) else None
    lookup_id = (events.get("lookup") or {}).get("id")
    if status == "CROSSED":
        crosses = list(events.get("crosses") or [])
        got = UnitReading(unit, "CROSSED", lang, crosses, list(events.get("relations") or []), [], lookup_id)
        if lang == "ja":
            _ask_the_parts_of_parallel_fillers(got, lookup, event_cross)
        return got
    abstain = events.get("abstain") or {}
    reasons = [str(item) for item in (abstain.get("reasons") or [])] or [str(abstain.get("kind") or "NO_REASON")]
    return UnitReading(unit, status if status in ("ABSTAINED", "INPUT_REJECTED") else "ERROR", lang, [], [], reasons, lookup_id)


def _ask_the_parts_of_parallel_fillers(reading: UnitReading, lookup: Any, event_cross: Any) -> None:
    """W5-d2 (D2-2), Japanese only.  The placement answer the event cross attaches is for the filler as a whole (``ハルとセキ``); R-J1 examines each name that
    a relation uses, and a name that is one part of a parallel filler (``ハル``) had no answer, so it stopped as ``NAME_UNVERIFIED:ハル:NO_PLACEMENT`` even
    under a placement that answers.  Each part (a group of ``_split_parallel``, two or more of them) is asked of the SAME lookup; an answer that keeps the
    contract of the placement query is kept in ``part_places`` (the first answer for a name stays), anything else is not entered (= no answer, as before).
    No new rule: R-J1 is applied to the answer of the part as it is applied to the answer of a single name."""
    for cross in reading.crosses:
        for arm in (cross.get("arms") or {}).values():
            for filler in arm.get("fillers") or []:
                if not isinstance(filler, Mapping):
                    continue
                groups = _split_parallel(str(filler.get("surface")), "ja")
                if len(groups) < 2:
                    continue
                for group in groups:
                    name = _join(group, "ja")
                    if not name:
                        continue
                    answer = lookup.lookup(name)
                    if isinstance(answer, event_cross.PlaceResult) and not answer.invariant_problems():
                        reading.part_places.setdefault(_norm(name), answer.to_dict())


# ---------------------------------------------------------------------------------------------------------------------------------
# (3) extract: a cross -> relations of the closed set
# ---------------------------------------------------------------------------------------------------------------------------------
class _Stop(Exception):
    """A unit that cannot be mapped: the status (UNIT_STATUSES), a typed reason, and the readings kept when it is split."""

    def __init__(self, status: str, reason: str, held: Optional[List[dict]] = None):
        super().__init__(f"{status}: {reason}")
        self.status, self.reason, self.held = status, reason, held or []


@dataclass
class Relation:
    kind: str
    names: Tuple[str, ...] = ()
    work: Optional[Dict[str, Any]] = None
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = ""
    unit: int = -1
    witness: str = ""
    override: bool = False
    held: bool = False
    superseded_by: Optional[str] = None
    represented_by: Optional[str] = None

    def scope(self) -> frozenset:
        work = self.work or {}
        items = {(k, v) for k, v in work.items() if k in ("role", "kind", "size")}
        if work.get("residual"):
            items.add(("residual", True))
        return frozenset(items)

    def all_names(self) -> Tuple[str, ...]:
        extra = (self.data["than"],) if "than" in self.data else ()
        return tuple(self.names) + extra


@dataclass
class UnitResult:
    index: int
    status: str
    reasons: List[str]
    text: str
    witness: str
    override: bool


def _split_parallel(surface: str, lang: str) -> List[List[Tuple[str, str]]]:
    """A filler cut at 'と' (a particle) / 'and' into groups of morphemes."""
    groups: List[List[Tuple[str, str]]] = [[]]
    if lang == "ja":
        for piece, pos in _ja_tokens(surface):
            if piece == "と" and pos == "助詞":
                groups.append([])
            else:
                groups[-1].append((piece, pos))
        return groups
    for word in surface.split():
        if word.casefold() == "and":
            groups.append([])
        else:
            groups[-1].append((word, "EN"))
    return groups


def _join(tokens: List[Tuple[str, str]], lang: str) -> str:
    return "".join(piece for piece, _ in tokens) if lang == "ja" else " ".join(piece for piece, _ in tokens)


def _name_from_tokens(tokens: List[Tuple[str, str]], lang: str) -> str:
    """One agent's name, or ``NAME_UNRESOLVED``: an anaphor, a description (an adjective at the head, a particle inside, a determiner at
    the head), an honorific, or a word of the work vocabulary is not a name."""
    if not tokens:
        raise _Stop("NAME_UNRESOLVED", "EMPTY_NAME")
    name = _join(tokens, lang)
    key = _norm(name)
    if key in ANAPHORS[lang]:
        raise _Stop("NAME_UNRESOLVED", f"ANAPHOR:{name}")
    if (lang, key) in WORK_TERMS or key in GENERIC_OBJECTS[lang] or key in HUMAN_TERMS[lang] or key in RESIDUAL_TERMS[lang]:
        raise _Stop("NAME_UNRESOLVED", f"WORK_WORD_AS_NAME:{name}")
    if lang == "ja":
        if tokens[0][1] in ("形容詞", "連体詞"):
            raise _Stop("NAME_UNRESOLVED", f"DESCRIPTIVE_HEAD:{name}")
        if tokens[-1][0] in HONORIFICS:
            raise _Stop("NAME_UNRESOLVED", f"HONORIFIC:{name}")
        if any(pos in NON_NAME_POS for _, pos in tokens):
            raise _Stop("NAME_UNRESOLVED", f"NOT_A_PLAIN_NAME:{name}")
    else:
        if tokens[0][0].casefold() in EN_DETERMINERS:
            raise _Stop("NAME_UNRESOLVED", f"DETERMINER_HEAD:{name}")
        if len(tokens) > 1:       # the reader can put an adverb into a filler ("<name> usually"); no part of speech is known, so one word only
            raise _Stop("NAME_UNRESOLVED", f"MULTI_WORD_NAME:{name}")
    return name


def _single_name(surface: str, lang: str) -> str:
    groups = _split_parallel(surface, lang)
    if len(groups) != 1:
        raise _Stop("UNREPRESENTABLE", f"PARALLEL_NAMES:{surface}")
    return _name_from_tokens(groups[0], lang)


def _is_human(surface: str, lang: str) -> bool:
    return _norm(surface) in HUMAN_TERMS[lang]


def _parse_work(surface: str, lang: str, allow_residual: bool = False) -> Tuple[Dict[str, Any], bool]:
    """A work phrase -> ({role | kind | size | residual}, generic).  ``generic`` is True when the head is a GENERIC_OBJECT (it adds
    nothing).  An unknown head is ``WORK_TERM_UNKNOWN``; the phrase is never cut by a pattern."""
    key = _norm(surface)
    if key in RESIDUAL_TERMS[lang]:
        if not allow_residual:
            raise _Stop("UNREPRESENTABLE", f"RESIDUAL_SCOPE_NOT_ALLOWED:{surface}")
        return {"residual": True}, False
    hit = WORK_TERMS.get((lang, key))
    if hit is not None:
        return {hit[0]: hit[1]}, False
    if key in GENERIC_OBJECTS[lang]:
        return {}, True
    size: Optional[str] = None
    rest = key
    if lang == "ja":
        tokens = _ja_tokens(surface)
        if len(tokens) >= 2 and ("ja", _norm(tokens[0][0])) in SIZE_TERMS:
            size, rest = SIZE_TERMS[("ja", _norm(tokens[0][0]))], _norm("".join(piece for piece, _ in tokens[1:]))
    else:
        words = key.split()
        if len(words) >= 2 and ("en", words[0]) in SIZE_TERMS:
            size, rest = SIZE_TERMS[("en", words[0])], " ".join(words[1:])
    if size is not None:
        hit = WORK_TERMS.get((lang, rest))
        if hit is not None:
            return {hit[0]: hit[1], "size": size}, False
        if rest in GENERIC_OBJECTS[lang]:
            return {"size": size}, True
    raise _Stop("WORK_TERM_UNKNOWN", f"{lang}:{surface}")


def _identity_of(surface: str, lang: str) -> Optional[str]:
    """'same' / 'different' when the phrase is exactly (identity word, lineage head), e.g. 同じ会社 / different lab; else None."""
    if lang == "ja":
        words = [piece for piece, pos in _ja_tokens(surface) if pos != "助詞"]
    else:
        words = surface.split()
    if len(words) != 2:
        return None
    identity = IDENTITY_TERMS.get((lang, _norm(words[0])))
    return identity if identity is not None and (lang, _norm(words[1])) in LINEAGE_HEADS else None


def _surface(arms: Mapping[str, Any], role: str) -> str:
    return arms[role]["fillers"][0]["surface"]


def _agent_relation(name_surface: str, work: Dict[str, Any], negative: bool, lang: str, only: bool = False,
                    comparison_than: Optional[str] = None) -> Relation:
    """A person does the work (HUMAN) or a named agent does / does not do it (SUITABILITY / PROHIBITION / COMPARISON)."""
    if _is_human(name_surface, lang):
        if negative or only or comparison_than is not None:
            raise _Stop("UNREPRESENTABLE", f"HUMAN_ARM_FORM:{name_surface}")
        return Relation("HUMAN", (), dict(work), {})
    name = _single_name(name_surface, lang)
    if work.get("residual"):
        raise _Stop("UNREPRESENTABLE", "RESIDUAL_ASSIGNMENT_HAS_NO_ROLE")
    if not {"role", "kind", "size"} & set(work):
        raise _Stop("WORK_TERM_UNKNOWN", "NO_WORK_IN_SENTENCE")
    if comparison_than is not None:
        if negative:
            raise _Stop("UNREPRESENTABLE", "NEGATED_COMPARISON")
        return Relation("COMPARISON", (name,), dict(work), {"than": comparison_than})
    if only:
        if negative or "size" in work or ("role" in work) == ("kind" in work):
            raise _Stop("UNREPRESENTABLE", "ONLY_SCOPE")
    return Relation("PROHIBITION" if negative else "SUITABILITY", (name,), dict(work), {"only": True} if only else {})


def _interpret_cross(cross: Mapping[str, Any], lang: str) -> List[Relation]:
    center, arms = cross["center"], cross["arms"]
    for role, arm in arms.items():
        if arm.get("kind") == "ARM_TIE":
            raise _Stop("AMBIGUOUS_RELATION", f"ARM_TIE:{role}")
    if center.get("voice", "active") != "active":
        raise _Stop("UNREPRESENTABLE", f"VOICE:{center.get('voice')}")
    if "scope" in center:
        raise _Stop("UNREPRESENTABLE", "OPERATOR_SCOPE")
    if "tense" in center and center["tense"] != "nonpast":      # a past event reports what happened; it does not declare an assignment
        raise _Stop("UNREPRESENTABLE", f"TENSE:{center['tense']}")
    modality, polarity = center.get("modality"), center.get("polarity")
    if modality not in (None, "obligation", "prohibition"):
        raise _Stop("UNREPRESENTABLE", f"MODALITY:{modality}")
    if polarity not in ("+", "-"):
        raise _Stop("UNREPRESENTABLE", f"POLARITY:{polarity}")
    if modality == "prohibition" and polarity != "+":
        raise _Stop("UNREPRESENTABLE", "PROHIBITION_WITH_NEGATIVE_POLARITY")
    negative = polarity == "-" or modality == "prohibition"
    quantifiers = dict(center.get("quantifiers") or {})
    comparison = center.get("comparison")
    predicate = _norm(str(center.get("predicate")))
    cls = PREDICATE_CLASSES.get((lang, predicate))
    unused = set(arms)
    used_quant: set = set()

    def take(*roles: str) -> Optional[str]:
        for role in roles:
            if role in arms:
                unused.discard(role)
                return role
        return None

    def finish(rels: List[Relation]) -> List[Relation]:
        if unused:
            raise _Stop("UNREPRESENTABLE", "UNUSED_ARM:" + ",".join(sorted(unused)))
        left = sorted(set(quantifiers) - used_quant)
        if left:
            raise _Stop("UNREPRESENTABLE", "QUANTIFIER:" + ",".join(f"{k}={quantifiers[k]}" for k in left))
        return rels

    if cls is None:
        if comparison and set(arms) == {"entity", "standard"} and not quantifiers:
            a, b = _single_name(_surface(arms, "entity"), lang), _single_name(_surface(arms, "standard"), lang)
            return [Relation("COMPARISON_ONLY", (a, b), None, {"polarity": polarity})]
        raise _Stop("PREDICATE_CLASS_UNKNOWN", f"{lang}:{predicate}")
    if comparison and cls != "SUIT":
        raise _Stop("UNREPRESENTABLE", f"COMPARISON_WITH_CLASS:{cls}")

    def work_quant(work_role: str) -> bool:
        value = quantifiers.get(work_role)
        if value is None:
            return False
        if value != "only":
            return False
        used_quant.add(work_role)
        return True

    if cls == "ASSIGN":
        recipient, patient = take("recipient"), take("patient")
        if recipient is None or patient is None:
            raise _Stop("UNREPRESENTABLE", "ASSIGN_NEEDS_RECIPIENT_AND_WORK")
        if "agent" in arms and _is_human(_surface(arms, "agent"), lang):
            take("agent")        # the human who assigns: said, and not an arm that changes the relation
        work, generic = _parse_work(_surface(arms, patient), lang, allow_residual=True)
        if generic and not work:
            raise _Stop("WORK_TERM_UNKNOWN", "GENERIC_ONLY")
        return finish([_agent_relation(_surface(arms, recipient), work, negative, lang, work_quant(patient))])
    if cls in ("PERFORM", "SUIT"):
        agent = take("agent") if cls == "PERFORM" else take("agent", "entity")
        work_role = take("patient") if cls == "PERFORM" else take("goal", "patient", "attribute")
        if agent is None or work_role is None:
            raise _Stop("UNREPRESENTABLE", f"{cls}_NEEDS_AGENT_AND_WORK")
        work, generic = _parse_work(_surface(arms, work_role), lang, allow_residual=True)
        if generic and not work:
            raise _Stop("WORK_TERM_UNKNOWN", "GENERIC_ONLY")
        than = None
        if comparison:
            if cls != "SUIT" or comparison != "comparative":
                raise _Stop("UNREPRESENTABLE", f"COMPARISON:{comparison}")
            standard = take("standard")
            if standard is None:
                raise _Stop("UNREPRESENTABLE", "COMPARISON_WITHOUT_STANDARD")
            than = _single_name(_surface(arms, standard), lang)
        return finish([_agent_relation(_surface(arms, agent), work, negative, lang, work_quant(work_role), than)])
    if cls in ("ROLE_VERB", "CREATE_VERB"):
        agent, patient = take("agent"), take("patient")
        if agent is None:
            raise _Stop("UNREPRESENTABLE", f"{cls}_NEEDS_AGENT")
        default_field, default_value = VERB_WORK[(lang, predicate)]
        work: Dict[str, Any] = {default_field: default_value}
        if patient is not None:
            parsed, generic = _parse_work(_surface(arms, patient), lang)
            if cls == "ROLE_VERB" and not generic:
                raise _Stop("WORK_TERM_UNKNOWN", f"OBJECT_NOT_GENERIC:{_surface(arms, patient)}")
            if generic:
                work.update(parsed)                  # only a size can come with a generic object
            elif any(key in parsed for key in ("role", "kind")):
                work = dict(parsed)                  # the object says what is made
        return finish([_agent_relation(_surface(arms, agent), work, negative, lang, patient is not None and work_quant(patient))])
    if cls == "PREFER":
        upper, lower = take("agent", "patient", "entity"), take("standard", "source", "recipient")
        if upper is None or lower is None or negative:
            raise _Stop("AMBIGUOUS_RELATION", "PRECEDENCE_ARMS_NOT_UNIQUE")
        return finish([Relation("PRECEDENCE", (_single_name(_surface(arms, upper), lang), _single_name(_surface(arms, lower), lang)))])
    if cls == "WAIT":
        patient = take("patient")
        if "agent" in arms and _is_human(_surface(arms, "agent"), lang):
            take("agent")
        if patient is None or negative:
            raise _Stop("UNREPRESENTABLE", "WAIT_SCOPE_UNKNOWN")
        work, generic = _parse_work(_surface(arms, patient), lang, allow_residual=True)
        if generic and not work:
            raise _Stop("WORK_TERM_UNKNOWN", "GENERIC_ONLY")
        return finish([Relation("WAIT", (), work, {})])
    if cls == "CALL":
        first, second = take("patient"), take("result", "goal", "value", "quotation")
        if first is None or second is None or negative:
            raise _Stop("UNREPRESENTABLE", "CALL_FORM")
        return finish([Relation("ALIAS", (_single_name(_surface(arms, first), lang), _single_name(_surface(arms, second), lang)))])
    if cls == "RUN":
        who = take("agent", "patient", "entity")
        if who is None or negative or _is_human(_surface(arms, who), lang):
            raise _Stop("UNREPRESENTABLE", "RUN_FORM")
        found = None
        for key in ("event", who):
            value = quantifiers.get(key)
            if isinstance(value, str) and value.partition(":")[0] in ("at_most", "exactly") and value.partition(":")[2].isdigit():
                found = int(value.partition(":")[2])
                used_quant.add(key)
                break
        if found is None or found < 1:
            raise _Stop("UNREPRESENTABLE", "QUANTITY_FORM")
        return finish([Relation("QUANTITY", (_single_name(_surface(arms, who), lang),), None, {"concurrency": found})])
    # COPULA
    entity, value = take("entity"), take("value")
    if entity is None or value is None or negative and not _identity_of(_surface(arms, value), lang):
        raise _Stop("UNREPRESENTABLE", "COPULA_NEEDS_ENTITY_AND_VALUE")
    ent_s, val_s = _surface(arms, entity), _surface(arms, value)
    identity = _identity_of(val_s, lang)
    if identity is not None:
        groups = _split_parallel(ent_s, lang)
        if len(groups) != 2:
            raise _Stop("UNREPRESENTABLE", f"IDENTITY_NEEDS_TWO_NAMES:{ent_s}")
        phrases = [_join(g, lang) for g in groups]
        roles = [ROLE_NOUNS.get((lang, _norm(p))) for p in phrases]
        if all(roles):
            if identity != "different" or negative or roles[0] == roles[1]:
                raise _Stop("UNREPRESENTABLE", f"ROLE_IDENTITY_FORM:{ent_s}")
            pair = tuple(sorted(roles))
            rel = Relation("INDEPENDENCE", tuple(phrases), None, {"roles": list(pair)})
            if pair == ("implement", "verify"):
                rel.represented_by = "ROUTER_DEFAULT_R3"     # the router's own default for a verify request
            return finish([rel])
        if any(roles):
            raise _Stop("UNREPRESENTABLE", f"ROLE_NOUN_WITH_NAME:{ent_s}")
        a, b = (_name_from_tokens(g, lang) for g in groups)
        if identity == "same":
            return finish([Relation("INDEPENDENCE", (a, b), None, {"lineage": "distinct" if negative else "same"})])
        if negative:
            raise _Stop("UNREPRESENTABLE", "NEGATED_DIFFERENT")
        held = [{"kind": "INDEPENDENCE", "names": [a, b], "reading": "EACH_OTHER_DIFFERENT", "lineage": "distinct"},
                {"kind": "INDEPENDENCE", "names": [a, b], "reading": "BOTH_DIFFERENT_FROM_A_THIRD", "lineage": None}]
        raise _Stop("AMBIGUOUS_RELATION", "DIFFERENT_IS_MUTUAL_OR_EACH_FROM_A_THIRD", held)
    ent_work = val_work = None
    try:
        ent_work = _parse_work(ent_s, lang)
    except _Stop:
        pass
    try:
        val_work = _parse_work(val_s, lang)
    except _Stop:
        pass
    ent_is_work = ent_work is not None and not ent_work[1]
    val_is_work = val_work is not None and not val_work[1]
    if ent_is_work != val_is_work:               # "work is the agent's": an assignment written with a copula
        work_part, name_part = (ent_work, val_s) if ent_is_work else (val_work, ent_s)
        return finish([_agent_relation(name_part, work_part[0], negative, lang)])
    if ent_is_work and val_is_work:
        raise _Stop("UNREPRESENTABLE", "COPULA_OF_TWO_WORK_WORDS")
    if negative:
        raise _Stop("UNREPRESENTABLE", "NEGATED_ALIAS")
    # "X is Y" with two names: Y can be another name of X or what X belongs to / is (a company, a team); with no placement
    # the two cannot be told apart, so both readings are kept and no record is made.  Another name is taken from a CALL sentence only.
    a, b = _single_name(ent_s, lang), _single_name(val_s, lang)
    held = [{"kind": "ALIAS", "names": [a, b], "reading": "COPULA_IS_ANOTHER_NAME", "lineage": None},
            {"kind": "PREDICATION", "names": [a, b], "reading": "COPULA_IS_A_PREDICATE_OF_THE_FIRST", "lineage": None}]
    raise _Stop("AMBIGUOUS_RELATION", "COPULA_ALIAS_OR_PREDICATION", held)


def _interpret_unit(reading: UnitReading) -> Tuple[str, List[str], List[Relation], List[dict]]:
    """-> (status, reasons, relations, held readings)."""
    if reading.status != "CROSSED":
        return "UNREAD", list(reading.reasons), [], []
    if reading.relations:
        kinds = [str(item.get("type")) for item in reading.relations if isinstance(item, Mapping)]
        return "UNREPRESENTABLE", ["READER_RELATION:" + ",".join(kinds)], [], []
    if reading.lang not in ("ja", "en"):
        return "UNREPRESENTABLE", [f"LANG:{reading.lang}"], [], []
    rels: List[Relation] = []
    for cross in reading.crosses:
        try:
            rels.extend(_interpret_cross(cross, reading.lang))
        except _Stop as stop:
            return stop.status, [stop.reason], [], stop.held
    only_comparison = bool(rels) and all(item.kind == "COMPARISON_ONLY" for item in rels)
    return ("COMPARISON_ONLY" if only_comparison else "MAPPED"), [], rels, []


# ---------------------------------------------------------------------------------------------------------------------------------
# (3b) extract: all units together (names, aliases, overrides, contradictions)
# ---------------------------------------------------------------------------------------------------------------------------------
_SCOPE_KINDS = ("SUITABILITY", "PROHIBITION", "COMPARISON", "HUMAN", "WAIT")     # relations that hold a work scope


@dataclass
class Extraction:
    units: List[UnitResult]
    relations: List[Relation]                  # every relation, including held / superseded ones (see their fields)
    held: List[dict]                           # readings kept for a unit that was split (AMBIGUOUS_RELATION)
    canon: Dict[str, str]                      # name key -> the name as first called
    alias_groups: List[List[str]]
    auto_resolved: int
    agents: List[dict]
    rules: List[dict]
    precedence: List[dict]
    lineage: List[dict]
    constraints: List[dict]
    skipped_markup: int = 0
    additions_kept: int = 0                    # units under an ADDITION_LABELS label that were NOT read as a replacement (no REPLACEMENT_MARKERS word)
    common_noun_check: Dict[str, int] = field(default_factory=dict)    # names examined against the placement: checked / not_checked / flagged / introduced_by_naming

    def passing(self, unit: int) -> bool:
        return self.units[unit].status in PASSING_STATUSES

    def live(self) -> List[Relation]:
        return [r for r in self.relations if not r.held and r.superseded_by is None and self.passing(r.unit)]


def _set_status(units: List[UnitResult], index: int, status: str, reason: str) -> None:
    units[index].status = status
    units[index].reasons = list(units[index].reasons) + [reason]


_PUNCT = ".,;:!?()[]\"'“”‘’"


def _has_replacement_marker(text: str) -> bool:
    """The sentence says it takes the place of an earlier one: a Japanese marker as a part of the NFKC text, an English marker as a whole word."""
    key = _norm(text)
    if any(marker in key for marker in REPLACEMENT_MARKERS["ja"]):
        return True
    return bool({word.strip(_PUNCT) for word in key.split()} & REPLACEMENT_MARKERS["en"])


def _replaces(unit: Unit) -> bool:
    """Does this unit REPLACE an earlier statement?  A line under a label that only adds (ADDITION_LABELS) replaces when its own sentence
    says so; under any other override label it replaces as before."""
    if not unit.override:
        return False
    return unit.label not in ADDITION_LABELS or _has_replacement_marker(unit.text)


_CLAUSE_BREAKS = "、，,;；"            # the marks that end a clause inside a sentence (a form of the text, no word)


def _replaces_by_marker(unit: Unit) -> bool:
    """The unit is under an ADDITION_LABELS label and its own sentence carries a replacement marker (the only case in which a marker decides)."""
    return unit.override and unit.label in ADDITION_LABELS and _has_replacement_marker(unit.text)


def _marker_head(text: str) -> Optional[str]:
    """W5-d (R-J2): the fragment that stands between the first replacement marker of the sentence and the next clause break, when there is one.

    The marker's place is the first occurrence (NFKC text) of a ``REPLACEMENT_MARKERS["ja"]`` entry, or of an English entry as a whole word
    (the earliest of them). What follows it (``rest``) says what the marker is attached to:
      * ``rest`` begins with a clause break, or is nothing but end marks -> the marker is a lead-in word of the whole sentence: a replacement (None);
      * ``rest`` holds no clause break before the sentence end -> the marker leads the clause directly: a replacement (None);
      * otherwise the marker is followed by a fragment of its own, up to the first clause break (``head``): it is returned, to be read as it
        stands. No word is looked at: only the marks and the order."""
    nk = unicodedata.normalize("NFKC", text)
    spots: List[Tuple[int, int]] = []
    for marker in REPLACEMENT_MARKERS["ja"]:
        at = nk.find(marker)
        if at >= 0:
            spots.append((at, at + len(marker)))
    pos = 0
    for word in nk.split():
        start = nk.index(word, pos)
        pos = start + len(word)
        core = word.strip(_PUNCT)
        if core.casefold() in REPLACEMENT_MARKERS["en"]:
            begin = start + (len(word) - len(word.lstrip(_PUNCT)))
            spots.append((begin, begin + len(core)))
    if not spots:
        return None
    _, end = min(spots)
    rest = nk[end:].strip()
    if not rest or rest[0] in _CLAUSE_BREAKS:
        return None
    body = rest.rstrip("".join(SENTENCE_ENDS) + ". \t\n")
    cuts = [body.index(mark) for mark in _CLAUSE_BREAKS if mark in body]
    if not cuts:
        return None
    return body[:min(cuts)].strip() or None


def _marker_head_verdict(head: str, reading: Optional[UnitReading]) -> Tuple[str, str]:
    """W5-d (R-J2): ``("MAINTAIN", reason)`` when the fragment after a replacement marker reads as exactly one clause whose polarity is ``-``
    (a change that is denied: nothing is replaced and nothing is added in its place), else ``("AMBIGUOUS", reason)`` (it could not be read,
    is not one clause, or is affirmative: the marker's scope is not determined). The fragment's own predicate is not interpreted."""
    undetermined = f"MARKER_SCOPE_UNDETERMINED:{head}"
    if reading is None or reading.status != "CROSSED" or reading.relations or len(reading.crosses) != 1:
        return "AMBIGUOUS", undetermined
    if (reading.crosses[0].get("center") or {}).get("polarity") == "-":
        return "MAINTAIN", "MAINTAINED_AFTER_MARKER"
    return "AMBIGUOUS", undetermined


def _determiner_before(text: str, name: str) -> Optional[str]:
    """The English determiner that stands right before ``name`` in the sentence as it was written, else None.  The reader drops the
    determiner of a filler ("The crew" -> crew), so the sentence itself is looked at; words are cut at blanks and their end marks."""
    words = [word.strip(_PUNCT) for word in text.split()]
    want = name.casefold()
    for i in range(1, len(words)):
        if words[i].casefold() == want and words[i - 1].casefold() in EN_DETERMINERS:
            return words[i - 1]
    return None


def _places_of(reading: UnitReading) -> Dict[str, Mapping[str, Any]]:
    """Filler surface (compared form) -> the placement answer the event cross attached to it."""
    places: Dict[str, Mapping[str, Any]] = {}
    for cross in reading.crosses:
        for arm in (cross.get("arms") or {}).values():
            for filler in arm.get("fillers") or []:
                if isinstance(filler, Mapping) and isinstance(filler.get("place"), Mapping):
                    places.setdefault(_norm(str(filler.get("surface"))), filler["place"])
    for key, place in reading.part_places.items():      # W5-d2: the answers for the parts of a parallel name; the answer for the filler itself comes first
        places.setdefault(key, place)
    return places


def _common_noun_stop(reading: UnitReading, rels: List[Relation], introduced: set, check: Dict[str, int],
                      seen: Dict[str, str]) -> Optional[str]:
    """The reason (``COMMON_NOUN_SUBJECT:...``) why a name this unit declares is a common noun and not an agent's name, else None.
    Two testimonies, each enough by itself, and neither is a list of nouns:
      (a) an English determiner stands right before the name in the sentence as written ("The crew reviews code");
      (b) the placement says the word itself is typed (origin ``direct``, DECIDED or MULTIPLE).  An estimated, unplaced or unknown word
          says nothing (an estimate is a construction, not a testimony), and without a placement nothing is checked: the count of names
          that could not be checked is kept in ``check`` (and shown in the output's ``reading.common_noun_check``).
    A name that a naming sentence introduced and the names of a naming sentence are not examined.
    W5-d (R-J1), Japanese only: (b) takes only a direct type that is one of the noun types (``event_cross.NOUN_TYPE_IDS``), and a name with no usable
    placement answer (none, or ``NO_PLACEMENT``) that no naming sentence introduced is stopped as ``NAME_UNVERIFIED:<name>:NO_PLACEMENT`` (a name that
    is placed but UNPLACED / UNKNOWN / estimated still passes, as before)."""
    names: List[str] = []
    for rel in rels:
        if rel.kind != "ALIAS":
            names.extend(n for n in rel.all_names() if n not in names)
    if not names:
        return None
    if reading.lang == "en":
        for name in names:
            det = _determiner_before(reading.unit.text, name)
            if det is not None:
                return f"COMMON_NOUN_SUBJECT:{name}:DETERMINER:{det}"
    places = _places_of(reading)
    for name in names:
        key = _norm(name)
        if key in introduced:
            if key not in seen:
                seen[key] = "introduced_by_naming"
                check["introduced_by_naming"] += 1
            continue
        place = places.get(key)
        usable = place is not None and place.get("state") not in (None, "NO_PLACEMENT") and place.get("source") != "NO_PLACEMENT"
        typed = usable and place.get("origin") == "direct" and place.get("state") in ("DECIDED", "MULTIPLE")
        if typed and reading.lang == "ja":
            # W5-d (R-J1): a Japanese name is stopped as a common noun when its direct type is one of the noun types (event_cross.NOUN_TYPE_IDS);
            # a direct type of another kind (a predicate type, say) says nothing about the word being a common noun
            from . import event_cross
            typed = any(str(t) in event_cross.NOUN_TYPE_IDS for t in place.get("types") or [])
        if key not in seen:
            seen[key] = "flagged" if typed else ("checked" if usable else "not_checked")
            check[seen[key]] += 1
        if typed:
            return f"COMMON_NOUN_SUBJECT:{name}:PLACEMENT_DIRECT:{','.join(str(t) for t in place.get('types') or [])}"
        if reading.lang == "ja" and not usable:
            # W5-d (R-J1): with no placement answer a Japanese name that no naming sentence introduced cannot be told from a common noun
            return f"NAME_UNVERIFIED:{name}:NO_PLACEMENT"
    return None


def extract(readings: List[UnitReading]) -> Extraction:
    units: List[UnitResult] = []
    relations: List[Relation] = []
    held: List[dict] = []
    interpreted = [(reading, *_interpret_unit(reading)) for reading in readings]
    # a name that a naming sentence introduced ("call the reviewer Mira") is a name by that sentence: neither test below applies to it
    introduced = {_norm(rel.names[1]) for _, status, _, rels, _ in interpreted if status in PASSING_STATUSES
                  for rel in rels if rel.kind == "ALIAS" and len(rel.names) == 2}
    check = {"checked": 0, "not_checked": 0, "flagged": 0, "introduced_by_naming": 0}
    seen_names: Dict[str, str] = {}
    additions_kept = 0
    for reading, status, reasons, rels, kept in interpreted:
        unit = reading.unit
        if status in PASSING_STATUSES:
            stop = _common_noun_stop(reading, rels, introduced, check, seen_names)
            if stop is not None:
                status, reasons, rels, kept = "NAME_UNRESOLVED", [stop], [], []
        replaces = _replaces(unit)
        if replaces and status in PASSING_STATUSES and _replaces_by_marker(unit) and _marker_head(unit.text) is not None:
            # W5-d (R-J2): the marker is followed by a fragment of its own; what it says decides whether this line replaces, maintains or is undetermined
            head = _marker_head(unit.text)
            verdict, why = _marker_head_verdict(head, reading.marker_head)
            if verdict == "MAINTAIN":
                replaces, reasons = False, list(reasons) + [why]          # not a replacement; kept as an addition below
            else:
                status, reasons, rels, kept, replaces = "AMBIGUOUS_RELATION", list(reasons) + [why], [], [], False
                units.append(UnitResult(unit.index, status, reasons, unit.text, unit.witness, replaces))
                continue
        if unit.override and not replaces:
            additions_kept += 1
        units.append(UnitResult(unit.index, status, reasons, unit.text, unit.witness, replaces))
        for item in kept:
            held.append({**item, "unit": unit.index, "witness": unit.witness})
        for rel in rels:
            rel.unit, rel.witness, rel.override = unit.index, unit.witness, replaces
            relations.append(rel)
    for number, rel in enumerate(relations, start=1):
        rel.id = f"R{number:03d}"
    # names: the first way each name was called, in the order of the explanation (unit, then the order inside the sentence)
    first_call: Dict[str, Tuple[int, str]] = {}
    for rel in relations:
        for name in rel.all_names():
            first_call.setdefault(_norm(name), (len(first_call), name))
    parent: Dict[str, str] = {key: key for key in first_call}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for rel in relations:
        if rel.kind == "ALIAS":
            parent[find(_norm(rel.names[0]))] = find(_norm(rel.names[1]))
    classes: Dict[str, List[str]] = {}
    for key in first_call:
        classes.setdefault(find(key), []).append(key)
    canon: Dict[str, str] = {}
    alias_groups: List[List[str]] = []
    for members in classes.values():
        members.sort(key=lambda k: first_call[k][0])        # the earliest call is the name that is returned
        first = first_call[members[0]][1]
        for key in members:
            canon[key] = first
        if len(members) > 1:
            alias_groups.append([first_call[k][1] for k in members])
    alias_groups.sort(key=lambda g: first_call[_norm(g[0])][0])
    for rel in relations:
        rel.names = tuple(canon[_norm(n)] if rel.kind != "INDEPENDENCE" or "roles" not in rel.data else n for n in rel.names)
        if "than" in rel.data:
            rel.data["than"] = canon[_norm(rel.data["than"])]
    for held_item in held:
        held_item["names"] = [canon.get(_norm(n), n) for n in held_item["names"]]
    # overrides: a relation of a line that opens with an override label replaces the earlier relation of exactly the same scope
    auto_resolved = 0
    for rel in relations:
        if not rel.override or rel.held or not units[rel.unit].status in PASSING_STATUSES:
            continue
        earlier = [o for o in relations if o.unit < rel.unit and not o.held and o.superseded_by is None
                   and units[o.unit].status in PASSING_STATUSES]
        if rel.kind in _SCOPE_KINDS:
            comparable = [o for o in earlier if o.kind in _SCOPE_KINDS]
            equal = [o for o in comparable if o.scope() == rel.scope()]
            partial = [o for o in comparable if o.scope() != rel.scope() and _overlaps(o.scope(), rel.scope())]
            if partial:
                _set_status(units, rel.unit, "AMBIGUOUS_RELATION",
                            "OVERRIDE_PARTIALLY_OVERLAPS:" + ",".join(o.id for o in partial))
                continue
            # a replacement is the same kind of statement ("A does it" -> "B does it") or the same name ("A does it" -> "A does not");
            # a different kind about a different name ("A does it" -> "B does not") may add rather than replace, so it is held
            foreign = [o for o in equal if o.kind != rel.kind and o.names != rel.names]
            if foreign:
                _set_status(units, rel.unit, "AMBIGUOUS_RELATION",
                            "OVERRIDE_OTHER_KIND_AND_NAME:" + ",".join(o.id for o in foreign))
                continue
            for old in equal:
                old.superseded_by = rel.id
                auto_resolved += 1
        elif rel.kind in ("QUANTITY", "INDEPENDENCE"):
            for old in earlier:
                if old.kind == rel.kind and old.names == rel.names and old.data.get("roles") == rel.data.get("roles"):
                    old.superseded_by = rel.id
                    auto_resolved += 1
    _find_contradictions(units, relations)
    ex = Extraction(units, relations, held, {k: v for k, v in canon.items()}, alias_groups, auto_resolved, [], [], [], [], [],
                    additions_kept=additions_kept, common_noun_check=dict(check))
    _build_specs(ex)
    return ex


def _overlaps(a: frozenset, b: frozenset) -> bool:
    """Two scopes can apply to one job: every field both of them set has the same value (a residual scope overlaps nothing)."""
    if ("residual", True) in a or ("residual", True) in b:
        return False
    first, second = dict(a), dict(b)
    return all(first[k] == second[k] for k in first.keys() & second.keys())


def _find_contradictions(units: List[UnitResult], relations: List[Relation]) -> None:
    def alive() -> List[Relation]:
        return [r for r in relations if not r.held and r.superseded_by is None and units[r.unit].status in PASSING_STATUSES]

    for rel in alive():
        if rel.kind != "PROHIBITION":
            continue
        for other in alive():
            if other.kind in ("SUITABILITY", "COMPARISON") and other.names[0] == rel.names[0] and other.scope() == rel.scope():
                for item, partner in ((rel, other), (other, rel)):
                    _set_status(units, item.unit, "CONTRADICTION", f"CONTRADICTS:{partner.id}")
    sayings: Dict[Tuple[str, str], List[Relation]] = {}
    for rel in alive():
        if rel.kind == "QUANTITY":
            sayings.setdefault((rel.names[0], "concurrency"), []).append(rel)
        elif rel.kind in ("SUITABILITY",) and rel.data.get("only"):
            sayings.setdefault((rel.names[0], "only"), []).append(rel)
    for (_name, what), group in sayings.items():
        values = {json.dumps(r.data.get("concurrency") if what == "concurrency" else sorted(r.scope()), default=str) for r in group}
        if len(values) > 1:
            for rel in group:
                _set_status(units, rel.unit, "CONTRADICTION", f"CONFLICTING_{what.upper()}:" + ",".join(r.id for r in group))


def _work_conditions(work: Mapping[str, Any]) -> List[Tuple[str, str]]:
    return [(k, work[k]) for k in ("role", "kind", "size") if k in work]


def _build_specs(ex: Extraction) -> None:
    """Agents, rules, precedence entries, lineage relations and constraints from the live relations (specs, not yet records)."""
    live = ex.live()
    order: Dict[str, int] = {}
    for rel in ex.relations:
        for name in rel.all_names():
            if rel.kind not in ("COMPARISON_ONLY", "HUMAN", "WAIT") and not (rel.kind == "INDEPENDENCE" and "roles" in rel.data):
                order.setdefault(name, len(order))
    named = {name for rel in live for name in rel.all_names()
             if rel.kind not in ("COMPARISON_ONLY", "HUMAN", "WAIT") and not (rel.kind == "INDEPENDENCE" and "roles" in rel.data)}
    for name in sorted(named, key=lambda n: order[n]):
        mine = [r for r in live if name in r.all_names() and r.kind not in ("COMPARISON_ONLY", "HUMAN", "WAIT")
                and not (r.kind == "INDEPENDENCE" and "roles" in r.data)]
        spec: Dict[str, Any] = {"id": name, "roles": None, "kinds": None, "concurrency": None,
                                "witnesses": _witnesses(mine), "relations": [r.id for r in mine]}
        for rel in mine:
            if rel.kind == "QUANTITY" and rel.names[0] == name:
                spec["concurrency"] = rel.data["concurrency"]
            if rel.kind == "SUITABILITY" and rel.data.get("only") and rel.names[0] == name:
                if "role" in (rel.work or {}):
                    spec["roles"] = sorted({rel.work["role"]})
                else:
                    spec["kinds"] = sorted({rel.work["kind"]})
        ex.agents.append(spec)
    seen: Dict[Tuple[frozenset, bool, str], dict] = {}
    for rel in live:
        if rel.kind not in ("SUITABILITY", "COMPARISON"):
            continue
        conditions = _work_conditions(rel.work or {})
        fallback = [k for k, _ in conditions] == ["role"]
        key = (frozenset(conditions), fallback, rel.names[0])
        if key in seen:
            seen[key]["witnesses"] = _witnesses_of(seen[key]["witnesses"], [rel.witness])
            seen[key]["relations"].append(rel.id)
            seen[key]["comparison"] = seen[key]["comparison"] or rel.kind == "COMPARISON"
            continue
        spec = {"unit": rel.unit, "conditions": conditions, "fallback": fallback, "preference": [rel.names[0]],
                "witnesses": [rel.witness], "relations": [rel.id], "comparison": rel.kind == "COMPARISON",
                "kind_condition": "kind" in dict(conditions) or "size" in dict(conditions)}
        seen[key] = spec
        ex.rules.append(spec)
    per_unit: Dict[int, int] = {}
    for spec in ex.rules:
        per_unit[spec["unit"]] = per_unit.get(spec["unit"], 0) + 1
        spec["id"] = f"T{spec['unit']:03d}_{per_unit[spec['unit']]}"
    for rel in live:
        if rel.kind != "PRECEDENCE":
            continue
        upper, lower = rel.names
        highs = [s for s in ex.rules if not s["fallback"] and s["preference"] == [upper]]
        lows = [s for s in ex.rules if not s["fallback"] and s["preference"] == [lower]]
        pairs = [(h, l) for h in highs for l in lows if sorted(h["conditions"]) == sorted(l["conditions"])]
        if len(pairs) != 1:
            _set_status(ex.units, rel.unit, "AMBIGUOUS_RELATION", f"PRECEDENCE_NOT_ONE_PAIR_OF_RULES:{len(pairs)}")
            continue
        ex.precedence.append({"unit": rel.unit, "id": f"P{rel.unit:03d}_{len(ex.precedence) + 1}", "higher": pairs[0][0]["id"],
                              "lower": pairs[0][1]["id"], "witnesses": [rel.witness], "relations": [rel.id]})
    lineage: Dict[Tuple[frozenset, str], dict] = {}
    for rel in live:
        if rel.kind == "INDEPENDENCE" and rel.data.get("lineage") in ("same", "distinct"):
            if rel.names[0] == rel.names[1]:
                _set_status(ex.units, rel.unit, "UNREPRESENTABLE", f"RELATION_WITH_ITSELF:{rel.names[0]}")
                continue
            key = (frozenset(rel.names), rel.data["lineage"])
            if key in lineage:
                lineage[key]["witnesses"] = _witnesses_of(lineage[key]["witnesses"], [rel.witness])
                lineage[key]["relations"].append(rel.id)
            else:
                lineage[key] = {"a": rel.names[0], "b": rel.names[1], "relation": rel.data["lineage"],
                                "witnesses": [rel.witness], "relations": [rel.id]}
                ex.lineage.append(lineage[key])
    for rel in live:
        if rel.kind == "PROHIBITION":
            ex.constraints.append({"kind": "prohibit", "name": rel.names[0], "scope": dict(_scope_dict(rel)),
                                   "witnesses": [rel.witness], "relation": rel.id})
        elif rel.kind in ("HUMAN", "WAIT"):
            ex.constraints.append({"kind": rel.kind.lower(), "name": None, "scope": dict(_scope_dict(rel)),
                                   "witnesses": [rel.witness], "relation": rel.id})
        elif rel.kind == "INDEPENDENCE" and "roles" in rel.data and rel.represented_by is None:
            ex.constraints.append({"kind": "independent", "name": None, "scope": {}, "roles": list(rel.data["roles"]),
                                   "witnesses": [rel.witness], "relation": rel.id})


def _scope_dict(rel: Relation) -> Dict[str, Any]:
    work = rel.work or {}
    out: Dict[str, Any] = {k: work[k] for k in ("role", "kind", "size") if k in work}
    if work.get("residual"):
        out["residual"] = True
    return out


def _witnesses_of(first: List[str], more: Iterable[str]) -> List[str]:
    out = list(first)
    for item in more:
        if item not in out:
            out.append(item)
    return out


def _witnesses(rels: List[Relation]) -> List[str]:
    return _witnesses_of([], (r.witness for r in sorted(rels, key=lambda r: r.unit)))


# ---------------------------------------------------------------------------------------------------------------------------------
# (4) records
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass
class Records:
    agents: tuple
    rules: tuple
    precedence: tuple
    lineage_relations: tuple
    aliases: tuple
    constraints: tuple
    constructed: tuple


def to_records(ex: Extraction, source: str) -> Records:
    """Specs -> the record types of agent_routing.  Nothing the human did not say is added, except ``adapter="fake"`` which the
    record layer requires and which is declared in ``constructed`` (a made value, not testimony)."""
    agents = tuple(ar.AgentRecord(id=s["id"], adapter="fake", roles=s["roles"], kinds=s["kinds"], lineage=None, model=None,
                                  effort=None, concurrency=s["concurrency"], note=None,
                                  basis=ar.Basis.text(source, s["witnesses"])) for s in ex.agents)
    rules = tuple(ar.RoutingRule(s["id"], tuple(ar.Condition(k, v) for k, v in s["conditions"]), tuple(s["preference"]), None,
                                 ar.Basis.text(source, s["witnesses"]), s["fallback"]) for s in ex.rules)
    precedence = tuple(ar.RoutingPrecedence(s["id"], s["higher"], s["lower"], None, ar.Basis.text(source, s["witnesses"]))
                       for s in ex.precedence)
    lineage = tuple(ar.LineageRelation(s["a"], s["b"], s["relation"], ar.Basis.text(source, s["witnesses"])) for s in ex.lineage)
    constructed = tuple({"agent": s["id"], "field": "adapter", "value": "fake", "reason": "ADAPTER_NOT_STATED_ROUTE_ONLY"}
                        for s in ex.agents)
    aliases = tuple({"canonical": group[0], "aliases": group[1:]} for group in ex.alias_groups)
    return Records(agents, rules, precedence, lineage, aliases, tuple(ex.constraints), constructed)


def _basis_dict(basis: ar.Basis) -> dict:
    return basis.as_dict()


def records_dict(records: Records, table_status: str) -> dict:
    return {
        "agents": [{"id": a.id, "adapter": a.adapter, "roles": sorted(a.roles) if a.roles is not None else None,
                    "kinds": sorted(a.kinds) if a.kinds is not None else None, "lineage": a.lineage, "model": a.model,
                    "effort": a.effort, "concurrency": a.concurrency, "note": a.note, "basis": _basis_dict(a.basis)}
                   for a in records.agents],
        "rules": [{"id": r.id, "conditions": {c.field: c.value for c in r.conditions}, "preference": list(r.preference),
                   "fallback": r.fallback, "reason": r.reason, "basis": _basis_dict(r.basis)} for r in records.rules],
        "precedence": [{"id": p.id, "higher": p.higher, "lower": p.lower, "reason": p.reason, "basis": _basis_dict(p.basis)}
                       for p in records.precedence],
        "lineage_relations": [r.as_dict() for r in records.lineage_relations],
        "aliases": [dict(a) for a in records.aliases],
        "constraints": [{k: v for k, v in c.items() if k != "witnesses"} | {"witnesses": list(c["witnesses"])}
                        for c in records.constraints],
        "constructed": [dict(c) for c in records.constructed],
        "table": table_status,
    }


# ---------------------------------------------------------------------------------------------------------------------------------
# (5) the gate and the whole explanation
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass
class Explained:
    source: str
    extraction: Extraction
    records: Records
    table: Optional[ar.RoutingTable]
    table_error: Optional[Tuple[str, str]]     # (record error code, message)
    abstention: Optional[dict]
    lookup_id: Optional[str]
    unit_count: int
    skipped_markup: int


def _by_status(units: List[UnitResult]) -> Dict[str, int]:
    return {status: sum(1 for u in units if u.status == status) for status in UNIT_STATUSES}


def _gate(units: List[UnitResult]) -> Optional[dict]:
    if not units:
        return {"type": "NO_CONTENT", "detail": "the explanation has no sentence", "units": [], "by_status": _by_status(units)}
    stopped = [u for u in units if u.status not in PASSING_STATUSES]
    if stopped:
        return {"type": "INCOMPLETE_READING",
                "detail": f"{len(stopped)} of {len(units)} units were not read and mapped; no job is routed",
                "units": [{"index": u.index, "status": u.status, "text": u.witness, "reasons": list(u.reasons)} for u in stopped],
                "by_status": _by_status(units)}
    return None


def explain(text: str, source: str, reader: Optional[Callable[[str], Mapping[str, Any]]] = None, lookup: Any = None) -> Explained:
    units, skipped = segment_with_counts(text)
    readings = read_units(units, reader, lookup)
    ex = extract(readings)
    ex.skipped_markup = skipped
    records = to_records(ex, source)
    table: Optional[ar.RoutingTable] = None
    error: Optional[Tuple[str, str]] = None
    try:
        table = ar.build_routing_table(records.agents, records.rules, records.precedence, records.lineage_relations)
    except ar.RoutingRecordError as exc:
        error = (exc.code, exc.message)
    abstention = _gate(ex.units)
    if abstention is None and error is not None:
        abstention = {"type": "RECORD_REFUSED", "detail": error[0], "message": error[1], "units": [],
                      "by_status": _by_status(ex.units)}
    lookup_id = next((r.lookup_id for r in readings if r.lookup_id), None)
    return Explained(source, ex, records, table, error, abstention, lookup_id, len(units), skipped)


# ---------------------------------------------------------------------------------------------------------------------------------
# the task
# ---------------------------------------------------------------------------------------------------------------------------------
class TaskError(ValueError):
    """The task is not a task (not a decision: the entry exits with 2 and ``{"error": "BAD_TASK"}``)."""


class ExplanationError(ValueError):
    """The explanation cannot be read as a UTF-8 file (the entry exits with 2 and ``{"error": "BAD_EXPLANATION"}``)."""


def parse_task_argument(raw: str) -> Any:
    """``--task`` is json text; when it is not json and names an existing file, that file is read as json."""
    try:
        return json.loads(raw)
    except ValueError:
        if os.path.isfile(raw):
            try:
                with open(raw, "rb") as handle:
                    return json.loads(handle.read().decode("utf-8"))
            except (OSError, ValueError) as exc:
                raise TaskError(f"the task file is not json: {exc}") from exc
        raise TaskError("--task is neither json nor the path of a json file") from None


def normalize_task(task: Any) -> dict:
    if not isinstance(task, Mapping):
        raise TaskError("the task is a json object")
    for name, vocabulary in (("role", ar.ROLES), ("kind", ar.TASK_KINDS), ("size", ar.SIZES)):
        if task.get(name) not in vocabulary:
            raise TaskError(f"{name} must be one of {', '.join(vocabulary)} (got {task.get(name)!r})")
    used = task.get("already_used")
    already: Dict[str, List[str]] = {}
    if used not in (None, {}):
        if not isinstance(used, Mapping):
            raise TaskError("already_used is an object: role -> a name or a list of names")
        for role, names in used.items():
            if role not in ar.ROLES:
                raise TaskError(f"already_used: {role!r} is not a role")
            items = [names] if isinstance(names, str) else names
            if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
                raise TaskError(f"already_used[{role}] is a name or a list of names")
            already[role] = list(items)
    running_in = task.get("running")
    running: Dict[str, int] = {}
    if running_in not in (None, {}, []):
        if isinstance(running_in, str):
            running_in = [running_in]
        if isinstance(running_in, list):
            for item in running_in:
                if not isinstance(item, str) or not item.strip():
                    raise TaskError("running: a list holds names")
                running[item] = running.get(item, 0) + 1
        elif isinstance(running_in, Mapping):
            for item, count in running_in.items():
                if type(count) is not int or count < 0:
                    raise TaskError(f"running[{item}] is a whole number of at least 0")
                running[item] = count
        else:
            raise TaskError("running is an object (name -> count), a list of names or a name")
    ignored = []
    for key in sorted(task):
        if key in USED_TASK_FIELDS:
            continue
        ignored.append({"field": key, "value": task[key],
                        "reason": "NOT_USED_BY_ROUTER" if key in IGNORED_FIELDS else "UNKNOWN_TASK_FIELD"})
    return {"role": task["role"], "kind": task["kind"], "size": task["size"], "already_used": already, "running": running,
            "ignored": ignored}


# ---------------------------------------------------------------------------------------------------------------------------------
# (7)(8) the router and the constraints
# ---------------------------------------------------------------------------------------------------------------------------------
def _scope_applies(scope: Mapping[str, Any], request: ar.RoutingRequest) -> bool:
    if scope.get("residual"):
        return False
    return all(scope.get(k) in (None, getattr(request, k)) for k in ("role", "kind", "size"))


def _abstained(kind: str, detail: str, evidence: List[str]) -> dict:
    return {"decision": "undecided", "agent": None, "undecided_reason": "ABSTAINED", "decided_by": f"gate:{kind}",
            "abstention": {"type": kind, "detail": detail, "units": [], "by_status": None}, "evidence": evidence, "router": None,
            "decision_obj": None}


def _router_outcome(explained: Explained, task: dict) -> dict:
    ex, table = explained.extraction, explained.table
    ids = {a.id for a in table.agents}

    def resolve(name: str) -> Optional[str]:
        found = ex.canon.get(_norm(name))
        return found if found in ids else None

    used: Dict[str, Tuple[str, ...]] = {}
    for role, names in task["already_used"].items():
        resolved = [resolve(n) for n in names]
        if any(r is None for r in resolved):
            bad = [n for n, r in zip(names, resolved) if r is None]
            return _abstained("TASK_NAME_UNKNOWN", "already_used names no agent of the explanation: " + ", ".join(bad), [])
        used[role] = tuple(resolved)
    in_use: Dict[str, int] = {}
    for name, count in task["running"].items():
        found = resolve(name)
        if found is None:
            return _abstained("TASK_NAME_UNKNOWN", f"running names no agent of the explanation: {name}", [])
        in_use[found] = in_use.get(found, 0) + count
    request = ar.RoutingRequest(job_id="route-from-text", role=task["role"], kind=task["kind"], size=task["size"],
                                used_agents=used, in_use=in_use)
    try:
        decision = ar.route(table, request)      # the router as it is: no chooser_factory, so a split of heads is TESTIMONY_UNAVAILABLE
    except (ValueError, TypeError) as exc:
        return _abstained("ROUTER_UNEXPECTED", f"{type(exc).__name__}: {exc}", [])
    rule_by_id = {s["id"]: s for s in ex.rules}
    prec_by_id = {s["id"]: s for s in ex.precedence}
    if decision.decided:
        head = decision.decided_by
        ids_decided = head[len("rule:"):].split(",") if head.startswith("rule:") else []
        base: Dict[str, Any] = {"decision": "route", "agent": decision.agent_id, "undecided_reason": None, "decided_by": head,
                                "abstention": None}
        evidence: List[str] = []
        for rid in ids_decided:
            evidence = _witnesses_of(evidence, rule_by_id[rid]["witnesses"])
        for pid in decision.precedence_used:
            evidence = _witnesses_of(evidence, prec_by_id[pid]["witnesses"])
        if decision.stage == "precedence":
            for rid in decision.matched_rules:
                if rid in rule_by_id and rule_by_id[rid]["preference"][0] == decision.agent_id:
                    evidence = _witnesses_of(evidence, rule_by_id[rid]["witnesses"])
        base["evidence"] = evidence
        base["rules_decided"] = [rule_by_id[r] for r in ids_decided if r in rule_by_id]
    else:
        mapped = {"ROLE_NOT_ROUTABLE": "NOT_COVERED", "NO_VIABLE_CANDIDATE": "ALL_EXCLUDED",
                  "TESTIMONY_UNAVAILABLE": "TIE"}.get(decision.undecided_reason)
        if mapped is None:
            return {**_abstained("ROUTER_UNEXPECTED", f"router said {decision.undecided_reason}", []), "router": decision.ledger_fields(),
                    "decision_obj": decision}
        evidence = []
        if mapped == "TIE":
            for rid in decision.matched_rules:
                if rid in rule_by_id:
                    evidence = _witnesses_of(evidence, rule_by_id[rid]["witnesses"])
        base = {"decision": "undecided", "agent": None, "undecided_reason": mapped,
                "decided_by": f"router:{decision.undecided_reason}", "abstention": None, "evidence": evidence, "rules_decided": []}
    base["router"] = decision.ledger_fields()
    base["decision_obj"] = decision
    constraints = list(explained.records.constraints)
    if base["decision"] == "route" or base["undecided_reason"] != "ABSTAINED":
        humans, waits = [], []
        for c in constraints:
            if c["kind"] not in ("human", "wait"):
                continue
            applies = (not decision.decided and decision.undecided_reason == "ROLE_NOT_ROUTABLE") if c["scope"].get("residual") \
                else _scope_applies(c["scope"], request)
            if applies:
                (humans if c["kind"] == "human" else waits).append(c)
        if humans and waits:
            return {**_abstained("CONSTRAINT_CONFLICT", "a human-does-it statement and a wait statement both cover this job",
                                 _witnesses_of([w for c in humans for w in c["witnesses"]], [w for c in waits for w in c["witnesses"]])),
                    "router": base["router"], "decision_obj": decision}
        for group, label in ((humans, "HUMAN"), (waits, "WAIT")):
            if group:
                return {"decision": "undecided", "agent": None, "undecided_reason": label, "decided_by": f"constraint:{label.lower()}",
                        "abstention": None, "evidence": _witnesses_of([], [w for c in group for w in c["witnesses"]]),
                        "router": base["router"], "decision_obj": decision, "rules_decided": []}
        if base["decision"] == "route":
            vetoes = [c for c in constraints if c["kind"] == "prohibit" and c["name"] == base["agent"] and _scope_applies(c["scope"], request)]
            if vetoes:
                return {**_abstained("PROHIBITION_VETO", f"{base['agent']} was chosen but the explanation forbids it for this job",
                                     _witnesses_of([w for c in vetoes for w in c["witnesses"]], base["evidence"])),
                        "router": base["router"], "decision_obj": decision}
            for c in constraints:
                if c["kind"] != "independent" or request.role not in c["roles"]:
                    continue
                other = c["roles"][0] if c["roles"][1] == request.role else c["roles"][1]
                for name in used.get(other, ()):
                    if ar.lineage_relation(table, base["agent"], name).verdict != "distinct":
                        return {**_abstained("INDEPENDENCE_VETO", f"{base['agent']} is not known to be of a different lineage than "
                                             f"{name}, used for {other}", _witnesses_of(c["witnesses"], base["evidence"])),
                                "router": base["router"], "decision_obj": decision}
    return base


def _basis_kind(explained: Explained, outcome: dict) -> Optional[str]:
    """Order (the first that holds): a route -> the precedence stage: precedence (the precedence sentence is always a second one, so
    it is asked first); 2 or more sentences: combination; an exclusion by
    lineage or an independence judged for the winner: independence; an exclusion by concurrency: quantity; a rule read from a
    comparison: comparison; a rule with a kind / size condition: condition; else explicit.  Not routed -> NOT_COVERED: silence;
    TIE: precedence; ALL_EXCLUDED: independence / quantity by the exclusions, else silence; WAIT / HUMAN: explicit; ABSTAINED: None."""
    decision = outcome.get("decision_obj")
    reasons = {e.reason for e in decision.excluded} if decision is not None else set()
    independent = {"SAME_LINEAGE", "LINEAGE_UNDECLARED", "PRIOR_ROLE_UNUSED"}
    if outcome["decision"] == "route":
        if decision.stage == "precedence":
            return "precedence"
        if len(outcome["evidence"]) >= 2:
            return "combination"
        if reasons & independent or decision.independence:
            return "independence"
        if reasons & {"CONCURRENCY_FULL", "CONCURRENCY_UNDECLARED"}:
            return "quantity"
        decided = outcome.get("rules_decided") or []
        if any(r["comparison"] for r in decided):
            return "comparison"
        if any(r["kind_condition"] for r in decided):
            return "condition"
        return "explicit"
    reason = outcome["undecided_reason"]
    if reason == "NOT_COVERED":
        return "silence"
    if reason == "TIE":
        return "precedence"
    if reason == "ALL_EXCLUDED":
        if reasons & independent:
            return "independence"
        if reasons & {"CONCURRENCY_FULL", "CONCURRENCY_UNDECLARED"}:
            return "quantity"
        return "silence"
    if reason in ("WAIT", "HUMAN"):
        return "explicit"
    return None


def _relation_dicts(ex: Extraction) -> List[dict]:
    out = []
    for r in ex.relations:
        out.append({"id": r.id, "kind": r.kind, "unit": r.unit, "witness": r.witness, "names": list(r.names), "work": r.work,
                    "data": r.data, "override": r.override, "held": r.held, "superseded_by": r.superseded_by,
                    "represented_by": r.represented_by, "unit_status": ex.units[r.unit].status})
    for number, item in enumerate(ex.held, start=1):
        out.append({"id": f"H{number:03d}", "kind": item["kind"], "unit": item["unit"], "witness": item["witness"],
                    "names": item["names"], "work": None, "data": {"reading": item["reading"], "lineage": item["lineage"]},
                    "override": False, "held": True, "superseded_by": None, "represented_by": None,
                    "unit_status": ex.units[item["unit"]].status})
    return out


def route_task(explained: Explained, task: Mapping[str, Any]) -> dict:
    """The output of the entry for one task (section 2.9 of the plan; docs/ROUTING_FROM_TEXT.md)."""
    norm = normalize_task(task)
    ex = explained.extraction
    if explained.abstention is not None:
        gate = explained.abstention
        outcome: Dict[str, Any] = {"decision": "undecided", "agent": None, "undecided_reason": "ABSTAINED",
                                   "decided_by": f"gate:{gate['type']}", "abstention": gate, "router": None, "decision_obj": None,
                                   "evidence": _witnesses_of([], (u["text"] for u in gate["units"])), "rules_decided": []}
    else:
        outcome = _router_outcome(explained, norm)
        if outcome["abstention"] is not None:
            outcome["abstention"] = {**outcome["abstention"], "by_status": _by_status(ex.units)}
    table_status = "BUILT" if explained.table is not None else ("REFUSED:" + explained.table_error[0] if explained.table_error else "NOT_BUILT")
    return {
        "schema": SCHEMA,
        "decision": outcome["decision"],
        "agent": outcome["agent"],
        "undecided_reason": outcome["undecided_reason"],
        "abstention": outcome["abstention"],
        "basis_kind": _basis_kind(explained, outcome),
        "evidence": list(outcome["evidence"]),
        "decided_by": outcome["decided_by"],
        "records": records_dict(explained.records, table_status),
        "relations": _relation_dicts(ex),
        "reading": {"units": explained.unit_count, "skipped_markup": explained.skipped_markup, "by_status": _by_status(ex.units),
                    "auto_resolved": ex.auto_resolved, "lookup": explained.lookup_id or LOOKUP_ID_STUB,
                    "addition_labels_kept_as_addition": ex.additions_kept,
                    "common_noun_check": {"lookup": explained.lookup_id or LOOKUP_ID_STUB, **ex.common_noun_check}},
        "router": outcome["router"],
        "ignored_fields": norm["ignored"],
        "task": {"role": norm["role"], "kind": norm["kind"], "size": norm["size"],
                 "already_used": {k: norm["already_used"][k] for k in sorted(norm["already_used"])},
                 "running": {k: norm["running"][k] for k in sorted(norm["running"])}},
    }


def read_explanation(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExplanationError(f"{type(exc).__name__}: {exc}") from exc


def run(explanation_path: str, task: Mapping[str, Any], reader: Optional[Callable[[str], Mapping[str, Any]]] = None) -> dict:
    """What ``python -m verantyx.cli route`` does: read the file, explain it, route the task."""
    normalize_task(task)                 # a bad task is refused before anything is read
    text = read_explanation(explanation_path)
    return route_task(explain(text, explanation_path, reader=reader), task)


def dumps(result: Mapping[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)       # the key order is the construction order, fixed above


def main(argv: Optional[List[str]] = None) -> int:
    """``python -m verantyx.routing_from_text --explanation F --task J`` (the CLI's ``route`` calls the same ``run``)."""
    import argparse
    parser = argparse.ArgumentParser(prog="python -m verantyx.routing_from_text")
    parser.add_argument("--explanation", required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    return emit(args.explanation, args.task)


def emit(explanation: str, task_argument: str) -> int:
    try:
        task = parse_task_argument(task_argument)
        normalize_task(task)
        text = read_explanation(explanation)
        result = route_task(explain(text, explanation), task)
    except TaskError as exc:
        sys.stdout.write(json.dumps({"error": "BAD_TASK", "detail": str(exc)}, ensure_ascii=False) + "\n")
        return 2
    except ExplanationError as exc:
        sys.stdout.write(json.dumps({"error": "BAD_EXPLANATION", "detail": str(exc)}, ensure_ascii=False) + "\n")
        return 2
    sys.stdout.write(dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
