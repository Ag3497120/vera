"""PUB-M6: recall on the crosses (docs/LINE3_PUBLIC_DESIGN.md 4.7, 8; local decisions L-PUB-4x).

question -> the shape exchanger -> (tank, centre, arm path, value seat) -> the crosses -> a verdict, every value with the sentence that wrote it.

  1. THE QUESTION.  The tail (ですか, でしたか, か, ？) is cut, the question word (memqwords) is replaced by a placeholder, and the declarative frame is read by the SAME shape exchanger as a write:
     「認証モジュールの担当者は誰ですか」 -> 「認証モジュールの担当者は<>」 = F1, centre 担当者, の: 認証モジュール, asking the value; 「障害訓練はどこで行いますか」 -> F3 行う, が: 障害訓練 (the topic),
     asking the arm で.  A frame the exchanger cannot read (a relative clause, a paraphrase) is NONE `question_unparsed:<why>`.
  2. THE LOOKUP, routes in this order, the first that finds a value wins and is named in `route` (and in each occurrence's `via`):
       exact     the position (F1 / F2, the centre phrase, the arm path) of the question.
       flat      the same words as ONE phrase: 「認証モジュール担当」 meets 「認証モジュールの担当」, either way round.
       bridge    the slot noun the question asked is replaced by a phrase the MODEL bridged to it (`bridge`, constructed, ledgered) ...
       class     ... or by the other slot nouns of its question word (memqwords); a question with no slot noun at all (「障害訓練はどこで…」) asks the nouns of the class of X.
       event     an event cross (F3, the verb's dictionary form) whose clause holds the other arms of the question: the value is the arm that was asked.
       nest      a SUBJECT-LESS question (no 「X の」): the positions with that centre whose owner is the centre of a declared nest, `via: nest`.
     Statements written while a nest was open (scope) are separate groups; if the recall happens inside a session the statements of the open nest are preferred.
  3. THE VERDICT, from the values of the positions found, in slide order:
       a value is REPLACED when a change clause comes later at its position and scope (it replaces everything before it) or when the model superseded its sentence (history, never an answer);
       one live value  -> ANSWER, or UPDATED when something was replaced (the latest + `history`);
       two or more     -> CHOICE (SAME_SEAT when they stand at one position and scope, else `positions` / `scopes`): nothing is ranked or retracted;
       none            -> NONE (`issues` say why).
     Each live value is a group {"text", "answers", "occurrences"}; an occurrence = {"sid", "source", "session", "role", "answer", "span" (the units of the stretch to quote), "clause", "via", "scope", "kind",
     "turn"?, "change"?, "position"}.  The OUTPUT is unchanged: the model quotes `span` of sentence `sid` with weave_span and emits, and the evidence gate judges the quote against the question AS ASKED.
Pure and deterministic.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.loom import memcross as mx
from verantyx.loom import memdetect as mdt
from verantyx.loom import memnotes as mn
from verantyx.loom import memqwords as qw
from verantyx.loom import memshape as ms
from verantyx.loom.memguard import parse_source

ASK_VERSION = "ask.v2"                     # ask.v1 + (PUB-M6b, L-PUB-58) the bare 「何」 takes the counter that touches it (何日 何箱 何段 何年 何枚 何番): the question word is 「何日」, not 「何」 + a leftover 「日」
PLACEHOLDER = "QQ"
TAILS: Tuple[str, ...] = ("でしょうか", "ですか", "でしたか", "か")           # cut from the end of the question (longest first)
END_MARKS = "？?。 　"
VERDICTS: Tuple[str, ...] = ("ANSWER", "CHOICE", "UPDATED", "NONE")
ROUTES: Tuple[str, ...] = ("exact", "flat", "bridge", "class", "event", "nest")

Path = mx.Path
Position = mx.Position


@dataclass(frozen=True)
class Query:
    ok: bool
    reason: Optional[str]
    text: str
    frame: Optional[str] = None
    shape: Optional[str] = None
    centre: Optional[str] = None
    path: Path = ()
    qword: Optional[str] = None
    qclass: Optional[str] = None
    asked: Optional[str] = None                  # "は" (the value of an attribute) | an arm particle | quantity | object_bare
    fixed: Tuple[Tuple[str, str], ...] = ()      # an event: the other arms the question names
    via_topic: bool = False
    need_nest: bool = False                      # an F4 frame: the subject is the open nest's

    def to_obj(self) -> dict:
        return {"v": ASK_VERSION, "ok": self.ok, "reason": self.reason, "frame": self.frame, "shape": self.shape, "centre": self.centre, "path": [list(p) for p in self.path],
                "qword": self.qword, "class": self.qclass, "asked": self.asked, "fixed": [list(p) for p in self.fixed], "via_topic": self.via_topic}


def _clean(question: str) -> str:
    t = unicodedata.normalize("NFC", question).strip()
    while t and t[-1] in END_MARKS:
        t = t[:-1]
    for tail in TAILS:
        if t.endswith(tail) and len(t) > len(tail):
            t = t[:-len(tail)]
            break
    return t.strip()


def _with_counter(t: str, i: int) -> str:
    """ask.v2: the bare 「何」 at `i` and the unit that touches it: a single-character noun or a counter of the tagger (日 箱 段 年 枚 番 名 分 ...; at most two characters): 「何日」.  A particle after 「何」 (を が も か) is
    no counter.  Otherwise the bare 「何」 as it was."""
    for tok in ms._tokens(t):
        if tok.a == i + 1 and not tok.fn and tok.pos1 in ("名詞", "接尾辞") and len(tok.s) <= 2 and (len(tok.s) == 1 or tok.pos3 in ms.COUNTER_POS3):
            return qw.BARE_WHAT + tok.s
    return qw.BARE_WHAT


def parse_question(question: str) -> Query:
    """The frame of a question (see the module doc).  `ok` False with a `reason`: no_question_word | frame_not_read:<why> | placeholder_not_asked | no_clause."""
    t = _clean(question)
    hit = qw.find_word(t)
    if hit is None:
        return Query(False, "no_question_word", question)
    i, word = hit
    if word == qw.BARE_WHAT:
        word = _with_counter(t, i)
    frame = t[:i] + PLACEHOLDER + t[i + len(word):]
    ex = ms.exchange(frame, ms.SHAPES_V2)
    if len(ex.clauses) != 1:
        return Query(False, "no_clause" if not ex.clauses else "several_clauses", question, frame, qword=word, qclass=qw.class_of_word(word))
    c = ex.clauses[0]
    cls = qw.class_of_word(word)
    if c.shape == "F0":
        return Query(False, "frame_not_read:%s" % c.reason, question, frame, qword=word, qclass=cls)
    if c.shape in ("F1", "F2"):
        if c.value is None or c.value.text != PLACEHOLDER:
            return Query(False, "placeholder_not_asked", question, frame, qword=word, qclass=cls)
        return Query(True, None, question, frame, c.shape, c.centre, mx._flatten(c.arms), word, cls, mx.VALUE)
    asked = None
    for a in c.arms:
        if a.seat.text == PLACEHOLDER and not a.arms:
            asked = a.particle
    if asked is None and c.quantity is not None and PLACEHOLDER in c.quantity.text:
        asked = "quantity"
    if asked is None and c.object_bare is not None and PLACEHOLDER in c.object_bare.text:
        asked = "object_bare"
    if asked is None:
        return Query(False, "placeholder_not_asked", question, frame, qword=word, qclass=cls)
    fixed = tuple((a.particle, a.seat.text) for a in c.arms if not (a.particle == asked and a.seat.text == PLACEHOLDER))
    return Query(True, None, question, frame, c.shape, c.centre, (), word, cls, asked, fixed, c.via_topic, c.shape == "F4")


# ------------------------------------------------------------------------------------------------------------
# the lookup
# ------------------------------------------------------------------------------------------------------------
def _has(index: mx.MemIndex, pos: Position) -> bool:
    return bool(index.history_full(pos))


def _variants(index: mx.MemIndex, qy: Query, text: str) -> Tuple[List[Tuple[str, str]], bool]:
    """([(noun, source)] the slot nouns to try after the asked one, in order; source = bridge | class), and whether the question's own slot noun IS one of the class (then it is replaced, else the question
    asks the nouns as the slot of its subject)."""
    out: List[Tuple[str, str]] = []
    keys = [x for x in (qy.centre, qy.qword) if x]
    for b in index.bridges:
        if (b.qword in keys or (len(b.qword) >= 2 and b.qword in text)) and all(b.phrase != n for n, _ in out) and b.phrase != qy.centre:
            out.append((b.phrase, "bridge"))
    nouns = qw.slots_of_word(qy.qword) if qy.qword else ()
    for n in nouns:
        if n != qy.centre and all(n != m for m, _ in out):
            out.append((n, "class"))
    bridged = any(b.phrase == qy.centre or b.qword == qy.centre for b in index.bridges)
    explicit = qy.centre in nouns or bridged
    return out, explicit


def _owner_path(path: Path, owner: str) -> Path:
    return (("の", owner),) + path


def _flat(path: Path, centre: str) -> Optional[str]:
    if any(p != "の" for p, _ in path):
        return None
    return "".join(ph for _, ph in reversed(path)) + centre


def _attribute_route(index: mx.MemIndex, qy: Query, text: str) -> Tuple[Optional[str], List[Position], List[str]]:
    """(route, positions, looked_for) of an F1 / F2 frame."""
    looked: List[str] = []
    tank = "F1" if qy.path else "F2"
    pos0: Position = (tank, qy.centre or "", qy.path)
    looked.append("exact:%s" % qy.centre)
    if _has(index, pos0):
        return "exact", [pos0], looked
    f0 = _flat(qy.path, qy.centre or "")
    if f0 is not None:
        looked.append("flat:%s" % f0)
        ps = [p for p in index.positions_flat(f0) if _has(index, p)]
        if ps:
            return "flat", ps, looked
    variants, explicit = _variants(index, qy, qy.text)
    for noun, source in variants:
        path = qy.path if explicit else _owner_path(qy.path, qy.centre or "")
        tk = "F1" if path else "F2"
        looked.append("%s:%s" % (source, noun))
        p1: Position = (tk, noun, path)
        if _has(index, p1):
            return source, [p1], looked
        f1 = _flat(path, noun)
        if f1 is not None:
            ps = [p for p in index.positions_flat(f1) if _has(index, p)]
            if ps:
                return source, ps, looked
    if not qy.path:                                               # subject-less: the positions that sit under the centre of a declared nest
        centres = [n.centre for n in index.nests]
        ps = [p for p in index.positions_of(qy.centre or "", ("F1",)) if any(a == "の" and ph in centres for a, ph in p[2]) and _has(index, p)]
        looked.append("nest:%s" % qy.centre)
        if ps:
            return "nest", ps, looked
    return None, [], looked


def _event_entries(index: mx.MemIndex, qy: Query, open_nest: Optional[str]) -> List[mx.Entry]:
    by_clause: Dict[Tuple[int, int], Dict[str, List[mx.Seat]]] = {}
    for tank in ("F3", "F4"):                                      # an event no nest completed stays in the F4 tank
        cr = index.cross(tank, qy.centre or "")
        if cr is None:
            continue
        for slot, seats in cr.slots:
            if slot == mx.VALUE:
                continue
            for s in seats:
                by_clause.setdefault((s.prov.sid, s.prov.clause), {}).setdefault(slot, []).append(s)
    out: List[mx.Entry] = []
    for key in sorted(by_clause):
        arms = by_clause[key]
        if qy.asked not in arms:
            continue
        if not all(any(s.phrase == ph for q in ((p, "を") if (p == mx.NEST_ARM and qy.via_topic) else (p,)) for s in arms.get(q, ())) for p, ph in qy.fixed):
            continue                                              # 「会議はどこで…」: the topic of the question is the subject or the object of the event
        if qy.need_nest:
            subj = arms.get(mx.NEST_ARM, ())
            if not subj or all(s.via != mx.NEST_VIA for s in subj):
                continue
        s = arms[qy.asked][0]
        out.append(mx.Entry(s.phrase, s.prov.sid, s.prov.clause, s.prov.session, s.prov.turn, "first" if not out else "other", None, None, s.marks, s.scope, s.units))
    return out


# ------------------------------------------------------------------------------------------------------------
# the fold of the values of a position and scope, and the verdict
# ------------------------------------------------------------------------------------------------------------
def _fold(entries: Sequence[mx.Entry]) -> Tuple[List[List[mx.Entry]], List[Tuple[mx.Entry, dict]]]:
    """(live, history) of the values of ONE position in ONE scope, in slide order.  live = groups of entries with the same normalised value; history = (entry, who replaced it)."""
    live: List[List[mx.Entry]] = []
    hist: List[Tuple[mx.Entry, dict]] = []

    def norm(e: mx.Entry) -> str:
        return mn.norm_answer(e.value)

    for e in entries:
        if e.marks:
            hist.append((e, {"sid": e.marks[0].by, "kind": "supersede", "reason": e.marks[0].reason}))
            continue
        if e.change is not None:
            same: List[mx.Entry] = []
            for grp in live:
                if norm(grp[0]) == norm(e):
                    same = grp
                else:
                    for o in grp:
                        hist.append((o, {"sid": e.sid, "kind": "change"}))
            live = [same + [e]]
            continue
        for grp in live:
            if norm(grp[0]) == norm(e):
                grp.append(e)
                break
        else:
            live.append([e])
    return live, hist


def _unit_span(corpus: Any, sid: int, units: Sequence[str]) -> Optional[List[int]]:
    if corpus is None or not units:
        return None
    try:
        us = corpus.tier("WORD").sentence_units[sid]
    except (IndexError, KeyError):
        return None
    n = len(units)
    last = None
    for i in range(len(us) - n + 1):
        if tuple(us[i:i + n]) == tuple(units):
            last = i
    return None if last is None else [last, last + n - 1]


def _squash(s: str) -> str:
    """The loom's own text equivalence (T9, L-LOOM-144): whitespace and 「・」 / 「·」 are not part of a text.  Nothing else is dropped: a full stop, a hyphen, a slash or a colon IS."""
    return "".join(ch for ch in s if not ch.isspace() and ch not in "・·")


