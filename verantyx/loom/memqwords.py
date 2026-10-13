"""PUB-M6: the QUESTION-WORD TANK (docs/LINE3_PUBLIC_DESIGN.md 4.7, OP-PUB-7; local decisions L-PUB-4x).

A thin, FROZEN vocabulary of the initial layout: for each kind of question word, the slot nouns a memory writer uses for what the word asks (どこ <-> 場所・会場・開催地 ..., いつ <-> 期限・日 ..., 誰 <-> 担当・
責任者 ...).  It was written from general Japanese, in one sitting, BEFORE the offline measurement of this ticket was run, and it is NOT read from any bank, any meter story or any gold answer; a
word that is not here is added by the model with `bridge(question_word, memory_phrase)` (constructed, marked, ledgered), never by editing this table.  An edit is a new version (`qwords.v2`) and a new
`QWORDS_SHA` -- the sha256 of the version and the canonical table -- which a mem.v4 begin row records.

How recall uses it (memask): a question 「X の Y は <question word>」 whose Y is not what the memory calls the slot is tried with the other nouns of the class of the question word (Y first, then the
model's bridges, then this table in this order); a question 「X は <question word>…」 with no slot noun at all is tried with every noun of the class as the slot of X.  Exact surface only: a compound
(副担当, 設置場所) is another noun.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Tuple

QWORDS_VERSION = "qwords.v1"

# (class id, the question words (longest match wins), the slot nouns in the order they are tried)
QWORD_CLASSES: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ("where", ("どこ", "どちら"), ("場所", "開催地", "会場", "所在地", "拠点", "置き場", "設置場所")),
    ("when", ("いつ", "何曜日"), ("日", "日時", "期日", "期限", "締切", "締め切り", "予定日", "開始日", "終了日")),
    ("clock", ("何時",), ("時刻", "時間", "開始時刻", "終了時刻")),
    ("who", ("誰", "だれ"), ("担当", "担当者", "責任者", "窓口", "当番", "管理者")),
    ("count", ("いくつ", "何人", "何個", "何本", "何台", "何部", "何件", "何回"), ("数", "人数", "個数", "本数", "台数", "部数", "件数", "回数")),
    ("money", ("いくら", "何円"), ("価格", "費用", "予算", "金額", "料金", "単価")),
    ("duration", ("何分", "何秒", "何時間", "どれくらい"), ("所要時間", "時間", "期間")),
    ("temperature", ("何度", "何℃"), ("温度", "室温")),
    ("length", ("何メートル", "何センチ"), ("距離", "長さ", "高さ")),
    ("weight", ("何キロ", "何グラム"), ("重さ", "重量")),
    ("rate", ("何％", "何%"), ("割合",)),
)
BARE_WHAT = "何"                                   # the bare 「何」 (「Y は何ですか」): no class, the slot is named in the question


def table_obj() -> dict:
    return {"version": QWORDS_VERSION, "classes": [{"id": c, "words": list(w), "slots": list(s)} for c, w, s in QWORD_CLASSES], "bare": BARE_WHAT}


def table_entries() -> int:
    """How many strings the table holds (question words + slot nouns): the cap of the ticket is about 80."""
    return sum(len(w) + len(s) for _, w, s in QWORD_CLASSES)


QWORDS_SHA = hashlib.sha256(json.dumps(table_obj(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

_BY_WORD: Dict[str, int] = {}
for _i, (_c, _ws, _ss) in enumerate(QWORD_CLASSES):
    for _w in _ws:
        _BY_WORD[_w] = _i
WORDS_LONGEST_FIRST: Tuple[str, ...] = tuple(sorted(_BY_WORD, key=lambda w: (-len(w), w)))


def class_of_word(word: str) -> Optional[str]:
    i = _BY_WORD.get(word)
    return None if i is None else QWORD_CLASSES[i][0]


def slots_of_word(word: str) -> Tuple[str, ...]:
    i = _BY_WORD.get(word)
    return () if i is None else QWORD_CLASSES[i][2]


def find_word(text: str) -> Optional[Tuple[int, str]]:
    """The leftmost question word in `text` (the longest at that place; the bare 何 last): (index, word) or None."""
    best: Optional[Tuple[int, str]] = None
    for w in WORDS_LONGEST_FIRST:
        i = text.find(w)
        if i >= 0 and (best is None or i < best[0]):
            best = (i, w)
    if best is None:
        i = text.find(BARE_WHAT)
        if i >= 0:
            return (i, BARE_WHAT)
    return best


def entries_listing() -> List[str]:
    return ["%s: %s => %s" % (c, "・".join(w), "・".join(s)) for c, w, s in QWORD_CLASSES] + ["bare: %s" % BARE_WHAT]
