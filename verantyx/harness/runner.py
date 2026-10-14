"""The runner: one question over documents (`ask`), a memory (`mem`), and the checks of a finished run (`verify`, `replay`).

Every path is the same shape: a backend (any of the three) is driven by the UNCHANGED loom drivers (verantyx.loom.driver / memdriver) over a loom or memory
server, so every operation of the model is one row of a hash-chained ledger and the only things the user is ever shown are

  * the text of a successful `emit` of a ledger that verifies and replays identically (a quote of the documents, with its source sentence), or
  * 「分かりません」 with the typed reason (the abstention type, the reason the run was abandoned, the last refusal of the gate).

Free text of the model is hashed (a `free_text_dropped` row) and dropped.  Nothing here prints a key.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from verantyx import __version__
from verantyx.harness import docs_corpus as dc
from verantyx.harness import keys, plugins as pl, prompting
from verantyx.harness.backends import Backend, BackendError, DriverClient
from verantyx.ledger_events import LedgerError
from verantyx.loom import driver as drv
from verantyx.loom import evidence as evl
from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memdriver as mdrv
from verantyx.loom import memory as mem
from verantyx.loom import memview as mview
from verantyx.loom.mcp import LoomServer
from verantyx.loom.state import Refuse

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUNS_DIR = "runs"
TASK_ID = "ask/1"
EVIDENCE_DEFAULT = "v6"
MEM_BUNDLE = mem.V4_VERSIONS_M6D                  # shape.v4 + qwords.v2 + ask.v3 (PUB-M6d); the answer run is memanswer.v17
MEM_ANSWER_VERSION = ma.ANSWER_V17
MEMORY_PROFILE_DEFAULT = "m6d-v17"                 # the built-in memory_profile plugin that is MEM_BUNDLE + MEM_ANSWER_VERSION
MEM_ANSWER_MAX_TURNS = 40
MEM_MAX_CALLS = mdrv.MAX_CALLS_PER_TURN_V3
REFUSAL_TEXT = "分かりません"
UNSOURCED_MARK = "出所: 利用者の発言ではない（エージェントの記録）"

REASON_JA = {
    "unrecorded_user_statement": "利用者がこの場所について別のことを言っていますが、記憶に入っていません",
    "redacted_turn_unreadable": "利用者の発言の一部が秘密の形として伏せられ、読み取れませんでした（この回より前のことには答えません）",
    "store_not_verified": "記憶の台帳が検証できません",                                         # the typed reason, said in Japanese; the token stays visible
    "no_record": "文書にその答えが書かれていません",
    "cannot_weave": "文書に関係する記述はありますが、引用の形にできませんでした",
    "unknown": "判断できませんでした",
    "contested": "記録の中で答えが食い違っています",
    "max_turns": "モデルが規定の回数以内に答えを出せませんでした",
    "no_tool_call": "モデルが道具を使いませんでした",
    "api_error": "モデルの呼び出しに失敗しました",
    "cap_repeat": "モデルが同じ操作を繰り返したため止めました",
    "cap_status": "モデルが状態の確認を繰り返したため止めました",
    "done_without_close": "モデルが答えを出さずに終えました",
    "no_close": "モデルが答えを出さずに終えました",
    "run_not_verified": "台帳が検証できませんでした",
    "plugin_refused": "プラグインのゲートが答えを通しませんでした",
    "not_from_user": "利用者の発言の引用でない書き込みを拒否しました",
}


def safe_error(text: object) -> str:
    """An error shown to a person: the exception class (and an HTTP status when the SDK message starts with `Error code: NNN`), a fixed message, NOTHING else.  The text of an API error can carry
    raw model output (an OpenAI-compatible server echoes the tool call it could not parse), which would be model text reaching the reader outside emit / abstain."""
    t = str(text or "")
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]{0,63}):\s*(?:Error code:\s*(\d{3}))?", t)
    kind = m.group(1) if m else "Error"
    status = " (HTTP %s)" % m.group(2) if m and m.group(2) else ""
    return "%s%s: details withheld (an API error can carry raw model output)" % (kind, status)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


_SENT_END = re.compile(r"(?<=[。！？!?])")


def user_sentences(text: str) -> List[str]:
    """The sentences of a user message: split ONLY after 。！？ (and !?), the last one ends with the message; NFC; surrounding white space removed.  A line break is NOT a boundary: it stays inside
    the sentence (「山本\nではありません。」 is one sentence, so no clean 「…は山本」 can equal it).  A bracket or a quote does not end a sentence either."""
    out = []
    for part in _SENT_END.split(nfc(text)):
        p = part.strip()
        if p:
            out.append(p)
    return out


def equals_whole_sentence(write: str, text: str) -> bool:
    """A memory write must EQUAL one whole sentence of the user message (NFC; a trailing 。 is optional on either side): never a piece of one.  A piece can invert what was said
    (「山本ではない」 -> 「山本」), turn a question or a condition into an assertion, or cut a quotation."""
    w = nfc(write).strip()
    wc = w[:-1] if w.endswith("。") else w
    return bool(wc) and any((s[:-1] if s.endswith("。") else s) == wc for s in user_sentences(text))


def sentence_positions(sentence: str) -> Optional[set]:
    """The positions (shape tank, centre, arms) the memory reads in a sentence; an empty set when it reads nothing but F0 clauses (it cannot read it), None if the grammar layer fails."""
    try:
        from verantyx.loom import memshape as ms
        ex = ms.exchange(sentence, ms.SHAPES_V4)
        return {(c.shape, c.centre, tuple((a.particle, a.seat.text) for a in c.arms)) for c in ex.clauses if c.shape != "F0"}
    except Exception:
        return None


def blocked_positions(message: str) -> set:
    """The positions one user message leaves AMBIGUOUS (`ambiguous_in_turn`): a position the memory reads in two or more sentences of the message (a self-correction written out in full), and the
    position(s) of a readable sentence that is followed by a sentence the memory cannot read (a subjectless correction like 「いや、鈴木です」).  No write for such a position is accepted from that
    message, so nothing stale is stored."""
    sents = user_sentences(message)
    per = [sentence_positions(s) for s in sents]
    out: set = set()
    for i, a in enumerate(per):
        if a is None:
            continue
        for b in per[i + 1:]:
            if b:
                out |= a & b
        if i + 1 < len(per) and per[i + 1] is not None and not per[i + 1] and a:
            out |= a
    return out


_OWN_MARK = re.compile(r"\[redacted:[0-9a-f]{8}\]")
_LABEL = re.compile(r"(?i)(?:api[_-]?key|token|secret|password)[\"']?\s*[=:]\s*[\"']?")


def reading_sentences(text: str) -> List[str]:
    """The sentences of a recorded user turn AS THE READER SHOULD SEE THEM: a redaction marker (and the `key=` label in front of it) is not part of what the user said about a place, so it is
    taken out before reading (「広報の担当は鈴木です api_key=[redacted:…]」 is read as 「広報の担当は鈴木です」)."""
    out = []
    for s0 in user_sentences(text):
        c = _LABEL.sub("", _OWN_MARK.sub("", s0)).strip() if "[redacted:" in s0 else s0
        if c:
            out.append(c)
    return out


_VALUE_STOP = re.compile(r"[\u3000-\u9fff\uf900-\ufaff\uff00-\uffef。！？!?]")


def redact_user_text(text: str) -> Tuple[str, List[str], bool]:
    """A user message as it may be recorded: every secret-shaped span (the ledger's own detector: sk-ant-, sk-, AKIA…, ghp_…, xox…, private keys, Bearer, key=value, ...) is replaced by
    「[redacted:<sha256-8 of the span>]」.  A `key=value` secret's value ends at white space, a CJK character or 。！？!? (so 「password=hunter2。広報の担当は…」 loses only `hunter2`).  -> (the text,
    the sha256-8 list, LOSSY).  LOSSY is true when the redaction removed or changed a sentence boundary (a terminator disappeared or appeared), erased a whole sentence, or (the fail-safe) had to
    drop the whole message: the reading of such a turn cannot be trusted, and the memory then answers nothing about places it could have spoken of (`redacted_turn_unreadable`)."""
    from verantyx.ledger_events import _spans, _variant_stage
    t = nfc(text)
    shas: List[str] = []
    for s0, e0, name in reversed(_spans(t)):
        if name == "kv_secret":
            m = _VALUE_STOP.search(t, s0, e0)
            if m is not None:
                e0 = m.start()
            if e0 - s0 < 1:
                continue
        h = hashlib.sha256(t[s0:e0].encode("utf-8")).hexdigest()[:8]
        shas.append(h)
        t = t[:s0] + "[redacted:%s]" % h + t[e0:]
    rest = _OWN_MARK.sub("", t)
    leftover = _variant_stage(rest)[1] > 0
    for s0, e0, name in _spans(rest):                      # what the detector still finds once the harness's own markers are gone (a key=value whose value was only the rest of the sentence is no secret)
        if name == "kv_secret":
            m = _VALUE_STOP.search(rest, s0, e0)
            e0 = m.start() if m is not None else e0
            if e0 - s0 < 8:
                continue
        leftover = True
    if leftover:                                           # a secret-shaped residue the markers do not explain: the whole message goes
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        return "[redacted:%s]" % h, [h], True
    term = lambda x: [c for c in x if c in "。！？!?"]
    lossy = bool(shas) and (term(nfc(text)) != term(t) or any(not re.sub(r"[\s。！？!?、，,.]+", "", _LABEL.sub("", _OWN_MARK.sub("", x))) for x in user_sentences(t) if "[redacted:" in x))
    return t, list(reversed(shas)), lossy


def clause_values(sentence: str) -> Dict[Tuple, str]:
    """{position: value text} of the F1 / F2 clauses the memory reads in a sentence (a change clause's value is its new value)."""
    try:
        from verantyx.loom import memshape as ms
        return {(c.shape, c.centre, tuple((a.particle, a.seat.text) for a in c.arms)): c.value.text for c in ms.exchange(sentence, ms.SHAPES_V4).clauses if c.shape in ("F1", "F2") and c.value is not None}
    except Exception:
        return {}


def recorded_user_turns(store: str) -> List[Tuple[str, str]]:
    """[(turn id, text)] of every user turn recorded in the committed sessions of a store, in order."""
    out: List[Tuple[str, str]] = []
    sd = os.path.join(store, "sessions")
    for n in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        try:
            for ln in open(os.path.join(sd, n, "ops.jsonl"), encoding="utf-8"):
                if '"user_turn"' in ln:
                    r = json.loads(ln)
                    if r.get("op") == "user_turn":
                        out.append((r["args"]["turn"], r["args"]["text"]))
        except (OSError, ValueError):
            continue
    return out


def lossy_block(store: str, sids: Sequence[int]) -> Optional[str]:
    """The first recorded turn marked `redaction_lossy` that is NOT earlier than the turn an answer's source sentence was said in (an unsourced sentence has no turn: any lossy turn blocks): the
    turn that could have said something else about this place and cannot be read.  -> its turn id, else None."""
    lossy: List[str] = []
    sd = os.path.join(store, "sessions")
    for n in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        try:
            for ln in open(os.path.join(sd, n, "ops.jsonl"), encoding="utf-8"):
                if '"redaction_lossy"' in ln:
                    r = json.loads(ln)
                    if r.get("op") == "user_turn" and r["args"].get("redaction_lossy"):
                        lossy.append(r["args"]["turn"])
        except (OSError, ValueError):
            continue
    if not lossy:
        return None
    try:
        rows = mem.MemStore(store).rows()
    except Exception:
        return lossy[0]
    for t in lossy:
        kt = turn_key(t)
        for i in sids:
            ka = turn_key(rows[i].get("turn")) if isinstance(i, int) and 0 <= i < len(rows) else None
            if ka is None or kt is None or ka <= kt:
                return t
    return None


def unrecorded_statement(store: str, sids: Sequence[int], max_session: Optional[int] = None) -> Optional[str]:
    """The recorded user turns are the source of truth; the model's writes only SELECT from them.  Read EVERY sentence of EVERY recorded user turn with the memory's reader: if one carries, at the
    position of the answer, a value different from the answer's and is not a stored write the memory already accounts for, the model left out (or the memory refused) something the user said about
    this place.  -> the turn id of the first such sentence, else None.  (Scope rules are not applied: the check is conservative.)"""
    try:
        rows = mem.MemStore(store).rows()
    except Exception:
        return None
    stored: Dict[str, set] = {}
    for r in rows:
        if r.get("turn"):
            stored.setdefault(r["turn"], set()).add(nfc(r["sent"]).strip().rstrip("。"))
    ans: Dict[Tuple, str] = {}
    for i in sids:
        if isinstance(i, int) and 0 <= i < len(rows):
            ans.update(clause_values(rows[i]["sent"]))
    if not ans:
        return None
    for turn, text in recorded_user_turns(store):
        k = turn_key(turn)
        if max_session is not None and k is not None and k[0] > max_session:
            continue
        for sent in reading_sentences(text):
            if nfc(sent).strip().rstrip("。") in stored.get(turn, set()):
                continue
            for pos, val in clause_values(sent).items():
                if pos in ans and nfc(val).strip() != nfc(ans[pos]).strip():
                    return turn
    return None


def turn_key(turn: Any) -> Optional[Tuple[int, int]]:
    m = re.match(r"^(\d+)-(\d+)$", turn) if isinstance(turn, str) else None
    return (int(m.group(1)), int(m.group(2))) if m else None


def supersede_targets(run: Any, a: dict) -> Optional[List[int]]:
    """The sentences a `supersede` call WOULD retire (the live sentences of the old answer group), computed exactly as the memory does; None when the call is malformed (the memory refuses it itself)."""
    try:
        from verantyx.loom import memnotes as mn
        from verantyx.loom import memrecall as mr
        new_sid = a["new_sid"]
        if run.evidence_version is None or not isinstance(new_sid, int) or isinstance(new_sid, bool) or not 0 <= new_sid < len(run.rows) or ("old_sid" in a) == ("old_answer" in a):
            return None
        question = a["question"] if isinstance(a.get("question"), str) else (run.clause_of(new_sid) or {}).get("question")
        if not question:
            return None
        j = mr.analyse(run.corpus_cur, question, run.evidence_version, True, bool(getattr(run.hook, "subject_guard", False)))
        comps, sets = j["comps"], j["sets"]
        of = {s: k for k, comp in enumerate(comps) for s in comp}
        if "old_sid" in a:
            if a["old_sid"] not in of:
                return None
            old_k = of[a["old_sid"]]
        else:
            norm = mn.norm_answer(a["old_answer"])
            hits = [k for k, comp in enumerate(comps) if any(norm in sets[s] for s in comp)]
            if not norm or not hits:
                return None
            old_k = hits[0]
        return [s for s in comps[old_k] if s not in run.superseded]
    except Exception:                                                   # anything odd: the memory's own checks decide
        return None


def supersede_verdict(run: Any, args: dict, store: str) -> Optional[str]:
    """THE rule for retirement: a sentence an AGENT wrote (a session with no user turns) never takes part in ordering or retirement.  A supersede runs only if its new side is user-sourced and every
    retired sentence is user-sourced and from a strictly earlier user turn.  -> None (allowed / not decidable here: the memory's own checks decide), `unsourced_order` or `supersede_order`."""
    try:
        rows = run.rows
        sourced = sourced_sessions(store)

        def src(s: Any) -> bool:
            return isinstance(s, int) and not isinstance(s, bool) and 0 <= s < len(rows) and _session_of_source(rows[s].get("source")) in sourced

        def later(a: int, b: int) -> bool:
            ka, kb = turn_key(rows[a].get("turn")), turn_key(rows[b].get("turn"))
            return (ka > kb) if ka is not None and kb is not None else False
        new = args.get("new_sid")
        if not isinstance(new, int) or isinstance(new, bool) or not 0 <= new < len(rows):
            return None
        if not src(new):
            return "unsourced_order"
        olds = list(supersede_targets(run, args) or [])
        if isinstance(args.get("old_sid"), int) and not isinstance(args.get("old_sid"), bool) and args["old_sid"] not in olds:
            olds.append(args["old_sid"])
        if any(0 <= o < len(rows) and not src(o) for o in olds):
            return "unsourced_order"
        if any(0 <= o < len(rows) and not later(new, o) for o in olds):
            return "supersede_order"
    except Exception:
        return None
    return None


def has_change_clause(text: str) -> bool:
    """The memory reads a CHANGE in this sentence (「担当は鈴木に変更」): a change clause replaces every earlier value at its position."""
    try:
        from verantyx.loom import memshape as ms
        return any(c.change is not None for c in ms.exchange(text, ms.SHAPES_V4).clauses)
    except Exception:
        return False


class UnrecordedGate:
    """At `emit` of a memory answer run: the quote is read back; if a recorded user sentence at its position says something else and is not a stored write (`unrecorded_user_statement`), a
    `statement_refused` row (with the turn) is written and the run closes with an `abstain`: nothing is emitted."""

    def __init__(self, inner: Any, store: str) -> None:
        self.inner, self.store = inner, store

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)

    def call(self, tool: Any, args: Any = None) -> dict:
        if tool == "emit":
            ra = dict(args) if isinstance(args, dict) else {}
            r = self.inner.call("read", dict(ra))
            if isinstance(r, dict) and r.get("ok") is True and not r.get("refusals"):
                sids = [e["sid"] for e in (r.get("evidence") or []) if isinstance(e, dict) and isinstance(e.get("sid"), int)]
                turn, why = lossy_block(self.store, sids), "redacted_turn_unreadable"
                if turn is None:
                    turn, why = unrecorded_statement(self.store, sids), "unrecorded_user_statement"
                if turn is not None:
                    self.inner.harness(ra.get("run_id"), "statement_refused", {"turn": turn, "reason": why})
                    return self.inner.call("abstain", dict(ra, type="unknown"))
        return self.inner.call(tool, args)


