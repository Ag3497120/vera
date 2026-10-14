"""MEM-b: the history key and the notes of a memory write (docs/LINE3_LOOM_MEMORY_DESIGN.md 3.3, 4.2 step 7, 9.2 L-MEM-06..10, 19, 20).

THE HISTORY RULE (G4 【条件 2】, L-MEM-06).  The write of sentence t is judged against the sentences BEFORE t, never against itself:
  C_t   = Corpus(bytes(H[0..t]))      the sentence included: the weave reads it
  C_<t  = Corpus(bytes(H[0..t-1]))    the history: the KEY and UNANCHORED read it
so a sentence never confirms itself.  `read.stability_of` is called UNCHANGED with an object whose `corpus` is C_<t (`history_view`): the counts n and p
(sentence co-occurrence and word order, placement.Weights) and the adhesion adj(v, particle) are the structure's own history of the memory space.

THE NOTES (profile `mem.v1`, L-MEM-08; none of them blocks a write: L-MEM-09)
  REVERSAL      the cross is UNSTABLE under (n, p) alone (`strict_np`): the history holds this pair of words in the OTHER order (the only (n, p)-improving swap
                of a cross of at most one arm unit is centre <-> arm unit).  Needs the pair written at least once before.  COUNTED.
  NEW_RELATION  unstable under (n, p, a) and NOT under (n, p): only the adhesion term improves, i.e. a unit has adhesion in the history to another arm
                particle and none to this one.  Information (a legitimate sentence says it as often as a wrong one).
  UNANCHORED    the loom's UNANCHORED re-read against C_<t, for the units of this write only (floor of two sentences).  Information.
  CONFLICT      the loom's `conflicts_prose` over the cumulative thread, reported only when a variant includes a cross of this write.  Meaning in memory:
                one head with different modifiers on one relation, i.e. mostly an enumeration (認証の期限 / 決済の期限).  Counted only under OP-MEM-2 (b)/(c).
  SAME_QUESTION OP-MEM-2 (a): on each clause 「[X の] Y は A」 the structure asks ITSELF 「[X の] Y は何ですか」 through a PLUGGABLE `self_question(question,
                memory)` (the evidence gate of MEM-c plugs in here; a stub stands in until then) and finds two or more distinct answer groups.  COUNTED.
  SELF_QUESTION_UNREADABLE  the hook returned no answer for sentence t's own clause (the gate cannot read the model's own clause): a coverage count, never a detection.
  IDENTIFIER_FLATTENED (L-MEM-19) / NO_RELATION_SEATED (L-MEM-20): information.
Every note is a plain JSON-able dict; the list is sorted (type order, thread position, arm order, canonical form), nothing depends on a dict / set order.

THE EVENTS read from the LEDGER only (like `notes.self_corrections`): UNSEATABLE (a write refused `span_inexpressible`: a SHAPE event, OP-MEM-3) and RESEAT (a
refused or noted write followed within the next 3 model ops of the session by an ok write that shares a WORD unit of two or more characters): `content` iff
what made the model rephrase was a counted CONTENT note and the new write changes the answer set of that question / the order of that pair, else `shape` (cost).
`session_events(rows, ...)` is that reading; it never looks at the memory, only at the rows.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from verantyx.line3 import space as sp
from verantyx.loom import evidence
from verantyx.loom import notes as notelib
from verantyx.loom import read as rd
from verantyx.loom.state import AXES, SPEC, LoomCross, canonical, fmt_seat

MEM_NOTES_VERSION = "mem.v1"
MEM_NOTES_V2 = "mem.v2"                # MEM-fix (L-MEM-61): mem.v1 + a REVERSAL note CITES the two sentences (sid, turn) it is about; recorded as header.notes_profile of a mem.v3 session
MEM_NOTES_V4 = "mem.v4"                # PUB-M5: mem.v2 + the notes made on the memory crosses (SAME_SEAT, UPDATE, REVERSAL_X, ENUMERATION: memdetect); SAME_QUESTION / REVERSAL / CONFLICT stay as second witnesses
MEM_NOTES_VERSIONS: Tuple[str, ...] = (MEM_NOTES_VERSION, MEM_NOTES_V2, MEM_NOTES_V4)
REVERSAL_CITE_MAX = 8                  # the earlier sentences a REVERSAL note lists (the count is in `earlier_n`)
CONFLICT, UNANCHORED = notelib.CONFLICT, notelib.UNANCHORED
REVERSAL, NEW_RELATION, SAME_QUESTION = "REVERSAL", "NEW_RELATION", "SAME_QUESTION"
SELF_QUESTION_UNREADABLE, IDENTIFIER_FLATTENED, NO_RELATION_SEATED = "SELF_QUESTION_UNREADABLE", "IDENTIFIER_FLATTENED", "NO_RELATION_SEATED"
NOTE_TYPES: Tuple[str, ...] = (CONFLICT, UNANCHORED, REVERSAL, NEW_RELATION, SAME_QUESTION, SELF_QUESTION_UNREADABLE, IDENTIFIER_FLATTENED, NO_RELATION_SEATED)
NOTE_TYPES_V4: Tuple[str, ...] = NOTE_TYPES + ("SAME_SEAT", "UPDATE", "REVERSAL_X", "ENUMERATION")      # the notes of the profile mem.v4 (memdetect.CROSS_NOTE_TYPES are the last four)
COUNTED_V4: Tuple[str, ...] = ("SAME_SEAT", "REVERSAL_X")                                              # what the meter counts under notes mem.v4 (UPDATE in a column of its own); the v3 notes are witnesses
NOTE_OP, NOTE_ACTOR = notelib.NOTE_OP, notelib.NOTE_ACTOR
SHAPE = "SHAPE"                        # the event class of a refused `span_inexpressible` write (a ledger event, not a note row)
SHAPE_REFUSALS: Tuple[str, ...] = ("span_inexpressible", "no_shape")      # a write the structure could not seat: the loom's refusal (mem.v1..v3) and the shape exchanger's F0 refusal (mem.v4, PUB-M2)
EVENT_CLASSES: Tuple[str, ...] = NOTE_TYPES + (SHAPE,)           # the `mem.v1` profile: the five of the design + the three informations; SHAPE read from the refusals

# OP-MEM-2: which note types are COUNTED as structural detections.  (a) the new reading, (b) the existing arm CONFLICT only, (c) both.
CONTRADICTION_POLICIES: Tuple[str, ...] = ("a", "b", "c")
COUNTED_BY_POLICY: Dict[str, Tuple[str, ...]] = {"a": (SAME_QUESTION, REVERSAL), "b": (CONFLICT, REVERSAL), "c": (SAME_QUESTION, CONFLICT, REVERSAL)}
# OP-MEM-3: (a) only content RESEATs are structural detections, shape RESEATs are cost; (b) every refused-then-rephrased write counts (the headline only).
UNSEATABLE_POLICIES: Tuple[str, ...] = ("a", "b")
RESEAT_WINDOW = 3                      # L-MEM-07: the next 3 model ops of the same session
MIN_OVERLAP_CHARS = 2                  # L-MEM-07: one shared WORD unit of at least two characters
QUESTION_TAIL = "何ですか"             # L-MEM-10
ARM_PARTICLES = tuple(SPEC.arms)
_IDENT_RX = re.compile(r"[A-Za-z0-9]+(?:[_.][A-Za-z0-9]+)+")


def counted_types(contradiction_policy: str) -> Tuple[str, ...]:
    return COUNTED_BY_POLICY[contradiction_policy]


# ------------------------------------------------------------------------------------------------------------
# the history key (L-MEM-06, L-MEM-07)
# ------------------------------------------------------------------------------------------------------------
def history_view(corpus_before, state) -> SimpleNamespace:
    """What `read.stability_of` / `notes.unanchored` need of a run: `.corpus` and `.state`.  `corpus_before` is C_<t."""
    return SimpleNamespace(corpus=corpus_before, state=state)


def _arm_units(state, cross: LoomCross) -> List[dict]:
    out = []
    for ax in rd.ARM_ORDER:
        arm = cross.arms[AXES.index(ax)]
        for k in range(0, cross.inner_k + 1):
            if arm[k] is not None:
                out.append({"seat": fmt_seat(ax, k), "unit": state.units[arm[k]].surface, "particle": SPEC.arm_of_axis(ax)})
    return out


def history_keys(view, crosses: Sequence[LoomCross]) -> List[dict]:
    """The two stability readings of each new cross against the history: [{cid, centre, np: entry, npa: entry}] (an entry = read.stability_of's)."""
    out = []
    for c in crosses:
        if c.centre is None:
            continue
        out.append({"cid": c.cid, "centre": view.state.units[c.centre].surface,
                    "np": rd.stability_of(view, c, "strict_np"), "npa": rd.stability_of(view, c, "strict_npa")})
    return out


def key_notes(view, keys: Sequence[dict], pos0: int = 0) -> List[dict]:
    """REVERSAL / NEW_RELATION from `history_keys` (L-MEM-07).  trivially_stable (no history, or none of the unit in it) says nothing."""
    out: List[dict] = []
    for pos, k in enumerate(keys):
        cross = view.state.crosses[k["cid"]]
        e_np, e_npa = k["np"], k["npa"]
        if e_np["status"] == "unstable":
            typ, e = REVERSAL, e_np
        elif e_npa["status"] == "unstable":
            typ, e = NEW_RELATION, e_npa
        else:
            continue
        out.append({"type": typ, "cid": k["cid"], "centre": k["centre"], "units": _arm_units(view.state, cross), "key": list(e["key"]),
                    "best_key": list(e["best_key"]), "swaps": [list(s) for s in e["best_swaps"]], "improving": [list(i) for i in e["improving"]],
                    "_pos": pos0 + pos, "_arm": 0})
    return out


def reversal_witnesses(corpus_before, centre: str, arm_units: Sequence[str]) -> List[int]:
    """MEM-fix (L-MEM-61): the sentences of the history that make a cross a REVERSAL.  A cross is unstable under (n, p) iff swapping the centre and an arm unit improves p: the history
    holds the two words more often in the OTHER order.  `p(u, v)` (`space.p_pair`) counts the sentences where u's first occurrence precedes v's, so the witnesses are the sentences of
    C_<t in which the first occurrence of `centre` precedes the first occurrence of an arm unit (the flagged write has the arm unit first).  Sorted sids; [] when a word is not in the space."""
    t = corpus_before.tier("WORD")
    if centre not in t.postings:
        return []
    out = set()
    for u in arm_units:
        if u not in t.postings or u == centre:
            continue
        for sid in set(t.postings[centre]).intersection(t.postings[u]):
            us = t.sentence_units[sid]
            if us.index(centre) < us.index(u):
                out.add(sid)
    return sorted(out)


def _cite_entry(sid: int, rows: Sequence[dict]) -> dict:
    d = {"sid": sid, "source": rows[sid]["source"]}
    if "turn" in rows[sid]:
        d["turn"] = rows[sid]["turn"]
    return d


def cite_reversals(notes: List[dict], corpus_before, t: int, rows_after: Sequence[dict]) -> List[dict]:
    """MEM-fix (L-MEM-61, owner 「REVERSAL ... does not cite the two messages」): every REVERSAL note gains
      sentence  {sid, source, turn?}     this write (sentence t)
      earlier   [{sid, source, turn?}]   the first REVERSAL_CITE_MAX witness sentences (sid order), `earlier_n` = how many there are
      cite      [[turn, turn]]           for a report: the pair (this write's turn, a witness's turn) for each witness written at a DIFFERENT turn, in witness order, at most 3 pairs
    Pure function of the history; other notes are returned unchanged."""
    out = []
    for n in notes:
        if n["type"] != REVERSAL:
            out.append(n)
            continue
        wit = reversal_witnesses(corpus_before, n["centre"], [u["unit"] for u in n["units"]])
        me = _cite_entry(t, rows_after)
        pairs: List[List[str]] = []
        if "turn" in me:
            for w in wit:
                wt = rows_after[w].get("turn")
                if wt is not None and wt != me["turn"]:
                    pair = sorted([wt, me["turn"]], key=lambda x: tuple(int(y) for y in x.split("-")))
                    if pair not in pairs:
                        pairs.append(pair)
        d = dict(n)
        d.update(sentence=me, earlier=[_cite_entry(w, rows_after) for w in wit[:REVERSAL_CITE_MAX]], earlier_n=len(wit), cite=pairs[:3])
        out.append(d)
    return out


def unanchored_notes(view, crosses: Sequence[LoomCross]) -> List[dict]:
    return [dict(n) for n in notelib.unanchored(view, list(crosses))]


def conflict_notes(view, linked: Sequence[LoomCross], new_cids: Sequence[str]) -> List[dict]:
    """The loom's CONFLICT/arm_contents over the cumulative thread, kept only when a variant includes a cross of this write (L-MEM-08)."""
    mine = set(new_cids)
    out = []
    for n in notelib.conflicts_prose(view, list(linked)):
        if any(cid in mine for v in n["variants"] for cid in v["cids"]):
            out.append(n)
    return out


# ------------------------------------------------------------------------------------------------------------
# the clause and the self-question (L-MEM-10) -- the hook for MEM-c
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Answer:
    """One answer the hook found: the sentence `sid` of the memory it stands in, its text, and (optional) the unit stretch (i0, i1) of that sentence.  A stretch
    contained in another stretch of the same sentence is dropped by the detection (one statement, L-MEM-11)."""
    sid: int
    text: str
    span: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class MemoryBefore:
    """What the hook is given.  `rows_before` / `corpus_before` are the memory BEFORE sentence t (H[0..t-1], C_<t); `row` is sentence t and `rows_after` /
    `corpus_after` the memory with it (H[0..t], C_t: the corpus the evidence gate reads, L-MEM-12).  The hook must return the answers of `question`
    over H[0..t]; sentence t's own answers have to be among them, or the detection reports SELF_QUESTION_UNREADABLE."""
    t: int
    row: dict
    rows_before: Tuple[dict, ...]
    rows_after: Tuple[dict, ...]
    corpus_before: Any
    corpus_after: Any


SelfQuestionFn = Callable[[str, MemoryBefore], Sequence[Answer]]
NO_HOOK = "none"


def hook_id(fn: Optional[SelfQuestionFn]) -> str:
    """The name a ledger records for the hook (`header.self_question`).  A hook must have an `id` attribute; replay needs the same id."""
    if fn is None:
        return NO_HOOK
    hid = getattr(fn, "id", None)
    if not isinstance(hid, str) or not hid or hid == NO_HOOK:
        raise ValueError("a self_question hook needs a non-empty str attribute `id` (not %r)" % (NO_HOOK,))
    return hid


def clause_geometry(corpus_t, sid: int, crosses: Sequence[dict]) -> Optional[dict]:
    """Where the clause of `sentence_clause` sits in the sentence as written: {"j" (index of the topic cross T in `crosses`), "first" (index of T's first unit in the
    sentence), "centre" (index of T's centre unit), "start" (character offset of T's first unit), "end" (offset just after T's は)}, or None.  The one place the clause is
    cut (`sentence_clause` and MEM-d's topic expansion both read it)."""
    idx = corpus_t.spans()
    sps = idx.spans("WORD", sid)
    text = idx.text(sid)
    units = list(corpus_t.tier("WORD").sentence_units[sid])
    ranges: List[Tuple[int, int]] = []
    pos = 0
    for c in crosses:
        size = 1 + len(c["seated"])
        ranges.append((pos, pos + size - 1))
        pos += size
    if pos != len(units):
        return None
    for j in range(len(crosses) - 1):
        c = crosses[j]
        if not c["topic"] or any(s["seat"] != "+x:0" for s in c["seated"]):
            continue
        first, centre = ranges[j]
        nxt = ranges[j + 1][0]
        gap = text[sps[centre][1]:sps[nxt][0]]
        k = gap.find(SPEC.centre)
        if k < 0:
            continue
        return {"j": j, "first": first, "centre": centre, "next": nxt, "start": sps[first][0], "end": sps[centre][1] + k + 1}
    return None


def sentence_clause(corpus_t, sid: int, crosses: Sequence[dict], start: Optional[int] = None) -> Optional[dict]:
    """The clause 「[X の] Y は A」 of a woven sentence (L-MEM-10): a topic cross T immediately followed, in the same weave, by a cross N, where T holds no arm unit
    other than on +x (の).  `crosses` = the `crosses` of the weave_span result (the units are consecutive in sentence order: one or two per cross).
    {"cid", "question", "subject": [units], "answer": [the units after T]} or None.  The question is the LITERAL substring of the sentence from T's first
    unit to T's は (so punctuation stays) + 「何ですか」.  `start` (MEM-d): a sentence stored with a DECLARED TOPIC in front of its clause starts the question at the topic (the
    character offset the row records as `topic_at`), not at the first WORD unit of the clause: a compound topic (認証機能 = 認証 + 機能) is asked whole, 「認証機能の締め切りは何ですか」."""
    g = clause_geometry(corpus_t, sid, crosses)
    if g is None:
        return None
    text = corpus_t.spans().text(sid)
    units = list(corpus_t.tier("WORD").sentence_units[sid])
    return {"cid": crosses[g["j"]]["cid"], "question": text[g["start"] if start is None else start:g["end"]] + QUESTION_TAIL, "subject": units[g["first"]:g["centre"] + 1], "answer": units[g["next"]:]}


def subject_less(crosses: Sequence[dict], geometry: dict) -> bool:
    """MEM-d (owner 2026-10-13 「主語の無い文」): the clause's topic cross holds no unit but its centre -- 「締め切りは金曜」, no 「X の」 before the Y."""
    return not crosses[geometry["j"]]["seated"]


def norm_answer(s: str) -> str:
    """NFKC + casefold + `evidence.strip_ignore` (L-MEM-11, MEM-c): the gate's own ignorable characters (spaces, the brackets 「」『』, quotes, 「・」) are not part of an
    answer.  Stripping is applied AFTER the NFKC / casefold so that a full-width variant of an ignorable character is ignored too."""
    return evidence.strip_ignore(unicodedata.normalize("NFKC", s).casefold())


def answer_groups(answers: Sequence[Answer]) -> Tuple[Dict[int, Dict[str, str]], List[List[int]]]:
    """({sid: {norm: display}} of each sentence's MAXIMAL answers, the components).  A stretch contained in another of the same sentence (by span when both
    have one, else by the normalised text) is dropped: one sentence is one statement (O: 「今日の作業はK3の修正」 passes {K3, K3の修正}).  Two sentences AGREE
    iff their answer sets intersect; the components are the connected groups of 'agree' (union-find in sid order), each a sorted list of sids, ordered by
    their smallest sid."""
    per: Dict[int, List[Answer]] = {}
    for a in answers:
        per.setdefault(a.sid, []).append(a)
    sets: Dict[int, Dict[str, str]] = {}
    for sid in sorted(per):
        keep: Dict[str, str] = {}
        items = per[sid]
        for a in items:
            na = norm_answer(a.text)
            if not na:
                continue
            inside = False
            for b in items:
                if b is a:
                    continue
                nb = norm_answer(b.text)
                if a.span is not None and b.span is not None:
                    contained = b.span[0] <= a.span[0] and a.span[1] <= b.span[1] and a.span != b.span
                else:
                    contained = na != nb and na in nb
                if contained:
                    inside = True
                    break
            if not inside and (na not in keep or len(a.text) > len(keep[na])):
                keep[na] = a.text
        if keep:
            sets[sid] = keep
    sids = sorted(sets)
    parent = {s: s for s in sids}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(sids):
        for b in sids[i + 1:]:
            if set(sets[a]) & set(sets[b]):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    comps: Dict[int, List[int]] = {}
    for s in sids:
        comps.setdefault(find(s), []).append(s)
    return sets, [sorted(v) for _, v in sorted(comps.items())]


def same_question_note(question: str, answers: Sequence[Answer], t: int, rows_after: Sequence[dict], cid: str) -> Optional[dict]:
    """The note for one self-question (L-MEM-11 verdicts): CHOICE (>= 2 components) with sentence t among the occurrences -> SAME_QUESTION; sentence t with
    no answer -> SELF_QUESTION_UNREADABLE; ANSWER / NONE -> None.  A tie abstains: nothing is ranked, the variants are listed in sid order."""
    sets, comps = answer_groups(answers)
    if t not in sets:
        return {"type": SELF_QUESTION_UNREADABLE, "question": question, "cid": cid}
    if len(comps) < 2:
        return None
    variants = []
    for comp in comps:
        ans: Dict[str, str] = {}
        for s in comp:
            for n, d in sets[s].items():
                if n not in ans or len(d) > len(ans[n]):
                    ans[n] = d
        variants.append({"answers": [ans[n] for n in sorted(ans, key=lambda n: (-len(n), n))],
                         "occurrences": [dict({"sid": s, "source": rows_after[s]["source"]}, **({"turn": rows_after[s]["turn"]} if "turn" in rows_after[s] else {}))
                                         for s in comp]})
    return {"type": SAME_QUESTION, "question": question, "cid": cid, "variants": variants}


# ------------------------------------------------------------------------------------------------------------
# informations (L-MEM-19, L-MEM-20)
# ------------------------------------------------------------------------------------------------------------
def shape_notes(text: str, crosses: Sequence[dict], n_units: int) -> List[dict]:
    out: List[dict] = []
    idents = sorted(set(_IDENT_RX.findall(text)))
    if idents:
        out.append({"type": IDENTIFIER_FLATTENED, "identifiers": idents,
                    "read_as": [re.sub(r"[_.]", "", i) for i in idents], "_pos": 0, "_arm": 0})
    if n_units >= 3 and not any(c["seated"] or c["topic"] for c in crosses):
        out.append({"type": NO_RELATION_SEATED, "units": n_units, "_pos": 0, "_arm": 0})
    return out


# ------------------------------------------------------------------------------------------------------------
# one write: every note (MEM-b assembly)
# ------------------------------------------------------------------------------------------------------------
def compute_write_notes(*, t: int, row: dict, rows_before: Sequence[dict], rows_after: Sequence[dict], corpus_key: Any, corpus_before: Any, corpus_after: Any,
                        state, linked: Sequence[LoomCross], new_crosses: Sequence[LoomCross], weave: dict, contradiction_policy: str,
                        self_question: Optional[SelfQuestionFn], superseded: Optional[Dict[int, dict]] = None,
                        clause_start: Optional[int] = None, cite: bool = False) -> Tuple[List[dict], dict]:
    """The notes of the write of sentence t, in the loom's note order, and {"keys": [...], "clause": ... | None}.

    `corpus_key` is C_<t as the KEY reads it (= `corpus_before` for OP-MEM-1 (a)/(b); under (c) the rows of the current session are relabelled so they give
    no adhesion).  Nothing here reads `corpus_after` for a KEY: it is only handed to the self-question hook (the gate's corpus) and to the clause cut."""
    view = history_view(corpus_key, state)
    keys = history_keys(view, new_crosses)
    found: List[dict] = []
    found += key_notes(view, keys)
    if cite:                                                       # mem.v2 notes (a mem.v3 session): a REVERSAL names the two sentences it is about
        found = cite_reversals(found, corpus_key, t, rows_after)
    found += unanchored_notes(view, new_crosses)
    found += conflict_notes(view, linked, [c.cid for c in new_crosses])
    clause = sentence_clause(corpus_after, t, weave["crosses"], clause_start)
    if clause is not None and contradiction_policy in ("a", "c") and self_question is not None:
        mem = MemoryBefore(t=t, row=row, rows_before=tuple(rows_before), rows_after=tuple(rows_after), corpus_before=corpus_before, corpus_after=corpus_after)
        answers = list(self_question(clause["question"], mem))
        if superseded:                                  # MEM-d: a sentence the model replaced is history, not a statement that still contests (SAME_QUESTION is made of live ones)
            answers = [a for a in answers if a.sid not in superseded]
        sq = same_question_note(clause["question"], answers, t, rows_after, clause["cid"])
        if sq is not None and sq["type"] == SELF_QUESTION_UNREADABLE and getattr(self_question, "subject_guard", False):       # MEM-c2: say when the guard (not the gate) refused it
            why = self_question.unreadable_reason(clause["question"], mem)
            if why:
                sq["reason"] = why
        if sq is not None:
            sq.update(_pos=0, _arm=0)
            found.append(sq)
    found += shape_notes(row["sent"], weave["crosses"], len(corpus_after.tier("WORD").sentence_units[t]))
    counted = counted_types(contradiction_policy)
    found.sort(key=lambda n: (NOTE_TYPES.index(n["type"]), n["_pos"], n["_arm"], canonical({k: v for k, v in n.items() if not k.startswith("_")})))
    notes = []
    for n in found:
        d = {k: v for k, v in n.items() if not k.startswith("_")}
        d["counted"] = d["type"] in counted
        notes.append(d)
    return notes, {"keys": [{"cid": k["cid"], "centre": k["centre"], "np": _key_view(k["np"]), "npa": _key_view(k["npa"])} for k in keys], "clause": clause}


def _key_view(e: dict) -> dict:
    return {"status": e["status"], "key": e["key"], "improving": e["improving"]}


# ------------------------------------------------------------------------------------------------------------
# events read from the ledger (OP-MEM-3)
# ------------------------------------------------------------------------------------------------------------
def word_units(text: str) -> List[str]:
    """The WORD units of a sentence text on its own (default unit filter): the units of a REFUSED write, which the ledger holds only as text."""
    t = sp.build_tier("WORD", [sp.strip_attribution(text)])
    return list(t.sentence_units[0])


def _model_ops(rows: Sequence[dict]) -> List[dict]:
    return [r for r in rows if r["actor"] == "model" and r["op"] != "begin"]


def _notes_after(rows: Sequence[dict]) -> Dict[int, List[dict]]:
    """row index -> the notes of the loom_note row that follows it directly."""
    out: Dict[int, List[dict]] = {}
    for k, r in enumerate(rows):
        if r["actor"] == NOTE_ACTOR and r["op"] == NOTE_OP and k > 0:
            out[rows[k - 1]["i"]] = r["args"]["notes"]
    return out


def _units_of_write(r: dict) -> List[str]:
    res = r["result"]
    if res.get("ok") is True:
        return [u["surface"] for u in res["units"]]
    return word_units(r["args"].get("text", ""))


def _cross_pairs(res: dict) -> List[Tuple[Tuple[str, ...], str]]:
    """[(arm unit surfaces, centre surface)] of an ok write's crosses."""
    return [(tuple(s["surface"] for s in c["seated"]), c["centre"]["surface"]) for c in res["crosses"]]


def _content_changed(trigger_note: dict, w1: dict, w2: dict) -> bool:
    """Does the ok write w2 change what the counted note on w1 is about?  SAME_QUESTION: w2 asks the same question with another answer unit set.  REVERSAL: w2
    holds both words of the pair in the other order (the flagged order is gone and the reverse is there).  CONFLICT (arm): w2 has a cross with the same centre
    and a different arm content.  Anything else (a shape rephrase, an identical sentence is not even a RESEAT): not content."""
    typ = trigger_note["type"]
    r1, r2 = w1["result"], w2["result"]
    if typ == SAME_QUESTION:
        c1, c2 = r1.get("clause"), r2.get("clause")
        return bool(c1 and c2 and c2["question"] == trigger_note["question"] and set(c2["answer"]) != set(c1["answer"]))
    if typ == REVERSAL:
        arm = tuple(u["unit"] for u in trigger_note["units"])
        pairs2 = _cross_pairs(r2)
        flagged = (arm, trigger_note["centre"])
        reverse = ((trigger_note["centre"],), arm[0] if arm else "")
        return flagged not in pairs2 and reverse in pairs2
    if typ == CONFLICT:
        mine = [p for p in _cross_pairs(r1) if p[1] == trigger_note["centre"]]
        theirs = [p for p in _cross_pairs(r2) if p[1] == trigger_note["centre"]]
        return bool(mine and theirs and all(p not in mine for p in theirs))
    return False


def session_events(rows: Sequence[dict], contradiction_policy: str = "a", unseatable_policy: str = "a", notes_profile: Optional[str] = None) -> dict:
    """Everything a session's ledger says about the structure, from the rows alone:
      notes          {type: count} over the ok writes' note rows;  counted {type: count} for the types the policy counts
      unseatable     {"total", "by_reason": {reason: n}}  (writes refused `span_inexpressible`)
      refused        {refusal type: n} for every refused write
      reseats        [{"trigger_i", "trigger", "to_i", "kind": content | shape}]   (each trigger pairs with its FIRST matching ok write)
      units          {"new", "record"} over the ok writes (origin new = the model supplied the word)
      detections     {"notes": counted notes, "reseat_content": n, "headline": ...}   cost: {"unseatable", "reseat_shape", "unreadable"}
    A RESEAT needs: a trigger (a refused span_inexpressible write, or an ok write with a COUNTED note) and, in the next RESEAT_WINDOW model ops, an ok write
    with a different text that shares a WORD unit of >= MIN_OVERLAP_CHARS characters.  The headline is OP-MEM-3's: (a) notes + content RESEATs, (b) + shape."""
    v4 = notes_profile == MEM_NOTES_V4
    counted = COUNTED_V4 if v4 else counted_types(contradiction_policy)
    notes_by_row = _notes_after(rows)
    ops = _model_ops(rows)
    n_notes = {t: 0 for t in (NOTE_TYPES_V4 if v4 else NOTE_TYPES)}
    refused: Dict[str, int] = {}
    reasons: Dict[str, int] = {}
    new_u = rec_u = 0
    for r in ops:
        if r["op"] != "write" and not (v4 and r["op"] == "keep_unshaped"):
            continue
        res = r["result"]
        if res.get("ok") is True:
            for u in res.get("units", ()):
                if u["origin"] == "new":
                    new_u += 1
                else:
                    rec_u += 1
            for n in notes_by_row.get(r["i"], []):
                n_notes[n["type"]] += 1
        elif r["op"] == "write":
            refused[res["refusal"]] = refused.get(res["refusal"], 0) + 1
            if res["refusal"] in SHAPE_REFUSALS:
                reasons[res["detail"].get("reason", "")] = reasons.get(res["detail"].get("reason", ""), 0) + 1
    reseats: List[dict] = []
    for k, r in enumerate(ops):
        if r["op"] != "write":
            continue
        res = r["result"]
        trig: Optional[dict] = None
        if res.get("ok") is not True:
            if res["refusal"] not in SHAPE_REFUSALS:
                continue
        else:
            trig_notes = [n for n in notes_by_row.get(r["i"], []) if n["type"] in counted]
            if not trig_notes:
                continue
        u1 = {u for u in _units_of_write(r) if len(u) >= MIN_OVERLAP_CHARS}
        for w in ops[k + 1:k + 1 + RESEAT_WINDOW]:
            if w["op"] != "write" or w["result"].get("ok") is not True:
                continue
            if w["args"].get("text") == r["args"].get("text"):
                continue
            if not (u1 & {u for u in _units_of_write(w) if len(u) >= MIN_OVERLAP_CHARS}):
                continue
            kind = "shape"
            if res.get("ok") is True:
                if any(_content_changed(n, r, w) for n in trig_notes):
                    kind = "content"
            reseats.append({"trigger_i": r["i"], "trigger": res["refusal"] if res.get("ok") is not True else trig_notes[0]["type"], "to_i": w["i"], "kind": kind})
            break
    content = sum(1 for x in reseats if x["kind"] == "content")
    shape = len(reseats) - content
    counted_notes = sum(n_notes[t] for t in counted)
    headline = counted_notes + content + (shape if unseatable_policy == "b" else 0)
    out = {"notes": n_notes, "counted": {t: n_notes[t] for t in counted}, "unseatable": {"total": sum(reasons.values()), "by_reason": dict(sorted(reasons.items()))},
           "refused": dict(sorted(refused.items())), "reseats": reseats, "units": {"new": new_u, "record": rec_u},
           "detections": {"notes": counted_notes, "reseat_content": content, "headline": headline},
           "cost": {"unseatable": sum(reasons.values()), "reseat_shape": shape, "unreadable": n_notes[SELF_QUESTION_UNREADABLE]},
           "policy": {"contradiction": contradiction_policy, "unseatable": unseatable_policy}}
    out.update(op_counts(ops))
    return out


def op_counts(ops: Sequence[dict]) -> dict:
    """MEM-d: what the model did with the structure's new operations and what writing in the structure's form cost it, from the model rows alone.
      rewrites   {"refused": writes the structure could not seat (`span_inexpressible`), "rewritten": of those, the ones a later ok write rephrased (a RESEAT whose trigger is
                 the refusal, L-MEM-27), "unrewritten": the rest}.  Owner 2026-10-13 「書き直しは費用として数える」: the cost of the form, never a detection.
      topics     {"declared": ok `declare_topic` rows, "refused": n, "expanded": ok writes stored with the topic as their implicit subject}
      supersedes {"ok": n, "sentences": sentences marked, "refused": {refusal: n}}
      reports    {"ok": n, "refused": n}   (the `report` tool: what the model noticed, mechanically)
    Absent keys are zeros: a ledger of a session before MEM-d has none of these ops."""
    rewritten = 0
    # a refused write is "rewritten" iff a RESEAT (session_events) pairs it; recomputed here so op_counts needs only the model rows
    seat_refused = [k for k, r in enumerate(ops) if r["op"] == "write" and r["result"].get("ok") is not True and r["result"].get("refusal") in SHAPE_REFUSALS]
    for k in seat_refused:
        u1 = {u for u in _units_of_write(ops[k]) if len(u) >= MIN_OVERLAP_CHARS}
        for w in ops[k + 1:k + 1 + RESEAT_WINDOW]:
            if w["op"] != "write" or w["result"].get("ok") is not True or w["args"].get("text") == ops[k]["args"].get("text"):
                continue
            if u1 & {u for u in _units_of_write(w) if len(u) >= MIN_OVERLAP_CHARS}:
                rewritten += 1
                break
    topics_ok = sum(1 for r in ops if r["op"] == "declare_topic" and r["result"].get("ok") is True)
    topics_bad = sum(1 for r in ops if r["op"] == "declare_topic" and r["result"].get("ok") is not True)
    expanded = sum(1 for r in ops if r["op"] == "write" and r["result"].get("ok") is True and "implicit_topic" in r["result"])
    sup_ok = [r for r in ops if r["op"] == "supersede" and r["result"].get("ok") is True]
    sup_ref: Dict[str, int] = {}
    for r in ops:
        if r["op"] == "supersede" and r["result"].get("ok") is not True:
            sup_ref[r["result"]["refusal"]] = sup_ref.get(r["result"]["refusal"], 0) + 1
    rep_ok = sum(1 for r in ops if r["op"] == "report" and r["result"].get("ok") is True)
    rep_bad = sum(1 for r in ops if r["op"] == "report" and r["result"].get("ok") is not True)
    refused = len(seat_refused)
    return {"rewrites": {"refused": refused, "rewritten": rewritten, "unrewritten": refused - rewritten},
            "topics": {"declared": topics_ok, "refused": topics_bad, "expanded": expanded},
            "supersedes": {"ok": len(sup_ok), "sentences": sum(len(r["result"]["superseded"]) for r in sup_ok), "refused": dict(sorted(sup_ref.items()))},
            "reports": {"ok": rep_ok, "refused": rep_bad}}


# ------------------------------------------------------------------------------------------------------------
# the stand-in hook (until the evidence gate is merged: MEM-c)
# ------------------------------------------------------------------------------------------------------------
class StubSelfQuestion:
    """A literal reader of 「<subject>は何ですか」: every memory sentence that starts with 「<subject>は」 answers with the rest of the sentence.  It is NOT the gate (no
    word alignment, no clause cut, no copula rule); it exists so that the SAME_QUESTION detection (answer groups, components, the note) can be built and tested
    before MEM-c plugs `evidence.judge_quote` in.  The hook contract is the same: it answers over H[0..t], sentence t included."""
    id = "stub.v1"

    def __call__(self, question: str, mem: MemoryBefore) -> List[Answer]:
        if not question.endswith("は" + QUESTION_TAIL):
            return []
        subject = question[:-len("は" + QUESTION_TAIL)]
        out: List[Answer] = []
        for sid, r in enumerate(mem.rows_after):
            text = r["sent"]
            if text.startswith(subject + "は"):
                ans = text[len(subject) + 1:].rstrip("。")
                if ans:
                    out.append(Answer(sid, ans))
        return out
