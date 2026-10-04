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
ROW_TYPES = ("header", "testimony", "not_adopted", "backend_failed", "reread_agreed", "distribution_backed", "human_confirmed", "promotable")
STATES = ("unconfirmed", "reread_agreed", "distribution_backed", "human_confirmed")
DEFAULT_PROMOTE_N = 3


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
            same = [e for e in self.entries() if e.get("type") == "testimony" and e.get("fill_id") != decision["fill_id"] and
                    key_of(e["word"], e["candidate"], e["declaration"]["type"], e["declaration"].get("role")) == k]
            sha = (decision.get("context") or {}).get("sentence_sha256")
            seen = {(e.get("context") or {}).get("sentence_sha256") for e in same} | {(e.get("context") or {}).get("sentence_sha256") for e in self.entries()
                                                                                        if e.get("type") == "reread_agreed" and e.get("key") == k}
            if same and sha not in seen:
                extra.append(self._append({"type": "reread_agreed", "fill_id": decision["fill_id"], "key": k, "word": decision["word"], "candidate": decision["candidate"],
                                           "context": decision.get("context")}))
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
        rows = [e for e in self.entries() if e.get("type") == "testimony" and e.get("fill_id") == fill_id]
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
            if e.get("type") == "testimony":
                d = e["declaration"]
                k = key_of(e["word"], e["candidate"], d["type"], d.get("role"))
                g = groups.setdefault(k, {"key": k, "word": e["word"], "candidate": e["candidate"], "declared_type": d["type"], "role": d.get("role"), "fill_ids": [],
                                          "reread_agreed": 0, "distribution_backed": False, "human_confirmed": False, "history": []})
                g["fill_ids"].append(e["fill_id"]); g["history"].append({"seq": e["seq"], "type": "testimony", "fill_id": e["fill_id"]})
        for e in entries:
            g = groups.get(e.get("key")) if e.get("type") in ("reread_agreed", "distribution_backed", "human_confirmed", "promotable") else None
            if g is None: continue
            g["history"].append({"seq": e["seq"], "type": e["type"], "fill_id": e.get("fill_id")})
            if e["type"] == "reread_agreed": g["reread_agreed"] += 1
            elif e["type"] == "distribution_backed": g["distribution_backed"] = True
            elif e["type"] == "human_confirmed": g["human_confirmed"] = True
        by_word: Dict[str, set] = {}
        for g in groups.values():
            by_word.setdefault(_nfkc(g["word"]), set()).add(_nfkc(g["candidate"]))
        for g in groups.values():
            g["state"] = ("human_confirmed" if g["human_confirmed"] else "distribution_backed" if g["distribution_backed"] else
                          "reread_agreed:%d" % g["reread_agreed"] if g["reread_agreed"] else "unconfirmed")
            earned = g["human_confirmed"] or g["distribution_backed"] or g["reread_agreed"] >= self.promote_n
            conflict = len(by_word[_nfkc(g["word"])]) > 1
            g["blocked_by"] = "CONFLICTING_TESTIMONY" if (earned and conflict and not g["human_confirmed"]) else None
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

    def listing(self) -> List[Dict[str, Any]]:
        return [{"fill_id": fid, "word": g["word"], "candidate": g["candidate"], "declared_type": g["declared_type"], "role": g["role"], "state": g["state"],
                 "promotable": g["promotable"], "blocked_by": g["blocked_by"]} for g in self.fold().values() for fid in g["fill_ids"][:1]]

    def show(self, fill_id: str) -> Optional[Dict[str, Any]]:
        rows = [e for e in self.entries() if e.get("fill_id") == fill_id or e.get("ref") == fill_id]
        if not rows:
            return None
        fold = None
        for e in rows:
            if e["type"] == "testimony":
                k = key_of(e["word"], e["candidate"], e["declaration"]["type"], e["declaration"].get("role"))
                fold = self.fold().get(k)
        return {"fill_id": fill_id, "rows": rows, "fold": fold}
