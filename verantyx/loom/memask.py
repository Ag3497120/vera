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

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.loom import memcross as mx
from verantyx.loom import memdetect as mdt
from verantyx.loom import memnotes as mn
from verantyx.loom import memqwords as qw
from verantyx.loom import memshape as ms
from verantyx.loom.memguard import parse_source

ASK_VERSION = "ask.v2"                     # ask.v1 + (PUB-M6b, L-PUB-58) the bare 「何」 takes the counter that touches it (何日 何箱 何段 何年 何枚 何番): the question word is 「何日」, not 「何」 + a leftover 「日」
ASK_V3 = "ask.v3"                          # PUB-M6c (L-PUB-70..): ask.v2 + qwords.v2 (「どの<名詞>」) + a question with a relative clause is read by its last noun (never answered by itself) + CANDIDATES when no exact route
                                           # reaches a value + a confirmed bridge may name a whole position + occurrences are checked against the weave_span.v4 read-out (joiners kept) + `sources` of a CHOICE
ASK_VERSIONS: Tuple[str, ...] = (ASK_VERSION, ASK_V3)
JOINERS_V4 = ".,-:/"           # the joiners weave_span.v4 keeps (ops.READOUT_JOINERS): owner 2026-10-13
CANDIDATE_MIN = 2                          # ask.v3: a candidate shares at least this many content units with the question
CANDIDATE_CAP = 5                          # ... and at most this many are offered
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
    ask: str = ASK_VERSION
    relative: bool = False                       # ask.v3: a relative clause before 「は」, read by its last noun (`centre`): this reading is never answered by itself (bridge + candidates only)
    kind_noun: Optional[str] = None              # ask.v3: the noun of 「どの<名詞>」

    def to_obj(self) -> dict:
        d = {"v": self.ask, "ok": self.ok, "reason": self.reason, "frame": self.frame, "shape": self.shape, "centre": self.centre, "path": [list(p) for p in self.path],
             "qword": self.qword, "class": self.qclass, "asked": self.asked, "fixed": [list(p) for p in self.fixed], "via_topic": self.via_topic}
        if self.ask == ASK_V3:
            d["relative"] = self.relative
            d["kind_noun"] = self.kind_noun
        return d


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


def _with_noun(t: str, i: int) -> str:
    """ask.v3: 「どの」 at `i` and the nouns that touch it (「どの部屋」, 「どの会議室」): the question word.  Without a noun the word is 「どの」."""
    end = i + len(qw.WHICH)
    out = ""
    for tok in ms._tokens(t):
        if tok.a == end and not tok.fn and tok.pos1 in ("名詞", "接尾辞"):
            out += tok.s
            end = tok.b
    return qw.WHICH + out


def _relative(question: str, frame: str, word: str, cls: Optional[str], shape: str) -> Optional[Query]:
    """ask.v3: a frame the exchanger cannot read because its subject holds a relative clause or a verb (「新館を開ける日はQQ」, 「分室を閉じる…」) but which ends 「<subject> は QQ」 is read by the LAST NOUN before
    the 「は」 (the head noun of the subject: 日, 箱, 目安): shape F2, centre that noun (with the nouns touching it before), no owner.  None when the frame does not end in 「は QQ」 or the last
    word before the 「は」 is not a noun.  The reading is marked `relative`: recall never answers a question by it (the head noun alone is no position); it serves the bridges and the candidates."""
    toks = ms._tokens(frame)
    for k, t in enumerate(toks):
        if t.s == ms.TOPIC and t.pos2 == "係助詞":
            if frame[t.b:].strip() != PLACEHOLDER:
                return None
            subj = [x for x in toks[:k] if not x.fn]
            if not subj or subj[-1].pos1 not in ("名詞", "接尾辞"):
                return None
            a = subj[-1].a
            j = len(subj) - 1
            while j > 0 and subj[j - 1].b == subj[j].a and subj[j - 1].pos1 in ("名詞", "接尾辞"):
                j -= 1
                a = subj[j].a
            return Query(True, None, question, frame, "F2", frame[a:subj[-1].b], (), word, cls, mx.VALUE, ask=ASK_V3, relative=True)
    return None


