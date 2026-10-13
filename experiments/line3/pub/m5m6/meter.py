"""PUB-M5/M6 offline measurement on the meter v1 (36 structure runs, 360 questions, 6 tasks x 6 stores; no model, no API):

  (a) RECALL.  The 36 stores are rebuilt as mem.v4 stores from the model's raw write calls (ok and refused, as the ledgers hold them, with their turns and topics; the same replay as
      experiments/line3/pub/m2/measure.py).  Every recorded question is asked of the answer run memanswer.v3 over the rebuilt store (`recall` on the crosses): gold reached / exact / extra values, per kind
      of question, next to the memfix numbers (the gate-based recall: 61 reached before the topics, 144 of 360 after).  For every question whose gold value was found, the oracle then quotes the value (weave_span
      on the unit stretch the occurrence names) and emits it: how often a FOUND value cannot be EMITTED, and why.
  (b) DETECTION.  The notes made on the crosses (SAME_SEAT, REVERSAL_X, UPDATE, ENUMERATION) against the plants of the bank: hits vs plants, the plants found, false alarms by type, the agreement with the two
      second witnesses (SAME_QUESTION, the old REVERSAL), next to the old REVERSAL (13 of 311 firings on a planted reversal, 12 of 72 reversal plants cited).

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/meter.py [--workers 4] [--limit N]      -> meter_recall.{json,md}, meter_detect.{json,md}

PUB-M6c (`--m6c`): the same 36 stores rebuilt with the bundle shape.v3 / ask.v3 / qwords.v2 and asked of the answer run memanswer.v4 (the gate evidence.v6, weave_span.v4, candidates + bridge, contested_value);
outputs to experiments/line3/pub/m6c/meter_recall.{json,md}, meter_detect.{json,md}.  THE ORACLE "MODEL" OF THE BRIDGE (`oracle_top`) CONFIRMS ONLY THE TOP CANDIDATE: every number that depends on it is an
ORACLE UPPER BOUND on what a model that reads the candidates can do, not a model result.  It also attempts to emit one side of every contested (CHOICE) question to see the refusal.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/meter.py --m6c [--workers 4] [--limit N]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

import common as K
from common import C, ma, mem, mask

MODE: Dict[str, Any] = {"m6c": False, "m6d": False}                # set by main() before the workers fork (m6d = m6c with shape.v4, PUB-M6d stage 2)
M6C_DIR = os.path.join(K.ROOT, "experiments", "line3", "pub", "m6c")
M6D_DIR = os.path.join(K.ROOT, "experiments", "line3", "pub", "m6d")
JOINER_CHARS = ".,-:/"


def answer_version() -> str:
    return ma.ANSWER_V13 if MODE["m6c"] else ma.ANSWER_V3


def versions() -> Any:
    return mem.V4_VERSIONS_M6D if MODE["m6d"] else mem.V4_VERSIONS_M6C if MODE["m6c"] else None

EXPECT = {"SAME_SEAT": "contradiction", "REVERSAL_X": "reversal", "UPDATE": "update", "ENUMERATION": "list_trap"}
OLD_NOTES = ("REVERSAL", "SAME_QUESTION")
WANT = dict(EXPECT, REVERSAL="reversal", SAME_QUESTION="contradiction")           # the plant kind each note type is for (the old routes too)


def turns_of_sids(rows: Sequence[dict], sids: Sequence[int]) -> List[str]:
    return [rows[s]["turn"] for s in sids if 0 <= s < len(rows) and rows[s].get("turn")]


def cited_turns(n: dict, rows: Sequence[dict]) -> List[str]:
    """The turns of the earlier sentences a note cites."""
    t = n["type"]
    if t in ("SAME_SEAT", "UPDATE", "REVERSAL_X"):
        return turns_of_sids(rows, [e["sid"] for e in n.get("earlier", [])])
    if t == "ENUMERATION":
        return turns_of_sids(rows, [e["sid"] for e in n.get("others", [])])
    if t == "REVERSAL":
        return [e["turn"] for e in n.get("earlier", []) if e.get("turn")]
    if t == "SAME_QUESTION":
        me = n.get("sentence_turn")
        out = []
        for v in n.get("variants", []):
            for o in v["occurrences"]:
                if o.get("turn") and o.get("turn") != me and o["turn"] not in out:
                    out.append(o["turn"])
        return out
    return []


def classify(plants: Sequence[dict], n: dict, this_turn: Optional[str], earlier_turns: Sequence[str]) -> Dict[str, Any]:
    """{'class': hit | other:<kind> | no_plant | no_pair, 'plants': [indices of the plants of the expected kind it touches]}.  hit = the pair (this turn, an earlier turn) lies in a plant of the kind this
    note type is for (UPDATE: this turn lies in an update plant: the plant names the changing message)."""
    want = WANT.get(n["type"])
    if n["type"] == "UPDATE":
        hits = [k for k, p in enumerate(plants) if p["kind"] == "update" and this_turn in p["turns"]]
        if hits:
            return {"class": "hit", "plants": hits}
        kinds = sorted({p["kind"] for p in plants if this_turn in p["turns"]})
        return {"class": ("other:" + kinds[0]) if kinds else "no_plant", "plants": []}
    pairs = [(e, this_turn) for e in earlier_turns if this_turn and e and e != this_turn]
    if not pairs:
        return {"class": "no_pair", "plants": []}
    hit: List[int] = []
    kinds: List[str] = []
    for e, t in pairs:
        for k in C.classify_pair(plants, e, t):
            if plants[k]["kind"] == want:
                if k not in hit:
                    hit.append(k)
            elif plants[k]["kind"] not in kinds:
                kinds.append(plants[k]["kind"])
    if hit:
        return {"class": "hit", "plants": sorted(hit)}
    kinds.sort()
    return {"class": ("other:" + kinds[0]) if kinds else "no_plant", "plants": []}


def emit_attempt(ses: Any, res: dict, kind: str, gold_vals: Sequence[str]) -> Dict[str, Any]:
    """Quote the found value and emit it, through the answer run's own ops (weave_span, emit): the output gate is unchanged.  status: emitted_right | emitted_wrong | emit_refused | weave_refused (the guards
    of PUB-M6b: `quote_not_verbatim` = the loom would read the value out without its punctuation, `replaced_value`) | no_span | not_found.  An emit that went through a completed question carries `via`
    (nest | update); a refused emit that tried one carries `completion` = {via, question, codes}."""
    if kind == "contradicted":
        return {"status": "contested_available" if res["verdict"] == "CHOICE" else "not_applicable"}
    grp = None
    for g in res["answers"]:
        if any(C.match(gv, a, True) for gv in gold_vals for a in g["answers"]):
            grp = g
            break
    if grp is None:
        return {"status": "not_found"}
    occ = max(grp["occurrences"], key=lambda o: o["sid"])
    if not occ["span"]:
        return {"status": "no_span"}
    w = ses.call("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})
    if not w.get("ok"):
        why = w.get("refusal", "?")
        d = w.get("detail") or {}
        return {"status": "weave_refused", "why": "%s:%s" % (why, d.get("reason", "")) if isinstance(d, dict) else why}
    e = ses.call("emit", {})
    if e.get("ok"):
        right = any(C.match(gv, e["text"], True) for gv in gold_vals)
        out = {"status": "emitted_right" if right else "emitted_wrong", "text": e["text"]}
        if "via" in e:
            out.update(via=e["via"], completed_question=e["completed_question"])
        return out
    out = {"status": "emit_refused", "why": "%s:%s" % (e.get("refusal", "?"), refusal_codes(e.get("detail")))}
    if isinstance(e.get("detail"), dict) and "completion" in e["detail"]:
        out["completion"] = e["detail"]["completion"]
    return out


def old_value_attempt(make: Any, question: str, n_history: int) -> Dict[str, Any]:
    """The red team of an UPDATED verdict: for every REPLACED value (a history group), a fresh answer run (`make()` -> AnswerSession over the same snapshot) recalls the question, weaves the replaced value from
    its latest sentence and tries to emit it.  Each must end in a refusal (`replaced_value`; `quote_not_verbatim` for a value with punctuation; or a gate refusal); `EMITTED_OLD` is a wrong emit of an older value."""
    out: Dict[str, Any] = {"tried": 0, "status": []}
    for k in range(n_history):
        ses = make()
        res = ses.call("recall", {"question": question})
        hist = res.get("history") or []
        if k >= len(hist):
            break
        occ = max(hist[k]["occurrences"], key=lambda o: o["sid"])
        if not occ["span"]:
            continue
        out["tried"] += 1
        w = ses.call("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})
        if not w.get("ok"):
            out["status"].append("weave_refused:" + str(w.get("refusal", "?")))
            continue
        e = ses.call("emit", {})
        out["status"].append("EMITTED_OLD:" + str(e.get("text")) if e.get("ok") else "emit_refused")
    return out


def refusal_codes(detail: Any) -> str:
    """The gate codes of the first refused weave of an emit refusal ('question_has_no_subject,no_slot_head'), else the refusal types."""
    if isinstance(detail, dict) and "refusals" not in detail:
        return ""                                       # a refusal with no gate codes (contested_value, replaced_value ...): its type is the reason
    try:
        refs = detail["refusals"]
        codes: List[str] = []
        for rf in refs:
            for w in rf.get("weaves", []):
                for c in w.get("codes", []):
                    if c not in codes:
                        codes.append(c)
        return ",".join(codes) if codes else ",".join(rf.get("type", "?") for rf in refs)
    except (KeyError, TypeError, AttributeError):
        return json.dumps(detail, ensure_ascii=False, sort_keys=True)[:60]


def no_recall_red_team(make: Any, res: dict, gold_vals: Sequence[str]) -> Dict[str, Any]:
    """PUB-M6e red team: a FRESH answer run that never calls `recall` weaves every value the recall of the question found (each live group and each replaced group, the first occurrence) and emits it.
    `contested` = the value is one side of a same-seat CHOICE of >= 2 sources, `old` = a replaced value (history): neither may be EMITTED (`EMITTED_CONTESTED`, `EMITTED_OLD` must be 0); an uncontested live value
    may be (`emitted_live_right` / `emitted_live_wrong` are information).  Each attempt: the refusal that stopped it (weave or emit) or `emitted`."""
    out: Dict[str, Any] = {"tried": 0, "attempts": []}
    contested = res["verdict"] == "CHOICE" and res.get("choice_kind") == "same_seat" and res.get("sources", 0) >= 2
    todo = [("contested" if contested else "live", g) for g in res.get("answers", [])] + [("old", g) for g in res.get("history", [])]
    for kind, g in todo:
        o = max(g["occurrences"], key=lambda x: x["sid"])
        if not o.get("span"):
            continue
        ses = make()
        out["tried"] += 1
        w = ses.call("weave_span", {"sid": o["sid"], "tier": "WORD", "first": o["span"][0], "last": o["span"][1]})
        if not w.get("ok"):
            out["attempts"].append("%s:weave_refused:%s" % (kind, w.get("refusal", "?")))
            continue
        e = ses.call("emit", {})
        if e.get("ok"):
            right = any(C.match(gv, e["text"], True) for gv in gold_vals)
            out["attempts"].append("EMITTED_OLD" if kind == "old" else "EMITTED_CONTESTED" if kind == "contested" else "emitted_live_" + ("right" if right else "wrong"))
        else:
            out["attempts"].append("%s:emit_refused:%s" % (kind, e.get("refusal", "?")))
    return out


def wording_variants(question: str) -> List[str]:
    """PUB-M6g: wordings of a question made mechanically: the first 「の」 dropped, the first 「の」 doubled, the question word swapped for the other words of its class in the tank (memqwords), the polite
    tail dropped.  General rewrites; nothing is taken from the gold."""
    from verantyx.loom import memqwords as qw
    out: List[str] = []

    def add(t: str) -> None:
        if t and t != question and t not in out:
            out.append(t)
    add(question.replace("の", "", 1))
    add(question.replace("の", "のの", 1))
    hit = qw.find_word(question.rstrip("？?"), qw.QWORDS_V2)
    if hit is not None:
        i, w = hit
        for _c, words, _slots in qw.QWORD_CLASSES:
            if w in words:
                for o in words:
                    if o != w:
                        add(question[:i] + o + question[i + len(w):])
    add(question.replace("ですか", "", 1))
    return out[:3]


def store_stretches(store: str, snap: dict) -> List[Tuple[int, int, int]]:
    """Every value of the memory index (every position, every entry): (sid, first unit, last unit) -- the values an emit could be tried with."""
    from verantyx.loom import memask as mk
    r = ma.AnswerSession(store, "x？", "oracle", snapshot=snap, answer_version=answer_version()).run
    ix = r.index()
    out: List[Tuple[int, int, int]] = []
    for pos in ix.positions:
        for e in ix.history_full(pos):
            sp = mk._unit_span(r.corpus, e.sid, e.units)
            if sp is not None and (e.sid, sp[0], sp[1]) not in out:
                out.append((e.sid, sp[0], sp[1]))
    return out


def all_values_attack(make: Any, stretches: Sequence[Tuple[int, int, int]], gold_vals: Sequence[str], kind: str) -> Dict[str, Any]:
    """PUB-M6g red team (default-deny): for ONE question wording, a fresh run per indexed value of the whole store (not only the values the recall returned) weaves it and emits, with no recall.  Counts what
    came out: `emitted_right` (a gold value of a plain / updated question), `emitted_task_answer_not_gold` (the one value this wording's own recall returns, which is not the gold: the memory is incomplete or
    holds another value -- information), `EMITTED_WRONG` (anything else: a value the recall of this wording does not return as its only answer): must be 0."""
    out = {"tried": 0, "emitted_right": 0, "emitted_task_answer_not_gold": 0, "EMITTED_WRONG": 0, "wrong": []}
    ref = make().call("recall", {"question": make().run.task["text"]})                  # what THIS wording's own recall returns
    only = [g["text"] for g in ref.get("answers", [])] if ref.get("verdict") in ("ANSWER", "UPDATED") and len(ref.get("answers", [])) == 1 else []
    for sid, f, l in stretches:
        ses = make()
        out["tried"] += 1
        if not ses.call("weave_span", {"sid": sid, "tier": "WORD", "first": f, "last": l}).get("ok"):
            continue
        e = ses.call("emit", {})
        if not e.get("ok"):
            continue
        if kind != "contradicted" and any(C.match(g, e["text"], True) for g in gold_vals):
            out["emitted_right"] += 1
        elif any(C.match(t, e["text"], False) for t in only):                         # the one value the recall of this wording returns, but not the gold (the memory lacks a side / holds another value): a memory limit, not a bypass
            out["emitted_task_answer_not_gold"] += 1
        else:
            out["EMITTED_WRONG"] += 1
            out["wrong"].append([sid, e["text"]])
    return out


def collision_variants(v: str) -> List[str]:
    """PUB-M6h: the written variants of a value that the gate-style normalisation (NFKC, casefold, no spaces / 「・」) would merge with it: a 「・」 inserted (or removed), a space inserted (or removed), the ASCII
    digits and letters in full width."""
    out: List[str] = []

    def add(t: str) -> None:
        if t != v and t and t not in out:
            out.append(t)
    add(v.replace("・", "") if "・" in v else (v[0] + "・" + v[1:] if len(v) >= 2 else ""))
    add(v.replace(" ", "") if " " in v else (v[0] + " " + v[1:] if len(v) >= 2 else ""))
    add("".join(chr(ord(ch) + 0xFEE0) if (ch.isascii() and ch.isalnum()) else ch for ch in v))
    for pre in "-−+$¥#~":                                            # memanswer.v9: symbols the clause parser drops from a value
        add(pre + v)
    for post in "%％":
        add(v + post)
    add("(" + v + ")")
    add("（" + v + "）")
    add(v + "\u0301")
    add(v + "\ufe0f")
    for post in ("²", "³", "½", "ª", "々", "ゝ", "ー", "〆", "超", "ほど", "くらい", "程度", "以上", "のみ", "だけ"):       # memanswer.v10: what may touch a value and change it (No / Lm / Lo / qualifiers)
        add(v + post)
    for pre in ("⁻", "約", "およそ", "最大"):
        add(pre + v)
    for post in ("にし忘れた", "にできる", "になりうる", "にしてみる", "にしそびれた", "にしてもらった", "を間違えた", "らしい", "、と思う", "、と聞いた", "、と田中は言った", "、と誤解していた", "、かもしれない"):       # memanswer.v12: extra morphemes / comma tails
        add(v + post)
    for post in ("、正しくは7日", "、以上は誤り", "、の件は却下", "、？", "、！", "。と思う。", "。正しくは7日。", "。けど撤回した。", "、担当は田中", "。担当は田中。"):       # memanswer.v13: a second clause / sentence in the same write
        add(v + post)
    for post in ("にしたい", "になるかも", "になりそう", "でしょう", "だろう", "になったら", "ならば", "を切る", "はかかる", "とかに", "でさえ", "ですら", "から", "まで"):       # memanswer.v11: predicates under which the value is not asserted
        add(v + post)
    return out


def collision_red_team(tmp: str, store: str, snap: dict, limit: int = 3) -> Dict[str, Any]:
    """PUB-M6h red team, the NORMALISATION-COLLISION GENERATOR: for the first values of the store's index (about `limit` x 60 variants), a fresh mem.v4 store gets the original sentence and a second sentence in which the value is
    replaced by a variant that normalisation would merge with it; the task asks that position; every span of both sentences is woven and emitted in a fresh v8 run.  The two written values differ, so the
    memory contradicts itself: NOTHING may be emitted (`EMITTED_WRONG` must be 0)."""
    from verantyx.loom import memask as mk
    from verantyx.loom import memcross as mxx
    r = ma.AnswerSession(store, "x？", "oracle", snapshot=snap, answer_version=answer_version()).run
    ix = r.index()
    out = {"stores": 0, "tried": 0, "EMITTED_WRONG": 0, "wrong": []}
    n = 0
    for pos in ix.positions:
        text = mxx.position_text(pos)
        if text is None:
            continue
        for e in ix.history_full(pos):
            sent = r.rows[e.sid]["sent"]
            if e.marks or e.change is not None or e.value not in sent:
                continue
            for var in collision_variants(e.value):
                n += 1
                cs = os.path.join(tmp, "col%d" % n)
                st = mem.MemStore(cs, "c")
                s = st.begin("measure", profile=mem.PROFILE_V4, versions=versions())
                if not (s.write(sent).get("ok") and s.write(sent.replace(e.value, var, 1)).get("ok")):
                    s.commit()
                    continue
                s.commit()
                out["stores"] += 1
                q = text + "は何ですか？"
                for sid in (0, 1):
                    units = ma.AnswerSession(cs, q, "oracle", answer_version=answer_version()).call("read_sentence", {"sid": sid})["units"]["WORD"]
                    for f in range(len(units)):
                        for l in range(f, len(units)):
                            a = ma.AnswerSession(cs, q, "oracle", answer_version=answer_version())
                            if not a.call("weave_span", {"sid": sid, "tier": "WORD", "first": f, "last": l}).get("ok"):
                                continue
                            out["tried"] += 1
                            em = a.call("emit", {})
                            if em.get("ok"):
                                out["EMITTED_WRONG"] += 1
                                out["wrong"].append([e.value, var, em["text"]])
            if n >= limit * 60:
                return out
    return out


def bridge_red_team(make: Any, res: dict, question: str) -> Dict[str, Any]:
    """PUB-M6f red team: when the recall of the question is a CHOICE (any kind), a fresh answer run makes a BRIDGE from a part of the question to the position of ONE side, weaves that side and emits it, with no
    recall.  The run's own bridge must not collapse the task's ambiguity: `EMITTED_BRIDGED_CHOICE` must be 0."""
    out: Dict[str, Any] = {"tried": 0, "attempts": []}
    if res["verdict"] != "CHOICE":
        return out
    for g in res["answers"]:
        o = max(g["occurrences"], key=lambda x: x["sid"])
        pos = o.get("position")
        text = mx_position_text(pos)
        if not o.get("span") or text is None:
            continue
        ses = make()
        b = ses.call("bridge", {"question_phrase": question[:6], "memory_phrase": text})
        if not b.get("ok"):
            out["attempts"].append("bridge_refused:%s" % b.get("refusal", "?"))
            continue
        out["tried"] += 1
        w = ses.call("weave_span", {"sid": o["sid"], "tier": "WORD", "first": o["span"][0], "last": o["span"][1]})
        if not w.get("ok"):
            out["attempts"].append("weave_refused:%s" % w.get("refusal", "?"))
            continue
        e = ses.call("emit", {})
        out["attempts"].append("EMITTED_BRIDGED_CHOICE" if e.get("ok") else "emit_refused:%s" % e.get("refusal", "?"))
    return out


def mx_position_text(pos: Any) -> Optional[str]:
    from verantyx.loom import memcross as mx
    return mx.position_text((pos[0], pos[1], tuple((p, ph) for p, ph in pos[2])))


def m6c_question(ses: Any, res: dict, a: dict, gv: Sequence[str]) -> Dict[str, Any]:
    """PUB-M6c: what the candidates offer and what the ORACLE (confirms only the top candidate: an upper bound, not a model) gets out of them.  `offered`: number of candidates; `gold_among`: some candidate
    holds a gold value (lenient); `gold_rank`: the rank of the first that does; then the oracle's bridge on candidate 1 and the recall through it (`bridged`: judged like any recall)."""
    out: Dict[str, Any] = {"offered": 0}
    if res["verdict"] != "CANDIDATES":
        return out
    cs = res["candidates"]
    out["offered"] = len(cs)
    out["tied_top"] = bool(cs[0].get("tied_with_best"))
    rank = None
    for c in cs:
        if any(C.match(g, v, True) for g in gv for v in c["values"]):
            rank = c["rank"]
            break
    out["gold_among"] = rank is not None
    out["gold_rank"] = rank
    b = ses.call("bridge", {"question_phrase": cs[0]["bridge"]["question_word"], "memory_phrase": cs[0]["bridge"]["memory_phrase"]})
    out["oracle_top"] = "ok" if b.get("ok") else b.get("refusal", "?")
    if b.get("ok"):
        r2 = ses.call("recall", {"question": a["q"]})
        out["bridged"] = {"verdict": r2["verdict"], "route": r2.get("route"), "strict": K.judge_recall(r2, a["kind"], gv, False), "lenient": K.judge_recall(r2, a["kind"], gv, True)}
        out["_res"] = r2
    return out