def quote_check(corpus: Any, sid: int, i0: int, i1: int, value: Optional[str] = None) -> Tuple[str, str, bool]:
    """(readout, source, verbatim) of the WORD-unit stretch i0..i1 of sentence `sid`.  `readout` is what `weave_span` would read out (the units with the LETTERS of the gaps between them: the loom writes no
    punctuation, so 「v2.4」 reads out as 「v24」, 「6.5万円」 as 「65万円」, 「6/14」 as 「614」), `source` the characters of the sentence from the first unit to the last, `verbatim` iff they are the same text
    (`_squash`), and, when the value the memory holds is given, also the same text as that value (a prefix or a suffix the loom drops as a function word, 「閉」室日, is in the value and not in the units).  An emit is the
    read-out of the thread, so a stretch that is not verbatim cannot be emitted without changing the value (PUB-M6b, L-PUB-54)."""
    t = corpus.tier("WORD")
    units = t.sentence_units[sid]
    ok, gaps = corpus.span_gaps("WORD", sid, i0, i1)
    surf = units[i0:i1 + 1]
    readout = "".join(surf[k] + (gaps[k] if k < len(surf) - 1 else "") for k in range(len(surf)))
    idx = corpus.spans()
    sps = idx.spans("WORD", sid)
    source = idx.text(sid)[sps[i0][0]:sps[i1][1]]
    return readout, source, bool(ok) and _squash(readout) == _squash(source) and (value is None or _squash(readout) == _squash(value))