def parse_question(question: str, ask: str = ASK_VERSION, shape: str = ms.SHAPES_V2) -> Query:
    """The frame of a question (see the module doc).  `ok` False with a `reason`: no_question_word | frame_not_read:<why> | placeholder_not_asked | no_clause | several_clauses.
    `ask` ask.v3: the question words of qwords.v2 (「どの<名詞>」), the frame is read with the table `shape` (the one the memory was written with), and a frame with a relative clause is read by its last noun."""
    v3 = ask == ASK_V3
    t = _clean(question)
    hit = qw.find_word(t, qw.QWORDS_V2 if v3 else qw.QWORDS_VERSION)
    if hit is None:
        return Query(False, "no_question_word", question, ask=ask)
    i, word = hit
    kind_noun = None
    if word == qw.BARE_WHAT:
        word = _with_counter(t, i)
    elif v3 and word == qw.WHICH:
        word = _with_noun(t, i)
        kind_noun = word[len(qw.WHICH):] or None
    frame = t[:i] + PLACEHOLDER + t[i + len(word):]
    ex = ms.exchange(frame, shape if v3 else ms.SHAPES_V2)
    cls = qw.class_of_word(word)
    if len(ex.clauses) != 1:
        return Query(False, "no_clause" if not ex.clauses else "several_clauses", question, frame, qword=word, qclass=cls, ask=ask, kind_noun=kind_noun)
    c = ex.clauses[0]
    if c.shape == "F0":
        if v3:
            rel = _relative(question, frame, word, cls, shape)
            if rel is not None:
                return rel
        return Query(False, "frame_not_read:%s" % c.reason, question, frame, qword=word, qclass=cls, ask=ask, kind_noun=kind_noun)
    if c.shape in ("F1", "F2"):
        if c.value is None or c.value.text != PLACEHOLDER:
            return Query(False, "placeholder_not_asked", question, frame, qword=word, qclass=cls, ask=ask, kind_noun=kind_noun)
        return Query(True, None, question, frame, c.shape, c.centre, mx._flatten(c.arms), word, cls, mx.VALUE, ask=ask, kind_noun=kind_noun)
    asked = None
    for a in c.arms:
        if a.seat.text == PLACEHOLDER and not a.arms:
            asked = a.particle
    if asked is None and c.quantity is not None and PLACEHOLDER in c.quantity.text:
        asked = "quantity"
    if asked is None and c.object_bare is not None and PLACEHOLDER in c.object_bare.text:
        asked = "object_bare"
    if asked is None:
        return Query(False, "placeholder_not_asked", question, frame, qword=word, qclass=cls, ask=ask, kind_noun=kind_noun)
    fixed = tuple((a.particle, a.seat.text) for a in c.arms if not (a.particle == asked and a.seat.text == PLACEHOLDER))
    return Query(True, None, question, frame, c.shape, c.centre, (), word, cls, asked, fixed, c.via_topic, c.shape == "F4", ask=ask, kind_noun=kind_noun)


# ------------------------------------------------------------------------------------------------------------
# the lookup
# ------------------------------------------------------------------------------------------------------------
def _has(index: mx.MemIndex, pos: Position) -> bool:
    return bool(index.history_full(pos))


def _variants(index: mx.MemIndex, qy: Query, text: str, bridges: Optional[Sequence[mx.Bridge]] = None) -> Tuple[List[Tuple[str, str]], bool]:
    """([(noun, source)] the slot nouns to try after the asked one, in order; source = bridge | class), and whether the question's own slot noun IS one of the class (then it is replaced, else the question
    asks the nouns as the slot of its subject)."""
    out: List[Tuple[str, str]] = []
    keys = [x for x in (qy.centre, qy.qword) if x]
    brs = index.bridges if bridges is None else bridges
    for b in brs:
        if (b.qword in keys or (len(b.qword) >= 2 and b.qword in text)) and all(b.phrase != n for n, _ in out) and b.phrase != qy.centre:
            out.append((b.phrase, "bridge"))
    nouns = qw.slots_of_word(qy.qword) if qy.qword else ()
    for n in nouns:
        if n != qy.centre and all(n != m for m, _ in out):
            out.append((n, "class"))
    bridged = any(b.phrase == qy.centre or b.qword == qy.centre for b in brs)
    explicit = qy.centre in nouns or bridged
    return out, explicit


def _owner_path(path: Path, owner: str) -> Path:
    return (("の", owner),) + path


def _flat(path: Path, centre: str) -> Optional[str]:
    if any(p != "の" for p, _ in path):
        return None
    return "".join(ph for _, ph in reversed(path)) + centre


def _bridge_positions(index: mx.MemIndex, bridges: Sequence[mx.Bridge], qy: Optional[Query], text: str) -> Tuple[Optional[mx.Bridge], List[Position]]:
    """ask.v3: the positions a bridge the MODEL confirmed names as a whole (`bridge(question_phrase, memory_phrase)` with the phrase of a position as a candidate shows it: 棚ラベル照合の締切).  A bridge
    applies when its question phrase is the question's slot noun / question word or occurs in the question text (>= 2 characters); the first bridge that reaches a position wins, no union."""
    keys = [x for x in (qy.centre, qy.qword) if x] if qy is not None and qy.ok else []
    for b in bridges:
        if b.qword in keys or (len(b.qword) >= 2 and b.qword in text):
            ps = [p for p in index.positions_text(b.phrase) if _has(index, p)]
            if ps:
                return b, ps
    return None, []


