"""Frame -> sentence, by grammar, checked by reading it back.

The generation half of the frame: 渡す(agent=花子, patient=資料A,
recipient=太郎) becomes 花子が太郎に資料Aを渡した — or the passive, the
cleft, the polite form — built from the verb's conjugation class, not from a
harvested template. Every surface is read back with `frames.read`; a
sentence whose frame does not come back identical is not emitted. That
round trip is what keeps generation from asserting a relation the frame
does not hold (the failure of the harvested forms: 正当防衛が侵害している).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .frames import Frame, read
from .typed_edges import _tagger

_A = {"う": "わ", "く": "か", "ぐ": "が", "す": "さ", "つ": "た", "ぬ": "な",
      "ぶ": "ば", "む": "ま", "る": "ら"}
_I = {"う": "い", "く": "き", "ぐ": "ぎ", "す": "し", "つ": "ち", "ぬ": "に",
      "ぶ": "び", "む": "み", "る": "り"}
_TA = {"う": "った", "つ": "った", "る": "った", "む": "んだ", "ぶ": "んだ", "ぬ": "んだ",
       "く": "いた", "ぐ": "いだ", "す": "した"}


def _class(verb: str) -> str:
    if verb.endswith("する"):
        return "suru"
    if verb in ("来る", "くる"):
        return "kuru"
    toks = list(_tagger()(verb))
    ct = str(toks[-1].feature.cType) if toks else ""
    if "一段" in ct:
        return "ichidan"
    return "godan"


def conjugate(verb: str, *, past: bool = False, neg: bool = False,
              polite: bool = False, passive: bool = False) -> Optional[str]:
    c = _class(verb)
    if passive:
        if c == "suru":
            verb = verb[:-2] + "される"
        elif c == "kuru":
            verb = "来られる"
        elif c == "ichidan":
            verb = verb[:-1] + "られる"
        else:
            verb = verb[:-1] + _A[verb[-1]] + "れる"
        c = "ichidan"
    if c == "suru":
        stem_i, stem_a, stem = verb[:-2] + "し", verb[:-2] + "し", verb[:-2]
    elif c == "kuru":
        stem_i, stem_a = "来", "来"
    elif c == "ichidan":
        stem_i = stem_a = verb[:-1]
    else:
        if verb[-1] not in _A:
            return None
        stem_i, stem_a = verb[:-1] + _I[verb[-1]], verb[:-1] + _A[verb[-1]]
    if polite:
        return stem_i + ("ませんでした" if neg and past else "ません" if neg
                         else "ました" if past else "ます")
    if neg:
        return stem_a + ("なかった" if past else "ない")
    if past:
        if c == "godan":
            return "行った" if verb.endswith("行く") and verb[-2:] == "行く" else verb[:-1] + _TA[verb[-1]]
        return stem_i + "た"
    return verb


def surfaces(fr: Frame, *, past: bool = True) -> Dict[str, str]:
    v = dict(past=past, neg=fr.negated)
    out: Dict[str, str] = {}
    act = conjugate(fr.predicate, **v)
    if act and fr.agent:
        parts = [fr.agent + "が"]
        if fr.recipient:
            parts.append(fr.recipient + "に")
        if fr.patient:
            parts.append(fr.patient + "を")
        out["active"] = "".join(parts) + act + "。"
        pol = conjugate(fr.predicate, polite=True, **v)
        if pol:
            out["polite"] = fr.agent + "は" + "".join(parts[1:]) + pol + "。"
        if fr.patient:
            out["cleft"] = "".join(parts[1:]) + act + "のは" + fr.agent + "だ。"
    pas = conjugate(fr.predicate, passive=True, **v)
    if pas and fr.patient and fr.agent:
        out["passive"] = fr.patient + "が" + fr.agent + "によって" + \
            (fr.recipient + "に" if fr.recipient else "") + pas + "。"
    return out


def realize(fr: Frame, *, past: bool = True) -> Dict[str, object]:
    """Every surface whose reading-back equals the frame; the rest dropped
    and named."""
    kept, dropped = {}, {}
    for form, s in surfaces(fr, past=past).items():
        back = read(s)
        (kept if back and back.key() == fr.key() else dropped)[form] = s
    return {"frame": fr.as_dict(), "sentences": kept, "dropped": dropped}


def regression() -> Dict[str, object]:
    fr = Frame("渡す", "花子", "資料A", "太郎", False)
    r = realize(fr)
    checks = {
        "active": r["sentences"].get("active") == "花子が太郎に資料Aを渡した。",
        "passive": r["sentences"].get("passive") == "資料Aが花子によって太郎に渡された。",
        "all_round_trip": not r["dropped"],
        "neg": realize(Frame("支給する", "会社", "日当", "", True))["sentences"].get("active")
               == "会社が日当を支給しなかった。",
        "ichidan": conjugate("食べる", past=True) == "食べた" and conjugate("食べる", neg=True) == "食べない",
        "godan": conjugate("読む", past=True) == "読んだ" and conjugate("書く", past=True) == "書いた",
    }
    return {"all_pass": all(checks.values()), **checks, "_r": r}
