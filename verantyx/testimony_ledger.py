"""W10-f04 (O2): 証言の台帳 — LLM が出した候補（証言）の追記のみ・ハッシュ連鎖の台帳 (docs/FUSION.md §6.2 K284)。

保存は `llm_choice.ChoiceLedger`（追記のみ・ハッシュ連鎖・manifest）を部品として使う。`llm_choice` 自身は変えない。1 行の種類:
  header（台帳の `store_id`）・testimony（採用された候補）・not_adopted（門で落ちた・申告が無効）・backend_failed（後段の失敗。「候補なし」と混ぜない）・
  reread_agreed（同じ (語, 候補, 申告の型, 役割) が **別の文の sha** で再び門を通った）・distribution_backed（配置がその語を申告の型で DECIDED/direct と答えた）・
  human_confirmed（`vera ledger confirm`）・promotable（昇格の判定の結果の印）。
確認の状態は行の畳み込みで出す: unconfirmed → reread_agreed:<n> → distribution_backed → human_confirmed。
**昇格の規則（凍結）**: `reread_agreed` が N（既定 3）以上、または `distribution_backed`、または `human_confirmed` → `promotable`（W10-f05 が配置の層に流せる状態）。
狭める方向（J6）: 同じ語に別の候補が採用された行があれば、人の確認以外では `promotable` にしない（CONFLICTING_TESTIMONY）。**このモジュールは配置を変えない**。
`fill_candidates` は `human_confirmed` を書かない（書けるのは `confirm`、人が呼ぶ CLI だけ）。
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .llm_choice import ChoiceLedger, LedgerIntegrityError

SCHEMA = "verantyx.testimony_ledger/1"
ROW_TYPES = ("header", "testimony", "not_adopted", "backend_failed", "reread_agreed", "distribution_backed", "human_confirmed", "promotable", "promoted_to_layer", "human_confirmation", "human_confirmation_undone", "assumption")
TESTIMONY_TYPES = ("testimony", "assumption")       # W3-e2 (K334): an assumption row is folded, confirmed and promoted like a testimony (only when its declared type is ONE noun type)
STATES = ("unconfirmed", "reread_agreed", "distribution_backed", "human_confirmed")
DEFAULT_PROMOTE_N = 3


def foldable(e: Dict[str, Any]) -> bool:
    """W3-e2 (D5): a testimony row, or an assumption row whose declared type is exactly one of the 18 noun types (never `UNTYPED_VERB`, never a `+` joined type: those are shown, not folded)."""
    if e.get("type") == "testimony":
        return True
    if e.get("type") != "assumption":
        return False
    from .coarse_types import NOUN_TYPES
    return (e.get("declaration") or {}).get("type") in NOUN_TYPES


def _nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


def sentence_sha256(text: str) -> str:
    return hashlib.sha256(_nfkc(text).encode("utf-8")).hexdigest()


def key_of(word: str, candidate: str, declared_type: str, role: Optional[str]) -> str:
    return json.dumps([_nfkc(word), _nfkc(candidate), declared_type, role], ensure_ascii=False)


class LedgerError(Exception):
    def __init__(self, type_: str, detail: str = "") -> None:
        super().__init__("%s %s" % (type_, detail))
        self.type, self.detail = type_, detail


class TestimonyLedger:
    __test__ = False        # not a pytest class

    def __init__(self, path: Optional[str | Path] = None, *, clock: Optional[Callable[[], str]] = None, promote_n: int = DEFAULT_PROMOTE_N,
                 id_source: Optional[Callable[[], str]] = None) -> None:
        if type(promote_n) is not int or promote_n < 1:
            raise ValueError("promote_n must be a positive integer")
        self.promote_n = promote_n
        self._new_id = id_source or (lambda: uuid.uuid4().hex[:16])
        self._led = ChoiceLedger(path, clock)
        self.path = self._led.path
        self.verify()
        if not self._led.entries():
            self._led.append_manifested({"type": "header", "schema": SCHEMA, "store_id": uuid.uuid4().hex[:16], "ts": self._led.now()})

    # ---- integrity -------------------------------------------------------------------------------------------------------------------
    def verify(self) -> Dict[str, Any]:
        """The chain and the manifest (a cut-off tail, a rewritten row). Raises `LedgerIntegrityError`."""
        info = self._led.verify()
        mm = self._led.manifest_mismatch("")
        if mm:
            raise LedgerIntegrityError(0, "MANIFEST_MISMATCH", mm)
        return info

    def entries(self) -> tuple:
        self.verify()
        return self._led.entries()

    @property
    def store_id(self) -> str:
        head = self.entries()[0]
        return head["store_id"]

    # ---- append (no update, no delete) ---------------------------------------------------------------------------------------------
    def _append(self, row: Dict[str, Any]) -> Dict[str, Any]:
        self.verify()
        return self._led.append_manifested(dict(row, ts=self._led.now()))

    def record_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """One `FillDecision` (as a dict) -> one row: testimony (ADOPTED), backend_failed, not_adopted. For ADOPTED also reread_agreed / distribution_backed when they hold.
        Returns {'row': the row, 'extra': [rows]}."""
        status = decision["status"]
        kind = {"ADOPTED": "testimony", "BACKEND_FAILED": "backend_failed"}.get(status, "not_adopted")
        base = {k: decision.get(k) for k in ("fill_id", "word", "declaration", "candidate", "hole", "provenance", "context", "gate_log", "status", "reason",
                                              "choice_decision_id", "basis", "mask_user_text", "records_checked")}
        row = self._append(dict(base, type=kind))
        extra: List[Dict[str, Any]] = []
        if status == "ADOPTED":
            decl = decision["declaration"]
            k = key_of(decision["word"], decision["candidate"], decl["type"], decl.get("role"))
            same = [e for e in self.entries() if foldable(e) and e.get("fill_id") != decision["fill_id"] and
                    key_of(e["word"], e["candidate"], e["declaration"]["type"], e["declaration"].get("role")) == k]
            sha = (decision.get("context") or {}).get("sentence_sha256")
            seen = {(e.get("context") or {}).get("sentence_sha256") for e in same} | {(e.get("context") or {}).get("sentence_sha256") for e in self.entries()
                                                                                        if e.get("type") == "reread_agreed" and e.get("key") == k}
            if same and sha not in seen:
                extra.append(self._append({"type": "reread_agreed", "fill_id": decision["fill_id"], "key": k, "word": decision["word"], "candidate": decision["candidate"],
                                           "context": decision.get("context")}))
        return {"row": row, "extra": extra}

    def record_assumption(self, a: Dict[str, Any]) -> Dict[str, Any]:
        """W3-e2 (K334, D5): one assumption of stage E2 -> one `assumption` row (`kind: assumption`): `{word, kind: name_type|nonce_predicate|noun_type, assumed, source, alternatives,
        sentence_sha256, doc_id, sentence (only when the caller does not mask), model}`. The declared type is the assumed type; when it is one noun type the row is folded like a testimony
        (a second sentence with the same key writes `reread_agreed`; N of them, a distribution or a human confirmation make it promotable). Returns {'row', 'extra'}."""
        word, assumed = a["word"], a["assumed"]
        fill_id = a.get("fill_id") or self._new_id()
        ctx = {"doc_id": a.get("doc_id"), "sentence_sha256": a["sentence_sha256"]}
        if a.get("sentence") is not None:
            ctx["sentence"] = a["sentence"]
        row = self._append({"type": "assumption", "kind": "assumption", "assumption_kind": a["kind"], "fill_id": fill_id, "word": word, "candidate": word,
                            "declaration": {"type": assumed, "role": None}, "source": a["source"], "alternatives": list(a.get("alternatives") or []),
                            "context": ctx, "provenance": {"stage": "W3-e2", "model": a.get("model")}, "basis": "ASSUMPTION"})
        extra: List[Dict[str, Any]] = []
        if foldable(row):
            k = key_of(word, word, assumed, None)
            same = [e for e in self.entries() if foldable(e) and e.get("fill_id") != fill_id and key_of(e["word"], e["candidate"], e["declaration"]["type"], e["declaration"].get("role")) == k]
            seen = {(e.get("context") or {}).get("sentence_sha256") for e in same} | {(e.get("context") or {}).get("sentence_sha256") for e in self.entries()
                                                                                    if e.get("type") == "reread_agreed" and e.get("key") == k}
            if same and a["sentence_sha256"] not in seen:
                extra.append(self._append({"type": "reread_agreed", "fill_id": fill_id, "key": k, "word": word, "candidate": word, "context": ctx}))
            extra += self.promote_pending()
        return {"row": row, "extra": extra}

    def mark_distribution_backed(self, word: str, candidate: str, declared_type: str, role: Optional[str], fill_id: str, placement_answer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The placement now answers `word` DECIDED / direct / no `gen_definition` with the declared type: written once per key. The caller has run the gate of the placement (`placement_type`)."""
        k = key_of(word, candidate, declared_type, role)
        if any(e.get("type") == "distribution_backed" and e.get("key") == k for e in self.entries()):
            return None
        return self._append({"type": "distribution_backed", "fill_id": fill_id, "key": k, "word": word, "candidate": candidate,
                             "placement": {"state": placement_answer.get("state"), "top": placement_answer.get("top"), "origin": placement_answer.get("origin"),
                                           "decided_by": placement_answer.get("decided_by")}})

    def confirm(self, fill_id: str) -> Dict[str, Any]:
        """A human confirms an adopted testimony (`vera ledger confirm <id>`): a `human_confirmed` row with the ledger's `store_id` and a new `confirm_id`."""
        rows = [e for e in self.entries() if foldable(e) and e.get("fill_id") == fill_id]
        if not rows:
            raise LedgerError("NO_SUCH_TESTIMONY", fill_id)
        t = rows[0]
        k = key_of(t["word"], t["candidate"], t["declaration"]["type"], t["declaration"].get("role"))
        confirm_id = self._new_id()
        row = self._append({"type": "human_confirmed", "fill_id": fill_id, "key": k, "word": t["word"], "candidate": t["candidate"], "store_id": self.store_id, "confirm_id": confirm_id})
        return {"store_id": row["store_id"], "confirm_id": confirm_id, "fill_id": fill_id, "key": k}

    # ---- the folded view ---------------------------------------------------------------------------------------------------------------
    def fold(self) -> Dict[str, Dict[str, Any]]:
        """{key: {word, candidate, declared_type, role, fill_ids, state, reread_agreed, distribution_backed, human_confirmed, promotable, blocked_by, history}}. Computed from the rows."""
        entries = self.entries()
        groups: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            if foldable(e):
                d = e["declaration"]
                k = key_of(e["word"], e["candidate"], d["type"], d.get("role"))
                g = groups.setdefault(k, {"key": k, "word": e["word"], "candidate": e["candidate"], "declared_type": d["type"], "role": d.get("role"), "fill_ids": [],
                                          "reread_agreed": 0, "distribution_backed": False, "human_confirmed": False, "history": []})
                g["fill_ids"].append(e["fill_id"]); g["history"].append({"seq": e["seq"], "type": e["type"], "fill_id": e["fill_id"]})
        # W3-e2 round 3 (ruling 5): a re-reading of a SURFACE assumption (source == 'surface') is shown in `reread_agreed` but not counted toward N (the surface would confirm itself)
        surface_fills = {e.get("fill_id") for e in entries if e.get("type") == "assumption" and e.get("source") == "surface"}
        counted: Dict[str, int] = {}
        for e in entries:
            g = groups.get(e.get("key")) if e.get("type") in ("reread_agreed", "distribution_backed", "human_confirmed", "promotable") else None
            if g is None: continue
            g["history"].append({"seq": e["seq"], "type": e["type"], "fill_id": e.get("fill_id")})
            if e["type"] == "reread_agreed":
                g["reread_agreed"] += 1
                if e.get("fill_id") not in surface_fills: counted[g["key"]] = counted.get(g["key"], 0) + 1
            elif e["type"] == "distribution_backed": g["distribution_backed"] = True
            elif e["type"] == "human_confirmed": g["human_confirmed"] = True
        by_word: Dict[str, set] = {}
        for g in groups.values():
            by_word.setdefault(_nfkc(g["word"]), set()).add(_nfkc(g["candidate"]))
        for g in groups.values():
            g["state"] = ("human_confirmed" if g["human_confirmed"] else "distribution_backed" if g["distribution_backed"] else
                          "reread_agreed:%d" % g["reread_agreed"] if g["reread_agreed"] else "unconfirmed")
            n_counted = counted.get(g["key"], 0)
            earned = g["human_confirmed"] or g["distribution_backed"] or n_counted >= self.promote_n
            conflict = len(by_word[_nfkc(g["word"])]) > 1
            g["blocked_by"] = "CONFLICTING_TESTIMONY" if (earned and conflict and not g["human_confirmed"]) else None
            if not earned and g["reread_agreed"] >= self.promote_n:
                g["blocked_by"] = "SURFACE_ASSUMPTION"
            g["promotable"] = bool(earned and g["blocked_by"] is None)
        return groups

    def promote_pending(self) -> List[Dict[str, Any]]:
        """Writes a `promotable` row for each key that has just become promotable (once per key). Does NOT change a placement."""
        out = []
        marked = {e.get("key") for e in self.entries() if e.get("type") == "promotable"}
        for k, g in self.fold().items():
            if g["promotable"] and k not in marked:
                out.append(self._append({"type": "promotable", "key": k, "word": g["word"], "candidate": g["candidate"], "state": g["state"], "promote_n": self.promote_n,
                                         "fill_id": g["fill_ids"][0]}))
        return out

    # ---- W10-f05 (O3, K294): the way into a placement layer ----------------------------------------------------------------------------
    def record_promoted_to_layer(self, *, key: str, word: str, candidate: str, declared_type: str, layer_name: str, layer_base_sha256: Optional[str], origin: str,
                                 decided_by: Sequence[str], evidence: Dict[str, Any], fill_id: Optional[str], from_seq: Sequence[int]) -> Dict[str, Any]:
        """Appends the `promoted_to_layer` row of one layer write (the layer module calls this BEFORE it writes its row, and names the returned `seq`). Appends only; this module never changes a layer."""
        return self._append({"type": "promoted_to_layer", "key": key, "word": _nfkc(word), "candidate": _nfkc(candidate), "declared_type": declared_type, "layer_name": layer_name,
                             "layer_base_sha256": layer_base_sha256, "origin": origin, "decided_by": list(decided_by), "evidence": evidence, "fill_id": fill_id,
                             "from_seq": list(from_seq)})

    # ---- W16-t8 (K681): a human's confirmation made through `vera confirm` (docs/COARSE_PLACEMENT.md 12.21) ---------------------------------------------------------------
    def record_human_confirmation(self, *, kind: str, word: str, type: str, frame: Optional[Dict[str, Any]], by: str, reason: Optional[str], layer_name: str) -> Dict[str, Any]:
        """Appends a `human_confirmation` row (`kind`: type | frame) with a new `confirm_id`; the layer row follows (`placement_layer.write_entry` appends `promoted_to_layer` and names this row's seq). Appends only."""
        confirm_id = self._new_id()
        row = self._append({"type": "human_confirmation", "kind": kind, "word": _nfkc(word), "declared_type": type, "frame": frame, "by": by, "reason": reason, "layer_name": layer_name,
                            "store_id": self.store_id, "confirm_id": confirm_id})
        return {"row": row, "confirm_id": confirm_id}

    def record_human_confirmation_undone(self, *, undoes: str, word: str, by: str, reason: Optional[str], layer_name: str) -> Dict[str, Any]:
        """Appends a `human_confirmation_undone` row naming the `confirm_id` it undoes (a new `confirm_id` of its own). The earlier rows are never changed."""
        confirm_id = self._new_id()
        row = self._append({"type": "human_confirmation_undone", "undoes": undoes, "word": _nfkc(word), "by": by, "reason": reason, "layer_name": layer_name,
                            "store_id": self.store_id, "confirm_id": confirm_id})
        return {"row": row, "confirm_id": confirm_id}

    def promotion_plan(self, layer_name: str, base_query: Optional[Callable[[str], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """What `vera ledger promote --layer <name>` would write, one item per key of the folded view; changes neither a layer nor the ledger. Item keys: `key, word, candidate, declared_type,
        fill_id, origin` (the layer origin, or None) `skip` (a closed reason, or None), `decided_by, evidence, role_frame, from_seq`. The rules (docs/COARSE_PLACEMENT.md section 12.19, K290/K291, J10):
        a human confirmation -> `layer_human` (direct); a re-reading agreement of at least N alone -> `layer_estimated` (never direct); the word already DECIDED in the base -> `SKIP_BASE_DECIDED`;
        a distribution-backed row alone: the fill's testimony says the base decided it (`SKIP_BASE_DECIDED`), the grow's is already in the layer (`SKIP_ALREADY_IN_LAYER`);
        the same (key, layer, origin) already in the ledger -> `SKIP_ALREADY_PROMOTED`. `base_query(word)` is the base placement's answer (None: not asked)."""
        entries = self.entries()
        done = {(e.get("key"), e.get("layer_name"), e.get("origin")) for e in entries if e.get("type") == "promoted_to_layer"}
        in_layer = {(e.get("key"), e.get("layer_name")) for e in entries if e.get("type") == "promoted_to_layer"}
        tests = {}
        for e in entries:
            if foldable(e):
                tests.setdefault(key_of(e["word"], e["candidate"], e["declaration"]["type"], e["declaration"].get("role")), e)
        out: List[Dict[str, Any]] = []
        for k, g in self.fold().items():
            t = tests[k]
            decl = t.get("declaration") or {}
            item = {"key": k, "word": _nfkc(g["word"]), "candidate": g["candidate"], "declared_type": g["declared_type"], "fill_id": g["fill_ids"][0], "origin": None, "skip": None,
                    "decided_by": [], "evidence": {"ledger_key": k, "reread_agreed": g["reread_agreed"], "state": g["state"], "model": (t.get("provenance") or {}).get("model")},
                    "role_frame": decl.get("frame") if isinstance(decl.get("frame"), dict) and decl.get("frame") else None,
                    "from_seq": [h["seq"] for h in g["history"] if h["type"] in ("testimony", "assumption", "reread_agreed", "distribution_backed", "human_confirmed")]}
            if not g["promotable"]:
                item["skip"] = "NOT_PROMOTABLE:%s" % (g["blocked_by"] or g["state"])
            else:
                decided = False
                if base_query is not None:
                    try:
                        decided = base_query(item["word"]).get("state") == "DECIDED"
                    except Exception:
                        decided = False
                from_grow = str(t.get("basis") or "").startswith("LLM_TESTIMONY_PLACEMENT")
                if decided:
                    item["skip"] = "SKIP_BASE_DECIDED"
                elif g["human_confirmed"]:
                    item["origin"], item["decided_by"] = "layer_human", ["layer_human"]
                elif g["reread_agreed"] >= self.promote_n:
                    item["origin"] = "layer_estimated"
                elif g["distribution_backed"]:
                    item["skip"] = "SKIP_ALREADY_IN_LAYER" if from_grow else "SKIP_BASE_DECIDED"
                else:
                    item["skip"] = "SKIP_NO_LAYER_RULE"
                if item["origin"] is not None and (k, layer_name, item["origin"]) in done:
                    item["skip"], item["origin"] = "SKIP_ALREADY_PROMOTED", None
                elif item["skip"] == "SKIP_ALREADY_IN_LAYER" and (k, layer_name) not in in_layer:
                    item["skip"] = "SKIP_DISTRIBUTION_ONLY_NOT_IN_THIS_LAYER"
            out.append(item)
        return out

    def listing(self) -> List[Dict[str, Any]]:
        return [{"fill_id": fid, "word": g["word"], "candidate": g["candidate"], "declared_type": g["declared_type"], "role": g["role"], "state": g["state"],
                 "promotable": g["promotable"], "blocked_by": g["blocked_by"]} for g in self.fold().values() for fid in g["fill_ids"][:1]]

    def show(self, fill_id: str) -> Optional[Dict[str, Any]]:
        rows = [e for e in self.entries() if e.get("fill_id") == fill_id or e.get("ref") == fill_id]
        if not rows:
            return None
        fold = None
        for e in rows:
            if foldable(e):
                k = key_of(e["word"], e["candidate"], e["declaration"]["type"], e["declaration"].get("role"))
                fold = self.fold().get(k)
        return {"fill_id": fill_id, "rows": rows, "fold": fold}
