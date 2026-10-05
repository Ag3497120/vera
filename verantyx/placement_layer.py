"""W10-f05 (A11, O3, docs/COARSE_PLACEMENT.md section 12.19): the placement layer -- a domain / user overlay that sits on top of a base placement.

A layer is ONE SQLite file (append only).  ``coarse_place.query(term, placement=<base>, layer=<spec>)`` asks the base first and uses the layer only for a word the base
leaves undecided (UNPLACED / UNKNOWN / MULTIPLE; K290).  A word the base decided (DECIDED, direct or estimated) is never changed by the layer: the layer adds, it never
corrects (correcting the public placement is the job of the r series).  K290 is revised by K680 (W16-t8, docs/COARSE_PLACEMENT.md 12.21) for ONE kind of row only: a human's
confirmation row (``origin layer_human`` with ``evidence.confirm_id`` in the W10-f04 form (16 lowercase hex digits) and ``decided_by == ["human:<confirm_id>"]``, written by ``vera confirm``) acts ABOVE the base,
even for a word the base decided; the answer says ``decided_by: human:<confirm_id>`` and ``axes.layer.overrode_base`` keeps the base's value.  A human's ``set`` changes the TYPE only: the base's section 12.10
frame and role frame stay (r3, 12.21.7: only ``vera confirm frame`` adds to the role frame).  Every other row stays under K290; a row that has the SHAPE of a confirmation (a ``human:`` arm, a
``confirm_id`` / ``undoes``, a type / frame / undo ``kind``) but is not backed by a real confirm id is treated as ``layer_estimated`` (r3, 12.21.7).  The module never writes the base and never reads anything but the one layer file.

``spec`` is a path (it has a ``/`` or ends with ``.sqlite``) or a name (``[A-Za-z0-9_.-]{1,64}``) that lives in ``$VERA_PLACEMENT_LAYER_ROOT/<name>.sqlite`` (no home directory
and no other place is searched).  An empty ``VERA_PLACEMENT_LAYER`` is the same as an unset one.

A layer row has an ``origin``: ``layer_confirmed`` (an LLM's declaration that the documents' distribution agreed with: K291 (a)), ``layer_human`` (a human confirmed it through
the testimony ledger: K291 (b)) -- both are DIRECT -- and ``layer_estimated`` (a declaration alone, or a re-reading alone: shown, never read by the reader).  These three words
are the names of the rows only; the ``origin`` of an ANSWER stays ``direct`` / ``estimated`` (the contract of the placement query).

Every write goes through ``write_entry``: the testimony ledger gets a ``promoted_to_layer`` row first (K294) and the layer row names that row's ``store_id`` and ``seq``.
There is no other way in, and the layer table is never updated or deleted from.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import coarse_types as ct

SCHEMA = "verantyx.placement_layer/1"
ENV_LAYER = "VERA_PLACEMENT_LAYER"
ENV_ROOT = "VERA_PLACEMENT_LAYER_ROOT"
ORIGINS = ("layer_confirmed", "layer_estimated", "layer_human")
DIRECT_ORIGINS = ("layer_confirmed", "layer_human")
UNAVAILABLE_REASONS = ("MISSING", "UNREADABLE", "ROOT_UNSET", "BAD_NAME", "BASE_MISMATCH")
STATUSES = ("BASE_NO_PLACEMENT", "BASE_DECIDED", "LAYER_HAS_NO_ENTRY", "LAYER_CONFLICT", "LAYER_ESTIMATED_NOT_USED", "LAYER_DIRECT_USED",
            "LAYER_TYPE_NOT_AMONG_CANDIDATES") + tuple("LAYER_UNAVAILABLE:" + r for r in UNAVAILABLE_REASONS) + ("HUMAN_CONFIRMED_USED", "HUMAN_CONFLICT")
CONFIRM_KINDS = ("type", "frame", "undo")
CONFIRM_ID_RE = re.compile(r"^[0-9a-f]{16}$")             # the W10-f04 form of an id: ``TestimonyLedger._new_id`` = ``uuid4().hex[:16]``
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_CACHE: Dict[str, "Layer"] = {}

_DDL = (
    "CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)",
    "CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT NOT NULL, ns TEXT NOT NULL, type TEXT NOT NULL, "
    "origin TEXT NOT NULL CHECK(origin IN ('layer_confirmed','layer_estimated','layer_human')), decided_by TEXT NOT NULL, evidence TEXT NOT NULL, "
    "role_frame TEXT, ledger_store_id TEXT NOT NULL, ledger_seq INTEGER NOT NULL, ledger_key TEXT NOT NULL, ts TEXT NOT NULL)",
    "CREATE INDEX entries_word ON entries(word)",
)


class LayerError(Exception):
    def __init__(self, type_: str, detail: str = "") -> None:
        super().__init__("%s %s" % (type_, detail))
        self.type, self.detail = type_, detail


def _nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


def spec_from_env() -> Optional[str]:
    v = os.environ.get(ENV_LAYER)
    return v if v is not None and v.strip() != "" else None


def resolve(spec: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """``(path, name, None)`` or ``(None, None, reason)`` (reason: ``BAD_NAME`` / ``ROOT_UNSET``)."""
    spec = str(spec).strip()
    if "/" in spec or spec.endswith(".sqlite"):
        path = os.path.abspath(os.path.expanduser(spec))
        base = os.path.basename(path)
        return path, (base[:-len(".sqlite")] if base.endswith(".sqlite") else base), None
    if not _NAME.match(spec):
        return None, None, "BAD_NAME"
    root = os.environ.get(ENV_ROOT)
    if root is None or root.strip() == "":
        return None, None, "ROOT_UNSET"
    return os.path.join(os.path.abspath(os.path.expanduser(root)), spec + ".sqlite"), spec, None


class Layer:
    """An opened layer (read only)."""

    def __init__(self, path: str, name: str, con: sqlite3.Connection, meta: Dict[str, str]) -> None:
        self.path, self.name, self.con, self.meta = path, name, con, meta
        self.base_sha = meta.get("base_content_sha256")

    def entries(self, word: str) -> List[Dict[str, Any]]:
        rows = self.con.execute("SELECT id, word, ns, type, origin, decided_by, evidence, role_frame, ledger_store_id, ledger_seq, ledger_key, ts FROM entries WHERE word=? ORDER BY id",
                                (word,)).fetchall()
        return [_row(r) for r in rows]

    def all_entries(self) -> List[Dict[str, Any]]:
        rows = self.con.execute("SELECT id, word, ns, type, origin, decided_by, evidence, role_frame, ledger_store_id, ledger_seq, ledger_key, ts FROM entries ORDER BY id").fetchall()
        return [_row(r) for r in rows]


def _row(r) -> Dict[str, Any]:
    return {"id": r[0], "word": r[1], "ns": r[2], "type": r[3], "origin": r[4], "decided_by": json.loads(r[5]), "evidence": json.loads(r[6]),
            "role_frame": json.loads(r[7]) if r[7] else None, "ledger_store_id": r[8], "ledger_seq": r[9], "ledger_key": r[10], "ts": r[11]}


def open_layer(spec: str, base_sha: Optional[str] = None) -> Tuple[Optional[Layer], Optional[str]]:
    """``(layer, None)`` or ``(None, reason)`` with reason one of ``UNAVAILABLE_REASONS``.  With ``base_sha`` a layer made on another base is ``BASE_MISMATCH``."""
    path, name, why = resolve(spec)
    if path is None:
        return None, why
    try:
        st = os.stat(path)
    except OSError:
        return None, "MISSING"
    key = "%s|%d|%d" % (path, st.st_mtime_ns, st.st_size)
    got = _CACHE.get(key)
    if got is None:
        try:
            con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
            meta = dict(con.execute("SELECT k, v FROM meta").fetchall())
            if meta.get("schema") != SCHEMA:
                con.close()
                return None, "UNREADABLE"
            con.execute("SELECT COUNT(*) FROM entries").fetchone()
        except sqlite3.Error:
            return None, "UNREADABLE"
        for k in [k for k in _CACHE if k.startswith(path + "|")]:
            try:
                _CACHE.pop(k).con.close()
            except Exception:
                pass
        got = _CACHE[key] = Layer(path, name, con, meta)
    if base_sha is not None and got.base_sha != base_sha:
        return None, "BASE_MISMATCH"
    return got, None


def is_confirm_row(e: Dict[str, Any]) -> bool:
    """K680: a human's confirmation row (written by ``vera confirm`` only): ``layer_human`` + ``evidence.kind`` in type / frame / undo + ``evidence.confirm_id`` in the W10-f04 form
    (``CONFIRM_ID_RE``; for an undo row ``evidence.undoes`` too) + ``decided_by == ["human:<id>"]``.  A ``layer_human`` row made by ``vera ledger promote`` has no confirm_id and is NOT one
    (it stays under K290); neither is a row that has a confirm_id of another form (r3, 12.21.7)."""
    ev = e.get("evidence")
    if e.get("origin") != "layer_human" or not isinstance(ev, dict) or ev.get("kind") not in CONFIRM_KINDS:
        return False
    cid = ev.get("confirm_id")
    if not (isinstance(cid, str) and CONFIRM_ID_RE.match(cid)) or e.get("decided_by") != ["human:" + cid]:
        return False
    if ev["kind"] == "undo":
        und = ev.get("undoes")
        return isinstance(und, str) and bool(CONFIRM_ID_RE.match(und))
    return True


def is_unbacked_human_row(e: Dict[str, Any]) -> bool:
    """r3 (the auditor's ruling of 2026-10-06 00:24, narrowed; docs/COARSE_PLACEMENT.md 12.21.7): a ``layer_human`` row that is NOT a confirmation row (``is_confirm_row``) but has its shape: a ``human:`` arm in
    ``decided_by``, or the keys ``confirm_id`` / ``undoes``, or a ``kind`` of type / frame / undo in ``evidence`` (or in ``evidence.from_evidence``, where ``tools/build_initial_layers.py combine`` wraps it).
    Such a row (a copy with a wrong id, or one whose evidence was wrapped) is read as ``layer_estimated``: it never acts as a human's confirmation.  A plain ``decided_by == ["layer_human"]`` row of
    ``vera ledger promote`` has none of these and stays what it was (K290: a direct row)."""
    if e.get("origin") != "layer_human" or is_confirm_row(e):
        return False
    if any(isinstance(b, str) and b.startswith("human:") for b in (e.get("decided_by") or [])):
        return True
    ev = e.get("evidence")
    if not isinstance(ev, dict):
        return False
    for d in (ev, ev.get("from_evidence") if isinstance(ev.get("from_evidence"), dict) else None):
        if d is not None and ("confirm_id" in d or "undoes" in d or d.get("kind") in CONFIRM_KINDS):
            return True
    return False


def active_confirm_rows(entries: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """K680: ``{"type": [rows], "frame": [rows]}`` of the confirmation rows that are not undone (an undo row, and the row it undoes, are left out; id order)."""
    conf = [e for e in entries if is_confirm_row(e)]
    undone = {e["evidence"].get("undoes") for e in conf if e["evidence"]["kind"] == "undo"}
    return {"type": [e for e in conf if e["evidence"]["kind"] == "type" and e["evidence"]["confirm_id"] not in undone],
            "frame": [e for e in conf if e["evidence"]["kind"] == "frame" and e["evidence"]["confirm_id"] not in undone]}


def fold(entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """One word's rows -> ``{"direct": {type: [rows]}, "estimated": {type: [rows]}}`` (a row list is in id order).  K680: an undo row, a row that was undone and a frame row of a
    human's confirmation are left out first (they are not a type of the word); with no confirmation row the result is what it was.  r3: an unbacked human-shaped row (``is_unbacked_human_row``) is put under
    ``estimated`` whatever its origin says."""
    conf = [e for e in entries if is_confirm_row(e)]
    if conf:
        undone = {e["evidence"].get("undoes") for e in conf if e["evidence"]["kind"] == "undo"}
        entries = [e for e in entries if not (is_confirm_row(e) and (e["evidence"]["kind"] in ("undo", "frame") or e["evidence"]["confirm_id"] in undone))]
    out: Dict[str, Any] = {"direct": {}, "estimated": {}}
    for e in entries:
        direct = e["origin"] in DIRECT_ORIGINS and not is_unbacked_human_row(e)          # r3: an unbacked human-shaped row is a layer_estimated row (the dict itself is not changed)
        out["direct" if direct else "estimated"].setdefault(e["type"], []).append(e)
    return out


def _add(r: Dict[str, Any], layer: str, status: str) -> Dict[str, Any]:
    return dict(list(r.items()) + [("layer", layer), ("layer_status", status)])


def apply(r: Dict[str, Any], spec: str, base_pl: Any) -> Dict[str, Any]:
    """The answer ``r`` of the base placement (every key already there) -> the answer with the layer's keys ``layer`` and ``layer_status`` at the END (docs section 12.19, K290; K680 in 12.21:
    a human's confirmation row acts above the base)."""
    state = r.get("state")
    if state == "NO_PLACEMENT":
        return _add(r, "none", "BASE_NO_PLACEMENT")
    layer, why = open_layer(spec, getattr(base_pl, "sha", None))
    if layer is None:
        if state == "DECIDED":
            return _add(r, "base", "BASE_DECIDED")           # no layer to look at: what it was (K290)
        return _add(r, "base", "LAYER_UNAVAILABLE:%s" % why)
    word = ((r.get("spelling") or {}).get("normalized")) or _nfkc(r.get("term", ""))
    rows = layer.entries(word)
    if any(is_confirm_row(e) for e in rows):                 # K680: a human's confirmation of this word
        act = active_confirm_rows(rows)
        types = {e["type"] for e in act["type"]}
        if len(types) >= 2:
            return _add(r, "base", "HUMAN_CONFLICT")          # two human types: a tie abstains, the base answer stays
        if types:
            t = next(iter(types))
            return _human_answer(r, layer, t, [e for e in act["type"] if e["type"] == t], [e for e in act["frame"] if e["type"] == t], base_pl)
        rows = [e for e in rows if not is_confirm_row(e)]     # nothing active: the rest is judged by K290 as before
    if state == "DECIDED":                                   # direct or estimated: the layer does not look (K290)
        return _add(r, "base", "BASE_DECIDED")
    if not rows:
        return _add(r, "base", "LAYER_HAS_NO_ENTRY")
    f = fold(rows)
    d = f["direct"]
    if len(d) >= 2:
        return _add(r, "base", "LAYER_CONFLICT")              # two direct types: a tie abstains (J11)
    if not d:
        return _add(r, "base", "LAYER_ESTIMATED_NOT_USED")    # an estimate does not enter the answer (J3)
    t = next(iter(d))
    if state == "MULTIPLE" and t not in (r.get("top") or []):
        return _add(r, "base", "LAYER_TYPE_NOT_AMONG_CANDIDATES")
    return _direct_answer(r, layer, t, d[t], rows, base_pl)


def _human_role_frame(frame_rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The role frame a human gave: ``{particle: [{"role", "types"}]}`` (two keys only: the reader refuses any other key), particles in the order of the nine case particles, roles by name, the
    types of one (particle, role) joined; None when there is no frame row."""
    from .semantic_reader import _CASE_PARTICLES_9
    acc: Dict[str, Dict[str, set]] = {}
    for e in frame_rows:
        fr = e["evidence"].get("frame") or {}
        acc.setdefault(fr.get("particle"), {}).setdefault(fr.get("role"), set()).update(fr.get("types") or [])
    if not acc:
        return None
    return {p: [{"role": role, "types": sorted(acc[p][role])} for role in sorted(acc[p])] for p in _CASE_PARTICLES_9 if p in acc}


def _overlay_role_frame(base_rf: Dict[str, Any], frame_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """r3 (12.21.7): the base's CONFIRMED role frame with a human's (particle, role, types) laid over it.  The base's entries are copied as they are (``backed_by`` too: J15 is not fixed here, so the
    reader still refuses such a frame), a human's types are joined (union, sorted) into the entry of the same particle and role, or added as ``{"role", "types"}`` after the particle's base entries in
    role-name order.  Particles in the order of the nine case particles."""
    import copy
    from .semantic_reader import _CASE_PARTICLES_9
    human = _human_role_frame(frame_rows) or {}
    out: Dict[str, Any] = {}
    for p in _CASE_PARTICLES_9:
        if p not in base_rf and p not in human:
            continue
        items = copy.deepcopy(base_rf.get(p) or [])
        for h in human.get(p, []):
            same = [x for x in items if x.get("role") == h["role"]]
            if same:
                same[0]["types"] = sorted(set(same[0].get("types") or []) | set(h["types"]))
            else:
                items.append({"role": h["role"], "types": list(h["types"])})
        out[p] = items
    return out


def _human_answer(r: Dict[str, Any], layer: Layer, t: str, type_rows: List[Dict[str, Any]], frame_rows: List[Dict[str, Any]], base_pl: Any) -> Dict[str, Any]:
    """K680: the answer when a human confirmed type ``t`` (one type among the active rows).  The same keys in the same order as ``_direct_answer``.

    r3 (12.21.7): a human's ``set`` changes the TYPE only; what the human did not confirm stays the base's.  A predicate type keeps the base's section 12.10 frame as it was when the base CONFIRMED it
    (``frame_status``, ``frame``, ``frame_unconfirmed`` unchanged, and ``gen_frame`` after the human's id in ``decided_by``: the reader asks for it); a base frame that is NOT_CONFIRMED / NO_FRAME_TABLE stays so;
    anything else (no confirmed frame) is NOT_CONFIRMED with no frame.  The role frame is the base's, byte for byte, unless the human gave frame rows (``vera confirm frame``): then it is the base's
    CONFIRMED role frame with the human's entries laid over it, or, when the base has none, the human's own.  A human never changes the 12.10 frame (``gen_frame`` is a mark of provenance)."""
    import copy
    by = [e["decided_by"][0] for e in type_rows]
    is_pred = t.startswith("P_")
    base_fs = r.get("frame_status")
    keep_1210 = is_pred and base_fs == "CONFIRMED"
    if keep_1210:
        by = by + [ct.GEN_FRAME_ARM]
    axes = dict(r.get("axes") or {})
    axes["layer"] = {"name": layer.name, "origin": "layer_human", "entry_ids": [e["id"] for e in type_rows], "ledger_seq": [e["ledger_seq"] for e in type_rows],
                     "evidence": _evidence_summary(type_rows[-1]["evidence"]), "confirm_ids": [e["evidence"]["confirm_id"] for e in type_rows],
                     "frame_confirm_ids": [e["evidence"]["confirm_id"] for e in frame_rows],
                     "overrode_base": {"state": r.get("state"), "top": list(r.get("top") or []), "origin": r.get("origin"), "decided_by": list(r.get("decided_by") or [])},
                     "base_frame": {"frame_status": base_fs, "role_frame_status": r.get("role_frame_status")}}
    out: Dict[str, Any] = {
        "term": r["term"], "namespace": ct.type_namespace(t), "state": "DECIDED", "origin": "direct", "estimate_basis": None, "constructed": False,
        "top": [t], "candidates": [{"type": t, "axes": {"layer": 1}}], "axes": axes, "neighbors": [],
        "seen_in_material": r.get("seen_in_material"), "context": r.get("context"), "placement": r.get("placement"),
        "decided_by": by, "generated": any(b in ("gen_definition", "gen_frame") for b in by), "generated_definition": ct.GEN_ARM in by}
    if "spelling" in r:
        out["spelling"] = r["spelling"]
    if "frame_generated" in r:
        out["frame_generated"] = r["frame_generated"]
    out["generated_frame"] = ct.GEN_FRAME_ARM in by
    if keep_1210:
        out["frame_status"], out["frame"] = "CONFIRMED", copy.deepcopy(r.get("frame"))
        if "frame_unconfirmed" in r:
            out["frame_unconfirmed"] = copy.deepcopy(r["frame_unconfirmed"])
    elif is_pred and base_fs in ("NOT_CONFIRMED", "NO_FRAME_TABLE"):
        out["frame_status"], out["frame"] = base_fs, None
        if "frame_disagreement" in r:
            out["frame_disagreement"] = copy.deepcopy(r["frame_disagreement"])
    else:
        out["frame_status"] = "NOT_CONFIRMED" if is_pred else "NOT_PREDICATE"
        out["frame"] = None
    if "role_frame_status" in r:
        if not is_pred:
            out["role_frame_status"], out["role_frame"], out["role_frame_unconfirmed"] = "NO_ROLE_FRAME", None, None
        else:
            human_rf = _human_role_frame(frame_rows)
            base_rf = r.get("role_frame") if r.get("role_frame_status") == "CONFIRMED" and isinstance(r.get("role_frame"), dict) else None
            if human_rf is None:                                  # no frame row: the base's role frame, as it was
                out["role_frame_status"], out["role_frame"], out["role_frame_unconfirmed"] = (r.get("role_frame_status"), copy.deepcopy(r.get("role_frame")),
                                                                                              copy.deepcopy(r.get("role_frame_unconfirmed")))
            else:
                out["role_frame_status"] = "CONFIRMED"
                out["role_frame"] = _overlay_role_frame(base_rf, frame_rows) if base_rf is not None else human_rf
                out["role_frame_unconfirmed"] = copy.deepcopy(r.get("role_frame_unconfirmed"))
    out["layer"] = "overlay:%s" % layer.name
    out["layer_status"] = "HUMAN_CONFIRMED_USED"
    return out


def _direct_answer(r: Dict[str, Any], layer: Layer, t: str, rows: List[Dict[str, Any]], all_rows: List[Dict[str, Any]], base_pl: Any) -> Dict[str, Any]:
    human = [e for e in rows if e["origin"] == "layer_human"]
    chosen = (human or rows)[-1]                              # the provenance shown: a human's row first, else the latest (the TYPE is the same in every one)
    by = list(chosen["decided_by"])
    is_pred = t.startswith("P_")
    axes = dict(r.get("axes") or {})
    axes["layer"] = {"name": layer.name, "origin": chosen["origin"], "entry_ids": [e["id"] for e in rows], "ledger_seq": [e["ledger_seq"] for e in rows],
                     "evidence": _evidence_summary(chosen["evidence"])}
    out: Dict[str, Any] = {
        "term": r["term"], "namespace": ct.type_namespace(t), "state": "DECIDED", "origin": "direct", "estimate_basis": None, "constructed": False,
        "top": [t], "candidates": [{"type": t, "axes": {"layer": 1}}], "axes": axes, "neighbors": [],
        "seen_in_material": r.get("seen_in_material"), "context": r.get("context"), "placement": r.get("placement"),
        "decided_by": by, "generated": any(b in ("gen_definition", "gen_frame") for b in by),
        "generated_definition": ct.GEN_ARM in by}
    if "spelling" in r:
        out["spelling"] = r["spelling"]
    if "frame_generated" in r:
        out["frame_generated"] = r["frame_generated"]
    out["generated_frame"] = ct.GEN_FRAME_ARM in by
    out["frame_status"] = "NOT_CONFIRMED" if is_pred else "NOT_PREDICATE"      # the layer does not confirm a section 12.10 frame (J16)
    out["frame"] = None
    if "role_frame_status" in r:                              # only when the base answer has the role-frame keys (a placement with that table)
        if not is_pred or not chosen.get("role_frame"):
            out["role_frame_status"], out["role_frame"], out["role_frame_unconfirmed"] = "NO_ROLE_FRAME", None, None
        else:
            doc_rows = [tuple(x) for x in (chosen["evidence"].get("doc_rows") or []) if x and x[0] == "role_distribution"]
            checked = ct.role_frame_check(chosen["role_frame"], doc_rows, getattr(base_pl, "cfg", ct.DEFAULT_CONFIG))
            if checked["status"] == "CONFIRMED":
                out["role_frame_status"], out["role_frame"], out["role_frame_unconfirmed"] = "CONFIRMED", checked["confirmed"], checked["unconfirmed"]
            else:
                out["role_frame_status"], out["role_frame"], out["role_frame_unconfirmed"] = "ESTIMATED", None, checked["unconfirmed"]
    out["layer"] = "overlay:%s" % layer.name
    out["layer_status"] = "LAYER_DIRECT_USED"
    return out


def _evidence_summary(ev: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("model", "doc_ids", "decision", "human", "ledger_key")
    return {k: ev[k] for k in keep if k in ev}


# ------------------------------------------------------------------------------------------------------------------------ write (the only way in)
def write_entry(layer_path: str, ledger: Any, *, base_sha256: Optional[str], word: str, type: str, origin: str, decided_by: Sequence[str],
                evidence: Dict[str, Any], role_frame: Optional[Dict[str, Any]], key: str, fill_id: Optional[str] = None,
                candidate: Optional[str] = None, from_seq: Sequence[int] = ()) -> Dict[str, Any]:
    """Append one row to the layer, AFTER the testimony ledger has a ``promoted_to_layer`` row for it (K294).  ``LayerError('LAYER_BASE_MISMATCH')``: the layer was made on another
    base placement (nothing is written, not even the ledger row).  ``origin`` is one of ``ORIGINS`` and ``type`` a type id; a ``layer_confirmed`` / ``layer_human`` row
    needs a non-empty ``decided_by``.  Returns ``{"entry_id", "ledger_seq", "ledger_store_id"}``."""
    if origin not in ORIGINS:
        raise LayerError("BAD_ORIGIN", str(origin))
    if type not in ct.ALL_TYPES:
        raise LayerError("BAD_TYPE", str(type))
    by = [str(b) for b in decided_by]
    if origin in DIRECT_ORIGINS and not by:
        raise LayerError("DIRECT_WITHOUT_DECIDED_BY", word)
    w = _nfkc(word)
    if not w:
        raise LayerError("EMPTY_WORD")
    path = os.path.abspath(layer_path)
    name = os.path.basename(path)[:-len(".sqlite")] if path.endswith(".sqlite") else os.path.basename(path)
    existed = os.path.exists(path)
    if existed:
        try:
            con = sqlite3.connect(path)
            meta = dict(con.execute("SELECT k, v FROM meta").fetchall())
        except sqlite3.Error as exc:
            raise LayerError("LAYER_UNREADABLE", str(exc))
        if meta.get("schema") != SCHEMA:
            con.close()
            raise LayerError("LAYER_UNREADABLE", "schema")
        if base_sha256 is not None and meta.get("base_content_sha256") != base_sha256:
            con.close()
            raise LayerError("LAYER_BASE_MISMATCH", "%s != %s" % (meta.get("base_content_sha256"), base_sha256))
        layer_base = meta.get("base_content_sha256")
    else:
        layer_base = base_sha256
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        con = sqlite3.connect(path)
        for stmt in _DDL:
            con.execute(stmt)
        con.executemany("INSERT INTO meta VALUES (?, ?)", [("schema", SCHEMA), ("name", name), ("base_content_sha256", layer_base or ""),
                                                           ("created_ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))])
        con.commit()
    try:
        prow = ledger.record_promoted_to_layer(key=key, word=w, candidate=candidate or w, declared_type=type, layer_name=name, layer_base_sha256=layer_base,
                                               origin=origin, decided_by=by, evidence=evidence, fill_id=fill_id, from_seq=list(from_seq))
        cur = con.execute("INSERT INTO entries (word, ns, type, origin, decided_by, evidence, role_frame, ledger_store_id, ledger_seq, ledger_key, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (w, ct.type_namespace(type), type, origin, json.dumps(by, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                           json.dumps(role_frame, ensure_ascii=False, sort_keys=True) if role_frame else None, ledger.store_id, prow["seq"], key,
                           time.strftime("%Y-%m-%dT%H:%M:%S%z")))
        con.commit()
        return {"entry_id": cur.lastrowid, "ledger_seq": prow["seq"], "ledger_store_id": ledger.store_id}
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------------------------------ growth (section 7 of the ticket)
def growth(spec: str, ledger: Any = None, base_sha: Optional[str] = None, with_list: bool = False) -> Dict[str, Any]:
    """The indicators of a layer: words (direct = confirmed only, human, estimated only, conflict), rows, the last time it grew; with a ledger: its rows by type, the
    ``promoted_to_layer`` rows of this layer and ``chain_ok`` (every layer row names a ledger row whose word, type and origin agree with it)."""
    layer, why = open_layer(spec, base_sha)
    if layer is None:
        return {"layer_status": "LAYER_UNAVAILABLE:%s" % why}
    rows = layer.all_entries()
    by_word: Dict[str, List[Dict[str, Any]]] = {}
    for e in rows:
        by_word.setdefault(e["word"], []).append(e)
    words = {"direct": 0, "human": 0, "estimated": 0, "conflict": 0}
    listing = []
    for w, es in sorted(by_word.items()):
        f = fold(es)
        if not f["direct"] and not f["estimated"]:             # K680: only an undone / frame row of a human's confirmation: no type of the word
            state = "none"
        elif len(f["direct"]) >= 2:
            words["conflict"] += 1
            state = "conflict"
        elif f["direct"]:
            if any(e["origin"] == "layer_human" for es_ in f["direct"].values() for e in es_):
                words["human"] += 1
                state = "human"
            else:
                words["direct"] += 1
                state = "direct"
        else:
            words["estimated"] += 1
            state = "estimated"
        listing.append({"word": w, "state": state, "types": {"direct": sorted(f["direct"]), "estimated": sorted(f["estimated"])},
                        "origins": sorted({e["origin"] for e in es}), "ledger_seq": [e["ledger_seq"] for e in es]})
    out: Dict[str, Any] = {"layer": layer.name, "layer_status": "OK", "words": words, "words_total": len(by_word), "rows": len(rows),
                           "last_grown": max((e["ts"] for e in rows), default=None), "base_content_sha256": layer.base_sha}
    if ledger is not None:
        entries = ledger.entries()
        kinds: Dict[str, int] = {}
        for e in entries:
            kinds[e["type"]] = kinds.get(e["type"], 0) + 1
        mine = [e for e in entries if e.get("type") == "promoted_to_layer" and e.get("layer_name") == layer.name]
        by_seq = {e["seq"]: e for e in entries}
        bad = []
        for e in rows:
            p = by_seq.get(e["ledger_seq"])
            if (p is None or e["ledger_store_id"] != ledger.store_id or p.get("type") != "promoted_to_layer" or p.get("word") != e["word"]
                    or p.get("declared_type") != e["type"] or p.get("origin") != e["origin"] or p.get("layer_name") != layer.name):
                bad.append(e["id"])
        out["ledger"] = {"rows": len(entries), "by_type": dict(sorted(kinds.items())), "promoted_to_layer": len(mine), "chain_ok": not bad, "chain_mismatch": len(bad),
                         "chain_mismatch_ids": bad[:20], "store_id": ledger.store_id}
    if with_list:
        out["list"] = listing
    return out