def statement_refusal_of(run_dir: str) -> Optional[Tuple[str, str]]:
    try:
        for ln in open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8"):
            if '"statement_refused"' in ln:
                r = json.loads(ln)
                if r.get("op") == "statement_refused":
                    return r["args"]["turn"], r["args"]["reason"]
    except (OSError, ValueError):
        pass
    return None


class AnswerMarkGuard:
    """The MCP question phase: a successful `emit` result also says whether its source sentence(s) are the USER's words (`sourced`) and, if not, carries the same mark as the CLI / JSON / UI."""

    def __init__(self, inner: Any, store: str) -> None:
        self.inner, self.store = inner, store

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)

    def call(self, tool: Any, args: Any = None) -> dict:
        out = self.inner.call(tool, args)
        if tool == "recall" and isinstance(out, dict) and isinstance(out.get("answers"), list):
            try:
                sourced = sourced_sessions(self.store)
                rows = mem.MemStore(self.store).rows()
                groups = []
                for g in out["answers"]:
                    sids = [o["sid"] for o in g.get("occurrences", []) if isinstance(o.get("sid"), int)]
                    ok = bool(sids) and all(0 <= i < len(rows) and _session_of_source(rows[i].get("source")) in sourced for i in sids)
                    groups.append(dict(g, sourced=ok, **({} if ok else {"mark": UNSOURCED_MARK})))
                out = dict(out, answers=groups)
            except Exception:
                pass
        if tool == "emit" and isinstance(out, dict) and out.get("ok") is True:
            try:
                snap = self.inner.snapshot if hasattr(self.inner, "snapshot") else None
                rows = mem.MemStore(self.store).rows()
                sourced = sourced_sessions(self.store)
                sids = [e["sid"] for e in (out.get("evidence") or []) if isinstance(e.get("sid"), int)]
                ok = bool(sids) and all(0 <= i < len(rows) and _session_of_source(rows[i].get("source")) in sourced for i in sids)
            except Exception:
                ok = False
            out = dict(out, sourced=ok)
            if not ok:
                out["mark"] = UNSOURCED_MARK
        return out