def _occurrence(index: mx.MemIndex, rows: Sequence[dict], corpus: Any, e: mx.Entry, route: str, position: Any) -> dict:
    row = rows[e.sid]
    _, session, _, role = parse_source(row["source"])
    cr = index.clause_rec(e.sid, e.k)
    o: Dict[str, Any] = {"sid": e.sid, "source": row["source"], "session": session, "role": role, "answer": e.value, "span": _unit_span(corpus, e.sid, e.units),
                         "clause": cr.text if cr is not None else row["sent"], "via": [route], "scope": e.scope, "kind": e.kind,
                         "position": [position[0], position[1], [list(p) for p in position[2]]]}
    if o["span"] is not None:                                      # PUB-M6b: can the stretch be emitted as it stands?  (a value with punctuation inside is read out without it)
        try:
            readout, _source, verbatim = quote_check(corpus, e.sid, o["span"][0], o["span"][1], e.value)
        except (IndexError, KeyError):
            readout, verbatim = "", False
        o["verbatim"] = verbatim
        if not verbatim:
            o["readout"] = readout
    if e.turn is not None:
        o["turn"] = e.turn
    if e.change is not None:
        o["change"] = {"old": e.change.old, "form": e.change.form}
    return o


def _group(index: mx.MemIndex, rows: Sequence[dict], corpus: Any, entries: Sequence[Tuple[mx.Entry, Any]], route: str, replaced: Optional[Sequence[dict]] = None) -> dict:
    occ = []
    shown: List[str] = []
    for i, (e, pos) in enumerate(entries):
        o = _occurrence(index, rows, corpus, e, route, pos)
        if replaced is not None:
            o["replaced_by"] = replaced[i]
        occ.append(o)
        if e.value not in shown:
            shown.append(e.value)
    occ.sort(key=lambda o: (o["sid"], o["span"] or [0, 0]))
    answers = sorted(shown, key=lambda a: (-len(a), a))
    return {"text": answers[0], "answers": answers, "occurrences": occ}