def _attribute_route(index: mx.MemIndex, qy: Query, text: str, bridges: Optional[Sequence[mx.Bridge]] = None, v3: bool = False) -> Tuple[Optional[str], List[Position], List[str]]:
    """(route, positions, looked_for) of an F1 / F2 frame."""
    looked: List[str] = []
    tank = "F1" if qy.path else "F2"
    pos0: Position = (tank, qy.centre or "", qy.path)
    if v3 and qy.relative:                                         # a relative clause read by its last noun: only a bridge the model confirmed answers it (L-PUB-71)
        b, ps = _bridge_positions(index, index.bridges if bridges is None else bridges, qy, text)
        looked.append("bridge_position:%s" % (b.phrase if b else "-"))
        return ("bridge", ps, looked) if ps else (None, [], looked)
    looked.append("exact:%s" % qy.centre)
    if _has(index, pos0):
        return "exact", [pos0], looked
    f0 = _flat(qy.path, qy.centre or "")
    if f0 is not None:
        looked.append("flat:%s" % f0)
        ps = [p for p in index.positions_flat(f0) if _has(index, p)]
        if ps:
            return "flat", ps, looked
    if v3:
        b, ps = _bridge_positions(index, index.bridges if bridges is None else bridges, qy, text)
        if ps:
            looked.append("bridge_position:%s" % b.phrase)
            return "bridge", ps, looked
    variants, explicit = _variants(index, qy, qy.text, bridges)
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
def written_id(s: str) -> str:
    """memanswer.v8 (L-PUB-93): the identity of a value is the value AS WRITTEN, NFC only.  No casefold, no NFKC, and nothing is removed: 「・」, spaces and every other character are part of the value, so 「1・2日」,
    「12日」 and 「1 2日」 are three values (mn.norm_answer, which strips them, merged them: a contradiction looked like one answer).  No width folding is kept: none can be shown not to merge two written values."""
    return unicodedata.normalize("NFC", s)


SENTENCE_PUNCT = "、，。．.!?！？,"            # memanswer.v9: the punctuation that may stand next to a value without belonging to it (clause / sentence end)


def _is_symbol(ch: str) -> bool:
    cat = unicodedata.category(ch)
    return cat[0] in "SPM" or cat == "Cf"


# memanswer.v10 (L-PUB-99): the boundary of a value is DENY-BY-DEFAULT.  A value (the exact source characters of its parsed units) is CLEAN only if what stands before it is the clause start or the end of a particle /
# topic marker, and what stands after it is the sentence end, a clause mark or the beginning of a particle / copula / predicate ending.  Whatever else touches it (a qualifier 約 超 ほど くらい 程度 以上 以下 未満
# 前後 -- listed here only as DOCUMENTATION --, a superscript, a fraction, a modifier letter, 々 ゝ ー 〆, a symbol, a bracket ...) makes it unclean; whatever its Unicode category.
LEFT_PARTICLES = "はがのにでとをもへ"
LEFT_SUFFIXES = ("から", "まで", "より")
RIGHT_STARTS = ("は", "が", "の", "に", "で", "と", "を", "も", "へ", "から", "まで", "より", "だ", "です", "でし", "でも", "である", "ます", "なる", "なっ", "し", "する")
RIGHT_DENY = ("のみ", "だけ", "ばかり", "しか", "ずつ", "ほど", "くらい", "ぐらい", "など", "でも", "だって", "のくらい")      # particles that restrict or approximate the value: not a boundary
CLAUSE_MARKS = "、，。．!?！？"
QUALIFIERS_DOC = ("約", "超", "ほど", "くらい", "ぐらい", "程度", "以上", "以下", "未満", "前後", "弱", "強")      # documentation only


def _left_ok(text: str, a: int) -> bool:
    j = a
    while j > 0 and text[j - 1] in " \u3000\t":
        j -= 1
    if j == 0:
        return True
    if text[j - 1] in LEFT_PARTICLES or text[j - 1] in CLAUSE_MARKS or text[j - 1] in ":：":
        return True
    return text[max(0, j - 2):j] in LEFT_SUFFIXES


