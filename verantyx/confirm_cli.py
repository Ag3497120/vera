"""W16-t8 (T8, K681; docs/COARSE_PLACEMENT.md section 12.21): ``vera confirm`` -- a human's confirmation of a word's type or of a predicate's role frame, written into a placement layer.

  vera confirm suggest --text FILE [--placement P] [--layer L] [--json]   what, if confirmed, might let an abstained sentence be read (one line per candidate)
  vera confirm set <word> <TYPE> --by NAME [--reason T] --layer L --ledger-file F [--placement P]
  vera confirm frame <predicate> <particle> <role> <TYPES...> --by NAME [--reason T] --layer L --ledger-file F [--placement P]
  vera confirm list [--all] --layer L [--ledger-file F] [--placement P]
  vera confirm undo <confirm_id> --by NAME [--reason T] --layer L --ledger-file F [--placement P]

A confirmation is a layer row ``origin layer_human`` with ``evidence.confirm_id`` and ``decided_by == ["human:<confirm_id>"]``; ``placement_layer.apply`` (K680) puts it ABOVE the base placement.
Every write is: a ``human_confirmation`` row in the testimony ledger, then (``placement_layer.write_entry``) a ``promoted_to_layer`` row, then the layer row.  An undo is another appended row
(nothing is updated or deleted).  The reader (``semantic_reader`` / ``semantic_read``) is not touched: a confirmation reaches only a word the reader asks the placement about.  ``suggest``
says so (``reachable``) and never guesses a type (an unplaced word's candidates are empty).
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import coarse_types as ct
from . import placement_layer as PL

SUGGEST_COLUMNS = ("sentence_id", "text", "status", "op", "word", "particle", "role", "candidates", "reason", "reachable", "why")
NOT_REACHABLE = "NOT_REACHABLE_BY_CONFIRMATION"
EXIT_REFUSED = 2
EXIT_LEDGER_BROKEN = 3
_SET_REASONS = ("PLACEMENT_UNPLACED", "PLACEMENT_UNKNOWN", "PLACEMENT_MULTIPLE", "PLACEMENT_ESTIMATED_NEAR", "PLACEMENT_ESTIMATED_GENERATED", "PLACEMENT_DIRECT_VIA_GENERATED")
_FRAME_REASON_PREFIXES = ("ROLE_FRAME_", "PLACEMENT_FRAME_", "PLACEMENT_PARTICLE_NOT_IN_FRAME:", "PLACEMENT_TYPE_MISMATCH:")
# r3 (12.21.7): the reasons of the base's section 12.10 frame (exactly these names; ``PLACEMENT_FRAME_NOT_READ:`` is a K62 table reason, not a 12.10 one).  ``vera confirm`` never changes that frame.
_FRAME_1210_REASONS = ("PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED", "PLACEMENT_FRAME_TYPE_NOT_CONFIRMED", "PLACEMENT_FRAME_INVALID")
BASE_FRAME_KEPT = "BASE_FRAME_1210_KEPT"


class ConfirmError(Exception):
    def __init__(self, type_: str, detail: str = "") -> None:
        super().__init__("%s %s" % (type_, detail))
        self.type, self.detail = type_, detail


def _nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


def _out(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=False))


# ------------------------------------------------------------------------------------------------------------------------ the write path (shared with tools/t8/measure.py)
class Target:
    """What a confirmation is written into: the layer file, the testimony ledger and the base placement's content sha."""

    def __init__(self, layer_path: str, layer_name: str, ledger_path: Optional[str], base_sha: Optional[str], placement: Optional[str]) -> None:
        self.layer_path, self.layer_name, self.ledger_path, self.base_sha, self.placement = layer_path, layer_name, ledger_path, base_sha, placement
        self._ledger: Any = None

    @property
    def ledger(self) -> Any:
        """The testimony ledger, opened (and made, with its header) only when something is written: a refused confirmation leaves no file behind."""
        if self._ledger is None:
            from .testimony_ledger import TestimonyLedger
            self._ledger = TestimonyLedger(self.ledger_path)
        return self._ledger

    def rows(self) -> List[Dict[str, Any]]:
        layer, why = PL.open_layer(self.layer_path, self.base_sha)
        if layer is None:
            if why == "MISSING":
                return []
            raise ConfirmError("LAYER_BASE_MISMATCH" if why == "BASE_MISMATCH" else "LAYER_UNREADABLE", str(why))
        return layer.all_entries()