class UnsourcedGuard:
    """The door of an MCP memory session (the agent's own claims, no user turns).  An unsourced write NEVER takes part in ordering or retirement: its rows carry no turn (any `turn` argument is
    stripped, `report` does not set one); a `supersede` is judged by `supersede_verdict` (an agent's sentence is never the new side, never a retired one); a write that reads as a CHANGE
    (「…に変更」: it would replace the user's value) is refused.  An agent may add its record, which can CONTEST a user's value (the position becomes ambiguous and the memory abstains); it can never
    answer over it.  Each refusal is a ledger row."""
    unsourced = True

    def __init__(self, inner: Any, store: str) -> None:
        self.inner, self.store = inner, store

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)

    def call(self, tool: Any, args: Any = None) -> dict:
        raw = self.inner
        if isinstance(args, dict) and "turn" in args:
            args = {k: v for k, v in args.items() if k != "turn"}
        if tool == "supersede" and isinstance(args, dict):
            why = supersede_verdict(raw.session.run, args, self.store)
            if why:
                raw.harness(None, "supersede_refused", {"turn": "1-1", "new_sid": args.get("new_sid") if isinstance(args.get("new_sid"), int) and not isinstance(args.get("new_sid"), bool) else 0, "reason": why})
                return {"ok": False, "refusal": why, "detail": {"reason": "an agent's record takes no part in ordering or retirement"}}
        if tool in ("write", "keep_unshaped") and isinstance(args, dict) and isinstance(args.get("text"), str) and has_change_clause(args["text"]):
            t = args["text"]
            raw.harness(None, "write_refused", {"turn": "1-1", "sha256": hashlib.sha256(t.encode("utf-8")).hexdigest(), "chars": len(t), "reason": "unsourced_order"})
            return {"ok": False, "refusal": "unsourced_order", "detail": {"reason": "an agent's record may not state a change: it would replace what the user said"}}
        return self.inner.call(tool, args)