RIGHT_STARTS_V11 = ("は", "が", "の", "に", "で", "と", "を", "も", "へ", "だ", "です", "でし", "ある", "ます", "なる", "なっ", "し", "する")      # memanswer.v11: no から / まで / より (「5日から」 is a start, not the value)
RIGHT_DENY_V11 = RIGHT_DENY + ("とか", "でさえ", "ですら", "からは")
_COPULA = re.compile(r"^(だ|です|である|でした|だった|であった|でございます)$")
_CHANGE = re.compile(r"^に(変更|更新|延期)(する|した|します|しました|になった|になりました|となった|となりました|です|である)?$")
EVENT_ENDINGS = ("る", "う", "く", "ぐ", "す", "つ", "ぬ", "ぶ", "む", "た", "だ", "ます", "ました", "です", "でした")
EVENT_DENY = ("たい", "たく", "かも", "そう", "よう", "でしょ", "だろ", "たら", "なら", "れば", "ない", "なかっ", "ず", "べき", "ほしい", "欲し", "たかっ", "ください", "下さい", "ましょう", "らしい", "みたい",
              "とか", "さえ", "すら", "せいぜい", "もあれ", "はかかる", "を切る", "を過ぎる", "を超える", "を越える", "思", "考え", "聞", "かな", "けど", "ので", "のに", "たり", "まい", "つもり", "予定")
CLAUSE_END_MARKS = "、，。．!?！？"


def _tail(text: str, b: int) -> str:
    e = b
    while e < len(text) and text[e] not in CLAUSE_END_MARKS:
        e += 1
    return text[b:e].strip(" \u3000\t").rstrip(",.")


def asserted_tail(tail: str) -> bool:
    """memanswer.v11 (L-PUB-102): the PREDICATE side is deny-by-default too.  What follows the value in its clause is a plain assertion only if it is nothing (the clause ends with the value), a copula (だ です である
    でした だった ...), a change form in plain / polite present or past (に変更 に更新 に延期 + する した します しました になった となった ...), or a case particle (が を に で と へ) and an event predicate in the plain /
    polite present or past that carries no wish, volition, hedge, request, obligation, conditional, negation, report or bound (EVENT_DENY).  Anything else is NOT asserted: 5日にしたい, 5日になりそう, 5日でしょう,
    5日を切る, 5日はかかる, 5日もあれば, 変更したい / するかも / しよう / すべき / してほしい / したかった."""
    if tail == "" or _COPULA.match(tail) or _CHANGE.match(tail):
        return True
    if len(tail) >= 2 and tail[0] in "がをにでとへ" and len(tail) <= 16 and tail.endswith(EVENT_ENDINGS) and not any(d in tail for d in EVENT_DENY):
        return True
    return False


def value_status(corpus: Any, sid: int, i0: int, i1: int) -> Tuple[str, str, Optional[str]]:
    """memanswer.v11: (identity text, the clean source span, reason) of the WORD-unit stretch i0..i1.  reason None = the value is clean (boundary of v10 with the narrower right side, and an asserted
    predicate); `boundary` = a neighbour the rule does not accept; `not_asserted` = the clause does not end in a plain assertion.  The identity of an unclean value is the text extended to the boundary / the
    end of its clause, so two unclean values never merge with each other or with a clean one; the display is always the clean source span, never a cut string."""
    idx = corpus.spans()
    sps = idx.spans("WORD", sid)
    text = idx.text(sid)
    a, b = sps[i0][0], sps[i1][1]
    span = unicodedata.normalize("NFC", text[a:b])

    def right_ok(b_: int) -> bool:
        j = b_
        while j < len(text) and text[j] in " \u3000\t":
            j += 1
        if j >= len(text) or text[j] in CLAUSE_MARKS:
            return True
        if text[j] in ",." and (j + 1 >= len(text) or text[j + 1] in " \u3000\t" or text[j + 1] in CLAUSE_MARKS):
            return True
        return not any(text.startswith(r, j) for r in RIGHT_DENY_V11) and any(text.startswith(r, j) for r in RIGHT_STARTS_V11)
    a2, b2 = a, b
    while a2 > 0 and not _left_ok(text, a2):
        a2 -= 1
    while b2 < len(text) and not right_ok(b2):
        b2 += 1
    if (a2, b2) != (a, b):
        return unicodedata.normalize("NFC", text[a2:b2]), span, "boundary"
    if not asserted_tail(_tail(text, b)):
        e = b
        while e < len(text) and text[e] not in CLAUSE_END_MARKS:
            e += 1
        return unicodedata.normalize("NFC", text[a:e]), span, "not_asserted"
    return span, span, None


def _right_ok(text: str, b: int) -> bool:
    j = b
    while j < len(text) and text[j] in " \u3000\t":
        j += 1
    if j >= len(text):
        return True
    ch = text[j]
    if ch in CLAUSE_MARKS:
        return True
    if ch in ",." and (j + 1 >= len(text) or text[j + 1] in " \u3000\t" or text[j + 1] in CLAUSE_MARKS):
        return True
    if any(text.startswith(r, j) for r in RIGHT_DENY):
        return False
    return any(text.startswith(r, j) for r in RIGHT_STARTS)