def open_target(layer_spec: Optional[str], ledger_path: Optional[str], placement: Optional[str], *, need_ledger: bool, create_ledger: bool = False) -> Target:
    from . import coarse_place
    spec = layer_spec or PL.spec_from_env()
    if not spec:
        raise ConfirmError("LAYER_REQUIRED", "--layer (or VERA_PLACEMENT_LAYER) names the layer")
    path, name, why = PL.resolve(spec)
    if path is None:
        raise ConfirmError("LAYER_UNAVAILABLE:%s" % why, spec)
    placement = placement or os.environ.get("VERA_PLACEMENT") or None
    pl, nop = coarse_place._open(placement)
    if pl is None:
        raise ConfirmError("NO_PLACEMENT", nop[0] if nop else "UNSET")
    if need_ledger:
        if not ledger_path:
            raise ConfirmError("LEDGER_REQUIRED", "--ledger-file is needed")
        if not create_ledger and not os.path.exists(ledger_path):
            raise ConfirmError("LEDGER_NOT_FOUND", ledger_path)
    return Target(path, name, ledger_path if need_ledger else None, pl.sha, placement)


def _base_summary(t: Target, word: str) -> Dict[str, Any]:
    from . import coarse_place
    a = coarse_place.query(word, placement=t.placement, layer=False)
    return {"state": a.get("state"), "top": list(a.get("top") or []), "origin": a.get("origin"), "decided_by": list(a.get("decided_by") or [])}


def _precheck(t: Target) -> None:
    """The layer was made on another base: nothing is written, not even the ledger row (K294 keeps the two in step)."""
    layer, why = PL.open_layer(t.layer_path, t.base_sha)
    if layer is None and why == "BASE_MISMATCH":
        raise ConfirmError("LAYER_BASE_MISMATCH", t.layer_path)
    if layer is None and why not in ("MISSING",):
        raise ConfirmError("LAYER_UNREADABLE", str(why))