def recall(index: mx.MemIndex, rows: Sequence[dict], corpus: Any, question: str, *, open_nest: Optional[str] = None) -> dict:
    """The verdict of one question over the crosses.  `rows` = H (for the source of every sentence), `corpus` = its memory corpus (for the unit stretch to quote; None: no spans),
    `open_nest` = the nest open in the asking session (its statements are preferred)."""
    qy = parse_question(question)
    out: Dict[str, Any] = {"verdict": "NONE", "question": qy.to_obj(), "engine": ASK_VERSION, "qwords": qw.QWORDS_SHA, "sentences": index.n, "answers": []}
    if not qy.ok:
        out.update(issues=["question_unparsed:%s" % qy.reason], looked_for=[], route=None)
        return out
    groups: List[Tuple[Position, List[mx.Entry]]] = []
    looked: List[str] = []
    if qy.shape in ("F1", "F2"):
        route, positions, looked = _attribute_route(index, qy, question)
        for p in positions:
            groups.append((p, list(index.history_full(p))))
    else:
        route = "event"
        es = _event_entries(index, qy, open_nest)
        looked = ["event:%s" % qy.centre]
        if es:
            groups.append((("F3", qy.centre or "", qy.fixed + ((mdt.EVENT_MARK, qy.asked or ""),)), es))
        else:
            route = None
            subj = [ph for p, ph in qy.fixed if p == mx.NEST_ARM]
            if qy.via_topic and len(subj) == 1:                    # 「障害訓練はどこで行いますか」 and the memory says 「障害訓練の開催地は…」: the topic asks the slot nouns of the class of the question word
                dq = Query(True, None, qy.text, qy.frame, "F2", subj[0], (), qy.qword, qy.qclass, mx.VALUE)
                route, positions, looked2 = _attribute_route(index, dq, question)
                looked += looked2
                for p in positions:
                    groups.append((p, list(index.history_full(p))))
    if not groups:
        out.update(issues=["no_position"] + (["no_slot_noun_matches"] if qy.shape in ("F1", "F2") else ["no_event_clause"]), looked_for=looked, route=None)
        return out
    pool = [e for _, es in groups for e in es]
    if open_nest is not None and any(e.scope == open_nest for e in pool):
        groups = [(p, [e for e in es if e.scope == open_nest]) for p, es in groups]
        groups = [(p, es) for p, es in groups if es]
    live_all: List[Tuple[str, List[Tuple[mx.Entry, Any]]]] = []     # (norm, entries with their position)
    hist_all: List[Tuple[mx.Entry, Any, dict]] = []
    same_seat = False
    for pos, es in groups:
        scopes: List[Optional[str]] = []
        for e in es:
            if e.scope not in scopes:
                scopes.append(e.scope)
        for sc in scopes:
            live, hist = _fold([e for e in es if e.scope == sc])
            if len(live) >= 2:
                same_seat = True
            for grp in live:
                n = mn.norm_answer(grp[0].value)
                for item in live_all:
                    if item[0] == n:
                        item[1].extend((e, pos) for e in grp)
                        break
                else:
                    live_all.append((n, [(e, pos) for e in grp]))
            for e, who in hist:
                hist_all.append((e, pos, who))
    superseded_all = False
    if not live_all:
        if not hist_all:
            out.update(issues=["no_value"], looked_for=looked, route=route)
            return out
        superseded_all = True
        for e, pos, who in hist_all:
            n = mn.norm_answer(e.value)
            for item in live_all:
                if item[0] == n:
                    item[1].append((e, pos))
                    break
            else:
                live_all.append((n, [(e, pos)]))
        hist_all = []
    out["route"] = route
    out["looked_for"] = looked
    out["candidates"] = len(groups)
    out["answers"] = [_group(index, rows, corpus, ents, route or "exact") for _, ents in live_all]
    if hist_all:
        hnorm: List[Tuple[str, List[Tuple[mx.Entry, Any, dict]]]] = []
        for e, pos, who in hist_all:
            n = mn.norm_answer(e.value)
            for item in hnorm:
                if item[0] == n:
                    item[1].append((e, pos, who))
                    break
            else:
                hnorm.append((n, [(e, pos, who)]))
        out["history"] = [_group(index, rows, corpus, [(e, pos) for e, pos, _ in items], route or "exact", [w for _, _, w in items]) for _, items in hnorm]
    if superseded_all:
        out["superseded_all"] = True
    if len(out["answers"]) >= 2:
        out["verdict"] = "CHOICE"
        scopes_seen: List[Optional[str]] = []
        for g in out["answers"]:
            for o in g["occurrences"]:
                if o["scope"] not in scopes_seen:
                    scopes_seen.append(o["scope"])
        out["choice_kind"] = "same_seat" if same_seat else ("scopes" if len(scopes_seen) > 1 else "positions")
    else:
        out["verdict"] = "UPDATED" if hist_all else "ANSWER"
    return out


