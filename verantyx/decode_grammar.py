"""W10-f01 -- 融合の層 0・1: 入力の読解、記録から作る復号の文法、出力の検証、根拠の方針 (docs/FUSION.md §1)。

HTTP も LLM の呼び出しも持たない純粋な関数。LLM の返答は ``conclude`` に引数で渡す。
``semantic_*``・``observe``・``basis_policy``・``event_cross``・``sovereign`` と ``cli._qc_run``/``cli._qc_records`` は呼ぶだけで変えない。
``cli`` は関数の中で遅延 import する（循環を避ける）。

層 0（既定）: LLM が答える。記録が答えを持つ事実の問いは記録が答え。それ以外の LLM の文は 証言（factual）／構成（非 factual）／未読 の印つき。
層 1（strict）: 文法で縛る。文法の外の語は出ない。読めない・記録に候補が無い入力では LLM を呼ばない。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "verantyx.fusion/1"

MARK_CONSTRUCTED = "［構成: 事実の主張ではありません］"
MARK_TESTIMONY = "［証言: LLM の答えです。記録の裏づけはありません］"

#: 型ごとの固定文（LLM の文は本文に出さない）
FIXED_TEXT = {
    "NO_RECORD": "記録に根拠が無いので答えられません（NO_RECORD）。",
    "STRUCTURE_UNDETERMINED": "構造が決まらないので言えません（STRUCTURE_UNDETERMINED）。",
    "OUTSIDE_GRAMMAR": "出力が文法の外だったので出しません（OUTSIDE_GRAMMAR）。",
    "LLM_UNAVAILABLE": "LLM から答えを得られなかったので答えられません（LLM_UNAVAILABLE）。",
    "LLM_EMPTY": "LLM の答えが空だったので答えられません（LLM_EMPTY）。",
    "ABSTAIN": "根拠が足りないので答えられません（ABSTAIN）。",
}

READING_TYPES = ("QUESTION_CROSS", "RECORDS", "NO_RECORD", "STRUCTURE_UNDETERMINED")
#: `_qc_run` の question_cross.state のうち「記録に当たる十字が無い」もの（閉じた一覧）。これ以外の state は STRUCTURE_UNDETERMINED（保守側）。
NO_RECORD_STATES = ("NO_ATTESTED_CELL", "NO_TYPED_CANDIDATE", "TYPE_EXCLUDED_ALL", "DOCUMENTS_NOT_LOADED")
ANSWER_OUTCOMES = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "REFERENCE_GENERATED")
#: 節の十字の鍵は固定の一覧ではなく「roles 以外の全ての鍵」（回数 quantifiers などの修飾も十字の一部。閉じた一覧の外は保守側に倒す）。r2 の訂正（docs/FUSION.md §1.9）
_NON_CENTER_KEYS = ("roles",)
#: 腕の印（`arms[*].kind`）が見る中心は従来どおりの 5 鍵（腕の表記が記録に当たっているかを言うもので、回数などは文の印だけに効く）
_ARM_CENTER_KEYS = ("predicate", "polarity", "tense", "modality", "voice")
_JA_CHAR = re.compile("[぀-ヿ㐀-䶿一-鿿]")
_MAX_TOKENS = 120

_BASE_UNKNOWN = {"kind": "unknown", "verdict": "UNKNOWN_UNREAD", "text": "", "sources": [], "trace": []}


def _nfkc(text: Any) -> str:
    return unicodedata.normalize("NFKC", str(text)).strip()


def _split_re():
    from . import cli
    return re.compile(cli._QC_SPLIT)


def split_sentences(text: str) -> List[str]:
    """本文を文に分ける。`cli._QC_SPLIT` と同じ切り方（行ごとに切る）。"""
    cut = _split_re()
    out: List[str] = []
    for line in str(text).split("\n"):
        out.extend(x.strip() for x in cut.split(line) if x.strip())
    return out


# --- 文の十字 --------------------------------------------------------------------------------------------------------------------------------

def cross_of(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """文を再読し、節が 1 つで relations が無く、日本語なら述語の 4 形と派生の門を通ったものだけ十字を返す。(十字, None) か (None, 理由)。"""
    from . import semantic_read
    from . import semantic_reader as R
    try:
        out = semantic_read.read(text)
    except Exception as exc:  # 読めない文は未読。落とさない
        return None, "READ_ERROR:%s" % type(exc).__name__
    if not isinstance(out, dict) or not out.get("readable"):
        reasons = ((out or {}).get("abstain") or {}).get("reasons") or ["unread"]
        return None, "UNREAD:%s" % reasons[0]
    clauses = out.get("clauses") or []
    if len(clauses) != 1 or out.get("relations"):
        return None, "NOT_ONE_CLAUSE"
    written = None
    if out.get("lang") == "ja":
        try:
            why = semantic_read._w3b3_gates(text, out, R)
        except Exception as exc:
            return None, "GATE_ERROR:%s" % type(exc).__name__
        if why:
            return None, "FORM_NOT_READ:%s" % why
        span = ((out.get("clause_meta") or [{}])[0] or {}).get("span")
        if isinstance(span, (list, tuple)) and len(span) == 2:
            written = text[span[0]:].rstrip("。．.！!？? \t\r\n　")
    c = clauses[0]
    return {"arm_center": tuple((k, c.get(k)) for k in _ARM_CENTER_KEYS), "center": tuple(sorted(((k, c[k]) for k in c if k not in _NON_CENTER_KEYS), key=lambda kv: kv[0])), "roles": {r: _nfkc(v) for r, v in (c.get("roles") or {}).items()},
            "raw_roles": dict(c.get("roles") or {}), "lang": out.get("lang"), "written_predicate": written}, None


class Records:
    """渡された文書の文（`cli._qc_records` と同じ切り方）と、各文の再読。サーバ起動時に 1 回作る。"""

    def __init__(self, documents: Sequence[str]):
        from . import cli
        self.documents = [str(d) for d in documents]
        self.records, self.where, self.n_loaded, self.skipped = cli._qc_records(self.documents)
        self.crosses: Dict[str, Optional[Dict[str, Any]]] = {}
        self.cross_reason: Dict[str, Optional[str]] = {}
        self.by_text: Dict[str, List[str]] = {}
        for rec in self.records:
            cross, why = cross_of(rec["text"])
            self.crosses[rec["id"]] = cross
            self.cross_reason[rec["id"]] = why
            self.by_text.setdefault(_nfkc(rec["text"]), []).append(rec["id"])

    def source_of(self, sentence_id: str) -> Dict[str, Any]:
        w = self.where[sentence_id]
        return {"family": "document", "source": w["source"], "line": w["line"], "text": w["text"], "sentence_id": sentence_id}

    def all_sources(self) -> List[Dict[str, Any]]:
        return [self.source_of(r["id"]) for r in self.records]


def load_records(documents: Sequence[str]) -> Records:
    return Records(documents)


# --- 読解 ------------------------------------------------------------------------------------------------------------------------------------

def _reading(type_: str, state: Optional[str], reason: Optional[str], qc: Optional[Dict[str, Any]] = None,
             sources: Optional[List[Dict[str, Any]]] = None, filler: Optional[str] = None) -> Dict[str, Any]:
    qc = qc or {}
    return {"type": type_, "state": state, "reason": reason, "hole_role": qc.get("hole_role"), "hole_type": qc.get("hole_type"),
            "filler": filler, "sources": list(sources or [])}


def read_turn(question: str, request_kind: str, records: Records, documents: Sequence[str]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """入力を読む（docs/FUSION.md §1.2 の 2）。(reading, qc の結果)。"""
    from . import basis_policy as bp
    if bp.KIND_CLASS.get(request_kind) != "FACTUAL":
        why = None if records.n_loaded else "NO_DOCUMENTS"
        return _reading("RECORDS", None, why), None
    if records.n_loaded == 0:
        return _reading("NO_RECORD", "DOCUMENTS_NOT_LOADED", "NO_DOCUMENTS"), None
    from . import cli
    try:
        res = cli._qc_run(dict(_BASE_UNKNOWN), list(documents), question)
    except Exception as exc:
        return _reading("STRUCTURE_UNDETERMINED", "ERROR", "%s: %s" % (type(exc).__name__, exc)), None
    qc = res.get("question_cross") or {}
    state, reason = qc.get("state"), qc.get("reason")
    if res.get("verdict") == "ANSWER" and state == "FILLED" and isinstance(res.get("text"), str) and res.get("sources"):
        srcs = [{k: s[k] for k in ("source", "line", "text", "sentence_id")} for s in res["sources"]]
        return _reading("QUESTION_CROSS", state, reason, qc, srcs, res["text"]), res
    if state in NO_RECORD_STATES:
        return _reading("NO_RECORD", state, reason, qc), res
    return _reading("STRUCTURE_UNDETERMINED", state if state else "UNKNOWN_STATE", reason or res.get("verdict"), qc), res


# --- 文法 ------------------------------------------------------------------------------------------------------------------------------------

def gbnf_literal(text: str) -> str:
    """GBNF の文字列リテラル。`\\`・`"`・改行・復帰・タブを逃がす。"""
    esc = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return '"%s"' % esc


def gbnf_alternatives(alternatives: Sequence[str]) -> str:
    lines = ["root ::= " + " | ".join("alt%d" % i for i in range(len(alternatives)))]
    lines += ["alt%d ::= %s" % (i, gbnf_literal(a)) for i, a in enumerate(alternatives)]
    return "\n".join(lines) + "\n"


def gbnf_vocabulary(vocabulary: Sequence[str], max_tokens: int = _MAX_TOKENS) -> str:
    return ("root ::= tok{1,%d}\ntok ::= " % max_tokens) + " | ".join(gbnf_literal(v) for v in vocabulary) + "\n"


def grammar_id(kind: str, items: Sequence[str]) -> str:
    key = "alternatives" if kind == "alternatives" else "vocabulary"
    blob = json.dumps({"kind": kind, key: list(items)}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "g-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _sovereign_summary() -> Dict[str, Any]:
    configured = bool(os.environ.get("VERA_SOVEREIGN_ROOT") and os.environ.get("VERA_SOVEREIGN_STORE"))
    return {"state": "CONFIGURED" if configured else "NOT_CONFIGURED", "used_as_grammar_source": False, "reason": "SOVEREIGN_CLAIM_NOT_A_SENTENCE"}


def _candidate_ok(text: str, src_cross: Optional[Dict[str, Any]], hole_role: Optional[str], filler: str) -> bool:
    cross, _why = cross_of(text)
    if cross is None or src_cross is None:
        return False
    if cross["center"] != src_cross["center"] or cross["roles"] != src_cross["roles"]:
        return False
    return bool(hole_role) and cross["roles"].get(hole_role) == _nfkc(filler)


def _wh_of(question: str, records: Records) -> Optional[str]:
    from .observe import observe_question_records
    try:
        ans = observe_question_records(question, records.records).get("answer") or {}
    except Exception:
        return None
    wh = (ans.get("question") or {}).get("wh")
    return wh if isinstance(wh, str) and wh else None


def _a3(question: str, wh: Optional[str], filler: str) -> Optional[str]:
    if not wh or question.count(wh) != 1:
        return None
    q = question.strip()
    if q[-1:] in "？?":
        q = q[:-1].rstrip()
    return q.replace(wh, filler) + "。"


def build_grammar(reading: Dict[str, Any], records: Records, question: str, request_kind: str) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, str]]]:
    """層 1 の文法。(文法, None) か (None, (読解の型, state, reason))。作れなければ LLM を呼ばない。"""
    from . import basis_policy as bp
    if bp.KIND_CLASS.get(request_kind) == "FACTUAL":
        if reading["type"] != "QUESTION_CROSS":
            return None, (reading["type"], reading["state"] or "", reading["reason"] or "")
        filler, role = reading["filler"], reading["hole_role"]
        alts: List[str] = []
        for src in reading["sources"]:
            sc = records.crosses.get(src["sentence_id"])
            if _candidate_ok(src["text"], sc, role, filler) and src["text"] not in alts:
                alts.append(src["text"])
        a3 = _a3(question, _wh_of(question, records), filler)
        if a3 is not None and a3 not in alts:
            if all(_candidate_ok(a3, records.crosses.get(s["sentence_id"]), role, filler) for s in reading["sources"]):
                alts.append(a3)
        if not alts:
            return None, ("STRUCTURE_UNDETERMINED", "NO_VERIFIABLE_ALTERNATIVE", "no candidate sentence passes the verifier")
        first = next((records.crosses.get(s["sentence_id"]) for s in reading["sources"]), None) or {}
        summary = {"alternatives_n": len(alts), "fillers": [filler], "predicate_forms": sorted({records.crosses[s["sentence_id"]]["written_predicate"] for s in reading["sources"]
                                                                                               if records.crosses.get(s["sentence_id"]) and records.crosses[s["sentence_id"]].get("written_predicate")}),
                   "dictionary_form": dict(first.get("center", ())).get("predicate"), "polarity": dict(first.get("center", ())).get("polarity"),
                   "tense": dict(first.get("center", ())).get("tense"), "sources": [s["sentence_id"] for s in reading["sources"]], "sovereign": _sovereign_summary()}
        schema = {"type": "object", "properties": {"answer": {"type": "string", "enum": alts}}, "required": ["answer"], "additionalProperties": False}
        return {"id": grammar_id("alternatives", alts), "kind": "alternatives", "alternatives": alts, "summary": summary, "json_schema": schema,
                "gbnf": gbnf_alternatives(alts)}, None
    # 非 factual: 閉じた語彙
    if records.n_loaded == 0:
        return None, ("NO_RECORD", "DOCUMENTS_NOT_LOADED", "NO_DOCUMENTS")
    if not any(_JA_CHAR.search(r["text"]) for r in records.records):
        return None, ("STRUCTURE_UNDETERMINED", "CREATIVE_LANG_NOT_SUPPORTED", "documents hold no Japanese text")
    from . import semantic_reader as R
    vocab = set()
    for rec in records.records:
        for word, _a, _b in R._tokens(rec["text"]):
            if word.surface.strip():
                vocab.add(word.surface)
    if not vocab:
        return None, ("STRUCTURE_UNDETERMINED", "EMPTY_VOCABULARY", "no token")
    vocab_l = sorted(vocab)
    schema = {"type": "object", "properties": {"answer": {"type": "array", "items": {"type": "string", "enum": vocab_l}, "minItems": 1, "maxItems": _MAX_TOKENS}},
              "required": ["answer"], "additionalProperties": False}
    summary = {"vocabulary_n": len(vocab_l), "sources": [d for d in records.documents], "sovereign": _sovereign_summary()}
    return {"id": grammar_id("vocabulary", vocab_l), "kind": "vocabulary", "vocabulary": vocab_l, "summary": summary, "json_schema": schema,
            "gbnf": gbnf_vocabulary(vocab_l)}, None


def check_grammar(grammar: Dict[str, Any], content: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """LLM の返答が文法の内か。(内か, 本文, 理由)。縛りを信用せず必ず確かめる。"""
    try:
        obj = json.loads(content) if isinstance(content, str) else content
    except (TypeError, ValueError):
        return False, None, "NOT_JSON"
    if not isinstance(obj, dict):
        return False, None, "NOT_AN_OBJECT"
    if set(obj) != {"answer"}:
        return False, None, "KEYS_NOT_ANSWER_ONLY" if "answer" in obj else "NO_ANSWER_KEY"
    ans = obj["answer"]
    if grammar["kind"] == "alternatives":
        if not isinstance(ans, str):
            return False, None, "ANSWER_NOT_A_STRING"
        if ans not in grammar["alternatives"]:
            return False, None, "ANSWER_NOT_IN_ENUM"
        return True, ans, None
    if not isinstance(ans, list) or not 1 <= len(ans) <= _MAX_TOKENS:
        return False, None, "ANSWER_LENGTH_OUT_OF_RANGE"
    vocab = set(grammar["vocabulary"])
    if not all(isinstance(t, str) and t in vocab for t in ans):
        return False, None, "TOKEN_NOT_IN_VOCABULARY"
    return True, "".join(ans), None


# --- 検証 ------------------------------------------------------------------------------------------------------------------------------------

def verify(text: str, records: Records, request_kind: str, model: str = "") -> List[Dict[str, Any]]:
    """本文を文に分け、各文を再読し、腕ごとに 記録／証言（factual）／構成（非 factual）を付ける。読めない文は UNREAD。"""
    from . import basis_policy as bp
    other = "testimony" if bp.KIND_CLASS.get(request_kind) == "FACTUAL" else "constructed"
    items: List[Dict[str, Any]] = []
    for s in split_sentences(text):
        ids_verbatim = records.by_text.get(_nfkc(s), [])
        cross, why = cross_of(s)
        item: Dict[str, Any] = {"text": s, "read": cross is not None, "mark": None if cross is not None else "UNREAD", "unread_reason": why,
                                "sentence_kind": other, "origin": other, "evidence": [], "arms": {}, "center_kind": other, "via": None}
        if other == "testimony":
            item["source"] = {"family": "llm", "origin": "testimony", "model": model}
        if cross is not None:
            item["center"] = dict(cross["center"])
            ev_arm = [i for i, c in records.crosses.items() if c is not None and c["arm_center"] == cross["arm_center"]]
            ev_center = [i for i in ev_arm if records.crosses[i]["center"] == cross["center"]]
            if ev_center:
                item["center_kind"] = "record"
            for role, surf in cross["roles"].items():
                hit = [i for i in ev_arm if records.crosses[i]["roles"].get(role) == surf]
                item["arms"][role] = {"surface": cross["raw_roles"].get(role), "kind": "record" if hit else other, "evidence": hit}
            full = [i for i in ev_center if records.crosses[i]["roles"] == cross["roles"]]
            if full:
                item.update({"sentence_kind": "record", "origin": "record", "evidence": full, "via": "cross"})
        if ids_verbatim and item["sentence_kind"] != "record":
            item.update({"sentence_kind": "record", "origin": "record", "evidence": list(ids_verbatim), "via": "verbatim"})
        if item["sentence_kind"] == "record":
            item.pop("source", None)
            if item["mark"] == "UNREAD":
                item["mark"] = None            # 記録の文そのもの（逐語）。再読できないことは unread_reason に残す
        items.append(item)
    return items


def all_record_with_hole(items: Sequence[Dict[str, Any]], hole_role: Optional[str], filler: Optional[str]) -> bool:
    if not items or not hole_role or not filler:
        return False
    for it in items:
        if it["sentence_kind"] != "record" or not it.get("read"):
            return False
        arm = it["arms"].get(hole_role)
        if not arm or _nfkc(arm["surface"]) != _nfkc(filler):
            return False
    return True


# --- 根拠の方針 ------------------------------------------------------------------------------------------------------------------------------

def apply_policy(result: Dict[str, Any], request_kind: str, human_present: bool, query: str, documents: Sequence[str]) -> Tuple[Dict[str, Any], Optional[str], Dict[str, Any]]:
    from . import basis_policy as bp
    pol = bp.AskPolicy.from_args(SimpleNamespace(request_kind=request_kind, human_present=bool(human_present), show_generated_reference=False, confirm=None))
    if isinstance(pol, dict):
        return result, None, {"applied": False, "reason": pol.get("verdict")}
    out, _rc = bp.apply_to_ask(result, pol, query=query, mode="round5", documents=list(documents))
    note = out.get("basis_policy") if isinstance(out, dict) else None
    note = note if isinstance(note, dict) else {}
    return out, note.get("outcome"), note


def _llm_unavailable_note(llm: Dict[str, Any]) -> str:
    err = llm.get("error") or {}
    return "%s: %s" % (err.get("type", "UNKNOWN"), err.get("detail", "")) if isinstance(err, dict) else str(err)


# --- 1 ターン --------------------------------------------------------------------------------------------------------------------------------

def plan_turn(question: str, request_kind: str, records: Records, documents: Sequence[str], *, strict: bool) -> Dict[str, Any]:
    """読解と（層 1 では）文法。`call_llm` が偽なら LLM を呼ばない。"""
    from . import basis_policy as bp
    reading, qc = read_turn(question, request_kind, records, documents)
    factual = bp.KIND_CLASS.get(request_kind) == "FACTUAL"
    turn: Dict[str, Any] = {"layer": 1 if strict else 0, "request_kind": request_kind, "question": question, "reading": reading, "qc": qc,
                            "grammar": None, "call_llm": False, "skip_reason": None, "record_answer": None}
    if not strict:
        if reading["type"] == "QUESTION_CROSS":
            turn["record_answer"] = reading["sources"][0]["text"]
            turn["skip_reason"] = "RECORD_ANSWERED"
        else:
            turn["call_llm"] = True
        return turn
    grammar, why = build_grammar(reading, records, question, request_kind)
    if grammar is None:
        t, state, reason = why
        turn["reading"] = dict(reading, type=t, state=state or reading["state"], reason=reason or reading["reason"])
        turn["skip_reason"] = "NO_GRAMMAR:%s" % t
        return turn
    turn["grammar"], turn["call_llm"] = grammar, True
    return turn


def llm_messages(turn: Dict[str, Any], client_messages: Sequence[Dict[str, Any]], records: Records) -> List[Dict[str, Any]]:
    """LLM に渡す messages。層 0 の事実の問いはクライアントの会話をそのまま。非 factual は文書を前に添える。層 1 は問いだけ。"""
    from . import basis_policy as bp
    factual = bp.KIND_CLASS.get(turn["request_kind"]) == "FACTUAL"
    doc_lines = "\n".join("[%s:%d] %s" % (r["source"], r["line"], r["text"]) for r in (records.source_of(x["id"]) for x in records.records))
    if turn["layer"] == 1:
        if factual:
            sys_msg = "次の問いに、JSON の answer の値だけで答えてください。"
        else:
            sys_msg = ("利用者の文書は次のとおりです。\n%s\n\n依頼に、文書の語だけを使い、JSON の answer に語の配列（左から順に並べたもの）で答えてください。" % doc_lines)
        return [{"role": "system", "content": sys_msg}, {"role": "user", "content": turn["question"]}]
    msgs = [{"role": m.get("role", "user"), "content": _content_text(m.get("content"))} for m in client_messages]
    if not factual and records.n_loaded:
        msgs.insert(0, {"role": "system", "content": "利用者の文書は次のとおりです。依頼はこの文書の内容に基づいて答えてください。\n" + doc_lines})
    return msgs


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(p.get("text", "")) for p in content if isinstance(p, dict) and p.get("type") == "text")
    return "" if content is None else str(content)


def _testimony_result(items: Sequence[Dict[str, Any]], type_: str, model: str) -> Dict[str, Any]:
    """証言の出所だけの結果（記録の出所を混ぜない。classify_sources は document＋testimony を HUMAN にするため）。"""
    srcs = [{"family": "llm", "origin": "testimony", "model": model, "text": it["text"]} for it in items if it["sentence_kind"] != "record"]
    return {"kind": "unknown", "verdict": "UNKNOWN_%s" % type_, "text": "", "sources": srcs, "trace": []}


def conclude(turn: Dict[str, Any], llm: Optional[Dict[str, Any]], records: Records, *, model: str, human_present: bool = False) -> Tuple[str, Dict[str, Any]]:
    """読解・（LLM の返答）・検証・方針 -> (本文, vera 欄)。`llm` は {"ok","content","error","raw_status"} か None（呼ばなかったとき）。"""
    from . import basis_policy as bp
    rk, reading, grammar, layer = turn["request_kind"], turn["reading"], turn["grammar"], turn["layer"]
    factual = bp.KIND_CLASS.get(rk) == "FACTUAL"
    documents = records.documents
    called = llm is not None
    llm_field: Dict[str, Any] = {"called": called, "model": model, "ok": None, "error": None, "raw": None, "withheld": False, "skipped_reason": turn.get("skip_reason")}
    gcheck: Dict[str, Any] = {"in_grammar": None, "reason": None}
    provenance: List[Dict[str, Any]] = []
    outcome: Dict[str, Any] = {"outcome": None, "content_shown": False, "reason": None, "basis_policy": None}
    content = ""

    def fixed(kind: str, reason: Optional[str] = None, policy_note: Optional[Dict[str, Any]] = None) -> None:
        nonlocal content
        content = FIXED_TEXT[kind]
        outcome.update({"outcome": kind, "content_shown": False, "reason": reason, "basis_policy": policy_note})

    def abstain_policy(items: Sequence[Dict[str, Any]], type_: str) -> Dict[str, Any]:
        _o, _oc, note = apply_policy(_testimony_result(items, type_, model), rk if factual else "factual", human_present, turn["question"], documents)
        return note

    if turn.get("record_answer") is not None:
        # 層 0: 記録が答え。LLM は呼ばない（D10）。記録の文そのものを返し、記録の出所だけを方針に通す
        text = turn["record_answer"]
        provenance = verify(text, records, rk, model)
        _out, oc, note = apply_policy(turn["qc"], rk, human_present, turn["question"], documents)
        if oc == "ANSWER_HUMAN_BASIS" and all(p["sentence_kind"] == "record" for p in provenance):
            content = text
            outcome.update({"outcome": oc, "content_shown": True, "reason": "RECORD_ANSWERED", "basis_policy": note})
        else:
            fixed("ABSTAIN", "POLICY_OUTCOME:%s" % oc, note)
    elif not turn["call_llm"]:
        # 層 1 で文法が作れない: LLM を呼ばず、型で返す
        fixed(reading["type"], "%s: %s" % (reading["state"], reading["reason"]), abstain_policy([], reading["type"]))
    else:
        assert called, "plan said call the LLM but no result was given"
        llm_field.update({"ok": bool(llm.get("ok")), "error": llm.get("error"), "raw": llm.get("content")})
        if not llm.get("ok"):
            fixed("LLM_UNAVAILABLE", _llm_unavailable_note(llm))
        else:
            raw = llm.get("content")
            text: Optional[str] = raw if isinstance(raw, str) else ""
            if grammar is not None:
                ok, text, why = check_grammar(grammar, raw)
                gcheck.update({"in_grammar": ok, "reason": why})
                if not ok:
                    llm_field["withheld"] = True
                    fixed("OUTSIDE_GRAMMAR", why)
                    text = None
            if text is not None:
                text = text.strip()
                if not text:
                    fixed("LLM_EMPTY", "empty content")
                else:
                    provenance = verify(text, records, rk, model)
                    if factual:
                        shown = _finish_factual(turn, text, provenance, records, model, human_present, outcome, fixed, abstain_policy, grammar)
                        if shown is not None:
                            content = shown
                    else:
                        content = _finish_nonfactual(turn, text, records, model, human_present, outcome, fixed)
    vera = {"schema": SCHEMA, "layer": layer, "request_kind": rk,
            "reading": {k: reading[k] for k in ("type", "state", "reason", "hole_role", "hole_type", "filler", "sources")},
            "grammar": ({"id": grammar["id"], "kind": grammar["kind"], "summary": grammar["summary"], "json_schema": grammar["json_schema"], "gbnf": grammar["gbnf"]}
                        if grammar else None),
            "grammar_id": grammar["id"] if grammar else None,
            "llm": llm_field, "grammar_check": gcheck, "provenance": provenance, "outcome": outcome}
    return content, vera


def _finish_factual(turn, text, provenance, records, model, human_present, outcome, fixed, abstain_policy, grammar) -> Optional[str]:
    """本文を返す（答え・証言）。固定文にしたときは None（`fixed` が本文と outcome を決めた）。"""
    rk, reading, documents = turn["request_kind"], turn["reading"], records.documents
    if grammar is not None:
        # 層 1: 全文が記録で、穴の表記が充填物と等しい文だけが答え
        if reading["type"] == "QUESTION_CROSS" and all_record_with_hole(provenance, reading["hole_role"], reading["filler"]) and turn["qc"] is not None:
            _out, oc, note = apply_policy(turn["qc"], rk, human_present, turn["question"], documents)
            if oc == "ANSWER_HUMAN_BASIS":
                outcome.update({"outcome": oc, "content_shown": True, "reason": "ALL_SENTENCES_RECORD_HOLE_MATCHES", "basis_policy": note})
                return text
            fixed("ABSTAIN", "POLICY_OUTCOME:%s" % oc, note)
            return None
        fixed("ABSTAIN", "LLM_SENTENCE_NOT_RECORD", abstain_policy(provenance, reading["type"]))
        return None
    # 層 0: 記録が答えを持たない。LLM の文は証言の印つき。記録の出所と混ぜた方針は掛けない
    note = abstain_policy(provenance, reading["type"])
    outcome.update({"outcome": "TESTIMONY", "content_shown": True, "reason": "NO_RECORD_ANSWER:%s" % reading["type"], "basis_policy": note})
    return MARK_TESTIMONY + "\n" + text


def _finish_nonfactual(turn, text, records, model, human_present, outcome, fixed) -> str:
    rk = turn["request_kind"]
    srcs = records.all_sources()
    result = {"kind": "answer", "verdict": "ANSWER", "text": text, "values": [text], "evidence": [], "sources": srcs, "trace": []}
    _out, oc, note = apply_policy(result, rk, human_present, turn["question"], records.documents)
    if not srcs:
        oc, note = "CONSTRUCTED", dict(note, reason_by_fusion="NO_DOCUMENTS_CONSTRUCTED_WITHOUT_RECORDS")
    if oc == "CONSTRUCTED":
        outcome.update({"outcome": "CONSTRUCTED", "content_shown": True, "reason": "NON_FACTUAL_REQUEST", "basis_policy": note})
        return MARK_CONSTRUCTED + "\n" + text
    fixed("ABSTAIN", "POLICY_OUTCOME:%s" % oc, note)
    return FIXED_TEXT["ABSTAIN"]
