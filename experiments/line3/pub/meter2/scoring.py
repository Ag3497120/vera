"""PUB-M10: the scoring of the long-story meter (instrument v2).  Pure functions of a story (the bank_ls schema), the detections read from the ledgers of a run, and the answers of its checkpoints.  No API.

WHAT IS COUNTED (docs/LINE3_PUBLIC_DESIGN.md 6.3, bank_ls README "Grading"):

  PLANTS (intake time).  For each plant of kind contradiction | reversal | update that lies inside the part of the story that was fed (every ref in a session <= the last session fed):
      structure   the structure's OWN notes noticed it (ledger rows of the story phase):
                    contradiction  a SAME_SEAT note whose turn and one cited earlier turn are both refs of the plant
                    reversal       a REVERSAL_X note (any structure arm) or an old REVERSAL note (the key route: not shown, not counted for the flat table) with both turns in the plant's refs
                    update         an UPDATE note whose turn is the plant's message
      model       the MODEL's own act: a `report` pair of turns that are both refs of the plant (contradiction, reversal), or a `supersede` whose new sentence was written at the plant's message (update)
      any         structure or model
    The two are counted separately and never merged into one number without saying so.  A0 and A1 have no structure notes (0) and no `supersede`: their `update` column is not applicable (None).
  FALSE ALARMS.  Counted notes (SAME_SEAT, REVERSAL_X) that match no contradiction / reversal plant: `list_trap` (both turns refs of a list_trap or repeat plant), else `unmatched` (an unplanted conflict is possible:
      the bank's ledger is incomplete, bank_ls README limit 2).  Model report pairs that match no contradiction / reversal plant: `model_false_pairs`.
  ANSWERS (checkpoints).  kind of a question: present (bank `plain`) | contested (`contradiction`) | updated (`update`) | absent.  Class of one answer {kind: value | contested | none, values}:
      right            present / updated: the value equals the gold (NFKC, case- and space-folded); contested: kind contested with exactly the two gold values; absent: -- (see absent_admit)
      over_broad       present / updated: a value that CONTAINS the gold and is not equal to it
      abstain          kind none on a present / contested / updated question (no answer given)
      confident_wrong  every other answer: a wrong value, a one-sided answer to a contradiction, a conflict claimed on a question that has none (`false_contested`), any value on an absent question
      absent_admit     kind none on an absent question (the right answer)
    Per kind and in total; `right_rate` = right / questions asked.
  COST.  tokens in / out, API calls (= assistant turns), tool calls, turns capped by the runaway cap, turns without a report, results cut by the budget (n, characters omitted), forced reports.
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

ANSWER_KINDS = ("present", "contested", "updated", "absent")
BANK_KIND = {"plain": "present", "contradiction": "contested", "update": "updated", "absent": "absent"}
CLASSES = ("right", "over_broad", "abstain", "confident_wrong", "absent_admit")


def turn_id(s: int, i: int) -> str:
    return "%d-%d" % (s + 1, i + 1)


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().replace(" ", "").replace("　", "")


def gold_values(gold: str) -> Tuple[str, List[str]]:
    g = gold.strip()
    for head in ("矛盾:", "矛盾："):
        if g.startswith(head):
            rest = g[len(head):].strip()
            parts = [p.strip() for p in rest.split(" と ")] if " と " in rest else [p.strip() for p in rest.split("と")]
            return "contested", [p for p in parts if p]
    return "value", [g]


def question_kind(q: dict) -> str:
    if q.get("gold") == "記録なし" or q.get("kind") == "absent":
        return "absent"
    return BANK_KIND.get(q.get("kind", "plain"), "present")


def classify(answer: dict, q: dict) -> str:
    """The class of one answer {kind, values} to one question (see the module doc)."""
    k = question_kind(q)
    ak = answer.get("kind", "none")
    vals = [v for v in answer.get("values", []) if isinstance(v, str)]
    if k == "absent":
        return "absent_admit" if ak == "none" else "confident_wrong"
    if ak == "none":
        return "abstain"
    gk, gv = gold_values(q["gold"])
    if k == "contested":
        return "right" if ak == "contested" and sorted(norm(v) for v in vals) == sorted(norm(v) for v in gv) else "confident_wrong"
    if ak == "contested":
        return "confident_wrong"
    if len(vals) != 1:
        return "confident_wrong"
    a, g = norm(vals[0]), norm(gv[0])
    if a == g:
        return "right"
    if g and g in a:
        return "over_broad"
    return "confident_wrong"


def false_contested(answer: dict, q: dict) -> bool:
    return answer.get("kind") == "contested" and question_kind(q) in ("present", "updated")


def score_answers(rows: Sequence[dict]) -> dict:
    """rows = [{"q": {...bank question...}, "answer": {kind, values}}].  -> per kind and total counts."""
    out: Dict[str, Any] = {k: {"n": 0, **{c: 0 for c in CLASSES}} for k in ANSWER_KINDS}
    tot = {"n": 0, **{c: 0 for c in CLASSES}, "false_contested": 0}
    for r in rows:
        k = question_kind(r["q"])
        c = classify(r["answer"], r["q"])
        out[k]["n"] += 1
        out[k][c] += 1
        tot["n"] += 1
        tot[c] += 1
        if false_contested(r["answer"], r["q"]):
            tot["false_contested"] += 1
    out["total"] = tot
    out["right_rate"] = None if tot["n"] == 0 else tot["right"] * 1000 // tot["n"]          # per mille, an int (no float in a result)
    return out


# ------------------------------------------------------------------------------------------------------------
# plants
# ------------------------------------------------------------------------------------------------------------
def plant_turns(p: dict) -> List[str]:
    return [turn_id(s, i) for s, i in p["message_refs"]]


def in_scope(p: dict, last_session: int) -> bool:
    refs = list(p["message_refs"]) + list(p.get("old_refs") or [])
    return all(s <= last_session for s, _ in refs)


def _cite_turns(n: dict, turn_of_sid: Dict[int, str]) -> List[str]:
    out: List[str] = []
    for e in n.get("earlier") or []:
        t = e.get("turn") or turn_of_sid.get(e.get("sid"))
        if t:
            out.append(t)
    return out


def struct_hits(plant: dict, notes: Sequence[dict], turn_of_sid: Dict[int, str], flat: bool) -> bool:
    """Did the structure's notes notice the plant?  (module doc)"""
    refs = plant_turns(plant)
    kind = plant["kind"]
    for n in notes:
        t = n.get("turn") or turn_of_sid.get(n.get("sid"))
        if kind == "contradiction" and n["type"] == "SAME_SEAT":
            if t in refs and any(c in refs and c != t for c in _cite_turns(n, turn_of_sid)):
                return True
        elif kind == "reversal" and (n["type"] == "REVERSAL_X" or (n["type"] == "REVERSAL" and not flat)):
            cites = _cite_turns(n, turn_of_sid)
            if not cites and n["type"] == "REVERSAL":
                cites = [c for c in (n.get("cite") or []) if isinstance(c, str)]
            if t in refs and any(c in refs and c != t for c in cites):
                return True
        elif kind == "update" and n["type"] == "UPDATE":
            if t in refs:
                return True
    return False