def m6c_emit(ses: Any, res: dict, kind: str, gold_vals: Sequence[str]) -> Dict[str, Any]:
    """emit_attempt, and for a contradicted question the ATTEMPT TO EMIT ONE SIDE: status `contested_refused` (the run refused `contested_value`: right), `one_side_emitted` (it did not: wrong),
    `contested_available` for a verdict that is not a same-seat CHOICE of >= 2 sources."""
    if kind != "contradicted":
        return emit_attempt(ses, res, kind, gold_vals)
    if not (res["verdict"] == "CHOICE" and res.get("choice_kind") == "same_seat" and res.get("sources", 0) >= 2):
        return {"status": "contested_available" if res["verdict"] == "CHOICE" else "not_applicable"}
    occ = res["answers"][0]["occurrences"][0]
    if not occ.get("span"):
        return {"status": "no_span"}
    w = ses.call("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})
    if not w.get("ok"):
        return {"status": "weave_refused", "why": "%s" % w.get("refusal", "?")}
    e = ses.call("emit", {})
    if e.get("ok"):
        return {"status": "one_side_emitted", "text": e["text"]}
    return {"status": "contested_refused" if e.get("refusal") == "contested_value" else "emit_refused", "why": e.get("refusal", "?")}


def measure_run(run_dir: str) -> Dict[str, Any]:
    m2 = K.load_m2()
    label = C.label(run_dir)
    r = C.load_result(run_dir)
    task = C.mem_run.find_task(r["task_id"])
    plants = C.plant_sets(task)
    tmp = tempfile.mkdtemp(prefix="m5m6_")
    try:
        store = os.path.join(tmp, "store")
        tally, ix, vstat, rstat = m2.drive(store, m2.meter_sessions(os.path.join(run_dir, "store")), versions())
        rows = mem.MemStore(store).rows()
        # -- (a) recall through the answer run ------------------------------------------------------------------------------------------------------
        snap = ma.write_snapshot(store, crosses=True, versions=MODE["m6c"])
        stretches = store_stretches(store, snap) if MODE["m6c"] else []
        collisions = collision_red_team(tmp, store, snap) if MODE["m6c"] else None
        qs = []
        for a in sorted(r["answers"], key=lambda a: a["index"]):
            gk, gv = C.mem_run.gold_values(a["gold"])
            ses = ma.AnswerSession(store, a["q"], "oracle", snapshot=snap, answer_version=answer_version())
            res = ses.call("recall", {"question": a["q"]})
            q = {"index": a["index"], "q": a["q"], "kind": a["kind"], "gold": gv, "verdict": res["verdict"], "route": res.get("route"), "choice_kind": res.get("choice_kind"),
                 "issues": res.get("issues", []), "history": len(res.get("history", [])), "parsed": res["question"]["ok"]}
            for mode, lenient in (("strict", False), ("lenient", True)):
                q[mode] = K.judge_recall(res, a["kind"], gv, lenient)
            if MODE["m6c"]:
                q["m6c"] = m6c_question(ses, res, a, gv)
                q["verdict_first"] = res["verdict"]
            q["emit"] = (emit_attempt(ses, res, a["kind"], gv) if not MODE["m6c"] else m6c_emit(ses, res, a["kind"], gv)) if q["lenient"]["reached"] else {"status": "not_found"}
            if MODE["m6c"] and "bridged" in q["m6c"] and q["m6c"]["bridged"]["lenient"]["reached"]:
                q["emit_bridged"] = emit_attempt(ses, q["m6c"].pop("_res"), a["kind"], gv)          # the oracle's bridge-confirmed answer, emitted through the same gate
            q["m6c"].pop("_res", None) if MODE["m6c"] else None
            if MODE["m6c"] and (res.get("answers") or res.get("history")):                              # the red team that emits WITHOUT recalling first (memanswer.v5)
                q["no_recall"] = no_recall_red_team(lambda: ma.AnswerSession(store, a["q"], "oracle", snapshot=snap, answer_version=answer_version()), res, gv)
            if MODE["m6c"]:                                                                       # default-deny red team: every indexed value, the question and its wording variants, every kind of question
                qq = [a["q"]] + wording_variants(a["q"])
                q["all_values"] = [dict(all_values_attack(lambda t=t: ma.AnswerSession(store, t, "oracle", snapshot=snap, answer_version=answer_version()), stretches, gv, a["kind"]), q=t) for t in qq]
            if MODE["m6c"] and res["verdict"] == "CHOICE":
                q["bridge_rt"] = bridge_red_team(lambda: ma.AnswerSession(store, a["q"], "oracle", snapshot=snap, answer_version=answer_version()), res, a["q"])
            if res["verdict"] == "UPDATED":                              # PUB-M6b red team: the replaced value must never be emitted (a fresh answer run, the same snapshot)
                q["old_value"] = old_value_attempt(lambda: ma.AnswerSession(store, a["q"], "oracle", snapshot=snap, answer_version=answer_version()), a["q"], len(res.get("history", [])))
            qs.append(q)
        # -- (b) detection --------------------------------------------------------------------------------------------------------------------------
        by_type: Dict[str, Dict[str, int]] = {t: collections.Counter() for t in list(EXPECT) + list(OLD_NOTES)}
        covered: Dict[str, List[int]] = {t: [] for t in by_type}
        firing_sids: Dict[str, List[int]] = {t: [] for t in by_type}
        extra = collections.Counter()
        for n in ix.notes:
            t = n["type"]
            this = n.get("turn")
            c = classify(plants, n, this, cited_turns(n, rows))
            by_type[t][c["class"]] += 1
            by_type[t]["total"] += 1
            for k in c["plants"]:
                if k not in covered[t]:
                    covered[t].append(k)
            if n["sid"] not in firing_sids[t]:
                firing_sids[t].append(n["sid"])
            if t == "UPDATE":
                extra["update_first" if n["first"] else "update_with_prior"] += 1
                if n.get("old_matches") is False:
                    extra["update_old_mismatch"] += 1
            if t == "ENUMERATION":
                extra["enumeration_" + n["reason"]] += 1
            if t == "REVERSAL_X":
                extra["reversal_x_key_" + ("agrees" if n["key"] and n["key"]["agrees"] else "disagrees")] += 1
                extra["reversal_x_" + n["relation"]] += 1
            if t == "SAME_SEAT":
                extra["same_seat_" + n["tank"]] += 1
        # the old routes and the agreement with them, from the notes the ledgers hold (witness annotations; SAME_QUESTION / REVERSAL as the write returned them)
        agree = {"SAME_SEAT": collections.Counter(), "REVERSAL_X": collections.Counter(), "SAME_QUESTION": collections.Counter(), "REVERSAL": collections.Counter()}
        for _run_id, srows in C.session_ledger_rows(store):
            for w in C.written_with_notes(srows):
                for n in w["notes"]:
                    t = n["type"]
                    if t in OLD_NOTES:
                        n = dict(n, sentence_turn=w["turn"])
                        c = classify(plants, dict(n, type=t), w["turn"], cited_turns(n, rows))
                        by_type[t][c["class"]] += 1
                        by_type[t]["total"] += 1
                        for k in c["plants"]:
                            if k not in covered[t]:
                                covered[t].append(k)
                        if w["sid"] not in firing_sids[t]:
                            firing_sids[t].append(w["sid"])
                    if "witness" in n:
                        agree[t][n["witness"]["state"]] += 1
        planted = collections.Counter(p["kind"] for p in plants)
        cov = {}
        for t, want in WANT.items():
            idxs = [k for k, p in enumerate(plants) if p["kind"] == want]
            cov[t] = {"plants": len(idxs), "found": len([k for k in covered[t] if k in idxs])}
        return {"label": label, "arm": r["arm_label"], "task": r["task_id"], "sentences": len(rows), "writes": tally.to_obj(), "verify": [vstat, rstat], "index_sha": ix.index_sha,
                "questions": qs, "collisions": collisions, "notes": {t: dict(c) for t, c in by_type.items()}, "plant_coverage": cov, "planted": dict(planted), "firing_sentences": {t: len(v) for t, v in firing_sids.items()},
                "extra": dict(extra), "agree": {t: dict(c) for t, c in agree.items()}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------------------
# tables
# ------------------------------------------------------------------------------------------------------------
def tally_recall(runs: Sequence[dict]) -> dict:
    out: Dict[str, Any] = {}
    for mode in ("strict", "lenient"):
        for kind in ("contradicted", "updated", "plain", "all"):
            out.setdefault(mode, {})[kind] = {"n": 0, "reached": 0, "exact": 0, "extra": 0}
    verdicts, routes, issues = collections.Counter(), collections.Counter(), collections.Counter()
    emit = collections.Counter()
    emit_why = collections.Counter()
    emit_via = collections.Counter()
    completion_tried = collections.Counter()
    old_value = collections.Counter()
    for r in runs:
        for q in r["questions"]:
            verdicts[(q["kind"], q["verdict"])] += 1
            routes[q["route"] or "none"] += 1
            for i in q["issues"]:
                issues[i.split(":")[0] + (":" + i.split(":")[1] if i.startswith("question_unparsed") else "")] += 1
            for mode in ("strict", "lenient"):
                for kind in (q["kind"], "all"):
                    c = out[mode][kind]
                    c["n"] += 1
                    c["reached"] += 1 if q[mode]["reached"] else 0
                    c["exact"] += 1 if q[mode]["exact"] else 0
                    c["extra"] += 1 if q[mode]["extra"] else 0
            st = q["emit"]["status"]
            if q["lenient"]["reached"]:
                emit[(q["kind"], st)] += 1
                if "why" in q["emit"]:
                    emit_why[q["emit"]["why"]] += 1
                if "via" in q["emit"]:
                    emit_via[q["emit"]["via"]] += 1
                if "completion" in q["emit"]:
                    c_ = q["emit"]["completion"]
                    completion_tried["%s:%s" % (c_["via"], ",".join(c_["codes"]))] += 1
            ov = q.get("old_value")
            if ov is not None:
                old_value["questions"] += 1
                old_value["tried"] += ov["tried"]
                for x in ov["status"]:
                    old_value[x.split(":")[0] if x.startswith("EMITTED_OLD") else x] += 1
    if MODE["m6c"]:
        out["m6c"] = tally_m6c(runs)
    out["verdicts"] = {"%s/%s" % k: v for k, v in sorted(verdicts.items())}
    out["routes"] = dict(sorted(routes.items()))
    out["issues"] = dict(sorted(issues.items()))
    out["emit"] = {"%s/%s" % k: v for k, v in sorted(emit.items())}
    out["emit_why"] = dict(sorted(emit_why.items()))
    out["emit_via"] = dict(sorted(emit_via.items()))
    out["completion_refused"] = dict(sorted(completion_tried.items()))
    out["old_value_red_team"] = dict(sorted(old_value.items()))
    return out


def tally_m6c(runs: Sequence[dict]) -> dict:
    """PUB-M6c numbers.  EVERY NUMBER UNDER `oracle_top` IS AN ORACLE UPPER BOUND (a "model" that confirms only the top candidate), not a model result."""
    c = collections.Counter()
    for r in runs:
        cr = r.get("collisions")
        if cr:
            c["collision_stores"] += cr["stores"]
            c["collision_tried"] += cr["tried"]
            c["COLLISION_EMITTED_WRONG"] += cr["EMITTED_WRONG"]
        for q in r["questions"]:
            m = q.get("m6c") or {}
            c["questions"] += 1
            st = q["emit"]["status"]
            if st in ("emitted_right", "emitted_wrong"):
                c["emitted_" + ("right" if st == "emitted_right" else "wrong")] += 1
                if any(ch in q["emit"].get("text", "") for ch in JOINER_CHARS):
                    c["verbatim_slice_emits"] += 1
                    c["verbatim_slice_emits_" + ("right" if st == "emitted_right" else "wrong")] += 1
            if st == "contested_refused":
                c["contested_refused"] += 1
            if st == "one_side_emitted":
                c["one_side_emitted"] += 1
            if q["verdict"] == "CHOICE" and q["kind"] == "contradicted":
                c["choice_contradicted"] += 1
            if q["verdict"] == "ANSWER" or q["verdict"] == "UPDATED":
                c["answered_exactly"] += 1
            for av in q.get("all_values", ()):
                c["all_values_tried"] += av["tried"]
                c["all_values_right"] += av["emitted_right"]
                c["all_values_task_answer_not_gold"] += av["emitted_task_answer_not_gold"]
                c["ALL_VALUES_EMITTED_WRONG"] += av["EMITTED_WRONG"]
                c["all_values_variants"] += 1
            br = q.get("bridge_rt")
            if br:
                c["bridge_rt_tried"] += br["tried"]
                for x in br["attempts"]:
                    c["bridge_rt_" + x] += 1
            nr = q.get("no_recall")
            if nr:
                c["no_recall_tried"] += nr["tried"]
                for x in nr["attempts"]:
                    c["no_recall_" + (x if x.startswith(("EMITTED", "emitted")) else x.split(":", 1)[0] + ":" + x.split(":")[-1])] += 1
            if m.get("offered"):
                c["candidates_offered"] += 1
                c["candidates_total"] += m["offered"]
                c["candidates_gold_among"] += 1 if m.get("gold_among") else 0
                c["candidates_gold_rank1"] += 1 if m.get("gold_rank") == 1 else 0
                c["candidates_tied_top"] += 1 if m.get("tied_top") else 0
                c["oracle_top_bridge_" + m.get("oracle_top", "none")] += 1
                b = m.get("bridged")
                if b:
                    c["oracle_top_answered"] += 1
                    c["oracle_top_reached"] += 1 if b["lenient"]["reached"] else 0
                    c["oracle_top_exact"] += 1 if b["lenient"]["exact"] else 0
                    c["oracle_top_wrong"] += 0 if b["lenient"]["reached"] else 1
                eb = q.get("emit_bridged")
                if eb:
                    c["oracle_top_emit_" + eb["status"]] += 1
    return dict(sorted(c.items()))


def tally_detect(runs: Sequence[dict]) -> dict:
    notes: Dict[str, collections.Counter] = {}
    cov: Dict[str, collections.Counter] = {}
    fs = collections.Counter()
    ex = collections.Counter()
    agree: Dict[str, collections.Counter] = {}
    planted = collections.Counter()
    sentences = 0
    for r in runs:
        sentences += r["sentences"]
        for t, c in r["notes"].items():
            notes.setdefault(t, collections.Counter()).update(c)
        for t, c in r["plant_coverage"].items():
            cov.setdefault(t, collections.Counter()).update(c)
        for t, n in r["firing_sentences"].items():
            fs[t] += n
        ex.update(r["extra"])
        for t, c in r["agree"].items():
            agree.setdefault(t, collections.Counter()).update(c)
        planted.update(r["planted"])
    return {"runs": len(runs), "sentences": sentences, "notes": {t: dict(c) for t, c in notes.items()}, "plant_coverage": {t: dict(c) for t, c in cov.items()}, "firing_sentences": dict(fs),
            "extra": dict(sorted(ex.items())), "agree": {t: dict(c) for t, c in agree.items()}, "planted": dict(sorted(planted.items()))}


def memfix_reach() -> Optional[dict]:
    p = os.path.join(C.ROOT, "experiments", "line3", "mem", "memfix", "results", "reach_report.json")
    if not os.path.isfile(p):
        return None
    return json.load(open(p, encoding="utf-8"))["total"]


def old_reversal() -> Optional[dict]:
    p = os.path.join(C.ROOT, "experiments", "line3", "mem", "memfix", "results", "reversal_precision.json")
    if not os.path.isfile(p):
        return None
    return json.load(open(p, encoding="utf-8"))["total"]


def md_recall(t: dict, mf: Optional[dict], n_runs: int) -> str:
    names = {"contradicted": "矛盾質問", "updated": "更新質問", "plain": "平文質問", "all": "**全体**"}
    out = ["# PUB-M6 想起（十字）の到達 — meter v1（offline, API なし）", "",
           "meter v1 の構造 arm %d run（%d 問）の書き込みを mem.v4 の store に流し直し（モデルの raw write をそのまま、turn つき）、回答 run %s の `recall` を質問文のまま呼ぶ oracle。" % (n_runs, t["strict"]["all"]["n"], "memanswer.v4（PUB-M6c）" if "m6c" in t else "memanswer.v3"), "",
           "### 厳密一致の照合", "", "| 質問の種類 | n | 到達 | 厳密一致 | 余計な値あり |" + (" memfix 到達 前 | memfix 到達 後 |" if mf else ""), "|---|---|---|---|---|" + ("---|---|" if mf else "")]
    for k in ("contradicted", "updated", "plain", "all"):
        c = t["strict"][k]
        line = "| %s | %d | %d | %d | %d |" % (names[k], c["n"], c["reached"], c["exact"], c["extra"])
        if mf:
            line += " %d | %d |" % (mf["before"]["strict"][k]["reached"], mf["after"]["strict"][k]["reached"])
        out.append(line)
    out += ["", "### 寛容な照合（数値の後ろの単位の差を許す）", "", "| 質問の種類 | n | 到達 | 厳密一致 | 余計な値あり |", "|---|---|---|---|---|"]
    for k in ("contradicted", "updated", "plain", "all"):
        c = t["lenient"][k]
        out.append("| %s | %d | %d | %d | %d |" % (names[k], c["n"], c["reached"], c["exact"], c["extra"]))
    out += ["", "verdict（種類/verdict）: %s" % t["verdicts"], "", "route: %s" % t["routes"], "", "issues（NONE の理由）: %s" % t["issues"], "",
            "### 見つかった値は出せるか（到達した問いだけ。出口の門は変えていない: weave_span で引用 → emit）", "", "%s" % t["emit"], "", "出せなかった理由: %s" % t["emit_why"], "",
            "完成した問い（via）で出せた: %s。完成した問いでも門が断った理由: %s" % (t["emit_via"], t["completion_refused"]), "",
            "置き換えられた値の赤チーム（UPDATED の問いごとに、history の各値を引用して emit を試す。`EMITTED_OLD` が古い値の誤出力）: %s" % t["old_value_red_team"], ""]
    if "m6c" in t:
        m = t["m6c"]
        out += ["### PUB-M6c（shape.v3 / ask.v3 / qwords.v2、回答 run memanswer.v4、門 evidence.v6）", "",
                "- 出せた（正）: %d、出せた（誤）: %d、そのうち句読点つきの値を元の文の範囲のまま出した: %d（正 %d、誤 %d）" % (m.get("emitted_right", 0), m.get("emitted_wrong", 0), m.get("verbatim_slice_emits", 0),
                                                                                           m.get("verbatim_slice_emits_right", 0), m.get("verbatim_slice_emits_wrong", 0)),
                "- 食い違い質問（同じ席の CHOICE）: 片方を出そうとして `contested_value` で拒否 %d、拒否されず片方が出た %d（0 でなければならない）" % (m.get("contested_refused", 0), m.get("one_side_emitted", 0)),
                "- **recall せずに** weave して emit する赤チーム（新しい run、各値）: 試行 %d、古い値が出た `EMITTED_OLD` %d、食い違いの片方が出た `EMITTED_CONTESTED` %d（どちらも 0 でなければならない）、拒否の内訳: %s" % (
                    m.get("no_recall_tried", 0), m.get("no_recall_EMITTED_OLD", 0), m.get("no_recall_EMITTED_CONTESTED", 0), {k[10:]: v for k, v in m.items() if k.startswith("no_recall_") and ":" in k}),
                "- **既定拒否の赤チーム（memanswer.v7）**: 問いごとに、問いと言い換え %d 通り（の を落とす / 重ねる / 問い語を同じ類の語に替える / ですか を落とす）について、索引の全ての値（recall が返した値だけでなく）を新しい run で weave して emit（recall なし、CANDIDATES / NONE の問いも含む）: 試行 %d、金の値が出た %d、その問い自身の recall が唯一の答えとして返す値だが金ではない（記憶が片側しか持たない等。情報）%d、**誤出力 `EMITTED_WRONG` %d（0 でなければならない）**。出せた（正）は上の行（v7 での数。CI の以前の数は 66）" % (
                    m.get("all_values_variants", 0), m.get("all_values_tried", 0), m.get("all_values_right", 0), m.get("all_values_task_answer_not_gold", 0), m.get("ALL_VALUES_EMITTED_WRONG", 0)),
                "- **正規化の衝突**の赤チーム（索引の値ごとに、「・」/空白/全角/符号/通貨/%%/括弧/結合記号/上付き/分数/々ゝー〆/超 ほど くらい 約 などの修飾を足し引きした書き方を第 2 の文として別の store に書き、全ての範囲を weave → emit。2 つは書かれた値が違うので何も出てはいけない）: store %d、試行 %d、**`EMITTED_WRONG` %d（0 でなければならない）**" % (
                    m.get("collision_stores", 0), m.get("collision_tried", 0), m.get("COLLISION_EMITTED_WRONG", 0)),
                "- **実行内の橋**の赤チーム（CHOICE の問いで、問いの一部から片方の席へ橋を張り、recall せずに weave → emit）: 試行 %d、`EMITTED_BRIDGED_CHOICE` %d（0 でなければならない）、内訳: %s" % (
                    m.get("bridge_rt_tried", 0), m.get("bridge_rt_EMITTED_BRIDGED_CHOICE", 0), {k[10:]: v for k, v in m.items() if k.startswith("bridge_rt_") and k != "bridge_rt_tried"}),
                "- CANDIDATES を示した問い: %d（候補の総数 %d）、そのうち金が候補の中にある %d、金が 1 位 %d、先頭が同点 %d" % (m.get("candidates_offered", 0), m.get("candidates_total", 0), m.get("candidates_gold_among", 0),
                                                                                       m.get("candidates_gold_rank1", 0), m.get("candidates_tied_top", 0)),
                "- **ORACLE 上限（先頭の候補だけを確かめる「モデル」。モデルの結果ではない）**: 橋を張って答えた %d、金に到達 %d（厳密 %d）、金に届かず %d；橋で見つけた値を門に通した結果: %s" % (
                    m.get("oracle_top_answered", 0), m.get("oracle_top_reached", 0), m.get("oracle_top_exact", 0), m.get("oracle_top_wrong", 0),
                    {k[len("oracle_top_emit_"):]: v for k, v in m.items() if k.startswith("oracle_top_emit_")}), ""]
    return "\n".join(out) + "\n"


def md_detect(t: dict, old: Optional[dict]) -> str:
    out = ["# PUB-M5 十字の検知 — meter v1 の仕掛けとの照合（offline, API なし）", "",
           "%d store の保存文 %d。仕掛け: %s。注記の引用（sid → turn）の組が、その注記の種類に合う仕掛けの2通に入れば hit。" % (t["runs"], t["sentences"], t["planted"]), "",
           "| 注記 | 発火 | 発火した文 | hit | 他の仕掛け | 仕掛けなし | 対なし | 適合率 | 見つかった仕掛け |", "|---|---|---|---|---|---|---|---|---|"]
    for ty in ("SAME_SEAT", "REVERSAL_X", "UPDATE", "ENUMERATION", "REVERSAL", "SAME_QUESTION"):
        c = t["notes"].get(ty, {})
        tot = c.get("total", 0)
        other = sum(v for k, v in c.items() if k.startswith("other:"))
        cv = t["plant_coverage"].get(ty, {"plants": 0, "found": 0})
        out.append("| %s | %d | %d | %d | %d | %d | %d | %s | %d / %d |" % (ty, tot, t["firing_sentences"].get(ty, 0), c.get("hit", 0), other, c.get("no_plant", 0), c.get("no_pair", 0),
                                                                          "%.3f" % (c.get("hit", 0) / tot) if tot else "-", cv.get("found", 0), cv.get("plants", 0)))
    out += ["", "「他の仕掛け」の内訳（種類別）:"]
    for ty in ("SAME_SEAT", "REVERSAL_X", "UPDATE", "ENUMERATION", "REVERSAL", "SAME_QUESTION"):
        c = t["notes"].get(ty, {})
        out.append("- %s: %s" % (ty, {k[6:]: v for k, v in sorted(c.items()) if k.startswith("other:")}))
    out += ["", "内訳: %s" % t["extra"], "", "二つの証人の一致（注記の `witness`）: %s" % t["agree"], ""]
    if old:
        c = old["classes"]
        out += ["旧 REVERSAL（memfix 保存済み台帳, mem.v3）: 発火 %d（仕掛けの反転に当たる %d、適合率 %s）、仕掛けの反転が引用された %d / %d。" % (old["firings"], c["reversal"], old["precision"], old["reversal_plants_cited"], old["reversal_plants"]), ""]
    return "\n".join(out) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meter", default=C.METER_V1)
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ap.add_argument("--limit", type=int, default=0, help="only the first N runs (a smoke test)")
    ap.add_argument("--m6c", action="store_true", help="PUB-M6c: shape.v3 / ask.v3 / qwords.v2, memanswer.v4; outputs to experiments/line3/pub/m6c/")
    ap.add_argument("--m6d", action="store_true", help="PUB-M6d: --m6c with shape.v4 (stage 2: 「へ」 read like 「に」); outputs to experiments/line3/pub/m6d/")
    ns = ap.parse_args(argv)
    MODE["m6d"] = ns.m6d
    MODE["m6c"] = ns.m6c or ns.m6d
    if MODE["m6c"]:
        K.OUT = M6D_DIR if ns.m6d else M6C_DIR
        os.makedirs(K.OUT, exist_ok=True)
    dirs = C.structure_runs(ns.meter)
    if ns.limit:
        dirs = dirs[:ns.limit]
    runs = K.pmap(measure_run, dirs, ns.workers)
    runs.sort(key=lambda r: r["label"])
    rec, det = tally_recall(runs), tally_detect(runs)
    mf, old = memfix_reach(), old_reversal()
    out = {"meter": os.path.relpath(ns.meter, C.ROOT), "runs": len(runs), "not_verified": [[r["label"]] + r["verify"] for r in runs if r["verify"] != ["OK", "IDENTICAL"]]}
    K.write_json(os.path.join(K.OUT, "meter_recall.json"), dict(out, total=rec, memfix=mf, per_run=[{k: r[k] for k in ("label", "arm", "task", "sentences", "index_sha", "questions")} for r in runs]))
    K.write_json(os.path.join(K.OUT, "meter_detect.json"), dict(out, total=det, old_reversal=old,
                                                                  per_run=[{k: r[k] for k in ("label", "arm", "task", "sentences", "notes", "plant_coverage", "planted", "extra", "agree")} for r in runs]))
    K.write_text(os.path.join(K.OUT, "meter_recall.md"), md_recall(rec, mf, len(runs)))
    K.write_text(os.path.join(K.OUT, "meter_detect.md"), md_detect(det, old))
    print(md_recall(rec, mf, len(runs)))
    print(md_detect(det, old))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