def _write(t: Target, *, kind: str, word: str, type_: str, by: str, reason: Optional[str], extra: Dict[str, Any], base: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    _precheck(t)
    w = _nfkc(word)
    if not w:
        raise ConfirmError("EMPTY_WORD")
    if kind == "undo":
        rec = t.ledger.record_human_confirmation_undone(undoes=extra["undoes"], word=w, by=by, reason=reason, layer_name=t.layer_name)
    else:
        rec = t.ledger.record_human_confirmation(kind=kind, word=w, type=type_, frame=extra.get("frame"), by=by, reason=reason, layer_name=t.layer_name)
    cid = rec["confirm_id"]
    evidence: Dict[str, Any] = {"kind": kind, "confirm_id": cid, "by": by, "reason": reason, "human": True}
    evidence.update(extra)
    if base is not None:
        evidence["base"] = base
    try:
        res = PL.write_entry(t.layer_path, t.ledger, base_sha256=t.base_sha, word=w, type=type_, origin="layer_human", decided_by=["human:" + cid], evidence=evidence,
                             role_frame=None, key="human:" + cid, candidate=w, from_seq=[rec["row"]["seq"]])
    except PL.LayerError as exc:
        raise ConfirmError(exc.type, exc.detail)
    return {"confirm_id": cid, "word": w, "type": type_, "layer": t.layer_name, "ledger_seq": res["ledger_seq"], "ledger_confirmation_seq": rec["row"]["seq"], "entry_id": res["entry_id"]}


def _need_by(by: Optional[str]) -> str:
    if by is None or not str(by).strip():
        raise ConfirmError("CONFIRMER_REQUIRED", "--by NAME")
    return str(by).strip()


def confirm_set(t: Target, word: str, type_: str, by: Optional[str], reason: Optional[str] = None) -> Dict[str, Any]:
    by = _need_by(by)
    if type_ not in ct.ALL_TYPES:
        raise ConfirmError("BAD_TYPE", str(type_))
    w = _nfkc(word)
    if not w:
        raise ConfirmError("EMPTY_WORD")
    res = _write(t, kind="type", word=w, type_=type_, by=by, reason=reason, extra={}, base=_base_summary(t, w))
    return dict(res, kind="human_confirmation")


def _active_by_word(t: Target, word: str) -> Dict[str, List[Dict[str, Any]]]:
    return PL.active_confirm_rows([e for e in t.rows() if e["word"] == word])


def confirm_frame(t: Target, predicate: str, particle: str, role: str, types: Sequence[str], by: Optional[str], reason: Optional[str] = None) -> Dict[str, Any]:
    from .event_cross import ROLE_NAMES
    from .semantic_reader import _CASE_PARTICLES_9
    by = _need_by(by)
    if particle not in _CASE_PARTICLES_9:
        raise ConfirmError("BAD_PARTICLE", str(particle))
    if role not in ROLE_NAMES:
        raise ConfirmError("BAD_ROLE", str(role))
    types = sorted(set(types))
    if not types:
        raise ConfirmError("BAD_TYPE", "no noun type")
    for x in types:
        if x not in ct.FRAME_NOUN_TYPES:
            raise ConfirmError("BAD_TYPE", str(x))
    w = _nfkc(predicate)
    if not w:
        raise ConfirmError("EMPTY_WORD")
    ptypes = sorted({e["type"] for e in _active_by_word(t, w)["type"] if e["type"].startswith("P_")})
    if not ptypes:
        raise ConfirmError("PREDICATE_TYPE_NOT_CONFIRMED", "%s: confirm its type first (vera confirm set %s <P_TYPE>)" % (w, w))
    if len(ptypes) >= 2:
        raise ConfirmError("HUMAN_CONFLICT", "%s: two confirmed types %s" % (w, "+".join(ptypes)))
    res = _write(t, kind="frame", word=w, type_=ptypes[0], by=by, reason=reason, extra={"frame": {"particle": particle, "role": role, "types": types}}, base=None)
    return dict(res, kind="human_confirmation", frame={"particle": particle, "role": role, "types": types})


def confirm_undo(t: Target, confirm_id: str, by: Optional[str], reason: Optional[str] = None) -> Dict[str, Any]:
    by = _need_by(by)
    rows = [e for e in t.rows() if PL.is_confirm_row(e)]
    hit = [e for e in rows if e["evidence"]["confirm_id"] == confirm_id]
    if not hit:
        raise ConfirmError("NO_SUCH_CONFIRMATION", str(confirm_id))
    row = hit[0]
    if row["evidence"]["kind"] == "undo":
        raise ConfirmError("CANNOT_UNDO_UNDO", str(confirm_id))
    if any(e["evidence"]["kind"] == "undo" and e["evidence"].get("undoes") == confirm_id for e in rows):
        raise ConfirmError("ALREADY_UNDONE", str(confirm_id))
    res = _write(t, kind="undo", word=row["word"], type_=row["type"], by=by, reason=reason, extra={"undoes": confirm_id}, base=None)
    return dict(res, kind="human_confirmation_undone", undoes=confirm_id)


def list_rows(t: Target, include_all: bool = False) -> List[Dict[str, Any]]:
    rows = [e for e in t.rows() if PL.is_confirm_row(e)]
    undone = {e["evidence"].get("undoes") for e in rows if e["evidence"]["kind"] == "undo"}
    out = []
    for e in rows:
        ev = e["evidence"]
        state = "undo" if ev["kind"] == "undo" else "undone" if ev["confirm_id"] in undone else "active"
        if not include_all and state != "active":
            continue
        out.append({"confirm_id": ev["confirm_id"], "kind": ev["kind"], "word": e["word"], "type": e["type"], "frame": ev.get("frame"), "undoes": ev.get("undoes"), "by": ev.get("by"),
                    "reason": ev.get("reason"), "ts": e["ts"], "state": state, "entry_id": e["id"]})
    return out


# ------------------------------------------------------------------------------------------------------------------------ suggest
class _Recorder:
    """Wraps ``semantic_reader.CoarseQuery``: records every answer the reader asks for and returns it unchanged."""

    def __init__(self, path: str) -> None:
        from . import semantic_reader as R
        self.inner = R.CoarseQuery(path)
        self.log: List[Tuple[str, Dict[str, Any]]] = []

    def query(self, term):
        a = self.inner.query(term)
        self.log.append((term, a))
        return a

    @property
    def id(self):
        return self.inner.id


def _parse_reason(reason: str) -> Tuple[str, List[str]]:
    parts = reason.split(":")
    return parts[0], parts[1:]


def _suggest_sentence(text: str, placement: str) -> Dict[str, Any]:
    from . import semantic_read as SR
    from . import semantic_reader as R
    rec = _Recorder(placement)
    try:
        out = SR.read(text, placement=rec)
    except SR.ReadError as exc:
        return {"status": "REFUSED_INPUT", "reasons": ["%s:%s" % (exc.type, exc.detail)], "rows": [], "read": False}
    if out.get("readable"):
        return {"status": "READ", "reasons": [], "rows": [], "read": True}
    reasons = list((out.get("abstain") or {}).get("reasons") or [])
    queried: Dict[str, Dict[str, Any]] = {}
    for term, ans in rec.log:
        queried.setdefault(term, ans)
    joined = "|".join(reasons)
    rows: List[Dict[str, Any]] = []
    seen = set()

    def add(row):
        k = (row["op"], row["word"], row["particle"], row["role"])
        if k not in seen:
            seen.add(k)
            rows.append(row)
    # 1. a word the reader asked about and the gate refused, which the abstention names: set
    for term, ans in queried.items():
        try:
            ptype, why = R.placement_type(ans)
        except Exception:
            continue
        if why is None or why.split(":")[0] not in _SET_REASONS:
            continue
        if term not in joined:
            continue
        cands = [] if why.split(":")[0] in ("PLACEMENT_UNPLACED", "PLACEMENT_UNKNOWN") else list(ans.get("top") or [])
        add({"op": "set", "word": term, "particle": None, "role": None, "candidates": cands, "reason": why, "reachable": True, "why": None})
    # 2. a role frame: the predicate is the asked word whose gate-passed type is the one in the reason
    for r in reasons:
        if not r.startswith(_FRAME_REASON_PREFIXES):
            continue
        name, rest = _parse_reason(r)
        ptype = next((x for x in rest if x.startswith("P_")), None)
        particle = next((x for x in rest if x in R._CASE_PARTICLES_9), None)
        if ptype is None or particle is None:
            continue
        preds, human_typed = [], False
        for term, ans in queried.items():
            try:
                tt, why = R.placement_type(ans)
            except Exception:
                continue
            if why is None and tt == ptype:
                preds.append(term)
                human_typed = ans.get("layer_status") == "HUMAN_CONFIRMED_USED"
        if len(preds) != 1:                                   # not one predicate: do not name one (a tie abstains)
            add({"op": "none", "word": None, "particle": particle, "role": None, "candidates": [], "reason": r, "reachable": False, "why": "PREDICATE_NOT_UNIQUE"})
            continue
        types = [x for x in rest if x in ct.FRAME_NOUN_TYPES]
        if name in _FRAME_1210_REASONS:                       # r3: the base's 12.10 frame refuses it; `vera confirm` does not change that frame
            add({"op": "frame", "word": preds[0], "particle": particle, "role": None, "candidates": types, "reason": r, "reachable": False, "why": BASE_FRAME_KEPT})
            continue
        kind, info = R.predicate_role_frame(queried[preds[0]])
        if kind is None:                                      # r3 (J15): the base's role frame has entries the reader refuses, so a human frame row would not be read either
            add({"op": "frame", "word": preds[0], "particle": particle, "role": None, "candidates": types, "reason": r, "reachable": False,
                 "why": "BASE_ROLE_FRAME_INVALID:%s (J15)" % info})
            continue
        add({"op": "frame", "word": preds[0], "particle": particle, "role": None, "candidates": types, "reason": r, "reachable": True,
             "why": None if human_typed else "PREDICATE_TYPE_SET_FIRST:%s (vera confirm frame needs a confirmed type of the predicate)" % ptype})
    # 2b. a refused filler type (PLACEMENT_TYPE_MISMATCH:<ptype>:<particle>:<noun type>): the word that has that type may be the one a human types otherwise
    for r in reasons:
        name, rest = _parse_reason(r)
        if name != "PLACEMENT_TYPE_MISMATCH" or len(rest) != 3 or rest[2] not in ct.NOUN_TYPES:
            continue
        for term, ans in queried.items():
            try:
                tt, why = R.placement_type(ans)
            except Exception:
                continue
            if why is None and tt == rest[2] and term in text:
                add({"op": "set", "word": term, "particle": rest[1], "role": None, "candidates": [], "reason": r, "reachable": True, "why": "FILLER_TYPE_REFUSED:%s" % rest[2]})
    # 3. an undetermined type of a word the reader never asked about: shown, and said not to be reachable
    for r in reasons:
        name, rest = _parse_reason(r)
        if name.endswith("_TYPE_UNDETERMINED") and rest and rest[0] not in queried:
            add({"op": "none", "word": rest[0], "particle": None, "role": None, "candidates": [], "reason": r, "reachable": False, "why": NOT_REACHABLE})
    if not rows:
        add({"op": "none", "word": None, "particle": None, "role": None, "candidates": [], "reason": joined, "reachable": False, "why": NOT_REACHABLE})
    return {"status": "ABSTAIN", "reasons": reasons, "rows": rows, "read": False}


def suggest(text_path: str, placement: Optional[str], layer: Optional[str]) -> Dict[str, Any]:
    from .cli import _qc_records
    placement = placement or os.environ.get("VERA_PLACEMENT") or None
    if not placement:
        raise ConfirmError("NO_PLACEMENT", "UNSET")
    records, _where, loaded, skipped = _qc_records([text_path])
    old = os.environ.get(PL.ENV_LAYER)
    try:
        if layer:
            path, _name, why = PL.resolve(layer)
            if path is None:
                raise ConfirmError("LAYER_UNAVAILABLE:%s" % why, layer)
            os.environ[PL.ENV_LAYER] = path
        table: List[Dict[str, Any]] = []
        per_sentence = []
        for rec_ in records:
            s = _suggest_sentence(rec_["text"], placement)
            per_sentence.append((rec_, s))
            if s["status"] == "READ":
                table.append({"sentence_id": rec_["id"], "text": rec_["text"], "status": "READ", "op": None, "word": None, "particle": None, "role": None, "candidates": [],
                              "reason": None, "reachable": None, "why": None})
            for row in s["rows"]:
                table.append(dict({"sentence_id": rec_["id"], "text": rec_["text"], "status": s["status"]}, **row))
    finally:
        if old is None:
            os.environ.pop(PL.ENV_LAYER, None)
        else:
            os.environ[PL.ENV_LAYER] = old
    n_read = sum(1 for _, s in per_sentence if s["status"] == "READ")
    n_abs = sum(1 for _, s in per_sentence if s["status"] == "ABSTAIN")
    with_cand = [rec_["id"] for rec_, s in per_sentence if s["status"] == "ABSTAIN" and any(x["reachable"] for x in s["rows"])]
    unreachable = [rec_["id"] for rec_, s in per_sentence if s["status"] == "ABSTAIN" and not any(x["reachable"] for x in s["rows"])]
    blocked: Dict[Tuple[str, str], set] = {}
    for row in table:
        if row["op"] in ("set", "frame"):
            blocked.setdefault((row["op"], row["word"]), set()).add(row["sentence_id"])
    by_word = [{"op": k[0], "word": k[1], "sentences": len(v)} for k, v in sorted(blocked.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]))]
    summary = {"sentences": len(per_sentence), "read": n_read, "abstained": n_abs, "refused_input": sum(1 for _, s in per_sentence if s["status"] == "REFUSED_INPUT"),
               "abstained_with_reachable_candidate": len(with_cand), "abstained_unreachable_only": len(unreachable), "candidates_by_word": by_word,
               "documents_loaded": loaded, "documents_skipped": skipped, "layer": layer}
    return {"columns": list(SUGGEST_COLUMNS), "rows": table, "summary": summary}