def source_value(corpus: Any, sid: int, i0: int, i1: int, strict: bool = False) -> Tuple[str, bool]:
    """memanswer.v9 (L-PUB-96): (the value AS WRITTEN, clean) for the WORD-unit stretch i0..i1 of sentence `sid`: the source slice extended over every adjacent symbol, punctuation (other than the clause / sentence
    marks of SENTENCE_PUNCT after it), combining mark or format character -- signs, currency, %, #, ~, parentheses, U+0301, U+FE0F ...  The clause parser drops those characters from the value of the index, so the
    value of the index is not what was written (「-5度」 is 「5度」, 「5%」 is 「5」).  clean = nothing had to be added: only then can the stretch be quoted as it stands."""
    idx = corpus.spans()
    sps = idx.spans("WORD", sid)
    text = idx.text(sid)
    a, b = sps[i0][0], sps[i1][1]
    s0, e0 = a, b
    if strict:                                                                  # memanswer.v10: extend to the nearest boundary the rule accepts; clean iff nothing had to be added
        while a > 0 and not _left_ok(text, a):
            a -= 1
        while b < len(text) and not _right_ok(text, b):
            b += 1
        return unicodedata.normalize("NFC", text[a:b]), (a, b) == (s0, e0)
    while a > 0 and _is_symbol(text[a - 1]):
        a -= 1
    while b < len(text) and _is_symbol(text[b]) and text[b] not in SENTENCE_PUNCT:
        b += 1
    return unicodedata.normalize("NFC", text[a:b]), (a, b) == (s0, e0)


def source_entries(corpus: Any, entries: Sequence[mx.Entry], strict: bool = False, v11: bool = False) -> List[mx.Entry]:
    """The entries with their value replaced by the value as written (`source_value`); an entry whose stretch is unknown keeps its value."""
    out: List[mx.Entry] = []
    for e in entries:
        sp = _unit_span(corpus, e.sid, e.units) if corpus is not None else None
        out.append(e if sp is None else replace(e, value=(value_status(corpus, e.sid, sp[0], sp[1])[0] if v11 else source_value(corpus, e.sid, sp[0], sp[1], strict)[0])))
    return out


def _fold(entries: Sequence[mx.Entry], exact: bool = False) -> Tuple[List[List[mx.Entry]], List[Tuple[mx.Entry, dict]]]:
    """(live, history) of the values of ONE position in ONE scope, in slide order.  live = groups of entries with the same normalised value; history = (entry, who replaced it)."""
    live: List[List[mx.Entry]] = []
    hist: List[Tuple[mx.Entry, dict]] = []

    def norm(e: mx.Entry) -> str:
        return written_id(e.value) if exact else mn.norm_answer(e.value)

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


def quote_check(corpus: Any, sid: int, i0: int, i1: int, value: Optional[str] = None, joiners: bool = False, exact: bool = False) -> Tuple[str, str, bool]:
    """(readout, source, verbatim) of the WORD-unit stretch i0..i1 of sentence `sid`.  `readout` is what `weave_span` would read out (the units with the LETTERS of the gaps between them: the loom writes no
    punctuation, so 「v2.4」 reads out as 「v24」, 「6.5万円」 as 「65万円」, 「6/14」 as 「614」), `source` the characters of the sentence from the first unit to the last, `verbatim` iff they are the same text
    (`_squash`), and, when the value the memory holds is given, also the same text as that value (a prefix or a suffix the loom drops as a function word, 「閉」室日, is in the value and not in the units).  An emit is the
    read-out of the thread, so a stretch that is not verbatim cannot be emitted without changing the value (PUB-M6b, L-PUB-54).  `joiners` (PUB-M6c): the read-out of `weave_span.v4`, which keeps the joiners
    . , - : / the source has between two touching units (v2.4 stays v2.4, 6.5万円 stays 6.5万円); any other punctuation is still dropped, so such a stretch is still not verbatim."""
    t = corpus.tier("WORD")
    units = t.sentence_units[sid]
    ok, gaps = corpus.span_gaps("WORD", sid, i0, i1)
    surf = units[i0:i1 + 1]
    idx = corpus.spans()
    sps = idx.spans("WORD", sid)
    if joiners:
        full = idx.text(sid)
        gaps = list(gaps)
        for k in range(len(surf) - 1):
            raw = full[sps[i0 + k][1]:sps[i0 + k + 1][0]]
            if raw != "" and gaps[k] == "" and all(ch in JOINERS_V4 for ch in raw):
                gaps[k] = raw
    readout = "".join(surf[k] + (gaps[k] if k < len(surf) - 1 else "") for k in range(len(surf)))
    source = idx.text(sid)[sps[i0][0]:sps[i1][1]]
    if exact:                                                       # memanswer.v8: the read-out IS the source text (joiners kept by weave_span.v4), no whitespace / 「・」 equivalence
        return readout, source, bool(ok) and readout == source and (value is None or readout == value)
    return readout, source, bool(ok) and _squash(readout) == _squash(source) and (value is None or _squash(readout) == _squash(value))