# ------------------------------------------------------------------------------------------------------------
# PUB-M6b: the question the gate is handed when the recall went through a nest, or when the value is the new value of a change clause (OP-PUB-4; local decisions L-PUB-56, L-PUB-57)
# ------------------------------------------------------------------------------------------------------------
CHANGE_WORDS: Dict[str, str] = {"henkou": "変更", "koushin": "更新", "enki": "延期"}
COMPLETE_VERSION = "complete.v1"


def _change_word(form: str) -> Optional[str]:
    """The predicate of a change form that ends in 「に」 (kara_ni_henkou, ni_koushin, ...): 「変更」 / 「更新」 / 「延期」.  kara_he (「へ」, no predicate) and the 「へ」 forms have none: the gate has no slot for them."""
    parts = form.split("_")
    if parts and parts[0] == "kara" and len(parts) == 3 and parts[1] == "ni":
        return CHANGE_WORDS.get(parts[2])
    if len(parts) == 2 and parts[0] == "ni":
        return CHANGE_WORDS.get(parts[1])
    return None


def _same_place(q: dict, position: Sequence[Any]) -> bool:
    """Is `position` (tank, centre, path) the place the question asked: the very position, or the same words read as one phrase (the `flat` route)?"""
    qpath = tuple((p, ph) for p, ph in q["path"])
    ppath = tuple((p, ph) for p, ph in position[2])
    if position[1] == q["centre"] and ppath == qpath:
        return True
    a, b = _flat(qpath, q["centre"] or ""), _flat(ppath, position[1])
    return a is not None and a == b