def _tsv_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        v = "+".join(str(x) for x in v)
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def render_tsv(res: Dict[str, Any]) -> str:
    lines = ["\t".join(SUGGEST_COLUMNS)]
    for row in res["rows"]:
        lines.append("\t".join(_tsv_cell(row.get(c)) for c in SUGGEST_COLUMNS))
    s = res["summary"]
    lines.append("# sentences=%d read=%d abstained=%d refused_input=%d abstained_with_reachable_candidate=%d abstained_unreachable_only=%d" % (
        s["sentences"], s["read"], s["abstained"], s["refused_input"], s["abstained_with_reachable_candidate"], s["abstained_unreachable_only"]))
    for b in s["candidates_by_word"]:
        lines.append("# blocks\t%s\t%s\t%d sentence(s)" % (b["op"], b["word"], b["sentences"]))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------------------ argparse / run
def add_arguments(p) -> None:
    common = __import__("argparse").ArgumentParser(add_help=False)
    common.add_argument("--layer", default=None, help="the placement layer (a name or a path; without it VERA_PLACEMENT_LAYER)")
    common.add_argument("--ledger-file", default=None, dest="ledger_file", help="the testimony ledger every confirmation is recorded in (needed to write)")
    common.add_argument("--placement", default=None, help="the base placement directory (without it VERA_PLACEMENT)")
    common.add_argument("--json", action="store_true", help="one JSON line")
    who = __import__("argparse").ArgumentParser(add_help=False)
    who.add_argument("--by", default=None, help="who confirms (required)")
    who.add_argument("--reason", default=None, help="why (free text)")
    sub = p.add_subparsers(dest="confirm_op", required=True)
    s = sub.add_parser("suggest", parents=[common], help="what a confirmation could unblock, one line per candidate")
    s.add_argument("--text", required=True, help="the text file to read, sentence by sentence")
    s = sub.add_parser("set", parents=[common, who], help="confirm a word's type")
    s.add_argument("word")
    s.add_argument("type")
    s = sub.add_parser("frame", parents=[common, who], help="confirm a predicate's role frame entry (the predicate's type must be confirmed first)")
    s.add_argument("predicate")
    s.add_argument("particle")
    s.add_argument("role")
    s.add_argument("types", nargs="+")
    s = sub.add_parser("list", parents=[common], help="the confirmations of the layer")
    s.add_argument("--all", action="store_true", help="also the undone ones and the undo rows")
    s = sub.add_parser("undo", parents=[common, who], help="undo a confirmation (an appended row)")
    s.add_argument("confirm_id")