def _occurrence(index: mx.MemIndex, rows: Sequence[dict], corpus: Any, e: mx.Entry, route: str, position: Any, joiners: bool = False, exact: bool = False, display: bool = False) -> dict:
    row = rows[e.sid]
    _, session, _, role = parse_source(row["source"])
    cr = index.clause_rec(e.sid, e.k)
    o: Dict[str, Any] = {"sid": e.sid, "source": row["source"], "session": session, "role": role, "answer": e.value, "span": _unit_span(corpus, e.sid, e.units),
                         "clause": cr.text if cr is not None else row["sent"], "via": [route], "scope": e.scope, "kind": e.kind,
                         "position": [position[0], position[1], [list(p) for p in position[2]]]}
    if o["span"] is not None:                                      # PUB-M6b: can the stretch be emitted as it stands?  (a value with punctuation inside is read out without it)
        try:
            readout, _source, verbatim = quote_check(corpus, e.sid, o["span"][0], o["span"][1], e.value, joiners, exact)
        except (IndexError, KeyError):
            readout, verbatim = "", False
        o["verbatim"] = verbatim
        if not verbatim:
            o["readout"] = readout
    if display and o["span"] is not None:                          # memanswer.v11: show the clean source span; an unclean value says why and keeps its identity in `written`
        try:
            _w, clean_span, why = value_status(corpus, e.sid, o["span"][0], o["span"][1])
        except (IndexError, KeyError):
            clean_span, why = o["answer"], None
        if why is not None:
            o["answer"], o["unclean"], o["written"] = clean_span, why, e.value
            o["verbatim"] = False
    if e.turn is not None:
        o["turn"] = e.turn
    if e.change is not None:
        o["change"] = {"old": e.change.old, "form": e.change.form}
    return o


def _group(index: mx.MemIndex, rows: Sequence[dict], corpus: Any, entries: Sequence[Tuple[mx.Entry, Any]], route: str, replaced: Optional[Sequence[dict]] = None, joiners: bool = False, exact: bool = False, display: bool = False) -> dict:
    occ = []
    shown: List[str] = []
    for i, (e, pos) in enumerate(entries):
        o = _occurrence(index, rows, corpus, e, route, pos, joiners, exact, display)
        if replaced is not None:
            o["replaced_by"] = replaced[i]
        occ.append(o)
        sv = o["answer"] if display else e.value
        if sv not in shown:
            shown.append(sv)
    occ.sort(key=lambda o: (o["sid"], o["span"] or [0, 0]))
    answers = sorted(shown, key=lambda a: (-len(a), a))
    return {"text": answers[0], "answers": answers, "occurrences": occ}


# ------------------------------------------------------------------------------------------------------------
# ask.v3: CANDIDATES.  Recall never answers fuzzily; when no exact route reaches a value it OFFERS the positions that share >= 2 content units with the question, and the model confirms one with
# bridge(question_phrase, memory_phrase) (constructed, marked, ledgered); only then does recall answer, through the bridge.  (PUB-M6c, owner 2026-10-13 「候補を示し、モデルが確かめて橋を張る」)
# ------------------------------------------------------------------------------------------------------------
TYPE_OF: Dict[str, "re.Pattern[str]"] = {"when": re.compile(r"\d+日|\d+月|曜"), "clock": re.compile(r"\d+時"), "count": re.compile(r"\d"), "money": re.compile(r"\d.*円"),
                                       "duration": re.compile(r"\d.*(分|秒|時間|日)"), "temperature": re.compile(r"\d.*(度|℃)"), "length": re.compile(r"\d"), "weight": re.compile(r"\d"),
                                       "rate": re.compile(r"\d.*[%％]")}
_UNITS: Dict[str, Tuple[str, ...]] = {}


def _units(text: str) -> Tuple[str, ...]:
    """The WORD units of the exchanger's tagger cut of `text` (a pure function of the text; cached)."""
    u = _UNITS.get(text)
    if u is None:
        if len(_UNITS) > 50000:
            _UNITS.clear()
        u = _UNITS[text] = tuple(t.s for t in ms._tokens(text) if not t.fn)
    return u


def _type_ok(word: Optional[str], value: str) -> bool:
    """Does the value look like what the question word asks (a date for いつ, a count for いくつ, an amount for いくら ...)?  General rules of the tank's classes; no class (誰, どこ, 何, どの<名詞>): yes.
    「何<counter>」: the counter is in the value."""
    cls = qw.class_of_word(word) if word else None
    if cls in TYPE_OF:
        return bool(TYPE_OF[cls].search(value))
    if word and word.startswith(qw.BARE_WHAT) and len(word) > 1:
        return word[1:] in value or (word[1:] == "日" and bool(re.search(r"\d+日", value)))
    return True