def completions(index: mx.MemIndex, res: dict, text: str) -> List[dict]:
    """The questions the evidence gate may be handed INSTEAD of the one asked, for the live occurrences of ONE answer (ANSWER / UPDATED; a CHOICE has none), each only for a stretch that can be emitted
    verbatim.  The gate itself is not changed; only the question text is.
      via nest    a SUBJECT-LESS question (no 「X の」) whose value was reached through a nest (route `nest`: the owner of the position is the centre of a declared nest, or a seat written while a nest was
                  open): the question completed by the centre of that nest, 「新製品」 + 「締め切りはいつですか」 -> 「新製品の締め切りはいつですか」.  The gate then reads the nest centre as the subject, so
                  the clause has to hold it.
      via update  the NEW value of a change clause (「6/12 から 6/14 に変更」: the clause of the value is 「6/14 に変更」, it has no subject) at the very position the question asked (route exact or flat):
                  the position is the check the gate cannot make, so the gate is handed the form of the change itself, 「変更は何に変更」 (subject and head are the change word, both in the clause).
    -> [{sid, span, via, question, nest?, centre?, scope, position}] in the order of the occurrences."""
    if res.get("verdict") not in ("ANSWER", "UPDATED") or len(res.get("answers", ())) != 1:
        return []
    q = res.get("question") or {}
    if not q.get("ok") or q.get("shape") not in ("F1", "F2") or q.get("asked") != mx.VALUE:
        return []
    route = res.get("route")
    asked = unicodedata.normalize("NFC", text).strip()
    out: List[dict] = []
    for o in res["answers"][0]["occurrences"]:
        span = o.get("span")
        if span is None or o.get("verbatim") is not True:
            continue
        ch = o.get("change")
        if ch is not None:
            word = _change_word(ch["form"])
            if word is not None and route in ("exact", "flat") and _same_place(q, o["position"]):
                out.append({"sid": o["sid"], "span": list(span), "via": "update", "question": "%sは何に%s" % (word, word), "scope": o["scope"], "position": o["position"]})
            continue
        if q["path"]:                                              # the question names its owner: the gate has its subject
            continue
        nest = None
        if route == "nest" and o["position"][2]:
            owner = o["position"][2][0][1]
            nest = next((n for n in index.nests if n.centre == owner), None)
        elif o["scope"] is not None:
            nest = next((n for n in index.nests if n.id == o["scope"]), None)
        if nest is not None:
            out.append({"sid": o["sid"], "span": list(span), "via": "nest", "nest": nest.id, "centre": nest.centre, "question": nest.centre + "の" + asked, "scope": o["scope"],
                        "position": o["position"]})
    return out
