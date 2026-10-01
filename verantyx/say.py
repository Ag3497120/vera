"""Grounded free text: a paragraph about a topic, every sentence composed by
grammar from an event the corpus wrote at least twice, independently.

    events   frames read from the store's own sentences that have the topic
             in a role; identical frames from different sources are one event
             with that many witnesses
    select   events with >= 2 independent sources, the topic as agent first,
             then as patient/recipient; ties broken by witness count, then
             alphabetically (no hidden ordering)
    compose  realize.realize — a sentence is emitted only if reading it back
             gives the same frame

Nothing is said that no two sources wrote. What is new is the wording: the
corpus wrote 「資料Aは花子が渡した」 and 「花子が資料Aを渡しました」, Vera says
「花子が資料Aを渡す。」 and cites both.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .frames import Frame, read, read_all
from .realize import realize

GENERAL = Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"


MAX_WITNESS = 80


def _quoted(text: str) -> str:
    import re
    return "".join(re.findall(r"[「『（(][^」』）)]*[」』）)]", text))


_KANA: Dict[str, str] = {}


def _reading(w: str) -> str:
    """Orthography-free key: 叩く/たたく, お母さん/母さん/母 -> one reading."""
    if w in _KANA:
        return _KANA[w]
    from .typed_edges import _tagger
    x = w
    for p in ("お", "ご"):
        if x.startswith(p) and len(x) > 1:
            x = x[1:]
    for suf in ("さん", "ちゃん", "様"):
        if x.endswith(suf) and len(x) > len(suf):
            x = x[: -len(suf)]
    r = "".join((t.feature.kana or t.surface) for t in _tagger()(x))
    _KANA[w] = r
    return r


def _nkey(fr) -> tuple:
    return (_reading(fr.predicate), _reading(fr.agent), _reading(fr.patient),
            _reading(fr.recipient), fr.negated)


def events(topic: str, db: Path = GENERAL, scan: int = 4000, via_index: bool = False,
           srcs: Any = None) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    if via_index:
        # only sentences whose stored edges already have the topic in a role
        # (the ix_dep index) — the same sentences are then read again by rule
        rows = con.execute("SELECT DISTINCT s.text, s.src FROM tedges t JOIN tsent s ON s.sha=t.sha "
                           "WHERE t.dep=? AND t.rel IN ('が','を','に','は') AND length(s.text)<=? LIMIT ?",
                           (topic, MAX_WITNESS, scan)).fetchall()
    else:
        rows = con.execute("SELECT text, src FROM tsent WHERE text LIKE ? LIMIT ?",
                           ("%" + topic + "%", scan)).fetchall()
    con.close()
    if srcs is not None:
        rows = [(t, s) for t, s in rows if s in srcs]     # one leaf of the stereo cross only
    agg: Dict[tuple, Dict[str, Any]] = {}
    for text, src in rows:
        if len(text) > MAX_WITNESS or not text.rstrip().endswith(("。", "！", "？")):
            continue          # list items and titles are not sentences
        q = _quoted(text)
        for fr in read_all(text):
            # generation uses only roles the text marked (が/を/に/によって/
            # cleft focus); topic- and relative-head guesses stay in reading
            if fr.negated or fr.ambiguous or fr.inferred or \
                    topic not in (fr.agent, fr.patient, fr.recipient):
                continue
            if not fr.agent or not (fr.patient or fr.recipient):
                continue
            # a title or quotation is not a claim about the world
            if any(p and p in q for p in (fr.agent, fr.patient, fr.recipient)):
                continue
            e = agg.setdefault(_nkey(fr), {"forms": {}, "sources": {}, "present": 0,
                                           "by_form": {}})
            e["forms"][fr.key()] = e["forms"].get(fr.key(), (fr, 0))[0], \
                e["forms"].get(fr.key(), (fr, 0))[1] + 1
            e["by_form"].setdefault(fr.key(), []).append((src, text))
            if src not in e["sources"]:
                e["sources"][src] = text
                e["present"] += (not fr.past)
    out = []
    for e in agg.values():
        fr = max(e["forms"].values(), key=lambda fc: (fc[1], fc[0].key()))[0]
        wit = e["by_form"][fr.key()]
        out.append({"frame": fr, "n": len(e["sources"]), "present": e["present"],
                    "everyday": sum(1 for s in e["sources"] if not s.startswith("human:")),
                    "witnesses": [{"source": s, "text": t} for s, t in wit[:2]]})
    return out


def say(topic: str, k: int = 5, db: Path = GENERAL, min_sources: int = 2,
        scan: int = 4000, via_index: bool = False, srcs: Any = None) -> Dict[str, Any]:
    # Two sources that both narrate one past episode (父が江戸に出た) are not
    # a general truth; with exactly the minimum, a present-tense witness is
    # required. Three or more independent sources stand on their own.
    # An encyclopedia narrates particular people and works (花 as a character
    # who becomes a golfer); two such lines are not a general truth. At the
    # minimum, one everyday-corpus witness and one present-tense witness are
    # required.
    evs = [e for e in events(topic, db, scan=scan, via_index=via_index, srcs=srcs) if e["n"] > min_sources
           or (e["n"] == min_sources and e["present"] >= 1 and e["everyday"] >= 1)]
    evs.sort(key=lambda e: (e["frame"].agent != topic, -e["n"], e["frame"].key()))
    lines = []
    for e in evs:
        r = realize(e["frame"], past=False)
        s = r["sentences"].get("active") or next(iter(r["sentences"].values()), None)
        if not s:
            continue
        lines.append({"sentence": s, "sources": e["n"], "witnesses": e["witnesses"]})
        if len(lines) >= k:
            break
    if not lines:
        return {"verdict": "NOTHING_ATTESTED_TWICE", "topic": topic, "text": ""}
    return {"verdict": "GROUNDED", "topic": topic,
            "text": "".join(x["sentence"] for x in lines), "lines": lines,
            "note": "every sentence: an event >= %d independent sources wrote; "
                    "wording composed by grammar and read back" % min_sources}