class UserSourceDoor:
    """The memory's source rule.  The USER's messages are rows of the session's hash chain (`user_turn`, with their text), recorded when each is delivered; a `write` / `keep_unshaped` whose text
    does not EQUAL one whole sentence (see `equals_whole_sentence`) of the message of the turn being delivered is NOT executed (a write's time is therefore the user's turn it was said in: an
    earlier message cannot be re-quoted to look newer): a `write_refused` row (sha256, length) is recorded and the model gets `not_from_user`.  So no sentence the memory
    holds, and no value an answer can quote, is anything but the user's own words.  Wraps the door the driver calls; everything else is the inner door's."""

    def __init__(self, inner: Any, raw: Any, messages: Dict[str, str], store: str = "", redacted: Optional[Dict[str, List[str]]] = None, lossy: Optional[set] = None) -> None:
        self.inner, self.raw, self.messages, self.store, self.redacted, self.lossy = inner, raw, messages, store, redacted or {}, lossy or set()
        self.turn: Optional[str] = None
        self.blocked: set = set()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)

    def set_turn(self, turn: str) -> None:
        self.turn = turn
        if turn in self.messages:
            self.raw.harness(None, "user_turn", dict({"turn": turn, "text": self.messages[turn]}, **({"redacted": self.redacted[turn]} if self.redacted.get(turn) else {}), **({"redaction_lossy": True} if turn in self.lossy else {})))
            self.blocked = blocked_positions(self.messages[turn])
        self.inner.set_turn(turn)

    def _supersede_targets(self, a: dict) -> Optional[List[int]]:
        return supersede_targets(self.raw.session.run, a)

    def _later(self, new_sid: int, old_sid: int) -> bool:
        """`new_sid` was said in a strictly LATER user turn than `old_sid` (by the turn each sentence was written in; the slide order only when a turn is unknown)."""
        try:
            rows = self.raw.session.run.rows
            a, b = turn_key(rows[new_sid].get("turn")), turn_key(rows[old_sid].get("turn"))
        except Exception:
            return False
        return (a > b) if a is not None and b is not None else new_sid > old_sid

    def call(self, tool: Any, args: Any = None) -> dict:
        if tool == "supersede" and isinstance(args, dict):
            why = supersede_verdict(self.raw.session.run, args, self.store)
            if why:
                nid = args.get("new_sid")
                self.raw.harness(None, "supersede_refused", {"turn": self.turn or "1-1", "new_sid": nid if isinstance(nid, int) and not isinstance(nid, bool) else 0, "reason": why})
                return {"ok": False, "refusal": why, "detail": {"reason": "a later user statement may replace an earlier one, never the other way round, and an agent's record takes no part"}}
        if tool in ("write", "keep_unshaped") and isinstance(args, dict) and isinstance(args.get("text"), str) and self.blocked and equals_whole_sentence(args["text"], self.messages.get(self.turn or "", "")):
            if (sentence_positions(args["text"]) or set()) & self.blocked:
                text = args["text"]
                self.raw.harness(None, "write_refused", {"turn": self.turn or "1-1", "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "chars": len(text), "reason": "ambiguous_in_turn"})
                return {"ok": False, "refusal": "ambiguous_in_turn", "detail": {"reason": "this message says two things about the same place, or follows a fact with a sentence the memory cannot read (a correction?): nothing from it is kept for that place; ask the user to say it once, in one sentence"}}
        if tool in ("write", "keep_unshaped"):
            text = args.get("text") if isinstance(args, dict) else None
            if isinstance(text, str) and not equals_whole_sentence(text, self.messages.get(self.turn or "", "")):
                self.raw.harness(None, "write_refused", {"turn": self.turn or "1-1", "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "chars": len(text), "reason": "not_from_user"})
                return {"ok": False, "refusal": "not_from_user", "detail": {"reason": "a memory sentence must equal one whole sentence of the user's message of this turn; write it exactly as it was said, not a piece of it"}}
        if tool in ("write", "keep_unshaped") and isinstance(args, dict) and "turn" in args:
            args = dict(args, turn=self.turn)                                    # the model never names the turn a sentence was said in
        return self.inner.call(tool, args)


def _session_of_source(src: Any) -> Optional[int]:
    m = re.search(r"/(\d+)#\d+$", src) if isinstance(src, str) else None
    return int(m.group(1)) if m else None


def sourced_sessions(store: str) -> set:
    """The numbers of the committed sessions of a store that recorded USER turns (their sentences are the user's words); the others are an agent's own claims (vera mcp)."""
    out: set = set()
    sd = os.path.join(store, "sessions")
    for n in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        f = os.path.join(sd, n, "ops.jsonl")
        try:
            for ln in open(f, encoding="utf-8"):
                if '"user_turn"' in ln:
                    r = json.loads(ln)
                    t = turn_key(r["args"].get("turn")) if r.get("op") == "user_turn" else None
                    if t:
                        out.add(t[0])
        except (OSError, ValueError):
            continue
    return out


def check_write_sources(store: str) -> List[Dict[str, Any]]:
    """The audit of a memory store.  In every session that recorded user turns: every ok `write` / `keep_unshaped` EQUALS one whole sentence of the user turn it was written in (the row's
    `turn`, recorded earlier in that session; a write before the first user turn fails); every executed `supersede` retires only sentences written in strictly earlier turns than its `new_sid`.
    -> the problems ([] = fine).  A session with no `user_turn` row (an MCP client's: its writes are the agent's own claims) is reported as `unsourced_session`, not as a failure; its supersedes
    are still audited."""
    out: List[Dict[str, Any]] = []
    try:
        mrows = mem.MemStore(store).rows()
    except Exception:
        mrows = []
    turn_of = {i: r.get("turn") for i, r in enumerate(mrows)}
    sess_of = {i: _session_of_source(r.get("source")) for i, r in enumerate(mrows)}
    sourced = sourced_sessions(store)
    sd = os.path.join(store, "sessions")
    for n in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        f = os.path.join(sd, n, "ops.jsonl")
        if not os.path.isfile(f):
            continue
        with open(f, encoding="utf-8") as fh:
            rows = [json.loads(ln) for ln in fh if ln.strip()]
        has = any(r.get("actor") == "harness" and r.get("op") == "user_turn" for r in rows)
        users: Dict[str, str] = {}
        bad: List[int] = []
        bad_sup: List[int] = []
        bad_unsrc: List[int] = []
        bad_amb: List[int] = []
        blocked_by_turn: Dict[str, set] = {}
        for r in rows:
            if r.get("actor") == "harness" and r.get("op") == "user_turn":
                users[r["args"]["turn"]] = r["args"]["text"]
                blocked_by_turn[r["args"]["turn"]] = blocked_positions(r["args"]["text"])
            elif r.get("actor") == "model" and r.get("op") == "supersede" and (r.get("result") or {}).get("ok") is True:
                new = (r.get("result") or {}).get("new_sid")
                olds = [x.get("sid") for x in r["result"].get("superseded", [])]
                issid = lambda v: isinstance(v, int) and not isinstance(v, bool)
                if not issid(new) or any(not issid(o) for o in olds):
                    bad_sup.append(r.get("i"))
                elif sess_of.get(new) not in sourced or any(sess_of.get(o) not in sourced for o in olds):
                    bad_unsrc.append(r.get("i"))                                    # an agent's sentence took part in ordering or retirement
                else:
                    a = turn_key(turn_of.get(new))
                    if any(not (a is not None and turn_key(turn_of.get(o)) is not None and a > turn_key(turn_of.get(o))) for o in olds):
                        bad_sup.append(r.get("i"))
            elif not has and r.get("actor") == "model" and r.get("op") in ("write", "keep_unshaped") and (r.get("result") or {}).get("ok") is True and has_change_clause((r.get("args") or {}).get("text") or ""):
                bad_unsrc.append(r.get("i"))                                        # an agent's write that states a change
            elif has and r.get("actor") == "model" and r.get("op") in ("write", "keep_unshaped") and (r.get("result") or {}).get("ok") is True:
                t = (r.get("args") or {}).get("text")
                tn = (r.get("result") or {}).get("turn") or (r.get("args") or {}).get("turn")
                if not isinstance(t, str) or tn not in users or not equals_whole_sentence(t, users[tn]):
                    bad.append(r.get("i"))
                elif (sentence_positions(t) or set()) & blocked_by_turn.get(tn, set()):
                    bad_amb.append(r.get("i"))
        if bad_sup:
            out.append({"session": n, "type": "supersede_order", "rows": bad_sup[:20]})
        if bad_unsrc:
            out.append({"session": n, "type": "unsourced_order", "rows": bad_unsrc[:20]})
        if bad_amb:
            out.append({"session": n, "type": "ambiguous_write", "rows": bad_amb[:20]})
        if bad:
            out.append({"session": n, "type": "write_not_from_user", "rows": bad[:20]})
        elif not has:
            out.append({"session": n, "type": "unsourced_session"})
    return out


class HarnessError(Exception):
    """A typed refusal of the harness (`code` is a stable token)."""

    def __init__(self, msg: str, code: str = "harness_error") -> None:
        super().__init__("%s: %s" % (code, msg))
        self.code = code


# ------------------------------------------------------------------------------------------------------------
# plugins: which ran (recorded in the ledger), the gate filters (refuse only), the note kinds (read only)
# ------------------------------------------------------------------------------------------------------------
def _plugin(kind: str, name: str) -> "pl.Plugin":
    try:
        return pl.registry().require(kind, name)
    except pl.PluginError as e:
        raise HarnessError(str(e), e.code) from e


def resolve_plugins(backend: Any, *, evidence: Optional[str] = None, filters: Sequence[str] = (), profile: Optional[str] = None, note_kinds: Sequence[str] = ()) -> Dict[str, Any]:
    """The plugins one run uses: {"used": [Plugin], "filters": [Plugin], "profile": MemoryProfile | None, "notes": [Plugin], "manifest": str}.  The backend and the built-in gate / profile are
    recorded as plugins too (registered the same way); a backend object that no plugin of that name stands behind (an embedder's own) is simply not listed."""
    reg = pl.registry()
    used: List[pl.Plugin] = []
    b = reg.get("backend", getattr(backend, "name", ""))
    if b is not None:
        used.append(b)
    if evidence and evidence != "off":
        used.append(_plugin("gate", "evidence.%s" % evidence))
    flt = [_plugin("gate", n) for n in filters]
    for f in flt:
        if isinstance(f.obj, pl.LoomGate):
            raise HarnessError("gate %s is one of the loom's evidence versions: select it with --evidence; --gate-filter takes a filter plugin" % f.name, "bad_plugin")
    used += flt
    prof = None
    if profile:
        pp = _plugin("memory_profile", profile)
        used.append(pp)
        prof = pp.obj
    notes = [_plugin("note_kind", n) for n in note_kinds]
    used += notes
    return {"used": used, "filters": flt, "profile": prof, "notes": notes, "manifest": pl.manifest(used)}


class FilterGate:
    """Gate-filter plugins at the moment of `emit`, so that the LEDGER says what happened.  When the model calls `emit`, the quote is first read back (`read`: the text and the evidence the loom's gate
    would pass); if a filter refuses it, a `plugin_refused` harness row (kind, name, version, code) is written and the run is closed with `abstain` instead: the ledger holds no emitted output,
    and `vera loom output` has nothing to print.  A filter can only turn an emit into an abstain.  Everything else is the inner server's / door's."""

    def __init__(self, inner: Any, filters: Sequence["pl.Plugin"], question: str, sentences: Callable[[int], Optional[Dict[str, Any]]]) -> None:
        self.inner, self.filters, self.question, self.sentences = inner, list(filters), question, sentences

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)

    def call(self, tool: Any, args: Any = None) -> dict:
        if tool == "emit" and self.filters:
            ra = dict(args) if isinstance(args, dict) else {}
            r = self.inner.call("read", dict(ra))
            if isinstance(r, dict) and r.get("ok") is True and not r.get("refusals") and isinstance(r.get("text"), str):
                srcs = [s for s in (self.sentences(e["sid"]) for e in (r.get("evidence") or []) if isinstance(e, dict) and isinstance(e.get("sid"), int)) if s]
                hit = pl.apply_gate_filters(self.question, r["text"], srcs, self.filters)
                if hit is not None:
                    p, code = hit
                    self.inner.harness(ra.get("run_id"), "plugin_refused", {"kind": p.kind, "name": p.name, "version": p.version, "code": code})
                    return self.inner.call("abstain", dict(ra, type="unknown"))
        return self.inner.call(tool, args)


def plugin_refusal_of(run_dir: str) -> Optional[Dict[str, str]]:
    """The `plugin_refused` row of a run's ledger, if any."""
    try:
        for ln in open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8"):
            if '"plugin_refused"' in ln:
                r = json.loads(ln)
                if r.get("op") == "plugin_refused":
                    return dict(r["args"])
    except (OSError, ValueError):
        pass
    return None


def apply_filters(ans: "Answer", filters: Sequence["pl.Plugin"]) -> "Answer":
    """Run the gate filters on an answered Answer; the first that refuses turns it into 「分かりません」 (reason plugin_refused).  A filter can only refuse."""
    if ans.status != "answered" or not filters:
        return ans
    hit = pl.apply_gate_filters(ans.question, ans.text or "", ans.sources, filters)
    if hit is None:
        return ans
    p, code = hit
    ans.status, ans.reason, ans.text, ans.sources, ans.output_sha = "refused", "plugin_refused", None, [], None
    ans.detail["plugin"] = {"kind": p.kind, "name": p.name, "version": p.version, "code": code}
    return ans


def annotate_memory(store: str, notes: Sequence["pl.Plugin"]) -> List[Dict[str, Any]]:
    """The notes of the note-kind plugins over the committed sentences of a memory (read only; a failing plugin yields one `error` note, never an exception)."""
    out: List[Dict[str, Any]] = []
    if not notes:
        return out
    rows = _store_rows(store)
    for p in notes:
        fn = getattr(p.obj, "annotate", None)
        if fn is None:
            continue
        try:
            got = list(fn(rows))
        except Exception as e:
            out.append({"kind": p.name, "version": p.version, "error": type(e).__name__})
            continue
        for n in got:
            if isinstance(n, dict) and isinstance(n.get("sid"), int) and isinstance(n.get("text"), str):
                out.append({"kind": p.name, "version": p.version, "sid": n["sid"], "text": n["text"][:300]})
    return out


def _store_rows(store: str) -> List[dict]:
    try:
        return mem.MemStore(store).rows()
    except Exception:
        return []


# ------------------------------------------------------------------------------------------------------------
# the tool schemas of the loom (the SAME ones the MCP door serves)
# ------------------------------------------------------------------------------------------------------------
def loom_tool_objects() -> List[Any]:
    """Objects with `name`, `description`, `inputSchema` for driver.api_tools: the schemas the FastMCP door of the loom serves.  Read from the bundled snapshot
    (`loom_tools.json`; a test compares it with the live door), so `vera ask` needs no MCP SDK."""
    with open(os.path.join(HERE, "loom_tools.json"), encoding="utf-8") as f:
        return [SimpleNamespace(name=t["name"], description=t["description"], inputSchema=t["inputSchema"]) for t in json.load(f)]


def live_loom_tool_objects(tmp_dir: str) -> List[Any]:
    """The tools of the live FastMCP door (needs the `mcp` extra); used by the test that pins the snapshot."""
    from verantyx.loom import mcp as lm
    tasks = os.path.join(tmp_dir, "tasks.jsonl")
    corpus = os.path.join(tmp_dir, "corpus.jsonl")
    with open(corpus, "w", encoding="utf-8") as f:
        f.write(json.dumps({"sha": "0" * 64, "title": "t", "sent": "テスト。", "source": "t#0"}, ensure_ascii=False) + "\n")
    with open(tasks, "w", encoding="utf-8") as f:
        f.write(json.dumps({"task_id": "x/1", "text": "q", "lang": "prose", "mode": "record_only", "corpus": corpus}) + "\n")
    m = lm.build(tasks, os.path.join(tmp_dir, "runs"))
    if m is None:
        raise HarnessError("the MCP SDK is not installed", "mcp_missing")
    return list(asyncio.run(m.list_tools()))


# ------------------------------------------------------------------------------------------------------------
# results
# ------------------------------------------------------------------------------------------------------------
@dataclass
class Answer:
    """What the user is shown.  `status`: answered | refused.  An answer has `text` (the quote) and `sources` (the sentences it was quoted from);
    a refusal has `reason` (a typed token) and `detail`."""
    status: str
    run_dir: str
    question: str
    text: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    output_sha: Optional[str] = None
    reason: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    backend: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, int] = field(default_factory=dict)
    free_text_dropped: int = 0

    def to_obj(self) -> dict:
        return {k: getattr(self, k) for k in ("status", "run_dir", "question", "text", "sources", "output_sha", "reason", "detail", "verified", "backend", "usage", "free_text_dropped")}

    def render(self) -> str:
        """The text printed for a person: the quote and its source sentence, or 「分かりません」 and the typed reason; then the run directory."""
        lines: List[str] = []
        if self.status == "answered":
            lines.append("答え: 「%s」" % self.text)
            for s in self.sources:
                lines.append("根拠: %s（%s）" % (s["text"], s["source"]))
                if s.get("sourced") is False:
                    lines.append(UNSOURCED_MARK)
        else:
            ja = REASON_JA.get(self.reason or "", "")
            lines.append("%s（理由: %s%s）" % (REFUSAL_TEXT, self.reason, "、%s" % ja if ja else ""))
            for k in ("last_refusal",):
                if self.detail.get(k):
                    lines.append("最後の拒否: %s" % self.detail[k])
            for c in self.detail.get("contested") or []:
                lines.append("  食い違い: 「%s」%s%s" % (c["value"], "" if c.get("sourced") else "  " + UNSOURCED_MARK,
                                                    "  （置き換え済み: 回 %s の発言が記憶に入っていません。現在の値ではありません）" % c["replaced_in"] if c.get("replaced_in") else ""))
            if self.detail.get("turn"):
                lines.append("  利用者の発言（回 %s）が記憶に入っていません" % self.detail["turn"])
            if self.detail.get("plugin"):
                lines.append("プラグイン: %s/%s %s（%s）" % (self.detail["plugin"]["kind"], self.detail["plugin"]["name"], self.detail["plugin"]["version"], self.detail["plugin"]["code"]))
        lines.append("run: %s" % self.run_dir)
        return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------
# ask: a question over documents
# ------------------------------------------------------------------------------------------------------------
def new_run_id(question: str, corpus_sha: str, prefix: str = "ask") -> str:
    h = hashlib.sha256((question + "\0" + corpus_sha + "\0" + str(time.time_ns())).encode("utf-8")).hexdigest()[:6]
    return "%s-%s-%s" % (prefix, time.strftime("%Y%m%d-%H%M%S", time.gmtime()), h)


def _write_once(path: str, data: bytes) -> None:
    if os.path.exists(path):
        if open(path, "rb").read() != data:
            raise HarnessError("a file of this name holds other bytes: %s" % path, "corpus_conflict")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _ledger_rows(run_dir: str) -> List[dict]:
    lines, _ = lg.read_lines(run_dir)
    return [json.loads(ln) for ln in lines]


def _sources_of(row: dict, sents: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    out = []
    for ev in row["result"].get("evidence") or []:
        sid = ev.get("sid")
        if isinstance(sid, int) and 0 <= sid < len(sents):
            out.append({"sid": sid, "source": sents[sid]["source"], "text": sents[sid]["sent"], "clause": ev.get("clause")})
    return out


def settle(run_dir: str, question: str, sents: Sequence[Dict[str, str]], corpus_path: str) -> Answer:
    """The Answer of a finished loom run, from its VERIFIED ledger only (`ledger.emitted_output`: chain + replay must be OK)."""
    o = lg.emitted_output(run_dir, corpus_path=corpus_path)
    rows = _ledger_rows(run_dir)
    dropped = sum(1 for r in rows if r["actor"] == "harness" and r["op"] == "free_text_dropped")
    if o["status"] == "emitted":
        emit = [r for r in rows if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok") is True][0]
        return Answer("answered", run_dir, question, text=o["text"], sources=_sources_of(emit, sents), output_sha=o["output_sha"], verified=True, free_text_dropped=dropped)
    if o["status"] == "run_not_verified":
        return Answer("refused", run_dir, question, reason="run_not_verified", detail={"verify": o.get("verify"), "problems": o.get("problems")}, verified=False, free_text_dropped=dropped)
    reason, detail = "no_close", {}
    refused_by = None
    for r in rows:
        if r["actor"] == "harness" and r["op"] == "plugin_refused":
            refused_by = dict(r["args"])
        if r["actor"] == "model" and r["op"] == "abstain" and r["result"].get("ok") is True:
            reason = r["result"].get("type") or "unknown"
        elif r["actor"] == "harness" and r["op"] == "abandoned":
            reason = r["args"].get("reason", "no_close")
    if refused_by is not None:
        reason, detail["plugin"] = "plugin_refused", refused_by
    refusals = [r for r in rows if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok") is False]
    if refusals:
        res = refusals[-1]["result"]
        codes = []
        for rf in (res.get("detail") or {}).get("refusals", []):
            for w in rf.get("weaves", []) or []:
                codes += w.get("codes", [])
        detail["last_refusal"] = "/".join([res.get("refusal", "")] + sorted(set(codes)))
        detail["emit_refusals"] = len(refusals)
    return Answer("refused", run_dir, question, reason=reason, detail=detail, verified=True, free_text_dropped=dropped)


def ask(question: str, docs: str, backend: Backend, runs_dir: str = DEFAULT_RUNS_DIR, *, evidence: str = EVIDENCE_DEFAULT, run_id: Optional[str] = None,
        max_turns: Optional[int] = None, gate_filters: Sequence[str] = ()) -> Answer:
    """One question over documents.  A record_only loom task with the evidence gate (`evidence.v6` by default)."""
    question = (question or "").strip()
    if not question:
        raise HarnessError("the question is empty", "bad_question")
    backend.ready()
    plug = resolve_plugins(backend, evidence=evidence, filters=gate_filters)
    try:
        data, sents = dc.build_corpus(docs)
    except dc.DocsError as e:
        raise HarnessError(str(e), e.code) from e
    sha = dc.corpus_sha(data)
    runs_dir = os.path.abspath(runs_dir)
    corpus_path = os.path.join(runs_dir, "_corpora", sha[:16] + ".jsonl")
    _write_once(corpus_path, data)
    task = {"task_id": TASK_ID, "text": question, "lang": "prose", "mode": "record_only", "corpus": corpus_path}
    try:
        srv = LoomServer([task], runs_dir, evidence=evidence)
    except ValueError as e:
        raise HarnessError(str(e), "bad_task") from e
    rid = run_id or new_run_id(question, sha)
    model = backend.model
    begun = srv.begin(TASK_ID, model, rid)
    if not begun.get("ok"):
        raise HarnessError("begin refused: %s" % json.dumps(begun, ensure_ascii=False, sort_keys=True), "begin_refused")
    system = prompting.loom_prompt()
    meta = {"driver": "L2-api", "requested_model": model, "agent_definition_sha": prompting.sha(system)}
    if plug["used"]:
        meta["plugins"] = plug["manifest"]
    srv.harness(rid, "harness_meta", meta)
    choice, strict = backend.tool_choice()
    tools = drv.api_tools(loom_tool_objects(), strict, False)
    client = DriverClient(backend)
    t0 = time.monotonic_ns()
    gate = FilterGate(srv, plug["filters"], question, lambda sid: {"text": sents[sid]["sent"], "source": sents[sid]["source"]} if 0 <= sid < len(sents) else None)
    res = drv.run_episode(client, gate, rid, model, system, drv.first_message(begun), tools, tool_choice=choice, max_turns=max_turns or drv.MAX_TURNS["prose"])
    wall = time.monotonic_ns() - t0
    rm = getattr(backend, "last_response_model", None)
    if isinstance(rm, str) and rm:                                       # what the SERVER says it ran is a claim: recorded as is only when it is the requested model (or its dated form), else as a hash
        ok_rm = rm == model or rm.startswith(model + "-") or model.startswith(rm + "-")
        srv.harness(rid, "harness_meta", {"response_model": rm[:200] if ok_rm else "unverified:" + hashlib.sha256(rm.encode("utf-8")).hexdigest()[:16]})
    if srv.closed(rid) is None:
        srv.harness(rid, "abandoned", {"reason": "no_close"})
    run_dir = str(srv.run_dir(rid))
    local_corpus = os.path.join(run_dir, "corpus.jsonl")                # beside the ledger, so that `verify` / `replay` find the corpus wherever the folder goes
    _write_once(local_corpus, data)
    rep = res.to_obj()
    if rep.get("error"):
        rep["error"] = safe_error(rep["error"])
    info = {"harness": "vera-harness %s" % __version__, "kind": "ask", "backend": backend.describe(), "question_chars": len(question), "evidence": evidence,
            "corpus_sha256": sha, "sentences": len(sents), "docs": docs if not os.path.isabs(docs) else os.path.basename(docs.rstrip("/")),
            "plugins": [x.ref() for x in plug["used"]], "system_prompt_sha256": prompting.sha(system), "tools": [t["name"] for t in tools], "driver_report": rep, "wall_driver_ns": wall}
    with open(os.path.join(run_dir, "harness.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    ans = apply_filters(settle(run_dir, question, sents, local_corpus), plug["filters"])
    ans.backend = backend.describe()
    ans.usage = dict(res.usage)
    if res.error:
        ans.detail["error"] = safe_error(res.error)
    return ans


# ------------------------------------------------------------------------------------------------------------
# verify / replay of any run folder
# ------------------------------------------------------------------------------------------------------------
def kind_of(path: str) -> str:
    """'loom' (a run folder with ops.jsonl and meta.json), 'mem_answer' (an answer run of a memory store), 'mem_store' (a memory store) or 'unknown'."""
    p = os.path.abspath(path)
    if os.path.isfile(os.path.join(p, "ops.jsonl")):
        try:
            meta = json.load(open(os.path.join(p, "meta.json"), encoding="utf-8"))
        except (OSError, ValueError):
            return "unknown"
        return "mem_answer" if meta.get("mode") == "memory_answer" else "loom"
    if os.path.isdir(os.path.join(p, "sessions")) or os.path.isfile(os.path.join(p, "memory.jsonl")):
        return "mem_store"
    return "unknown"


def _corpus_of(run_dir: str) -> Optional[str]:
    c = os.path.join(run_dir, "corpus.jsonl")
    return c if os.path.isfile(c) else None


def _corpus_mismatch(run_dir: str, corpus_path: Optional[str]) -> Optional[str]:
    """A typed mismatch when the corpus beside the ledger is not the bytes the run began on (checked before anything parses it): the begin row records its sha256."""
    if corpus_path is None:
        return None
    try:
        with open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8") as f:
            want = json.loads(f.readline())["result"]["header"]["corpus_sha"]
        got = hashlib.sha256(open(corpus_path, "rb").read()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        return "corpus_unreadable"
    return None if got == want else "corpus_sha_mismatch"


def _ops_files(path: str, kind: str) -> List[str]:
    p = os.path.abspath(path)
    if kind in ("loom", "mem_answer"):
        return [os.path.join(p, "ops.jsonl")]
    out: List[str] = []
    for sub in ("sessions", "answers"):
        d = os.path.join(p, sub)
        if os.path.isdir(d):
            out += [os.path.join(d, n, "ops.jsonl") for n in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, n, "ops.jsonl"))]
    return out


def check_answer_statements(store: str) -> List[Dict[str, Any]]:
    """For every answer run of the store that EMITTED: a recorded user sentence (of the sessions its snapshot covered) at the answered position with another value, not a stored write, makes
    the answer inconsistent with what the user said (`user_statement_not_recorded`).  (Answers refused at emit time have no emit and pass.)"""
    out: List[Dict[str, Any]] = []
    ad = os.path.join(store, "answers")
    try:
        rows = mem.MemStore(store).rows()
    except Exception:
        return out
    for a in sorted(os.listdir(ad)) if os.path.isdir(ad) else []:
        f = os.path.join(ad, a, "ops.jsonl")
        sids: List[int] = []
        n_snap = 0
        try:
            for ln in open(f, encoding="utf-8"):
                r = json.loads(ln)
                if r.get("op") == "begin":
                    n_snap = int(((r.get("result") or {}).get("mem_answer") or {}).get("sentences") or 0)
                if r.get("actor") == "model" and r.get("op") == "emit" and (r.get("result") or {}).get("ok") is True:
                    sids = [e["sid"] for e in (r["result"].get("evidence") or []) if isinstance(e.get("sid"), int)]
        except (OSError, ValueError):
            continue
        if not sids:
            continue
        sessions = [_session_of_source(r.get("source")) for r in rows[:n_snap]]
        mx_s = max([x for x in sessions if x is not None], default=None)
        t = unrecorded_statement(store, sids, mx_s)
        if t is not None:
            out.append({"answer": a, "type": "user_statement_not_recorded", "turn": t})
        else:
            t = lossy_block(store, sids)
            if t is not None:
                out.append({"answer": a, "type": "redacted_turn_unreadable", "turn": t})
    return out


def plugin_mismatch(path: str, kind: Optional[str] = None) -> Optional[str]:
    """The plugins a run folder / store DECLARES (the `plugins` key of its harness_meta rows, inside the hash chain) against the registry: None if every one is installed at the declared
    version, else `unknown_plugin:<kind>/<name>`, `plugin_version:...` or `plugins_malformed`.  A run that declares nothing (older runs) has no mismatch."""
    k = kind or kind_of(path)
    for f in _ops_files(path, k):
        try:
            with open(f, encoding="utf-8") as fh:
                for ln in fh:
                    if '"harness_meta"' not in ln or '"plugins"' not in ln:
                        continue
                    row = json.loads(ln)
                    if row.get("op") != "harness_meta" or "plugins" not in row.get("args", {}):
                        continue
                    declared = pl.parse_manifest(row["args"]["plugins"])
                    if declared is None:
                        return "plugins_malformed"
                    mm = pl.mismatch(declared)
                    if mm:
                        return mm
        except (OSError, ValueError):
            continue
    return None


def verify_path(path: str) -> dict:
    """The chain, then the replay, of a run folder or a memory store: {"kind", "status", ...}.  status "OK" or a typed failure (TAMPERED, TORN_TAIL, REPLAY_DIFFERS, ...).
    A run that declares a plugin which is not installed (or at another version) is not OK: status REPLAY_INPUTS_MISMATCH, replay.status INPUTS, replay.mismatch the token."""
    v = _verify_base(path)
    if v["status"] == "OK":
        mm = plugin_mismatch(path, v["kind"])
        if mm:
            v = dict(v, status="REPLAY_INPUTS_MISMATCH", replay={"status": "INPUTS", "mismatch": mm})
    return v


def _verify_base(path: str) -> dict:
    k = kind_of(path)
    if k == "loom":
        cp = _corpus_of(path)
        chain = lg.verify_chain(path)
        mm = _corpus_mismatch(path, cp) if chain["status"] == "OK" else None
        if mm:
            return {"kind": k, "status": "REPLAY_INPUTS_MISMATCH", "rows": chain.get("n"), "head": chain.get("head"), "replay": {"status": "INPUTS", "mismatch": mm}, "problems": None}
        try:
            v = lg.verify(path, corpus_path=cp)
        except (KeyError, ValueError, OSError) as e:
            return {"kind": k, "status": "REPLAY_INPUTS_MISMATCH", "rows": chain.get("n"), "head": chain.get("head"), "replay": {"status": "INPUTS", "mismatch": "corpus_unreadable"},
                    "problems": [{"error": type(e).__name__}]}
        return {"kind": k, "status": v["status"], "rows": v.get("n"), "head": v.get("head"), "replay": v.get("replay"), "problems": v.get("problems")}
    if k == "mem_answer":
        store = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        v = ma.verify_answer(path, store)
        return {"kind": k, "status": v["status"], "rows": v.get("n"), "head": v.get("head"), "replay": v.get("replay"), "problems": v.get("problems")}
    if k == "mem_store":
        v = mem.verify_store(path, mem.FROM_HEADER)
        out = {"kind": k, "status": v["status"], "sessions": v.get("sessions"), "sentences": v.get("sentences"), "replay": v.get("replay"), "problems": v.get("problems")}
        if v["status"] == "OK":
            src = check_write_sources(path)
            bad = [x for x in src if x["type"] != "unsourced_session"]
            out["unsourced_sessions"] = [x["session"] for x in src if x["type"] == "unsourced_session"]
            if bad:
                kinds = {x["type"] for x in bad}
                out["status"], out["problems"] = (next(iter(kinds)).upper() if len(kinds) == 1 else "WRITE_NOT_FROM_USER"), bad
        adir = os.path.join(path, "answers")
        if v["status"] == "OK" and os.path.isdir(adir):
            bad = []
            n = 0
            for a in sorted(os.listdir(adir)):
                n += 1
                va = ma.verify_answer(os.path.join(adir, a), path)
                if va["status"] != "OK":
                    bad.append({"answer": a, "status": va["status"]})
            out["answers"] = n
            if bad:
                out["status"], out["problems"] = "ANSWER_NOT_VERIFIED", bad
            else:
                unrec = check_answer_statements(path)
                if unrec:
                    out["status"], out["problems"] = ("REDACTED_TURN_UNREADABLE" if all(x["type"] == "redacted_turn_unreadable" for x in unrec) else "USER_STATEMENT_NOT_RECORDED"), unrec
        return out
    return {"kind": "unknown", "status": "NOT_A_RUN", "problems": [{"path": path}]}


def replay_path(path: str) -> dict:
    """Re-execute the run from its inputs and compare every row byte for byte: {"kind", "status": IDENTICAL | DIFFERS | INPUTS, "rows", "text", ...}.  INPUTS also when a declared
    plugin is not installed at the declared version: the replay would not be a replay of the same conditions."""
    r = _replay_base(path)
    if r.get("status") == "IDENTICAL":
        mm = plugin_mismatch(path, r.get("kind"))
        if mm:
            r = dict(r, status="INPUTS", identical=False, mismatch=mm)
    return r


def _replay_base(path: str) -> dict:
    k = kind_of(path)
    if k == "loom":
        cp = _corpus_of(path)
        mm = _corpus_mismatch(path, cp)
        if mm:
            return {"kind": k, "status": "INPUTS", "identical": False, "rows": None, "mismatch": mm}
        try:
            r = lg.replay(path, corpus_path=cp)
        except (KeyError, ValueError, OSError):
            return {"kind": k, "status": "INPUTS", "identical": False, "rows": None, "mismatch": "corpus_unreadable"}
    elif k == "mem_answer":
        r = ma.replay_answer(path, os.path.dirname(os.path.dirname(os.path.abspath(path))))
    elif k == "mem_store":
        r = mem.replay_store(path, mem.FROM_HEADER)
        return {"kind": k, "status": r.status, "identical": bool(r.identical), "detail": r.to_obj()}
    else:
        return {"kind": "unknown", "status": "NOT_A_RUN"}
    out = {"kind": k, "status": r.status, "identical": bool(r.identical), "rows": r.n_rows}
    if r.mismatch:
        out["mismatch"] = r.mismatch
    if r.first_diff:
        out["first_diff"] = r.first_diff
    if getattr(r, "text", None) is not None:
        out["text"] = r.text
    return out


# ------------------------------------------------------------------------------------------------------------
# mem: a memory that answers only with what it was told, and says so when two things were told
# ------------------------------------------------------------------------------------------------------------
MEM_GUIDANCE = ("1 回に事実を 1 つ、1 文で書いてください（例: 「広報の担当は山本」）。カンマでつないだ複数の事実や言い訳は、答えの根拠として使われません。"
                " One fact per message, one sentence ('X の Y は A'): a value written together with other statements is never used as an answer.")


def mem_intro(door: Any, budget: int) -> str:
    n = door.begin_result["header"]["session_no"]
    head = ("This is session %d of the memory in this store. It is a NEW conversation: you remember nothing of the earlier ones except through your tools.\n"
            "The result of begin (the rules, your tools and caps) follows; the first message of the session comes after it. Tool results are cut after %d characters per turn.\n"
            % (n, budget))
    return head + json.dumps(door.intro(), ensure_ascii=False, sort_keys=True)


def mem_first_question_message(begin_result: dict) -> str:
    return drv.first_message(begin_result)


def _store_head(store: str) -> Optional[dict]:
    return mem.MemStore(store).head()


@dataclass
class MemSessionResult:
    session: int
    run_id: str
    messages: int
    committed: bool
    ended: str
    reports: List[Any] = field(default_factory=list)
    turns_without_report: List[str] = field(default_factory=list)
    store: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    free_text_dropped: int = 0
    error: Optional[str] = None
    redacted_turns: List[str] = field(default_factory=list)          # turns in which a secret-shaped span was replaced
    lossy_turns: List[str] = field(default_factory=list)             # turns the redaction made unreadable (see redact_user_text)


def mem_say(store: str, messages: Sequence[str], backend: Backend, *, budget: int = mview.BUDGET_DEFAULT, speaker: str = "user", profile: str = MEMORY_PROFILE_DEFAULT) -> MemSessionResult:
    """One story session: the messages arrive one at a time, the model keeps what matters through `write` (one fact per write) and ends every turn with `report`.
    The session is committed to the store only if it completed."""
    raw_msgs = [m.strip() for m in messages if m and m.strip()]
    if not raw_msgs:
        raise HarnessError("no message to remember", "no_message")
    red = [redact_user_text(m) for m in raw_msgs]
    msgs = [r[0] for r in red]
    redacted_of = {i: r[1] for i, r in enumerate(red) if r[1]}
    lossy_of = {i for i, r in enumerate(red) if r[2]}
    if any(len(m) > mem.USER_TURN_MAX for m in msgs):
        raise HarnessError("a message is longer than %d characters (the ledger records every user message whole)" % mem.USER_TURN_MAX, "message_too_long")
    backend.ready()
    model = backend.model
    plug = resolve_plugins(backend, profile=profile)
    door = md.StructureDoor(store, "notes", model, profile=plug["profile"].profile, versions=dict(plug["profile"].versions), view=mview.make_view(budget))
    wd = mview.BudgetDoor(door, budget, ledger=True)
    door.harness(None, "harness_meta", {"plugins": plug["manifest"]})
    choice, strict = backend.tool_choice()
    tools = md.api_tools(door.tool_names, strict)
    sn = door.begin_result["header"]["session_no"]
    turns = [("%d-%d" % (sn, i + 1), "[%d-%d] %s: %s" % (sn, i + 1, speaker, m)) for i, m in enumerate(msgs)]
    src = UserSourceDoor(wd, door, {"%d-%d" % (sn, i + 1): m for i, m in enumerate(msgs)}, store, {"%d-%d" % (sn, i + 1): v for i, v in redacted_of.items()}, {"%d-%d" % (sn, i + 1) for i in lossy_of})
    client = DriverClient(backend)
    try:
        res = mdrv.run_story_session(client, src, model, prompting.mem_story_prompt(), mem_intro(wd, budget), turns, tools, tool_choice=choice, max_calls=MEM_MAX_CALLS,
                                     force_report=True, caps=drv.RUNAWAY_CAPS_V1)
        committed = res.ended == "complete"
        if committed:
            wd.commit()
        ledger_dir = str(door.session.ledger.dir)
    finally:
        door.close()
    rows = [lg._parse_line(ln) for ln in lg.read_raw_lines(ledger_dir)[0]]
    return MemSessionResult(session=sn, run_id=door.run_id, messages=len(msgs), committed=committed, ended=res.ended, reports=md.reports_of(rows),
                            turns_without_report=[t["turn"] for t in res.turns if t["report"] is None], store=store, usage=dict(res.usage),
                            free_text_dropped=res.text_blocks_dropped, error=safe_error(res.error) if res.error else None,
                            redacted_turns=["%d-%d" % (sn, i + 1) for i in sorted(redacted_of)], lossy_turns=["%d-%d" % (sn, i + 1) for i in sorted(lossy_of)])


def mem_ask(store: str, question: str, backend: Backend, *, budget: int = mview.BUDGET_DEFAULT, profile: str = MEMORY_PROFILE_DEFAULT, gate_filters: Sequence[str] = (),
            note_kinds: Sequence[str] = ()) -> Answer:
    """One question over the committed memory: an answer run over a snapshot (memanswer.v17).  The answer is a quote of a remembered sentence, `contested` when two
    answers were told and nobody replaced one, or 「分かりません」."""
    question = (question or "").strip()
    if not question:
        raise HarnessError("the question is empty", "bad_question")
    store = os.path.abspath(store)
    backend.ready()
    plug = resolve_plugins(backend, filters=gate_filters, profile=profile, note_kinds=note_kinds)
    if os.path.isfile(os.path.join(store, "HEAD")):
        vs = verify_path(store)
        if vs["status"] != "OK":
            return Answer("refused", store, question, reason="store_not_verified", detail={"status": vs["status"]}, verified=False, backend=backend.describe())
    try:
        snap = ma.write_snapshot(store, topics=False, crosses=True, versions=True)
    except Refuse as r:
        return Answer("refused", store, question, reason=r.type, detail=dict(r.detail), verified=True, backend=backend.describe())
    model = backend.model
    qd = md.AnswerDoor(store, "notes", question, model, snapshot=snap, answer_version=plug["profile"].answer_version)
    qd.harness(None, "harness_meta", {"plugins": plug["manifest"]})
    wd = mview.BudgetDoor(qd, budget, ledger=False)
    _, snap_rows = ma.read_snapshot(snap["path"])
    wd = UnrecordedGate(wd, store)
    wd = FilterGate(wd, plug["filters"], question, lambda sid: {"text": snap_rows[sid].get("sent") or "", "source": snap_rows[sid].get("source") or ""} if 0 <= sid < len(snap_rows) else None)
    choice, strict = backend.tool_choice()
    tools = md.api_tools(qd.tool_names, strict, done=True)
    client = DriverClient(backend)
    res = drv.run_episode(client, wd, qd.run_id, model, prompting.mem_question_prompt(), mem_first_question_message(qd.begin_result), tools, tool_choice=choice,
                          max_turns=MEM_ANSWER_MAX_TURNS, caps=drv.RUNAWAY_CAPS_V1)
    run_dir = str(qd.session.ledger.dir)
    out = qd.output()
    ans = Answer("refused", run_dir, question, backend=backend.describe(), usage=dict(res.usage), free_text_dropped=res.text_blocks_dropped)
    if out.get("status") == "emitted":
        ans.status, ans.text, ans.output_sha, ans.verified = "answered", out["text"], out.get("output_sha"), True
        ans.sources = _mem_sources(store, snap, out, run_dir)
    elif out.get("status") == "abstained":
        ans.reason, ans.verified = out.get("type") or "unknown", True
        pr = plugin_refusal_of(run_dir)
        if pr is not None:
            ans.reason, ans.detail["plugin"] = "plugin_refused", pr
        st = statement_refusal_of(run_dir)
        if st is not None:
            ans.reason, ans.detail["turn"] = st[1], st[0]
        if out.get("type") == "contested":
            choice_ = [r for r in out.get("recalls", []) if r["verdict"] == "CHOICE"]
            ans.detail["contested_values"] = [g[0] for g in choice_[-1]["answers"]] if choice_ else []
            ans.detail["contested"] = _contested_sources(store, run_dir)
            stale = [c["replaced_in"] for c in ans.detail["contested"] if c.get("replaced_in")]
            if stale:                                       # the list is not the truth about this place: say so, and keep only the values still standing
                ans.reason, ans.detail["turn"] = "unrecorded_user_statement", stale[0]
                ans.detail["contested_values"] = [c["value"] for c in ans.detail["contested"] if not c.get("replaced_in")]
    else:
        ans.reason = "run_not_verified" if out.get("status") == "run_not_verified" else (res.ended if res.ended not in ("closed", "done") else "no_close")
        ans.verified = out.get("status") != "run_not_verified"
    if res.error:
        ans.detail["error"] = safe_error(res.error)
    ans = apply_filters(ans, plug["filters"])
    notes = annotate_memory(store, plug["notes"])
    if notes:
        ans.detail["annotations"] = notes
    return ans


def _contested_sources(store: str, run_dir: str) -> List[Dict[str, Any]]:
    """The values of the last CHOICE the answer run recalled, each with its own `sourced` flag (the sentences of its group are the user's words or an agent's record)."""
    try:
        rows = mem.MemStore(store).rows()
        sourced = sourced_sessions(store)
        last = None
        for ln in open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8"):
            if '"recall"' in ln:
                r = json.loads(ln)
                if r.get("op") == "recall" and (r.get("result") or {}).get("verdict") == "CHOICE":
                    last = r["result"]
        out = []
        for g in (last or {}).get("answers", []):
            sids = [o["sid"] for o in g.get("occurrences", []) if isinstance(o.get("sid"), int)]
            ok = bool(sids) and all(0 <= i < len(rows) and _session_of_source(rows[i].get("source")) in sourced for i in sids)
            ent = {"value": (g.get("answers") or [g.get("text")])[0], "sourced": ok}
            t = unrecorded_statement(store, sids)
            if t is not None:
                ent["replaced_in"] = t                       # a later user sentence at this place says something else and is not stored: never present this value as current
            out.append(ent)
        return out
    except (OSError, ValueError, KeyError):
        return []


def _mem_sources(store: str, snap: dict, out: dict, run_dir: str) -> List[Dict[str, Any]]:
    """The remembered sentence(s) the answer was quoted from: the sentence ids of the successful `emit` row of the answer run's own ledger (its `evidence`), looked up in the snapshot.  Never a
    search for the value text: two facts with the same value are two different sources."""
    try:
        _, rows = ma.read_snapshot(snap["path"])
        sids: List[int] = []
        for ln in open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8"):
            r = json.loads(ln)
            if r.get("actor") == "model" and r.get("op") == "emit" and (r.get("result") or {}).get("ok") is True:
                sids = [e["sid"] for e in (r["result"].get("evidence") or []) if isinstance(e.get("sid"), int)]
    except (OSError, Refuse, ValueError, KeyError):
        return []
    found = []
    for i in sids:
        if 0 <= i < len(rows):
            ses = _session_of_source(rows[i].get("source"))
            found.append({"sid": i, "source": rows[i].get("source") or "", "text": rows[i].get("sent") or rows[i].get("text") or "", "turn": rows[i].get("turn"),
                          "sourced": ses in sourced_sessions(store)})
    return found[:3]