def run(args) -> int:
    from .llm_choice import LedgerIntegrityError
    from .testimony_ledger import LedgerError

    def refuse(verdict: str, reason: str = "", rc: int = EXIT_REFUSED) -> int:
        _out({"kind": "unknown", "verdict": verdict, "reason": reason})
        return rc
    op = args.confirm_op
    try:
        if op == "suggest":
            res = suggest(args.text, args.placement, args.layer)
            if args.json:
                _out(res)
            else:
                print(render_tsv(res))
            return 0
        writing = op in ("set", "frame", "undo")
        t = open_target(args.layer, args.ledger_file, args.placement, need_ledger=writing, create_ledger=writing)
        if op == "set":
            _out(confirm_set(t, args.word, args.type, args.by, args.reason))
        elif op == "frame":
            _out(confirm_frame(t, args.predicate, args.particle, args.role, args.types, args.by, args.reason))
        elif op == "undo":
            _out(confirm_undo(t, args.confirm_id, args.by, args.reason))
        else:
            rows = list_rows(t, args.all)
            if args.json:
                _out({"layer": t.layer_name, "confirmations": rows, "active": sum(1 for r in rows if r["state"] == "active")})
            else:
                print("layer=%s confirmations=%d" % (t.layer_name, len(rows)))
                for r in rows:
                    print("%s\t%s\t%s\t%s\t%s\tby=%s\t%s\t%s" % (r["confirm_id"], r["kind"], r["word"], r["type"], json.dumps(r["frame"], ensure_ascii=False) if r["frame"] else "-",
                                                                r["by"], r["state"], r["reason"] or ""))
        return 0
    except ConfirmError as exc:
        return refuse(exc.type, exc.detail)
    except LedgerIntegrityError as exc:
        return refuse("LEDGER_INTEGRITY", "%s line %s %s" % (exc.kind, exc.line_no, exc.detail), EXIT_LEDGER_BROKEN)
    except LedgerError as exc:
        return refuse(exc.type, exc.detail)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="vera confirm")
    add_arguments(p)
    return run(p.parse_args(list(argv) if argv is not None else None))


if __name__ == "__main__":
    sys.exit(main())