def _question_word(t: str, qy: Query) -> Optional[str]:
    if qy.qword:
        return qy.qword
    hit = qw.find_word(t, qw.QWORDS_V2)
    if hit is None:
        return None
    i, word = hit
    return _with_counter(t, i) if word == qw.BARE_WHAT else (_with_noun(t, i) if word == qw.WHICH else word)


def _phrase_hint(t: str, word: Optional[str]) -> str:
    """The part of the question the model would bridge from: what stands before the topic 「は」 (else before the question word), at most 24 characters from its end."""
    k = t.find(ms.TOPIC)
    if k <= 0 and word:
        k = t.find(word)
    h = t[:k] if k > 0 else t
    return h[-24:]


def candidates(index: mx.MemIndex, rows: Sequence[dict], question: str, qy: Query) -> List[dict]:
    """The positions (F1 / F2, owners joined by の only) that hold a live value of the type the question word asks and share >= CANDIDATE_MIN content units with the question, best first (stable: the order
    the positions got their first value), at most CANDIDATE_CAP, each with its sentence.  The content units of the question are its tagger units minus the question word and the placeholder."""
    t = _clean(question)
    word = _question_word(t, qy)
    qu = [u for u in dict.fromkeys(_units(t)) if not (word and u in word) and u != PLACEHOLDER]
    if len(qu) < CANDIDATE_MIN:
        return []
    hint = _phrase_hint(t, word)
    scored: List[Tuple[int, int, Position, List[str], List[mx.Entry], List[str]]] = []
    for n, p in enumerate(index.positions):
        text = mx.position_text(p)
        if text is None:
            continue
        pu = [u for _, ph in p[2] for u in _units(ph)] + list(_units(p[1]))
        shared = [u for u in qu if u in pu]
        if len(shared) < CANDIDATE_MIN:
            continue
        live_entries: List[mx.Entry] = []
        values: List[str] = []
        scopes: List[Optional[str]] = []
        es = index.history_full(p)
        for e in es:
            if e.scope not in scopes:
                scopes.append(e.scope)
        for sc in scopes:
            live, _hist = _fold([e for e in es if e.scope == sc])
            for grp in live:
                for e in grp:
                    live_entries.append(e)
                if grp[0].value not in values:
                    values.append(grp[0].value)
        if not live_entries or not _type_ok(word, live_entries[-1].value):
            continue
        scored.append((len(shared), n, p, shared, live_entries, values))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[0][0] if scored else 0
    out: List[dict] = []
    for rank, (sc, _n, p, shared, ents, values) in enumerate(scored[:CANDIDATE_CAP], 1):
        text = mx.position_text(p) or ""
        out.append({"rank": rank, "position": [p[0], p[1], [list(x) for x in p[2]]], "phrase": text, "score": sc, "tied_with_best": sc == top and sum(1 for x in scored if x[0] == top) > 1,
                    "shared": shared, "values": values,
                    "entries": [{"sid": e.sid, "value": e.value, "source": rows[e.sid]["source"], "sentence": rows[e.sid]["sent"]} for e in ents[:3]],
                    "bridge": {"question_word": hint, "memory_phrase": text}})
    return out