def model_hits(plant: dict, pairs: Sequence[Sequence[str]], supersedes: Sequence[str]) -> bool:
    """Did the model's own acts notice it?  `pairs` = the turn pairs of its reports, `supersedes` = the turns at which the sentences it declared as replacing were written."""
    refs = plant_turns(plant)
    if plant["kind"] in ("contradiction", "reversal"):
        return any(len(p) == 2 and p[0] in refs and p[1] in refs and p[0] != p[1] for p in pairs)
    if plant["kind"] == "update":
        return any(t in refs for t in supersedes)
    return False


def score_plants(story: dict, last_session: int, det: dict, has_structure: bool, flat: bool) -> dict:
    """det = {"notes": [counted notes of the ledgers, each with type / turn / sid / earlier], "turn_of_sid": {sid: turn}, "pairs": [...], "supersede_turns": [...]}."""
    plants = [p for p in story["plants"] if in_scope(p, last_session)]
    out: Dict[str, Any] = {}
    for kind in ("contradiction", "reversal", "update"):
        ps = [p for p in plants if p["kind"] == kind]
        st = [struct_hits(p, det["notes"], det["turn_of_sid"], flat) for p in ps] if has_structure else [False] * len(ps)
        md = [model_hits(p, det["pairs"], det["supersede_turns"] if has_structure else []) for p in ps]
        na_model = kind == "update" and not has_structure
        out[kind] = {"n": len(ps), "structure": sum(st), "model": None if na_model else sum(md), "any": sum(1 for a, b in zip(st, md) if a or b)}
    traps = [plant_turns(p) for p in plants if p["kind"] in ("list_trap", "repeat")]
    real = [plant_turns(p) for p in plants if p["kind"] in ("contradiction", "reversal")]
    fa = {"structure_list_trap": 0, "structure_unmatched": 0, "model_false_pairs": 0}
    for n in det["notes"]:
        if n["type"] not in ("SAME_SEAT", "REVERSAL_X"):
            continue
        t = n.get("turn") or det["turn_of_sid"].get(n.get("sid"))
        cites = _cite_turns(n, det["turn_of_sid"])
        pair_ok = lambda refs: t in refs and any(c in refs and c != t for c in cites)       # noqa: E731
        if any(pair_ok(r) for r in real):
            continue
        if any(pair_ok(r) for r in traps):
            fa["structure_list_trap"] += 1
        else:
            fa["structure_unmatched"] += 1
    for pr in det["pairs"]:
        if not any(len(pr) == 2 and pr[0] in r and pr[1] in r for r in real):
            fa["model_false_pairs"] += 1
    out["false"] = fa
    return out