def recall(index: mx.MemIndex, rows: Sequence[dict], corpus: Any, question: str, *, open_nest: Optional[str] = None, ask: str = ASK_VERSION,
           bridges: Optional[Sequence[mx.Bridge]] = None, exact_values: bool = False, source_values: bool = False) -> dict:
    """The verdict of one question over the crosses.  `rows` = H (for the source of every sentence), `corpus` = its memory corpus (for the unit stretch to quote; None: no spans),
    `open_nest` = the nest open in the asking session (its statements are preferred).  `ask` ask.v3 (PUB-M6c): see the module doc of that version; `bridges` (ask.v3) = the bridges to use instead of those of
    the index (an answer run adds the ones the model confirmed in it)."""
    v3 = ask == ASK_V3
    qy = parse_question(question, ask, index.shape_version if v3 else ms.SHAPES_V2)
    brs = index.bridges if bridges is None else tuple(bridges)
    out: Dict[str, Any] = {"verdict": "NONE", "question": qy.to_obj(), "engine": ask, "qwords": qw.QWORDS_SHAS[qw.QWORDS_V2 if v3 else qw.QWORDS_VERSION], "sentences": index.n, "answers": []}

    def none(issues: List[str], looked: List[str]) -> dict:
        out.update(issues=issues, looked_for=looked, route=None)
        if v3:
            cs = candidates(index, rows, question, qy)
            out["candidates"] = cs
            if cs:
                out["verdict"] = "CANDIDATES"                       # never an answer: the model confirms one with bridge(), then recall answers through it
        return out

    groups: List[Tuple[Position, List[mx.Entry]]] = []
    looked: List[str] = []
    route: Optional[str] = None
    if not qy.ok:
        if v3:
            b, ps = _bridge_positions(index, brs, None, question)
            if ps:
                route, looked = "bridge", ["bridge_position:%s" % b.phrase]
                groups = [(p, list(index.history_full(p))) for p in ps]
        if not groups:
            return none(["question_unparsed:%s" % qy.reason], [])
    elif qy.shape in ("F1", "F2"):
        route, positions, looked = _attribute_route(index, qy, question, brs, v3)
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
                dq = Query(True, None, qy.text, qy.frame, "F2", subj[0], (), qy.qword, qy.qclass, mx.VALUE, ask=ask)
                route, positions, looked2 = _attribute_route(index, dq, question, brs, v3)
                looked += looked2
                for p in positions:
                    groups.append((p, list(index.history_full(p))))
            if v3 and not groups:
                b, ps = _bridge_positions(index, brs, qy, question)
                if ps:
                    route = "bridge"
                    looked.append("bridge_position:%s" % b.phrase)
                    groups = [(p, list(index.history_full(p))) for p in ps]
    if not groups:
        return none(["no_position"] + (["no_slot_noun_matches"] if qy.shape in ("F1", "F2") else ["no_event_clause"]), looked)
    pool = [e for _, es in groups for e in es]
    if open_nest is not None and any(e.scope == open_nest for e in pool):
        groups = [(p, [e for e in es if e.scope == open_nest]) for p, es in groups]
        groups = [(p, es) for p, es in groups if es]
    live_all: List[Tuple[str, List[Tuple[mx.Entry, Any]]]] = []     # (norm, entries with their position)
    hist_all: List[Tuple[mx.Entry, Any, dict]] = []
    same_seat = False
    for pos, es in groups:
        if source_values:                                                    # memanswer.v9: the value as written, not as the clause parser kept it
            es = source_entries(corpus, es, source_values >= 2, source_values == 3)
        scopes: List[Optional[str]] = []
        for e in es:
            if e.scope not in scopes:
                scopes.append(e.scope)
        for sc in scopes:
            live, hist = _fold([e for e in es if e.scope == sc], exact_values)
            if len(live) >= 2:
                same_seat = True
            for grp in live:
                n = (written_id if exact_values else mn.norm_answer)(grp[0].value)
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
            return none(["no_value"], looked) if v3 else _none_plain(out, looked, route)
        superseded_all = True
        for e, pos, who in hist_all:
            n = (written_id if exact_values else mn.norm_answer)(e.value)
            for item in live_all:
                if item[0] == n:
                    item[1].append((e, pos))
                    break
            else:
                live_all.append((n, [(e, pos)]))
        hist_all = []
    out["route"] = route
    out["looked_for"] = looked
    out["positions_found" if v3 else "candidates"] = len(groups)
    out["answers"] = [_group(index, rows, corpus, ents, route or "exact", None, v3, exact_values, source_values == 3) for _, ents in live_all]
    if hist_all:
        hnorm: List[Tuple[str, List[Tuple[mx.Entry, Any, dict]]]] = []
        for e, pos, who in hist_all:
            n = (written_id if exact_values else mn.norm_answer)(e.value)
            for item in hnorm:
                if item[0] == n:
                    item[1].append((e, pos, who))
                    break
            else:
                hnorm.append((n, [(e, pos, who)]))
        out["history"] = [_group(index, rows, corpus, [(e, pos) for e, pos, _ in items], route or "exact", [w for _, _, w in items], v3, exact_values, source_values == 3) for _, items in hnorm]
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
        if v3:                                                      # how many sentences the values come from: a same_seat CHOICE of >= 2 sources is a contradiction (the answer run refuses to emit one side)
            sids: List[int] = []
            for g in out["answers"]:
                for o in g["occurrences"]:
                    if o["sid"] not in sids:
                        sids.append(o["sid"])
            out["sources"] = len(sids)
    else:
        out["verdict"] = "UPDATED" if hist_all else "ANSWER"
    return out


def _none_plain(out: Dict[str, Any], looked: List[str], route: Optional[str]) -> dict:
    out.update(issues=["no_value"], looked_for=looked, route=route)
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


def completions(index: mx.MemIndex, res: dict, text: str, no_bridge: bool = False) -> List[dict]:
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
    if no_bridge and route == "bridge":                            # memanswer.v6: a bridge the run made names a position the task did not: nothing is completed through it
        return []
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
