"""vera — CLI for Verantyx Vera α (lab + chat in one binary).

Knowledge:
  vera pour --source synthetic|wikitext|hf:<name>[#config][:field]|file:<path>
  vera remember "The bright apple is sweet ."
  vera ask "what is apple"
  vera forget apple
  vera stats
  vera chat                    interactive REPL (knowledge + math + code)

Math / logic:
  vera math "x + 3 = 7"        wire arithmetic / typed equations
  vera simplify "x + 0"        term rewriting (rules are data)

Code reasoning:
  vera code ingest <path>
  vera code ask "who calls foo"

Lab:
  vera lab                     run the fork self-test suites
  vera mcp                     start the MCP server (see docs/MCP.md)

Conductor:
  vera conduct --frame F --repo R --adapter codex|claude|fake [--dry-run]
                               read a project frame and start (or plan) an agent
                               (see docs/CONDUCT_ENTRY.md); a frame with an [agents]
                               table is routed: omit --adapter (docs/AGENT_ROUTING.md)

Default store: ./vera_store.json (override with --store).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .code_ingest import code_ask, ingest_python_repo
from .consensus_store import consensus_over_store
from .cross_store import CrossStore, pour_corpus
from .math_sim import math_ask
from .rewrite_kernel import default_algebra_rules, simplify

DEFAULT_STORE = "vera_store.json"


def _load(path: str, *, base_repo: str = "") -> CrossStore:
    p = Path(path)
    if not p.is_file() and base_repo:
        from .hf_store import ensure_store

        res = ensure_store(path, base_repo)
        if res.get("ok"):
            print(f"[store] fetched base store from HuggingFace: {base_repo}")
    return CrossStore.load(p) if p.is_file() else CrossStore()


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _round5_chat_evidence_lines(out: dict, vera: Any) -> list[str]:
    """Render returned source evidence without treating it as world truth."""
    originals = getattr(getattr(vera, "bot", None), "original_texts", {})
    if type(originals) is not dict:
        originals = {}
    source_texts = {key: value for key, value in originals.items()
                    if type(key) is str and type(value) is str}
    sources = out.get("sources")
    if type(sources) in (list, tuple):
        for source in sources:
            if type(source) is dict:
                source_id = source.get("id") or source.get("source")
                source_text = source.get("text")
                if (type(source_id) is str and type(source_text) is str
                        and source_id not in source_texts):
                    source_texts[source_id] = source_text
    lines: list[str] = []
    evidence = out.get("evidence")
    if type(evidence) not in (list, tuple):
        evidence = []
    pending = list(reversed(evidence))
    while pending:
        item = pending.pop()
        if type(item) in (list, tuple):
            pending.extend(reversed(item))
            continue
        if type(item) is str:
            lines.append(f"      根拠(応答の返却値): {item}")
            continue
        if type(item) is not dict:
            continue

        source_id = item.get("source") or item.get("id")
        source_sha = item.get("source_sha256") or item.get("sha256")
        event_sha = item.get("source_event_sha256")
        scope = item.get("scope")
        if (type(source_id) is str and type(item.get("start")) is int
                and type(item.get("end")) is int):
            source_text = source_texts.get(source_id)
            start, end = item["start"], item["end"]
            if (type(source_text) is str
                    and type(item.get("sha256")) is str
                    and item["sha256"] == hashlib.sha256(source_text.encode("utf-8")).hexdigest()
                    and 0 <= start <= end <= len(source_text)):
                lines.append(
                    f"      根拠範囲 {source_id}[{start}:{end}] (出典主張の真偽未確認): "
                    f"{source_text[start:end]}"
                )
                continue
        if type(source_id) is str:
            parts = [f"出典={source_id}"]
            if type(source_sha) is str:
                parts.append(f"source_sha256={source_sha}")
            if type(event_sha) is str:
                parts.append(f"source_event_sha256={event_sha}")
            lines.append("      根拠: " + "; ".join(parts))
            if type(scope) is str and scope:
                lines.append(f"      根拠の範囲: {scope}")

            source_text = source_texts.get(source_id)
            if type(source_text) is str:
                actual_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
                if type(source_sha) is str and source_sha == actual_sha:
                    if len(source_text) <= 240:
                        lines.append(f"      出典原文(source hash一致・真偽未確認): {source_text}")
                    else:
                        lines.append("      出典原文: hash一致。長文のため本文表示は省略")
            continue

    if not lines:
        sources = out.get("sources")
        if type(sources) in (list, tuple):
            for source in sources:
                if type(source) is dict:
                    label = source.get("source") or source.get("id")
                    digest = source.get("sha256") or source.get("original_document_sha256")
                    if type(label) is str:
                        suffix = f"; sha256={digest}" if type(digest) is str else ""
                        lines.append(f"      出典参照: {label}{suffix}")
    return lines


def _print_round5_chat_result(out: dict, vera: Any) -> None:
    verdict = out.get("verdict")
    status = out.get("status")
    body = (out.get("text") or out.get("value") or "").strip()
    if status == "PARTIAL_COMPLETENESS_UNVERIFIED" or verdict == "PARTIAL":
        if body:
            print(f"vera> {body}   [{out.get('door', '?')}]")
        else:
            print(f"vera> {verdict}   [{out.get('door', '?')}]")
        print("      状態: PARTIAL_COMPLETENESS_UNVERIFIED")
        verification = out.get("verification")
        verification = verification if type(verification) is dict else {}
        limited = verification.get("limited_projection_equivalent",
                                  out.get("limited_projection_equivalent"))
        represented = out.get("represented_projection_verified")
        if represented is None:
            represented = out.get("candidate_projection_verified", limited)
        full = verification.get("full_semantic_equivalent",
                                out.get("full_semantic_equivalent"))
        full_goal_verified = out.get("full_goal_verified")
        if full_goal_verified is None:
            full_goal_verified = False
        satisfied = verification.get("goal_satisfied", out.get("goal_satisfied"))
        eligible = verification.get("success_count_eligible",
                                    out.get("success_count_eligible"))
        truth_status = out.get("source_truth_status")
        print("      検証: limited_projection_equivalent=%s; represented_projection_verified=%s; "
              "full_semantic_equivalent=%s; full_goal_verified=%s; goal_satisfied=%s; "
              "success_count_eligible=%s; "
              "source_truth_status=%s" % (
                  limited, represented, "未確認" if full is None else full,
                  full_goal_verified,
                  "未確認" if satisfied is None else satisfied, eligible,
                  truth_status))
        print(f"      注意: {out.get('response_notice') or '出典全体の網羅性は未確認です。'}")
    elif verdict == "ANSWER" or out.get("kind") in ("skill", "answer"):
        print(f"vera> {body or verdict}   [{out.get('door', '?')}]")
    else:
        print(f"vera> {body or verdict}   [{out.get('door', '?')}] (推測せず保留)")
        if type(out.get("reason")) is str and out["reason"]:
            print(f"      理由: {out['reason']}")
    for line in _round5_chat_evidence_lines(out, vera):
        print(line)


def _route(store: CrossStore, query: str) -> Dict[str, Any]:
    """math → code → knowledge, refusing rather than guessing."""
    m = math_ask(query)
    if m["verdict"] != "UNKNOWN_UNPARSED":
        m["route"] = "math"
        return m
    c = code_ask(store, query)
    if c["verdict"] != "UNKNOWN_UNPARSED":
        c["route"] = "code"
        return c
    out = consensus_over_store(store, query)
    out["route"] = "knowledge"
    return out


def cmd_pour(args) -> int:
    ckpt = Path(args.store)
    prev = CrossStore.load(ckpt) if ckpt.is_file() else None
    source = args.source
    kw: Dict[str, Any] = {}
    if source.startswith("file:"):
        from .corpus_en import iter_local_rows

        rows = iter_local_rows(Path(source[5:]))
        st = prev or CrossStore()
        if not args.no_two_pass:
            st.scan_cap_stats(iter_local_rows(Path(source[5:])))
        rep = st.ingest_rows(rows, max_sentences=args.max_sentences)
        st.source = source
        st.save(ckpt)
        _print({"pour": rep, "store": str(ckpt)})
        return 0
    st, rep = pour_corpus(
        source=source,
        max_rows=args.max_rows,
        max_sentences=args.max_sentences,
        checkpoint_path=ckpt,
        store=prev,
        two_pass=not args.no_two_pass,
        checkpoint_every=args.checkpoint_every,
        **kw,
    )
    _print({"pour": rep, "store": str(ckpt)})
    return 0


def cmd_remember(args) -> int:
    st = _load(args.store)
    key = st.ingest_sentence(args.text)
    st.save(Path(args.store))
    _print({"remembered": key, "facets": st.top_facets(key or "", 8)})
    return 0 if key else 1


def cmd_forget(args) -> int:
    st = _load(args.store)
    removed = []
    for key in (args.core, args.core + "#p"):
        if key in st.crosses:
            del st.crosses[key]
            st.core_count.pop(key, None)
            removed.append(key)
    st.save(Path(args.store))
    _print({"forgot": removed})
    return 0 if removed else 1


# --- W3-c4: the question cross as a LATER STAGE of `vera ask --mode round5 --document` (docs/OBSERVATION.md, 文書 QA の後段（W3-c4）) ---------------------------
# Only when the round5 reading stopped with one of these two abstentions (closed set, registered before the build) and a document was handed over: the sentences of the
# documents are observed from the cross of the question (observe.observe_question_records, in memory, no file). Anything else is returned as the same object.
_QC_TRIGGER = ("UNKNOWN_UNREAD", "UNKNOWN_NO_EVIDENCE")
_QC_SPLIT = r"(?<=。)|(?<=\.)(?=\s)"
_QC_PAIRS = (("「", "」"), ("『", "』"), ("“", "”"))


def _qc_records(documents):
    """Documents read as `one.Vera.load_documents` reads them -> ([{"id","text"}], {id: {"source","line","text"}}, loaded, skipped)."""
    from .document_loaders import load_directory, load_paths
    loaded, skipped = [], []
    for item in documents:
        path = Path(item)
        res = load_directory(str(path)) if path.is_dir() else load_paths([str(path)])
        loaded.extend(res["documents"])
        skipped.extend(res["skipped"])
    cut = re.compile(_QC_SPLIT)
    records, where = [], {}
    for doc in loaded:
        for line_no, line in enumerate(doc.text.split("\n"), 1):
            pieces = [x.strip() for x in cut.split(line) if x.strip()]
            for k, piece in enumerate(pieces, 1):
                sid = "%s#%d:%d" % (doc.source, line_no, k)
                records.append({"id": sid, "text": piece})
                # a '.' cut that may not be the end of a sentence (an abbreviation, an initial): the piece before it is one token ending in '.', or the
                # piece after it starts with a lower-case letter. Both pieces next to such a cut are possibly the middle of a sentence: never the evidence of an answer.
                after = k < len(pieces) and piece.endswith(".") and pieces[k][:1].islower()
                before = k > 1 and pieces[k - 2].endswith(".") and (len(pieces[k - 2].split()) == 1 or piece[:1].islower())
                where.setdefault(sid, {"source": doc.source, "line": line_no, "text": piece, "cut_uncertain": bool(after or before)})
    return records, where, len(loaded), [{"verdict": x.get("verdict"), "path": x.get("path")} for x in skipped]


def _qc_sources(evidence, where):
    """The sentences that attest a filler, in the observer's order, each sentence once."""
    out, seen = [], set()
    for ev in evidence:
        sid = ev["reading"]
        if sid in seen:
            continue
        seen.add(sid)
        w = where[sid]
        out.append({"family": "document", "source": w["source"], "line": w["line"], "text": w["text"], "sentence_id": sid})
    return out


def _qc_quotes_open(text):
    return any(text.count(a) != text.count(b) for a, b in _QC_PAIRS) or text.count('"') % 2 == 1


_QC_END = "。．.！!？? \t\r\n　"


def _qc_predicate_form(text, tail):
    """Round 2 (M1). The reader gives `読みたかった` / `読みたがった` / `読んだらしかった` / a final `読んだら` the same clause as the plain past `読んだ` (it does not see the
    conjugated mark). So an evidence sentence of Japanese is an answer only when its WRITTEN predicate (from the reader's span of the predicate to the end of the sentence) is the end
    of the question as it was written. None: it is. Otherwise the reason: PREDICATE_POSITION_UNKNOWN (no single clause / no span) or PREDICATE_FORM_DIFFERS. Reads only; no word list."""
    from . import semantic_read
    try:
        out = semantic_read.read(text)
    except Exception:
        return "PREDICATE_POSITION_UNKNOWN"
    if not isinstance(out, dict) or out.get("lang") != "ja":
        return None                                 # not applied to other languages (docs/OBSERVATION.md, 事前登録の変更記録 第 2 ラウンド)
    meta, clauses = out.get("clause_meta") or [], out.get("clauses") or []
    if not out.get("readable") or len(meta) != 1 or len(clauses) != 1 or not isinstance(meta[0], dict):
        return "PREDICATE_POSITION_UNKNOWN"
    span = meta[0].get("span")
    if not (isinstance(span, (list, tuple)) and len(span) == 2 and all(type(i) is int for i in span) and 0 <= span[0] <= span[1] <= len(text)):
        return "PREDICATE_POSITION_UNKNOWN"
    written = text[span[0]:].rstrip(_QC_END)
    return None if written and tail.endswith(written) else "PREDICATE_FORM_DIFFERS"


def _qc_wrap(result, qc, step_state, observed, mapped):
    """The ORIGINAL form: a shallow copy of the result plus `question_cross` and one step of the trace (the original is not modified)."""
    out = dict(result)
    out["question_cross"] = qc
    out["trace"] = list(result.get("trace") or []) + [{"part": "question_cross", "status": "ran" if observed else "abstained",
                                                        "state": step_state, "mapped_to": mapped}]
    return out


def _qc_info(state, reason, mapped, answer, coord, structure, documents):
    q = (answer or {}).get("question") or {}
    return {"state": state, "reason": reason, "mapped_to": mapped, "hole_role": q.get("hole_role"), "hole_type": q.get("hole_type"),
            "coord": coord, "structure": structure, "documents": documents}


def _qc_run(result, documents, query):
    from .observe import observe_question_records
    records, where, n_loaded, skipped = _qc_records(documents)
    docs_info = {"loaded": n_loaded, "skipped": skipped}
    if n_loaded == 0:
        return _qc_wrap(result, _qc_info("DOCUMENTS_NOT_LOADED", None, "ORIGINAL", None, None, None, docs_info), "DOCUMENTS_NOT_LOADED", False, "ORIGINAL")
    try:
        obs = observe_question_records(query, records)
    except ValueError as exc:
        marker = "BAD_ARGUMENTS:STRUCTURE_INVALID:"
        if not str(exc).startswith(marker):
            raise
        return _qc_wrap(result, _qc_info("STRUCTURE_INVALID", str(exc)[len(marker):], "ORIGINAL", None, None, None, docs_info), "STRUCTURE_INVALID", False, "ORIGINAL")
    answer = obs.get("answer")
    if not answer:
        return _qc_wrap(result, _qc_info("NOT_A_QUESTION", None, "ORIGINAL", None, None, None, docs_info), "NOT_A_QUESTION", False, "ORIGINAL")
    state = answer["status"]
    reasons = answer.get("reasons") or []
    structure = {"sentences": answer["structure"]["sentences"], "crossed": answer["structure"]["crossed"],
                 "unread": answer["structure"]["unread"], "reasons": reasons}
    coord = [c for rank in (obs.get("ranks") or [])[:1] for el in rank["elements"] for c in el["coords"]]
    reason = reasons[0] if reasons else None

    def original(why=None):
        return _qc_wrap(result, _qc_info(state, why or reason, "ORIGINAL", answer, None, structure, docs_info), state, True, "ORIGINAL")

    if state not in ("FILLED", "TIE"):
        return original()
    rows = answer["fillers"]
    cands = [(row["surface"], _qc_sources(row["evidence"], where)) for row in rows]
    tail = query.strip().rstrip("？?").rstrip()     # the question as written, without its final question mark
    for surface, srcs in cands:                     # a surface that is not in its own evidence, or evidence cut in the middle of a quotation, is not an answer
        if not any(surface in s["text"] for s in srcs):
            return original("SURFACE_NOT_IN_EVIDENCE")
        if any(_qc_quotes_open(s["text"]) for s in srcs):
            return original("QUOTE_UNBALANCED_EVIDENCE")
        if any(where[s["sentence_id"]]["cut_uncertain"] for s in srcs):
            return original("PERIOD_CUT_UNCERTAIN")
        for s in srcs:                              # the written predicate of the evidence is the end of the question (round 2, M1)
            why = _qc_predicate_form(s["text"], tail)
            if why:
                return original(why)
    if state == "FILLED" and len(rows) == 1:
        surface, srcs = cands[0]
        qc = _qc_info("FILLED", reason, "ANSWER", answer, coord, structure, docs_info)
        return {"kind": "answer", "verdict": "ANSWER", "text": surface, "values": [surface], "evidence": [s["text"] for s in srcs], "sources": srcs,
                "door": "question_cross", "question_cross": qc,
                "trace": list(result.get("trace") or []) + [{"part": "question_cross", "status": "ran", "state": "FILLED", "mapped_to": "ANSWER"}]}
    why = "SURFACES_DIFFER:%d" % len(rows) if state == "FILLED" else reason
    qc = _qc_info(state, why, "AMBIGUOUS_QUESTION_CROSS_TIE", answer, coord, structure, docs_info)
    return {"kind": "unknown", "verdict": "AMBIGUOUS_QUESTION_CROSS_TIE", "text": "",
            "candidates": [{"text": surface, "sources": srcs} for surface, srcs in cands], "sources": [], "evidence": [],
            "door": "question_cross", "question_cross": qc,
            "trace": list(result.get("trace") or []) + [{"part": "question_cross", "status": "ran", "state": state, "mapped_to": "AMBIGUOUS_QUESTION_CROSS_TIE"}]}


def _round5_question_cross(result, documents, query):
    if not (documents and isinstance(result, dict) and result.get("verdict") in _QC_TRIGGER):
        return result
    try:
        return _qc_run(result, documents, query)
    except Exception as exc:    # the one outer frame of the later stage: it must never break the abstention that was already there
        info = _qc_info("ERROR", "%s: %s" % (type(exc).__name__, exc), "ORIGINAL", None, None, None, None)
        return _qc_wrap(result, info, "ERROR", False, "ORIGINAL")


def cmd_ask(args) -> int:
    """一問一答。既定は手元の店、`--engine` で本線(engine.ask)を通す。

    CLI は `engine.ask` に一度も繋がっていなかった(2026-08-19、到達性の
    棚卸しと同じ形の欠陥)。独自の `_route`(math→code→knowledge)を持って
    いたため、公開連合・文書扉・配置不変/向き不変の門・REVERSE_UNIQUE —
    engine.ask が束ねている層のどれも CLI からは届かなかった。
    `--engine` はその単一入口を CLI にも開ける。既定は据え置き。
    """
    mode = getattr(args, "mode", "legacy")
    documents = list(getattr(args, "document", None) or [])
    if documents and mode != "round5":
        _print({"kind": "unknown", "verdict": "UNKNOWN_ROUTE_CONFIGURATION",
                "reason": "--document requires --mode round5"})
        return 2
    if getattr(args, "engine", False) and mode != "legacy":
        _print({"kind": "unknown", "verdict": "UNKNOWN_ROUTE_CONFIGURATION",
                "reason": "--engine and --mode round5 select separate routes"})
        return 2
    from .basis_policy import AskPolicy, apply_to_ask
    policy = AskPolicy.from_args(args)
    if isinstance(policy, dict):
        _print(policy)
        return 2
    if mode == "round5":
        from .one import Vera
        v = Vera(mode="round5")
        if documents:
            v.load_documents(documents)
        res = _round5_question_cross(v.ask(args.query), documents, args.query)
        out, rc = apply_to_ask(res, policy, query=args.query, mode="round5",
                               documents=documents)
        _print(out)
        return rc
    if getattr(args, "engine", False):
        from .engine import ask as engine_ask
        from .export_sqlite import vera as load_published
        from .paths import corpus_root

        db = Path(getattr(args, "federation", "") or
                  (corpus_root() / "build" / "vera.db"))
        if not db.is_file():
            _print({"verdict": "UNKNOWN_NOT_LOADED", "federation": str(db),
                    "note": "公開連合が見つからない。--federation で指定するか "
                            "build/vera.db を復元する"})
            return 1
        v = load_published(db)
        sp = Path(args.store)
        out, rc = apply_to_ask(engine_ask(args.query, v,
                                          store_path=sp if sp.is_file() or
                                          sp.with_suffix(".documents.json").is_file() else None),
                               policy, query=args.query, mode="engine", documents=documents)
        _print(out)
        return rc
    from .one import Vera
    st = _load(args.store)
    out, rc = apply_to_ask(Vera().load_store(st).ask(args.query), policy, query=args.query,
                           mode="legacy", documents=documents)
    _print(out)
    return rc


def _doors(store_path: str) -> Dict[str, Any]:
    """126扉を**走らせずに**取り出す。CLI と MCP は同じ扉を使う。

    扉ごとに CLI のコマンドを書き写すと二つの表面が必ずずれるので、
    入口だけを増やして実体は一つに保つ(2026-08-22)。
    """
    from .mcp_server import build

    mcp = build(store_path)
    if mcp is None:
        return {}
    return {t.name: t for t in mcp._tool_manager.list_tools()}


def _coerce(fn, kwargs: Dict[str, str]) -> Dict[str, Any]:
    """`k=v` を扉の型注釈に合わせる(閉じた4型のみ。推測しない)。"""
    import inspect

    sig = inspect.signature(fn)
    out: Dict[str, Any] = {}
    for k, v in kwargs.items():
        ann = sig.parameters[k].annotation if k in sig.parameters else str
        if ann is bool:
            out[k] = str(v).strip().lower() in ("1", "true", "yes", "on")
        elif ann is int:
            out[k] = int(v)
        elif ann is float:
            out[k] = float(v)
        else:
            out[k] = v
    return out


def _call_door(store_path: str, name: str, payload: Dict[str, Any]) -> int:
    doors = _doors(store_path)
    if not doors:
        _print({"verdict": "UNKNOWN_NO_MCP_SDK"})
        return 2
    if name not in doors:
        near = [n for n in doors if name in n][:8]
        _print({"verdict": "UNKNOWN_NO_SUCH_DOOR", "door": name,
                "did_you_mean": near, "doors": len(doors)})
        return 1
    out = doors[name].fn(**payload)
    try:
        _print(json.loads(out) if isinstance(out, str) else out)
    except Exception:              # 扉が素の文字列を返す場合はそのまま
        print(out)
    return 0


def cmd_tool(args) -> int:
    """MCP の扉を CLI から。IDE を経由せずに全機能へ届かせるための橋。"""
    doors = _doors(args.store)
    if not doors:
        _print({"verdict": "UNKNOWN_NO_MCP_SDK"})
        return 2
    if args.tool_op == "list":
        pat = (args.name or "").lower()
        rows = [{"door": n,
                 "about": " ".join((t.description or "").split())[:90]}
                for n, t in sorted(doors.items())
                if not pat or pat in n.lower()]
        _print({"doors": len(rows), "list": rows})
        return 0
    if not args.name:
        _print({"verdict": "UNKNOWN_NO_DOOR_NAMED"})
        return 1
    if args.tool_op == "show":
        t = doors.get(args.name)
        if t is None:
            return _call_door(args.store, args.name, {})
        import inspect

        print(f"{args.name}{inspect.signature(t.fn)}\n")
        print(inspect.getdoc(t.fn) or "(no docstring)")
        return 0
    # call
    payload: Dict[str, Any] = {}
    if args.json:
        payload.update(json.loads(args.json))
    pairs = {}
    for kv in (args.arg or []):
        if "=" not in kv:
            _print({"verdict": "UNKNOWN_BAD_ARG", "arg": kv})
            return 1
        k, v = kv.split("=", 1)
        pairs[k] = v
    t = doors.get(args.name)
    if t is not None and pairs:
        payload.update(_coerce(t.fn, pairs))
    return _call_door(args.store, args.name, payload)


def cmd_documents(args) -> int:
    """文書を CLI から入れる(PDF/Word/HTML/CSV/JSON/テキスト、フォルダ可)。

    実体は扉 `load_documents` — IDE と同じ経路を通す(別経路を書くと
    「IDE では入るが CLI では入らない」が生まれる)。
    """
    return _call_door(args.store, "load_documents",
                      {"paths": ",".join(args.paths),
                       "ingest": not args.no_ingest})


def cmd_domain(args) -> int:
    """分野(語彙)の登録と確認。実体は既存の扉。"""
    op = args.domain_op
    if op == "list":
        return _call_door(args.store, "vera_domains", {})
    if op == "add":
        if not (args.name and args.path):
            _print({"verdict": "UNKNOWN_NEEDS_NAME_AND_PATH"})
            return 1
        return _call_door(args.store, "vera_domain",
                          {"name": args.name, "path": args.path})
    if op == "pending":
        return _call_door(args.store, "list_pending_domain_modules", {})
    if op in ("accept", "reject"):
        if args.index is None:
            _print({"verdict": "UNKNOWN_NEEDS_INDEX"})
            return 1
        return _call_door(args.store, f"{op}_domain_module",
                          {"index": args.index})
    _print({"verdict": "UNKNOWN_OP", "op": op})
    return 1


#: 貼り先(閉じた表)。IDE の MCP 画面が発行していたスニペットを CLI へ
#: 移す(2026-08-22)。**書き込みは --install を打った人の行為**で、
#: 既定は表示だけ — 設定ファイルを黙って書き換えない。
_MCP_CLIENTS = {
    "claude-code": ".mcp.json",
    "claude-desktop": "~/Library/Application Support/Claude/"
                      "claude_desktop_config.json",
    "cursor": "~/.cursor/mcp.json",
}


def _vera_binary() -> List[str]:
    """この機械で MCP を起動する実際のコマンド(推測しない)。"""
    import shutil
    import sys as _s

    vendor = Path.home() / ("Projects/Verantyx/cli/VerantyxIDE/Vendor/"
                            "vera-memory")
    if getattr(_s, "frozen", False):
        return [_s.executable]
    if vendor.exists():
        return [str(vendor)]
    found = shutil.which("vera-memory")
    if found:
        return [found]
    return [_s.executable, "-m", "verantyx.cli"]


def cmd_mcp_config(args) -> int:
    """MCP の設定スニペットを出す(必要なら貼る)。

    IDE の MCP 画面がやっていた仕事のうち、CLI に無かったのはこれ。
    他サーバの接続管理は Claude Code 自身の機能なので写さない
    (同じ仕事を二つ持つと必ずずれる)。
    """
    store = str(Path(args.store or DEFAULT_STORE).resolve())
    cmd = _vera_binary()
    entry = {"command": cmd[0],
             "args": cmd[1:] + ["--store", store, "mcp"]}
    snippet = {"mcpServers": {"vera-memory": entry}}
    targets = ([(k, v) for k, v in _MCP_CLIENTS.items()]
               if args.client == "all"
               else [(args.client, _MCP_CLIENTS[args.client])])
    out = {"verdict": "ANSWER", "snippet": snippet,
           "targets": {k: str(Path(v).expanduser()) for k, v in targets},
           "note": "既定は表示のみ。--install で貼る(貼るのは打った人の行為)"}
    if args.install:
        wrote = {}
        for name, rel in targets:
            path = (Path(rel).expanduser() if rel.startswith("~")
                    else Path.cwd() / rel)
            try:
                cur = json.loads(path.read_text(encoding="utf-8")) \
                    if path.is_file() else {}
            except Exception:
                out["verdict"] = "UNKNOWN_UNREADABLE_CONFIG"
                wrote[name] = "読めない設定があるので触らない"
                continue
            servers = dict(cur.get("mcpServers") or {})
            servers["vera-memory"] = entry     # 同名だけ差し替える
            cur["mcpServers"] = servers
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cur, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            wrote[name] = str(path)
        out["installed"] = wrote
    _print(out)
    return 0


def cmd_index(args) -> int:
    """「それは既に在るか」に答える索引 — 実装の前に必ずここを引く。

    67,145行・129扉・89 fork は誰の作業記憶にも文脈窓にも入らない。
    索引が無いと、人もモデルも既にあるものを作り直す(実際に起きた)。
    索引はコードと文書から**その場で導出**するので、古くならない。
    """
    from .index import build, markdown, search

    if args.index_op == "build":
        idx = build()
        _print({"verdict": "ANSWER", "counts": idx["counts"],
                "total": idx["total"], "root": idx["root"]})
    elif args.index_op == "markdown":
        text = markdown()
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            _print({"verdict": "ANSWER", "wrote": args.out,
                    "bytes": len(text.encode("utf-8"))})
        else:
            print(text)
    else:
        _print(search(" ".join(args.query), limit=args.limit))
    return 0


def cmd_read_events(args) -> int:
    """文を読み、事象の十字(述語が中心・役割が腕・語が充填物)を `events` 欄に足して 1 行で返す。

    `python -m verantyx.semantic_read --text=... --events` と同じ関数を通すので出力は 1 バイトも違わない。
    """
    from . import semantic_read

    argv = []
    if args.text is not None:
        argv.append("--text=" + args.text)
    if args.lang is not None:
        argv.append("--lang=" + args.lang)
    argv.append("--events")
    return semantic_read.main(argv)


def cmd_read(args) -> int:
    """W10-f04 (docs/FUSION.md section 6, J1): `vera read --text T [--lang L] [--placement DIR]` is `python -m verantyx.semantic_read` (byte for byte); with `--holes` the sentence a reader abstains
    on because of a filler's placement is returned with its typed holes (`semantic_read.read_with_holes`) and a `display` of them."""
    from . import semantic_read

    if not getattr(args, "holes", False):
        argv = []
        if args.text is not None:
            argv.append("--text=" + args.text)
        if args.lang is not None:
            argv.append("--lang=" + args.lang)
        if args.placement is not None:
            argv.append("--placement=" + args.placement)
        mode = _read_mode(args)
        if mode is None:
            _print({"error": {"type": "BAD_READ_MODE", "detail": "VERA_READ_MODE must be strict or assume"}})
            return 2
        if mode == "strict":
            return semantic_read.main(argv)
        return _read_assume(args, argv, semantic_read)
    from . import observe
    try:
        out = semantic_read.read_with_holes(args.text, args.lang, placement=semantic_read._UNSET if args.placement is None else args.placement,
                                            max_holes=args.max_holes)
        out["display"] = observe.describe_holes(out, args.text)
        code = 0
    except semantic_read.ReadError as err:
        out, code = {"error": {"type": err.type, "detail": err.detail}}, 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return code


def _chat_read(args, text) -> int:
    """W3-e2 (D3): `/read` of the chat: in the assume mode (the default; `--strict-read` / VERA_READ_MODE=strict turn it off) a sentence that stops only on a premise is printed as an assumed reading (or with the
    reason of stage E2 at the end); every other sentence goes through `cmd_read_events` exactly as before."""
    from . import semantic_read

    mode = _read_mode(args)
    plain = argparse.Namespace(text=text, lang=None)
    if mode is None:
        _print({"error": {"type": "BAD_READ_MODE", "detail": "VERA_READ_MODE must be strict or assume"}})
        return 2
    if mode == "strict":
        return cmd_read_events(plain)
    try:
        out = semantic_read.read_in_mode(text, None, mode="assume", assume=semantic_read.AssumeConfig())
    except semantic_read.ReadError:
        return cmd_read_events(plain)
    reasons = (out.get("abstain") or {}).get("reasons") or []
    if out.get("read_mode") == "assumed" or any(str(r).startswith(("ASSUMPTION_UNDETERMINED", "ASSUMPTION_BACKEND_FAILED")) for r in reasons):
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        return 0
    return cmd_read_events(plain)


def _read_mode(args):
    """W3-e2 (K333): the mode of a product entry that reads a sentence. `--strict-read` -> strict; else VERA_READ_MODE (strict | assume; anything else -> None, a typed refusal of the caller); else assume.
    Only the entries (vera read / chat / serve) call this: the library reads no variable (`semantic_read.read_in_mode`)."""
    import os

    if getattr(args, "strict_read", False):
        return "strict"
    v = os.environ.get("VERA_READ_MODE")
    if v is None or v.strip() == "":
        return "assume"
    return v.strip() if v.strip() in ("strict", "assume") else None


def _assume_config(args, ledger=None):
    """W3-e2: the `AssumeConfig` of an entry: the layer is the environment's (`--layer` sets VERA_PLACEMENT_LAYER); the ledger when `--ledger-file` is given; the back end (source (e)) only when
    `--backend` and `--model` are given (never by default: nothing leaves the machine unasked)."""
    from . import llm_backend
    from . import semantic_read

    chat, model = None, None
    backend = getattr(args, "assume_backend", None)
    if backend:
        model = getattr(args, "assume_model", None)
        chat = llm_backend.make_chat(backend, timeout=getattr(args, "llm_timeout", 180.0))
    return semantic_read.AssumeConfig(ledger=ledger, chat=chat, model=model, backend_name=backend or "fake")


def _read_assume(args, argv, semantic_read) -> int:
    """W3-e2 (D3): `vera read` in the assume mode prints what `semantic_read.main` prints byte for byte whenever stage E2 changed nothing; only an assumed reading, or a strict abstention with a
    reason of the stage at the end, is printed in the form of `read_in_mode`."""
    from .llm_choice import LedgerIntegrityError
    from .testimony_ledger import TestimonyLedger

    ledger = None
    if getattr(args, "ledger_file", None):
        try:
            ledger = TestimonyLedger(args.ledger_file)
        except LedgerIntegrityError as exc:
            _print({"error": {"type": "LEDGER_INTEGRITY", "detail": "%s line %s %s" % (exc.kind, exc.line_no, exc.detail)}})
            return 2
    try:
        out = semantic_read.read_in_mode(args.text, args.lang, placement=semantic_read._UNSET if args.placement is None else args.placement, mode="assume",
                                         assume=_assume_config(args, ledger))
    except semantic_read.ReadError:
        return semantic_read.main(argv)
    reasons = (out.get("abstain") or {}).get("reasons") or []
    if out.get("read_mode") == "assumed" or any(str(r).startswith(("ASSUMPTION_UNDETERMINED", "ASSUMPTION_BACKEND_FAILED")) for r in reasons):
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        return 0
    return semantic_read.main(argv)


def _ledger_promote(args, led) -> int:
    """W10-f05 (O3, docs/COARSE_PLACEMENT.md section 12.19): `vera ledger promote --layer L [--placement BASE] [--promote-n N]` writes the promotable rows of the ledger into the layer: a human's
    confirmation as `layer_human` (direct), a re-reading agreement alone as `layer_estimated` (never direct); every write is a `promoted_to_layer` row of the ledger first. A word the base already decides
    is skipped; running it again writes nothing new. One JSON line: what was written (per origin) and why the rest was not."""
    import os
    from collections import Counter
    from . import coarse_place, placement_layer

    def refuse(verdict: str, reason: str = "") -> int:
        _print({"kind": "unknown", "verdict": verdict, "reason": reason})
        return 2

    if not args.layer:
        return refuse("LAYER_REQUIRED", "ledger promote needs --layer")
    layer_path, layer_name, why = placement_layer.resolve(args.layer)
    if layer_path is None:
        return refuse("LAYER_UNAVAILABLE:%s" % why, args.layer)
    placement = args.placement or os.environ.get("VERA_PLACEMENT") or None
    pl, nop = coarse_place._open(placement)
    if pl is None:
        return refuse("NO_PLACEMENT", nop[0] if nop else "UNSET")
    plan = led.promotion_plan(layer_name, lambda w: coarse_place.query(w, placement=placement, layer=False))
    written, skipped, items = Counter(), Counter(), []
    for it in plan:
        if it["origin"] is None:
            skipped[it["skip"]] += 1
            items.append({"word": it["word"], "type": it["declared_type"], "skip": it["skip"]})
            continue
        try:
            res = placement_layer.write_entry(layer_path, led, base_sha256=pl.sha, word=it["word"], type=it["declared_type"], origin=it["origin"], decided_by=it["decided_by"],
                                              evidence=it["evidence"], role_frame=it["role_frame"], key=it["key"], fill_id=it["fill_id"], candidate=it["candidate"], from_seq=it["from_seq"])
        except placement_layer.LayerError as exc:
            return refuse(exc.type, exc.detail)
        written[it["origin"]] += 1
        items.append({"word": it["word"], "type": it["declared_type"], "origin": it["origin"], "ledger_seq": res["ledger_seq"]})
    _print({"kind": "promoted", "layer": layer_name, "written": {o: written.get(o, 0) for o in placement_layer.ORIGINS}, "skipped": dict(sorted(skipped.items())), "items": items})
    return 0


def cmd_ledger(args) -> int:
    """W10-f04 (O2, docs/FUSION.md section 6.2 K284): the testimony ledger. `list` (one line per adopted candidate: id, word -> candidate, declared type, state, promotable), `show <id>` (every row of
    that testimony and its folded state), `confirm <id>` (a human confirms: writes `human_confirmed` with the ledger's store_id and a new confirm_id). Never changes a placement. Exit 2: a bad
    argument or no such id; 3: the ledger is broken (nothing is appended)."""
    from .llm_choice import LedgerIntegrityError
    from .testimony_ledger import LedgerError, TestimonyLedger

    path = Path(args.ledger_file)
    if args.ledger_op not in ("list", "promote") and not args.id:
        _print({"kind": "unknown", "verdict": "ID_REQUIRED", "reason": "ledger %s needs an id" % args.ledger_op})
        return 2
    if not path.exists():
        _print({"kind": "unknown", "verdict": "LEDGER_NOT_FOUND", "reason": str(path)})
        return 2
    try:
        led = TestimonyLedger(path, promote_n=args.promote_n)
        if args.ledger_op == "promote":
            return _ledger_promote(args, led)
        if args.ledger_op == "list":
            rows = led.listing()
            if args.json:
                _print({"store_id": led.store_id, "promote_n": led.promote_n, "testimonies": rows})
            else:
                print("store_id=%s promote_n=%d testimonies=%d" % (led.store_id, led.promote_n, len(rows)))
                for r in rows:
                    print("%s  %s -> %s  type=%s role=%s  state=%s  promotable=%s%s" % (r["fill_id"], r["word"], r["candidate"], r["declared_type"], r["role"], r["state"],
                                                                                   "yes" if r["promotable"] else "no", "  (%s)" % r["blocked_by"] if r["blocked_by"] else ""))
            return 0
        if args.ledger_op == "show":
            shown = led.show(args.id)
            if shown is None:
                _print({"kind": "unknown", "verdict": "NO_SUCH_ID", "reason": args.id})
                return 2
            _print(shown)
            return 0
        _print(dict(led.confirm(args.id), kind="human_confirmed"))
        return 0
    except LedgerIntegrityError as exc:
        _print({"kind": "unknown", "verdict": "LEDGER_INTEGRITY", "reason": "%s line %s %s" % (exc.kind, exc.line_no, exc.detail)})
        return 3
    except LedgerError as exc:
        _print({"kind": "unknown", "verdict": exc.type, "reason": exc.detail})
        return 2


def cmd_realize(args) -> int:
    """十字トークン列を検証し、Vera の既存実現器で文に戻す。"""
    from .cross_tokens import realize_tokens

    tokens = sys.stdin.read() if args.tokens == "-" else args.tokens
    if args.tokens == "-" and tokens.endswith("\n"):
        tokens = tokens[:-1]
        if tokens.endswith("\r"):
            tokens = tokens[:-1]
    # W3-d1: `--forms` lays a user's forms table (added styles / endings) over the base table; a refused table is a typed result and exit code 2.
    result = realize_tokens(tokens, args.lang, placement=args.placement, forms=args.forms)
    _print(result)
    return 2 if result.get("reason") in ("FORMS_OVERRIDE_REFUSED", "FORMS_INVALID", "FORMS_NOT_FOUND") else 0


def cmd_observe(args) -> int:
    """視点(錨・向き・範囲・状態)から構造を観測し、見えた十字を実現器で文にして json で 1 行返す(docs/OBSERVATION.md)。

    処理はすべて `verantyx.observe.run_entry`。ここは引数を渡して結果を出すだけ。
    終了コード: 0 = 型付きの結果(棄権・TIE を含む)、2 = 引数の誤り、3 = 台帳ファイルが壊れている(何も追記しない)。
    """
    from . import observe

    result = observe.run_entry(
        anchor_text=args.anchor_text, anchor_record=args.anchor_record, anchor_kind=args.anchor_kind,
        anchor_cross=args.anchor_cross, lang=args.lang, direction=args.direction, range_=args.range,
        structure_path=args.structure, index_root=args.index, index_families=tuple(args.index_family or ("pro",)),
        no_index=args.no_index, placement_path=args.placement, ledger_path=args.ledger)
    if result.error is not None:
        print(json.dumps(result.error, ensure_ascii=False), file=sys.stderr)
    else:
        print(result.stdout)
    return result.exit_code

def cmd_route(args) -> int:
    """人間の自由文の説明と仕事 1 件を受け取り、説明を読んで分業の記録を作り、経路づけて 1 行で返す(W2-h2)。

    読めなかった文が 1 つでもあれば振らない(型付きの棄権)。決定でも棄権でも終了コード 0、入力の誤りは 2。
    """
    from . import routing_from_text

    return routing_from_text.emit(args.explanation, args.task)


def cmd_doctor(args) -> int:
    """入れた直後に叩く自己検査 — 二つの顔を1回で確かめる。

    番人(フック)の G1〜G4 と、単体の装置の S1〜S4 を**その場で実演**
    する。利用者の店にも台帳にも触らない(治具は毎回その場で作る)。
    片方が壊れていれば全体は BROKEN で、終了コードは1。
    """
    from .doctor import full_doctor

    out = full_doctor()
    _print(out)
    return 1 if out.get("verdict") == "BROKEN" else 0


def cmd_stats(args) -> int:
    st = _load(args.store)
    top = sorted(st.core_count.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    _print({**st.report(), "top_cores": top})
    return 0


def cmd_heartbeat(args) -> int:
    """Milestone M: scans growth_signals.json for recurring UNKNOWN
    patterns, drafts+verifies a candidate module via an LLM if one clears
    the boundary detector, and queues it for human review — never
    auto-activates. Intended for a daily cron/launchd job, not per-turn."""
    from . import boundary, domains
    from .growth_signals import GrowthSignals, growth_signals_path
    from .llm_local import ollama_available
    from .module_forge import build_test_queries, draft_module
    from .module_ingest import DomainModuleQuarantine
    from .module_verify import verify_module

    st = _load(args.store)
    store_path = Path(args.store)
    pkg_dir = Path(__file__).resolve().parent
    domains.register_builtins()
    domains.register_generated(pkg_dir)

    gpath = growth_signals_path(store_path)
    growth = GrowthSignals.load(gpath)
    drifted = growth.record_mass_snapshot(st)

    mqpath = store_path.with_name(store_path.stem + ".module_quarantine.json")
    module_quarantine = DomainModuleQuarantine.load(mqpath)

    candidates, drafted_out = [], []
    for bucket in growth.buckets.values():
        verdict = boundary.classify(bucket)
        if verdict.classification != "growth_candidate":
            continue
        candidates.append({"normalized": bucket.normalized, "reason": verdict.reason})
        if not args.llm_model or not ollama_available():
            continue
        draft = draft_module(bucket, args.llm_model)
        if not draft["ok"]:
            drafted_out.append({"normalized": bucket.normalized, "ok": False, "error": draft["error"]})
            continue
        ok, reports = verify_module(draft["source"], build_test_queries(bucket), st, draft["name"])
        report_dicts = [r.as_dict() for r in reports]
        if ok:
            module_quarantine.propose(draft["name"], draft["source"], bucket.normalized, report_dicts)
            drafted_out.append({"normalized": bucket.normalized, "ok": True, "name": draft["name"], "queued": True})
        else:
            drafted_out.append({"normalized": bucket.normalized, "ok": False, "verify_reports": report_dicts})

    # Capacity pass — same helper the MCP heartbeat uses, so the CLI and
    # server cannot drift apart in what a heartbeat means.
    from .capacity_calibration import capacity_pass
    from .capacity_ingest import CapacityQuarantine
    from .config import VeraConfig

    cqpath = store_path.with_name(store_path.stem + ".capacity_quarantine.json")
    capacity_quarantine = CapacityQuarantine.load(cqpath)
    capacity = capacity_pass(
        list(growth.buckets.values()), VeraConfig.load(), capacity_quarantine)
    if any(r.get("queued") for r in capacity):
        capacity_quarantine.save(cqpath)

    growth.save(gpath)
    module_quarantine.save(mqpath)
    _print({"drifted_cores": drifted, "growth_candidates": candidates,
            "drafted": drafted_out, "capacity": capacity})
    return 0


def _quarantine_path(args) -> Path:
    return Path(args.store).with_suffix("").with_name(
        Path(args.store).stem + ".ai_quarantine.json"
    )


def cmd_propose_ai_facts(args) -> int:
    """Feed an assistant's FINAL text (never a thinking block) into
    quarantine — nothing here is queryable until accepted."""
    from .ai_ingest import AiFactQuarantine

    qpath = _quarantine_path(args)
    q = AiFactQuarantine.load(qpath)
    added = q.propose(args.text, source=args.source)
    q.save(qpath)
    _print({"proposed": [e.text for e in added], "quarantine": str(qpath)})
    return 0


def cmd_review_ai_facts(args) -> int:
    from .ai_ingest import AiFactQuarantine
    from .tui import select

    qpath = _quarantine_path(args)
    q = AiFactQuarantine.load(qpath)
    pending = q.pending()
    if not pending:
        print("no pending AI-proposed facts")
        return 0

    if args.list:
        _print([e.as_dict() for e in pending])
        return 0

    st = _load(args.store)
    store_path = Path(args.store)
    for entry in list(pending):  # snapshot: entries resolve as we go
        choice = select(
            f"[{entry.source}] {entry.text}",
            ["Accept → remember in trusted store", "Reject", "Skip (decide later)"],
            default=0,
        )
        if choice == 0:
            key = q.accept(entry, st)
            st.save(store_path)
            print(f"  accepted → core={key}")
        elif choice == 1:
            q.reject(entry)
            print("  rejected")
        else:
            break
    q.save(qpath)
    return 0


def cmd_chat(args) -> int:
    if getattr(args, "mode", "lab") == "round5":
        import os
        import shlex
        import tempfile

        from . import observe
        from .basis_policy import AskPolicy, apply_to_ask
        from .one import Vera
        from .tui import read_input

        if getattr(args, "engine", False):
            _print({"kind": "unknown", "verdict": "UNKNOWN_ROUTE_CONFIGURATION",
                    "reason": "--engine cannot be combined with --mode round5; Round5 chat uses one.Vera.ask"})
            return 2

        documents = list(getattr(args, "document", []) or [])
        one_v = Vera(mode="round5")
        loaded = one_v.load_documents(documents) if documents else {"loaded": 0, "skipped": []}
        if documents:
            print(f"[round5] 読込文書: {loaded['loaded']}件（この対話のみ）")
            for skipped in loaded["skipped"]:
                print(f"[round5] 読込保留: {skipped}")
        else:
            print("[round5] 読込文書: 0件（この対話のみ）")

        placement = os.environ.get("VERA_PLACEMENT", "").strip()
        if not placement:
            print("[round5] 配置: 配置無し; 型の質問観測は動きません")
        else:
            placement_path = Path(placement)
            placement_sha = None
            try:
                if placement_path.is_dir():
                    manifest_path = placement_path / "manifest.json"
                    if manifest_path.is_file():
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        value = manifest.get("content_sha256") if isinstance(manifest, dict) else None
                        if isinstance(value, str) and value:
                            placement_sha = value
                    if placement_sha is None:
                        database_path = placement_path / "placement.sqlite"
                        if database_path.is_file():
                            placement_sha = hashlib.sha256(database_path.read_bytes()).hexdigest()
                elif placement_path.is_file():
                    placement_sha = hashlib.sha256(placement_path.read_bytes()).hexdigest()
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                placement_sha = None
            if placement_sha is None:
                print(f"[round5] 配置: 設定あり ({placement}); content_sha256=UNKNOWN_UNREADABLE")
            else:
                print(f"[round5] 配置: 設定あり ({placement}); content_sha256={placement_sha}")

        originals = getattr(getattr(one_v, "bot", None), "original_texts", {})
        source_count = len(originals) if isinstance(originals, dict) else 0
        print(f"[round5] 読込文書数: {source_count}")
        print("[round5] 使える経路: 質問 — Vera.ask → _round5_question_cross → basis_policy.apply_to_ask")
        print("[round5] 使える経路: 生成 — observe.run_entry (文書構造を観測)")
        print("[round5] 使える経路: 分業 — cmd_route → routing_from_text.emit")
        print("[round5] 使える経路: 読解 — semantic_read.read / event_cross.attach_events")
        print("[round5] コマンド: /doc <path>, /docs, /gen <text> [FACE_SWAP:role|EDGE:relation] [range], "
              "/route <explanation> <task-json>, /read <text>, /json on|off, /help, /quit")
        observe_placement = getattr(args, "placement", None)
        if observe_placement:
            print(f"[round5] 生成配置JSON: {observe_placement}")
        else:
            print("[round5] 生成配置JSON: 無し")

        json_enabled = bool(getattr(args, "json", False))

        def loaded_sources() -> dict:
            bot = getattr(one_v, "bot", None)
            current = getattr(bot, "original_texts", {})
            return current if isinstance(current, dict) else {}

        def show_round5_result(out: dict) -> None:
            status = out.get("status")
            verdict = out.get("verdict")
            if status == "PARTIAL_COMPLETENESS_UNVERIFIED" or verdict == "PARTIAL":
                print("PARTIAL_COMPLETENESS_UNVERIFIED")
                _print_round5_chat_result(out, one_v)
                policy = out.get("basis_policy")
                outcome = policy.get("outcome") if isinstance(policy, dict) else "UNKNOWN"
                print(f"basis_policy.outcome: {outcome}")
                return

            label = verdict
            if not isinstance(label, str) or not label:
                abstain = out.get("abstain")
                label = abstain.get("type") if isinstance(abstain, dict) else "UNKNOWN_RESULT"
            print(label)
            if verdict == "ANSWER" or out.get("kind") == "answer":
                body = out.get("text")
                if isinstance(body, str) and body:
                    print(f"答え: {body}")
            elif isinstance(out.get("reason"), str) and out["reason"]:
                print(f"理由: {out['reason']}")

            evidence_printed = False
            source_texts = loaded_sources()
            sources = out.get("sources")
            if isinstance(sources, (list, tuple)):
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    source_name = source.get("source") or source.get("id")
                    sentence = source.get("text")
                    if not isinstance(source_name, str) or not isinstance(sentence, str):
                        continue
                    line_no = source.get("line")
                    if type(line_no) is not int:
                        span = source.get("span")
                        start = span.get("start") if isinstance(span, dict) else None
                        original = source_texts.get(source_name)
                        if type(start) is int and isinstance(original, str) and 0 <= start <= len(original):
                            line_no = original[:start].count("\n") + 1
                    if type(line_no) is int:
                        print(f"根拠: {source_name}:{line_no}: {sentence}")
                    else:
                        print(f"根拠: {source_name}: {sentence}")
                    evidence_printed = True
            if not evidence_printed:
                evidence = out.get("evidence")
                if isinstance(evidence, (list, tuple)):
                    for item in evidence:
                        if isinstance(item, str):
                            print(f"根拠(返却値): {item}")

            policy = out.get("basis_policy")
            outcome = policy.get("outcome") if isinstance(policy, dict) else "UNKNOWN"
            print(f"basis_policy.outcome: {outcome}")

        def show_observation(stdout: str) -> None:
            try:
                result = json.loads(stdout)
            except (TypeError, json.JSONDecodeError):
                print(stdout, end="" if stdout.endswith("\n") else "\n")
                return

            claims = {"OBSERVED_OCCUPIED": "OBSERVED", "CONSTRUCTED_UNOCCUPIED": "CONSTRUCTED"}
            displayed = 0

            def show_element(element: Any) -> None:
                nonlocal displayed
                if not isinstance(element, dict):
                    return
                displayed += 1
                claim = claims.get(element.get("claim"), "UNKNOWN")
                realization = element.get("realization")
                sentence = realization.get("text") if isinstance(realization, dict) else None
                print(f"{claim}: {sentence if isinstance(sentence, str) and sentence else '実現文なし'}")
                coords = element.get("coords")
                if coords is not None:
                    print("座標: " + json.dumps(coords, ensure_ascii=False, separators=(",", ":")))

            show_element(result.get("anchor"))
            for rank in result.get("ranks", []):
                if isinstance(rank, dict):
                    for element in rank.get("elements", []):
                        show_element(element)
            focus = result.get("focus")
            focus_kind = focus.get("kind") if isinstance(focus, dict) else None
            if focus_kind == "NO_MOVE_LICENSED":
                print("UNKNOWN: 配置近傍の無い移動先は未確認です (NO_MOVE_LICENSED)")
            if displayed == 0:
                print(f"UNKNOWN: 観測要素なし ({focus_kind or 'UNKNOWN'})")

        def bad_command(verdict: str, **fields: Any) -> None:
            _print({"kind": "unknown", "verdict": verdict, **fields})

        while True:
            raw = read_input("入力> ")
            if raw is None:
                print()
                break
            line = raw.strip()
            if not line:
                continue
            if line == "/quit":
                break
            if not line.startswith("/"):
                ask_args = argparse.Namespace(
                    query=raw, mode="round5", document=list(documents),
                    request_kind=getattr(args, "request_kind", "factual"),
                    human_present=getattr(args, "human_present", False),
                    show_generated_reference=getattr(args, "show_generated_reference", False), confirm=None,
                )
                policy = AskPolicy.from_args(ask_args)
                if isinstance(policy, dict):
                    out, _rc = policy, 2
                else:
                    result = _round5_question_cross(one_v.ask(raw), documents, raw)
                    out, _rc = apply_to_ask(result, policy, query=raw, mode="round5", documents=documents)
                if json_enabled:
                    _print(out)
                else:
                    show_round5_result(out)
                continue

            command_match = re.match(r"(\S+)(?:\s+(.*))?$", line, re.DOTALL)
            command = command_match.group(1) if command_match else line
            argument = command_match.group(2) if command_match and command_match.group(2) else ""
            if command == "/help":
                print("コマンド: /doc <path>, /docs, /gen <text> [FACE_SWAP:role|EDGE:relation] [range], "
                      "/route <explanation> <task-json>, /read <text>, /json on|off, /help, /quit")
            elif command == "/json":
                try:
                    values = shlex.split(argument)
                except ValueError as exc:
                    bad_command("UNKNOWN_BAD_ARGUMENTS", command=command, detail=str(exc))
                    continue
                if values == ["on"]:
                    json_enabled = True
                    print("JSON: on")
                elif values == ["off"]:
                    json_enabled = False
                    print("JSON: off")
                else:
                    bad_command("UNKNOWN_BAD_ARGUMENTS", command=command, want=["on", "off"])
            elif command == "/doc":
                try:
                    values = shlex.split(argument)
                except ValueError as exc:
                    bad_command("UNKNOWN_BAD_ARGUMENTS", command=command, detail=str(exc))
                    continue
                if len(values) != 1 or not values[0]:
                    bad_command("UNKNOWN_BAD_ARGUMENTS", command=command, want="one document path")
                    continue
                path = values[0]
                try:
                    loaded_doc = one_v.load_documents([path])
                except (OSError, ValueError) as exc:
                    bad_command("UNKNOWN_DOCUMENT_LOAD", path=path, detail=f"{type(exc).__name__}: {exc}")
                    continue
                documents.append(path)
                print(f"読み込み: {path} (source documents={loaded_doc.get('loaded', 0)})")
                for skipped in loaded_doc.get("skipped", []):
                    print(f"読み込み保留: {skipped}")
            elif command == "/docs":
                names = list(loaded_sources())
                if not names:
                    print("読み込み済み文書: なし")
                else:
                    print("読み込み済み文書:")
                    for name in names:
                        print(f"  {name}")
            elif command == "/gen":
                work = argument.rstrip()
                range_value = None
                range_match = re.search(r"\s+([0-9]+)$", work)
                if range_match:
                    range_value = int(range_match.group(1))
                    work = work[:range_match.start()].rstrip()
                direction = ""
                direction_match = re.search(
                    r"\s+((?:FACE_SWAP|EDGE):[^,\s]+(?:,(?:FACE_SWAP|EDGE):[^,\s]+)*)$", work)
                if direction_match:
                    direction = direction_match.group(1)
                    work = work[:direction_match.start()].rstrip()
                anchor_text = work.strip()
                if anchor_text[:1] in ("'", '"'):
                    try:
                        quoted = shlex.split(anchor_text)
                    except ValueError as exc:
                        bad_command("UNKNOWN_BAD_ARGUMENTS", command=command, detail=str(exc))
                        continue
                    if len(quoted) == 1:
                        anchor_text = quoted[0]
                try:
                    records, _where, _loaded_count, _skipped = _qc_records(documents)
                    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", newline="\n") as structure_file:
                        for record in records:
                            structure_file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                        structure_file.flush()
                        structure_file.seek(0)
                        observation = observe.run_entry(
                            anchor_text=anchor_text, anchor_kind="seed", direction=direction, range_=range_value,
                            structure_path=f"/dev/fd/{structure_file.fileno()}", placement_path=observe_placement,
                        )
                except (OSError, ValueError) as exc:
                    bad_command("UNKNOWN_GENERATION_INPUT", detail=f"{type(exc).__name__}: {exc}")
                    continue
                if observation.error is not None:
                    if not observe_placement:
                        print("NO_MOVE_LICENSED: 配置の近傍が無いため面の移動は許可されません",
                              file=sys.stderr if json_enabled else sys.stdout)
                    _print(observation.error)
                else:
                    if not observe_placement:
                        print("NO_MOVE_LICENSED: 配置の近傍が無いため面の移動は許可されません",
                              file=sys.stderr if json_enabled else sys.stdout)
                    if json_enabled:
                        sys.stdout.write(observation.stdout)
                    else:
                        show_observation(observation.stdout)
            elif command == "/route":
                route_match = re.match(r'''(?s)\s*(?:"([^"]+)"|'([^']+)'|(\S+))\s+(.+?)\s*$''', argument)
                if not route_match:
                    bad_command("UNKNOWN_BAD_ARGUMENTS", command=command, want="explanation path and task JSON or path")
                    continue
                explanation = route_match.group(1) or route_match.group(2) or route_match.group(3)
                task_argument = route_match.group(4).strip()
                cmd_route(argparse.Namespace(explanation=explanation, task=task_argument))
            elif command == "/read":
                _chat_read(args, argument)
            else:
                bad_command("UNKNOWN_COMMAND", command=command)

        return 0

    from .config import VeraConfig
    from .one import Vera

    round5 = args.mode == "round5"
    documents = list(getattr(args, "document", []) or [])
    if documents and not round5:
        _print({"kind": "unknown", "verdict": "UNKNOWN_ROUTE_CONFIGURATION",
                "reason": "--document requires --mode round5"})
        return 2
    if round5 and getattr(args, "engine", False):
        _print({"kind": "unknown", "verdict": "UNKNOWN_ROUTE_CONFIGURATION",
                "reason": "--engine cannot be combined with --mode round5; Round5 chat uses one.Vera.ask"})
        return 2

    if round5:
        # The explicit experimental route stays local and uses the public
        # one.Vera.ask API. Source documents are session inputs, not persisted.
        st = _load(args.store)
        one_v = Vera(mode="round5").load_store(st)
        if documents:
            loaded = one_v.load_documents(documents)
            print(f"[round5] loaded {loaded['loaded']} source document(s) for this session")
            for skipped in loaded["skipped"]:
                print(f"[round5] skipped source: {skipped}")
    else:
        cfg = VeraConfig.load()
        st = _load(args.store, base_repo=cfg.hf_store_repo)
        one_v = Vera().load_store(st)
    store_path = Path(args.store)

    if args.mode == "hybrid":
        print("[one.Vera] this answering path uses structural sources only")

    from .tui import read_input

    # 本線(engine.ask)を通すか。連合の読み込みは**起動時に一度だけ** —
    # 1問ごとに読むと毎回7秒かかる(読み込み後は1問40ms)。
    engine_v = None
    if getattr(args, "engine", False):
        from .export_sqlite import vera as load_published
        from .paths import corpus_root

        db = Path(getattr(args, "federation", "") or
                  (corpus_root() / "build" / "vera.db"))
        if not db.is_file():
            print(f"[engine] 公開連合が見つかりません: {db}")
            print("[engine] --federation で場所を指定するか、build/vera.db を"
                  "復元してください。手元の店だけで続けます。")
        else:
            print(f"[engine] 連合を読み込み中… {db}")
            engine_v = load_published(db)
            _ja = getattr(engine_v, "stores", {}).get("ja")
            print("[engine] 準備完了 — ja 核 %s / 文書扉・門つき"
                  % (_ja.n_cores() if _ja else "?"))

    # 本線では自動記憶を既定で切る。engine.ask は店に何も書かない設計で、
    # かつ自動記憶は**質問そのものを事実として覚えてしまう**
    # (実測: 「書留の料金は」→「料金は書留」が記憶された)。
    auto_mem = False
    print("Verantyx Vera α — "
          f"mode={args.mode}, lang={args.lang}, auto-memory={'on' if auto_mem else 'off'}. "
          "Commands: :remember <text>, :forget <core>, :stats, :quit "
          "(multi-line paste is captured as one message)")
    while True:
        raw = read_input("you> ")
        if raw is None:
            print()
            break
        line = raw.strip()
        if not line:
            continue
        if line in (":quit", ":q", "exit"):
            break
        if line.startswith(":remember "):
            from .lang import ingest_text

            rep = ingest_text(st, line[len(":remember "):], lang=args.lang)
            st.save(store_path)
            one_v.load_store(st)
            print(f"vera> remembered {rep['cores']} [{rep['lang']}]")
            continue
        if line.startswith(":forget "):
            core = line[len(":forget "):].strip()
            n = 0
            for key in (core, core + "#p"):
                if key in st.crosses:
                    del st.crosses[key]
                    st.core_count.pop(key, None)
                    n += 1
            st.save(store_path)
            one_v.load_store(st)
            print(f"vera> forgot {n} cross(es)")
            continue
        if line == ":stats":
            print(f"vera> {st.report()}")
            continue

        if engine_v is not None:
            from .engine import ask as engine_ask

            o = engine_ask(line, engine_v,
                           store_path=store_path if
                           store_path.with_suffix(".documents.json").is_file()
                           else None)
            body = (o.get("text") or "").strip()
            w = o.get("written") or {}
            ws = [x.get("text") for x in (w.get("sentences") or []) if x.get("text")]
            verdict, door = str(o.get("verdict")), o.get("door") or "?"
            if body:
                print("vera> %s   [%s]" % (body.replace("\n", "\n      "), door))
            else:
                print("vera> %s   [%s] (知りません — 推測はしません)"
                      % (verdict, door))
            if ws:
                print("      📝 %s" % ws[0])
            src_ = o.get("origins") or []
            if src_:
                print("      出典: %s" % "、".join(map(str, src_[:2])))
            continue

        out = one_v.ask(raw if round5 else line)
        if round5:
            _print_round5_chat_result(out, one_v)
            continue
        if out.get("status") == "PARTIAL_COMPLETENESS_UNVERIFIED":
            body = (out.get("text") or "").strip()
            if body:
                print(f"vera> {body}   [{out.get('door','?')}]")
                print(f"      注意: {out.get('response_notice') or '出典全体の網羅性は未確認です。'}")
            else:
                print(f"vera> {out.get('verdict')}   [{out.get('door','?')}]")
                print(f"      注意: {out.get('response_notice') or '出典全体の網羅性は未確認です。'}")
        elif out.get("verdict") == "ANSWER" or out.get("kind") == "skill":
            body = (
                out.get("text")
                or out.get("value")
                or out.get("x")
                or out.get("callers")
                or out.get("calls")
                or out.get("impacted")
            )
            print(f"vera> {body}   [{out.get('door','?')}]")
        else:
            print(f"vera> {out.get('text') or out.get('verdict')}   [{out.get('door','?')}] "
                  "(I do not know — no guessing)")
    return 0


def cmd_math(args) -> int:
    _print(math_ask(args.query))
    return 0


def cmd_simplify(args) -> int:
    _print(simplify(args.expr, default_algebra_rules()))
    return 0


def cmd_code(args) -> int:
    st = _load(args.store)
    if args.action == "ingest":
        rep = ingest_python_repo(st, Path(args.target))
        st.save(Path(args.store))
        _print({**rep, "store": args.store})
        return 0
    _print(code_ask(st, args.target))
    return 0


def cmd_compile(args) -> int:
    from pathlib import Path

    from .verify import compile_docs

    _print(compile_docs([Path(p) for p in args.paths], Path(args.out)))
    return 0


_MARK = {"SUPPORTED": "✓ 根拠あり", "CONTRADICTED": "✗ 文書と矛盾",
         "UNSUPPORTED": "? 文書に根拠なし", "NOT_IN_DOCS": "- 文書の範囲外",
         "NOT_ASSERTED": "· 断定していない"}


def cmd_verify(args) -> int:
    import sys
    from pathlib import Path

    from .verify import verify

    text = args.text or (Path(args.file).read_text(encoding="utf-8") if args.file
                         else sys.stdin.read())
    r = verify(Path(args.store), text)
    if args.json:
        _print(r)
    else:
        for s in r["sentences"]:
            print(s["sentence"])
            for c in s["claims"]:
                print("   %s  %s%s" % (_MARK.get(c["verdict"], c["verdict"]), c["claim"],
                                      ("  — " + c["why"]) if c.get("why") else ""))
                for w in (c.get("witnesses") or [])[:1]:
                    print("        出典 %s: %s" % (w.get("source"), w.get("text")))
        print("\n総合: %s  %s" % (r["overall"], r["tally"]))
    return 1 if r["overall"] == "CONTRADICTED" else 0


def cmd_hub(args) -> int:
    from .hub_edges import generic_cut, open_on, walk

    store, edges_of, writer = open_on()
    out = walk(store, args.subject, edges_of, writer, hops=args.hops,
               generic=generic_cut(store), carry=not args.no_carry)
    _print(out)
    return 0


def cmd_lab(args) -> int:
    from .consensus_forks import all_consensus_forks
    from .cross_geometry_forks import all_cross_geometry_forks
    from .structure_forks import all_structure_forks
    from .kripke_rewrite_forks import all_kripke_rewrite_forks
    from .lean_witness_forks import all_lean_witness_forks
    from .agent_forks import all_agent_forks
    from .ai_ingest_forks import all_ai_ingest_forks
    from .obfuscate_forks import all_obfuscate_forks
    from .watermark_forks import all_watermark_forks
    from .lang_router_forks import all_lang_router_forks
    from .math_sim_forks import all_math_sim_forks
    from .phase2_forks import all_phase2_forks
    from .pour_forks import all_pour_forks

    experiments = (
        all_consensus_forks()
        + all_cross_geometry_forks()
        + all_structure_forks()
        + all_pour_forks()
        + all_math_sim_forks()
        + all_kripke_rewrite_forks()
        + all_lean_witness_forks()
        + all_lang_router_forks()
        + all_phase2_forks()
        + all_agent_forks()
        + all_ai_ingest_forks()
        + all_obfuscate_forks()
        + all_watermark_forks()
    )
    from .hub_edges import regression as _hub_regression

    _hub = _hub_regression()
    experiments.append({"fork": "centre_edge_seated_both_ways_and_ties_speak_as_sets_fork",
                        "pass": bool(_hub.pop("all_pass")), "detail": _hub})
    # A fork that could not run is reported by name and kept OUT of the pass
    # count, never folded into it. Optional extras are the usual reason (a
    # fork needing `cryptography` on an install without it); counting an
    # unrun check as a pass would make the suite quietly weaker on exactly
    # the installs where it is least verified.
    skipped = {e["fork"]: e["skipped"] for e in experiments if e.get("skipped")}
    forks = {e["fork"]: e["pass"] for e in experiments if not e.get("skipped")}
    all_pass = all(forks.values())
    _print({"all_pass": all_pass, "n_forks": len(forks),
            "n_skipped": len(skipped), "skipped": skipped, "forks": forks})
    return 0 if all_pass else 1


def cmd_mcp(args) -> int:
    from .mcp_server import serve

    return serve(args.store)


def cmd_field(args) -> int:
    """The whole thing on one screen, for somebody with a phone ringing.

    Separate from `vera audit` because the audience is: audit is for a person
    checking whether the ENGINE is right; this is for a person trying to find
    out whether the water is back on in their town.
    """
    from .field_app import serve

    return serve(port=args.port, open_browser=not args.no_browser)


def cmd_lexicon(args) -> int:
    """The dictionary half of a local model: state-likeness and neighbours.

    Never polarity — measured at 54.8%, a coin flip, and absent from the API.
    """
    import json as _json
    from pathlib import Path as _Path

    from .ja_grammar import ASPECT_OF
    from .jgen_lexicon import open_configured

    home = _Path.home() / ".verantyx-audit"
    lex = open_configured(home)
    if lex is None:
        print(_json.dumps({
            "verdict": "UNKNOWN_NO_LEXICON",
            "how": f"write {home / 'lexicon.json'} with "
                   '{"jgen": "...", "tokenizer": "..."} — build one with '
                   "jgen_forge pull <model> --parts lexicon",
        }, ensure_ascii=False, indent=2))
        return 1
    known = sorted(ASPECT_OF)
    out = []
    for w in args.words:
        out.append({
            "word": w,
            "state_likeness": lex.state_likeness(w, known),
            "nearest_known": lex.nearest(w, known, k=5),
        })
    print(_json.dumps({"verdict": "ANSWER", "words": out,
                       "not_in_this_dictionary": "polarity — measured 54.8%"},
                      ensure_ascii=False, indent=2))
    return 0


def cmd_self_evolve(args) -> int:
    """Read, prove, repair, measure, keep — with nothing outside the machine.

    The acceptance is mechanical only where the answer key is internal: a
    transform that cannot change what a document says, changing what the
    engine reads out of it. Everything else is filed for a person.
    """
    import json as _json
    from pathlib import Path as _Path

    from .self_evolve import run

    home = _Path.home() / ".verantyx-audit"
    overlay = _Path(args.overlay) if args.overlay else home / "grammar.json"
    out = run(list(args.paths), home=home, overlay=overlay, write=args.write)
    print(_json.dumps({"verdict": "ANSWER", **out}, ensure_ascii=False,
                      indent=2))
    return 0


def _cmd_placement_layer(args) -> int:
    """W10-f05: `vera placement grow --documents f... --layer L --backend ollama|openai|fake --ledger-file F [--placement BASE]` (document-driven growth of a placement layer) and
    `vera placement growth --layer L [--ledger-file F] [--list]` (its indicators). One JSON line. Exit 0: grew / measured; 2: a typed refusal (nothing was written)."""
    import os
    from . import llm_backend, placement_grow, placement_layer

    def refuse(verdict: str, reason: str = "") -> int:
        _print({"verdict": verdict, "reason": reason})
        return 2

    if not args.layer:
        return refuse("LAYER_REQUIRED", "placement %s needs --layer" % args.store)
    placement = args.placement or os.environ.get("VERA_PLACEMENT") or None
    if args.store == "growth":
        from . import coarse_place
        from .llm_choice import LedgerIntegrityError
        from .testimony_ledger import TestimonyLedger
        led = None
        if args.ledger_file:
            if not Path(args.ledger_file).exists():
                return refuse("LEDGER_NOT_FOUND", args.ledger_file)
            try:
                led = TestimonyLedger(args.ledger_file)
            except LedgerIntegrityError as exc:
                return refuse("LEDGER_INTEGRITY", "%s line %s %s" % (exc.kind, exc.line_no, exc.detail))
        base_pl, _why = coarse_place._open(placement) if placement else (None, None)
        out = placement_layer.growth(args.layer, led, getattr(base_pl, "sha", None), with_list=args.list)
        if out.get("layer_status", "").startswith("LAYER_UNAVAILABLE"):
            return refuse(out["layer_status"], args.layer)
        if led is not None:
            out = _growth_with_assumption(out, led)
        _print(out)
        return 0
    if not args.documents:
        return refuse("DOCUMENTS_REQUIRED", "placement grow needs --documents")
    if not args.ledger_file:
        return refuse("LEDGER_REQUIRED", "placement grow needs --ledger-file (every answer is a testimony)")
    if not args.backend:
        return refuse("BACKEND_REQUIRED", "placement grow needs --backend ollama|openai|fake")
    for item in args.documents:
        if not Path(item).exists():
            return refuse("DOCUMENT_NOT_FOUND", item)
    model = args.model or ("fake" if args.backend == "fake" else None)
    if not model:
        return refuse("MODEL_REQUIRED", "--backend %s needs --model" % args.backend)
    chat = None
    fake_version = None
    if args.backend == "fake":
        if bool(args.fake_table) == bool(args.fake_script):
            return refuse("FAKE_NEEDS_ONE_OF", "--backend fake needs exactly one of --fake-table and --fake-script")
        if args.fake_table:
            fake = placement_grow.TableBackend(json.loads(Path(args.fake_table).read_text(encoding="utf-8")))
            fake_version = "fake-table:%s" % hashlib.sha256(Path(args.fake_table).read_bytes()).hexdigest()[:12]
        else:
            fake = llm_backend.FakeBackend([json.loads(line) for line in Path(args.fake_script).read_text(encoding="utf-8").splitlines() if line.strip()])
            fake_version = "fake-script:%s" % hashlib.sha256(Path(args.fake_script).read_bytes()).hexdigest()[:12]
        chat = lambda m, msgs, fmt: fake(m, msgs, fmt)
    elif args.backend == "openai":
        if not (args.api_base or os.environ.get("VERA_LLM_API_BASE")):
            return refuse("API_BASE_REQUIRED", "--backend openai needs --api-base or VERA_LLM_API_BASE")
        chat = llm_backend.make_chat("openai", timeout=args.llm_timeout, api_base=args.api_base, api_key=os.environ.get("VERA_LLM_API_KEY"))
    out = placement_grow.grow(args.documents, args.layer, backend=args.backend, model=model, ledger_path=args.ledger_file, placement=placement, chat=chat,
                              min_sources=args.min_sources, max_words=args.max_words, batch_size=args.batch_size, send_sentences=args.send_sentences,
                              timeout=args.llm_timeout, ollama_url=args.ollama_url, dump_sent=args.dump_sent, model_version=fake_version)
    _print(out)
    return 0 if out.get("verdict") == "GREW" else 2


def _growth_with_assumption(out, led):
    """W3-e2 (K334): with at least one `assumption` row in the ledger, the last key `assumption` = {rows, words, promoted_words, assumption_rate}: `assumption_rate` is the share of the assumed words that
    have no `promoted_to_layer` row for this layer (null with no word). The more a layer grows, the fewer words are assumed."""
    import unicodedata

    nf = lambda w: unicodedata.normalize("NFKC", str(w)).strip()
    entries = led.entries()
    rows = [e for e in entries if e.get("type") == "assumption"]
    if not rows:
        return out
    words = {nf(e["word"]) for e in rows}
    promoted = {nf(e["word"]) for e in entries if e.get("type") == "promoted_to_layer" and e.get("layer_name") == out.get("layer")}
    left = words - promoted
    res = dict(out)
    res["assumption"] = {"rows": len(rows), "words": len(words), "promoted_words": len(words & promoted), "assumption_rate": (len(left) / len(words)) if words else None}
    return res


def cmd_placement(args) -> int:
    """Decide which facts occupy an arm's four faces — once, before shipping.

    A build-time stage, not a query-time one: it computes the anticipated
    answer distribution, bakes a placement into a copy of the store, and the
    engine that reads it stays as deterministic as it was. Refuses to write
    unless the placement is measured better on held-out questions.
    """
    if args.store in ("grow", "growth"):          # W10-f05: `vera placement grow|growth` (docs/COARSE_PLACEMENT.md section 12.19); any other first argument is a store, as before
        return _cmd_placement_layer(args)
    from .placement import main as _placement_main

    argv = [args.store, "--n-queries", str(args.n_queries),
            "--demand", args.demand, "--weight", str(args.weight)]
    if args.queries:
        argv += ["--queries", args.queries]
    if args.sweep:
        argv += ["--sweep"]
    if args.write:
        argv += ["--write", args.write]
    return _placement_main(argv)


def cmd_sovereign(args) -> int:
    """Documents in, one sovereign node out — every stage, in order.

    ingest -> simulate placement -> plan the depth capacity requires ->
    assemble routers -> federate -> descend real questions. Refuses to skip
    a stage; a tree assembled without the placement simulation routes on
    whichever four facts sorted first.
    """
    from .sovereign import main as _sovereign_main

    if getattr(args, "sovereign_op", None):
        # the memory sovereign operations (W4-m), kept apart from the build below
        if args.domain:
            args.sovereign_parser.error(
                "--domain belongs to the build, not to the memory operations")
        from .sovereign import memory_cli as _memory_cli
        return _memory_cli(args)
    if not args.domain:
        args.sovereign_parser.error("the following arguments are required: --domain")

    argv: list = []
    for d in args.domain:
        argv += ["--domain", d]
    for q in args.ask or []:
        argv += ["--ask", q]
    if args.questions:
        argv += ["--questions", args.questions]
    argv += ["--n-queries", str(args.n_queries), "--name", args.name]
    if args.out:
        argv += ["--out", args.out]
    return _sovereign_main(argv)


def cmd_self_audit(args) -> int:
    """Signals a defect leaves in the store, without anybody reading output.

    This is the end of the loop that still needed a person. It does NOT mark
    anything wrong — a suspected gap is a place to look, never a verdict, and
    it never reaches rule synthesis on its own.
    """
    import json as _json
    from pathlib import Path as _Path

    from .arm_schema import ArmIndex
    from .catalog import collect as _collect
    from .cross_store import CrossStore
    from .document_ingest import ingest_documents
    from .document_loaders import load_paths
    from .self_audit import scan, summary, to_gaps

    docs = load_paths(_collect(list(args.paths))["files"])["documents"]
    if not docs:
        print(_json.dumps({"verdict": "UNKNOWN_NO_DOCUMENTS"},
                          ensure_ascii=False))
        return 1
    store, arms = CrossStore(track_provenance=True), ArmIndex()
    ingest_documents(store, docs, arms)
    found = scan(store, arms)

    out = {"verdict": "ANSWER", "documents": len(docs), **summary(found),
           "signals": [s.as_dict() for s in found]}
    if args.file_gaps:
        from .gap_graph import GapGraph, gap_graph_path

        home = _Path.home() / ".verantyx-audit"
        home.mkdir(parents=True, exist_ok=True)
        path = gap_graph_path(home / "audit.json")
        graph = GapGraph.load(path)
        out["filed"] = to_gaps(graph, found)
        graph.save(path)
    print(_json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_audit(args) -> int:
    """A local page for auditing documents — the tool that lets somebody
    other than the author of the fixes read the output. Binds to 127.0.0.1
    only: the documents may be unpublished drafts."""
    from .audit_app import serve as serve_audit

    return serve_audit(port=args.port, open_browser=not args.no_open)


def cmd_serve(args) -> int:
    """Milestone N: HTTP+SSE daemon — Vera as the harness, the IDE (or any
    local caller) as a subscriber/tool-provider instead of an MCP client
    driving Vera as a flat tool. See vera_server.py's own docstring."""
    from .config import VeraConfig
    from .vera_server import serve as serve_http

    st = _load(args.store)
    store_path = Path(args.store)
    cfg = VeraConfig.load()
    model = args.llm or cfg.llm_model

    def save() -> None:
        st.save(store_path)

    if getattr(args, "no_llm", False):               # W12-c1: the entrance that never calls an LLM (a new function; the branches below are unchanged)
        return _serve_no_llm(args, st, save, store_path)
    if getattr(args, "profile", None) is not None or getattr(args, "tier", None):
        _print({"kind": "unknown", "verdict": "PROFILE_NEEDS_NO_LLM" if getattr(args, "profile", None) is not None else "TIER_NEEDS_NO_LLM",
                "reason": "--profile and --tier belong to `serve --no-llm`; without it the entrance is unchanged"})
        return 2
    if getattr(args, "backend", None) is None:      # W10-f01: without --backend this is exactly the daemon it was
        return serve_http(st, save, port=args.port, default_model=model,
                           jgen_endpoint=args.jgen_endpoint, store_path=store_path)
    return _serve_fusion(args, st, save, store_path)


def _serve_no_llm(args, st, save, store_path) -> int:
    """W12-c1 (docs/INITIAL_LAYERS.md section 6): `vera serve --no-llm [--profile strict|assume] [--tier NAME=SPEC ...] [--document f ...] [--placement P] [--layer L]`.
    No LLM is ever called: a record answers (QUESTION_CROSS), everything else is a typed abstention. `vera.confidence_tiers` says how many stages of Vera's own structure agreed."""
    import os
    from . import confidence_tiers as CT
    from .vera_server import FusionConfig, serve as serve_http

    def refuse(verdict: str, reason: str) -> int:
        _print({"kind": "unknown", "verdict": verdict, "reason": reason})
        return 2

    for flag, given in (("--backend", args.backend is not None), ("--model", args.model is not None), ("--strict", bool(args.strict)), ("--free", bool(args.free)),
                        ("--fill", bool(args.fill))):
        if given:
            return refuse("NO_LLM_WITH_BACKEND", "--no-llm never calls an LLM; it cannot be combined with %s" % flag)
    profile = args.profile or "strict"
    documents = list(args.document or [])
    for item in documents:
        if not Path(item).exists():
            return refuse("DOCUMENT_NOT_FOUND", item)
    if bool(args.sovereign_root) != bool(args.sovereign_store):
        return refuse("SOVEREIGN_NEEDS_BOTH", "--sovereign-root and --sovereign-store go together")
    if args.sovereign_root:
        os.environ["VERA_SOVEREIGN_ROOT"] = args.sovereign_root
        os.environ["VERA_SOVEREIGN_STORE"] = args.sovereign_store
    if args.placement:
        os.environ["VERA_PLACEMENT"] = args.placement
    try:
        tiers = [CT.parse_tier(t) for t in (args.tier or [])]
        if args.layer and not any(n == "layer" for n, _ in tiers):
            tiers.append(("layer", args.layer))          # the user's own layer given with --layer is one more stage after the base; the base stage never sees it
        runner = CT.TierRunner(tiers, documents, profile=profile, order=("base", "vocab", "law", "law+user") if args.tier else ("base",), with_default_missing=bool(args.tier))
    except CT.TierError as exc:
        return refuse(exc.error, exc.detail)
    fusion = FusionConfig(model="vera-no-llm", documents=documents, records=None, strict=False)
    fusion.no_llm, fusion.tiers = True, runner
    _print({"serve": {"no_llm": True, "profile": profile, "tiers": [{"name": s.name, "kind": s.kind} for s in runner.stages], "documents": len(documents)}})
    return serve_http(st, save, port=args.port, default_model="vera-no-llm", jgen_endpoint=args.jgen_endpoint, store_path=store_path, fusion=fusion)


def _serve_fusion(args, st, save, store_path) -> int:
    """W10-f01: `vera serve --backend ollama --model M [--document f ...] [--strict]` -- one entrance, OpenAI- and Ollama-compatible (docs/FUSION.md)."""
    import os
    from .vera_server import FusionBadRequest, FusionConfig, serve as serve_http

    def refuse(verdict: str, reason: str) -> int:
        _print({"kind": "unknown", "verdict": verdict, "reason": reason})
        return 2

    if not args.model:
        return refuse("MODEL_REQUIRED", "--backend %s needs --model" % args.backend)
    if args.backend == "openai" and not (args.api_base or os.environ.get("VERA_LLM_API_BASE")):
        return refuse("API_BASE_REQUIRED", "--backend openai needs --api-base or VERA_LLM_API_BASE")
    if args.fill and not args.ledger_file:
        return refuse("LEDGER_REQUIRED", "--fill needs --ledger-file (the testimony ledger)")
    if args.strict and args.free:
        return refuse("STRICT_AND_FREE", "--strict (layer 1) and --free (layer 0) cannot be combined")
    documents = list(args.document or [])
    for item in documents:
        if not Path(item).exists():
            return refuse("DOCUMENT_NOT_FOUND", item)
    if bool(args.sovereign_root) != bool(args.sovereign_store):
        return refuse("SOVEREIGN_NEEDS_BOTH", "--sovereign-root and --sovereign-store go together")
    if args.sovereign_root:
        os.environ["VERA_SOVEREIGN_ROOT"] = args.sovereign_root
        os.environ["VERA_SOVEREIGN_STORE"] = args.sovereign_store
    if args.placement:
        os.environ["VERA_PLACEMENT"] = args.placement
    read_mode = _read_mode(args)
    if read_mode is None:
        return refuse("BAD_READ_MODE", "VERA_READ_MODE must be strict or assume")
    fill = None
    if args.fill:
        from . import fill_candidates as FC
        from .llm_choice import LedgerIntegrityError
        from .testimony_ledger import TestimonyLedger
        try:
            ledger = TestimonyLedger(args.ledger_file)
        except LedgerIntegrityError as exc:
            return refuse("LEDGER_INTEGRITY", "%s line %s %s" % (exc.kind, exc.line_no, exc.detail))
        fill = FC.FillConfig(ledger=ledger, model=args.fill_model, backend_name=args.backend, mask_user_text=not args.no_mask_user_text, max_doc_holes=args.fill_max_holes)
    try:
        fusion = FusionConfig.load(model=args.model, documents=documents, strict=args.strict, ollama_url=args.ollama_url, timeout=args.llm_timeout,
                                   backend=args.backend, api_base=args.api_base, api_key=os.environ.get("VERA_LLM_API_KEY"), fill=fill, layer=args.layer,
                                   read_mode=read_mode, assume_ledger=(fill.ledger if fill is not None else None))
    except FusionBadRequest as exc:
        return refuse(exc.error, exc.detail)
    if fill is not None:
        _print({"fill": {"ledger": args.ledger_file, "mask_user_text": fill.mask_user_text, "documents": fusion.fill_stats}})
    return serve_http(st, save, port=args.port, default_model=args.model, jgen_endpoint=args.jgen_endpoint, store_path=store_path, fusion=fusion)


def cmd_setup(args) -> int:
    from .config import run_setup_menu

    cfg = run_setup_menu()
    _print({"llm_model": cfg.llm_model, "store": cfg.store,
            "allocation": cfg.allocation, "hf_store_repo": cfg.hf_store_repo})
    return 0


def cmd_wizard(args) -> int:
    """Guided data-placement: choose a source with arrow keys and pour."""
    from .tui import select

    presets = [
        ("hf:dbpedia_14:content", "DBpedia abstracts — best definitional pour"),
        ("hf:ag_news", "AG News headlines — current events"),
        ("wikitext", "WikiText-2 from local HF cache"),
        ("hf:wikitext#wikitext-103-raw-v1", "WikiText-103 — large"),
        ("synthetic", "tiny offline synthetic corpus (smoke test)"),
        ("file:", "a local text file (one document per line)"),
    ]
    i = select(
        "Choose a data source to pour into the store:",
        [p[0] for p in presets],
        descriptions=[p[1] for p in presets],
    )
    if i is None:
        print("cancelled")
        return 1
    source = presets[i][0]
    if source == "file:":
        source = "file:" + input("path to text file: ").strip()
    caps = ["2000", "40000", "120000", "560000", "all (2000000)"]
    j = select("Row budget:", caps, default=1)
    max_rows = {0: 2000, 1: 40000, 2: 120000, 3: 560000, 4: 2000000}[j or 1]
    print(f"pouring {source} (max_rows={max_rows}) → {args.store}")
    ns = argparse.Namespace(
        store=args.store, source=source, max_rows=max_rows,
        max_sentences=None, checkpoint_every=100000, no_two_pass=False,
    )
    return cmd_pour(ns)


def cmd_agent(args) -> int:
    from .agent import Agent
    from .config import VeraConfig
    from .tui import confirm_action

    cfg = VeraConfig.load()
    st = _load(args.store, base_repo=cfg.hf_store_repo)
    store_path = Path(args.store)

    llm_fn = None
    model = args.llm or cfg.llm_model
    if model:
        from .llm_local import ollama_available, ollama_generate

        if ollama_available():
            def llm_fn(prompt, system):  # noqa: E731
                return ollama_generate(model, prompt, system=system, timeout=180)
            print(f"[agent] planner LLM: {model}")
        else:
            print("[agent] Ollama unreachable — solo mode (manual !tool calls)")

    def approver(tool, tool_args):
        return confirm_action(
            f"{tool.name}({tool.args_hint})",
            detail=json.dumps(tool_args, ensure_ascii=False, indent=2),
        )

    agent = Agent(
        st, llm=llm_fn, save=lambda: st.save(store_path),
        approver=approver, allocation=cfg.allocation,
        auto_approve=args.yes,
    )

    if args.task:
        out = agent.run(args.task)
        _print(out.get("final", out))
        return 0

    from .tui import read_input

    print("Verantyx agent mode. Type a task, or '!tool {\"arg\":..}' for a "
          "manual tool call, ':quit' to exit. "
          "(multi-line paste is captured as one task)")
    while True:
        raw = read_input("task> ")
        if raw is None:
            print()
            break
        line = raw.strip()
        if not line or line in (":quit", ":q"):
            break
        if line.startswith("!"):
            out = agent.step_solo(line)
            _print(out)
            continue
        out = agent.run(line)
        final = out.get("final", out)
        print(f"agent> {final if isinstance(final, str) else json.dumps(final, ensure_ascii=False)[:600]}")
    return 0


def cmd_obfuscate(args) -> int:
    from .obfuscate import export_recovery_key, key_from_store, obfuscate_file

    st = _load(args.store)
    rep = obfuscate_file(Path(args.file), st)
    if args.export_key and rep.get("ok"):
        export_recovery_key(key_from_store(st), Path(args.export_key))
        rep["recovery_key"] = args.export_key
    _print(rep)
    return 0 if rep.get("ok") else 1


def cmd_deobfuscate(args) -> int:
    from .obfuscate import deobfuscate_file, load_recovery_key

    key = load_recovery_key(Path(args.key_file)) if args.key_file else None
    st = None if key is not None else _load(args.store)
    rep = deobfuscate_file(
        Path(args.obf_file), Path(args.map_file), store=st, key=key
    )
    _print(rep)
    return 0 if rep.get("ok") else 1


def cmd_watermark(args) -> int:
    from .watermark import identify_candidates, register_owner

    if args.action == "register":
        st = _load(args.store)
        rep = register_owner(Path(args.registry), args.owner_id, st)
    else:  # identify
        source = Path(args.file).read_text()
        rep = identify_candidates(Path(args.registry), source)
    _print(rep)
    return 0 if rep.get("ok") else 1


def cmd_push_store(args) -> int:
    from .config import VeraConfig
    from .hf_store import upload_store

    repo = args.repo or VeraConfig.load().hf_store_repo
    if not repo:
        print("no repo given; pass --repo user/name or set hf_store_repo in setup")
        return 2
    _print(upload_store(args.store, repo, private=args.private))
    return 0


def cmd_conduct(args) -> int:
    """枠(Markdown / JSONL)を読み、型付き記録にして、実装エージェントの起動へ進む。

    標準出力には JSON を1つだけ出す。終了コード: 0 = dry-run の起動予定を記録した／
    実行が完了した、1 = 実行したが未完了、2 = 型付きの拒否、3 = 想定外の内部エラー。
    codex / claude を dry-run なしで走らせたときは、エージェントの終了まで待ち、枠の
    command_exit 型の受入条件を指揮者が自分で実行し、結果の型を JSON の "outcome" に
    入れる(COMPLETE / ACCEPTANCE_FAILED / TIMED_OUT など。docs/CONDUCT_RUN.md)。
    既定は検証を要求する: 受入条件が通ったあと、読み取り専用の検証エージェントを指揮者が立て、
    その指摘を指揮者が再実行して確かめる(枠の verifier_* 設定 または --verifier-*)。設定が無ければ
    VERIFIER_NOT_CONFIGURED で止まり、--verifier-adapter none のときだけ省く。結果の型は
    VERIFICATION_FAILED / VERIFIER_FAILED など(docs/CONDUCT_VERIFY.md)。
    枠に [agents] 表があれば、実装役・検証役は経路づけ器が枠の記録から選ぶ(--adapter / --model /
    --effort / --verifier-adapter / --verifier-model / --verifier-effort は付けない)。仕事の種類は
    --task-kind か枠の task_kind。決定は 1 件ずつ ROUTING_DECISION として台帳に残る(docs/AGENT_ROUTING.md)。
    """
    from .conductor_run import conduct_entry

    outcome = conduct_entry(
        args.frame, args.repo, args.adapter, dry_run=args.dry_run, state_dir=args.state_dir,
        model=args.model, effort=args.effort, max_concurrency=args.max_concurrency,
        codex_bin=args.codex_bin, claude_bin=args.claude_bin,
        agent_timeout_seconds=args.agent_timeout_seconds,
        acceptance_timeout_seconds=args.acceptance_timeout_seconds,
        permission_mode=args.permission_mode, allowed_tools=args.allowed_tools,
        verifier_adapter=args.verifier_adapter, verifier_model=args.verifier_model,
        verifier_effort=args.verifier_effort, verifier_timeout_seconds=args.verifier_timeout_seconds,
        verification_retries=args.verification_retries, require_verification=True,
        task_kind=args.task_kind)
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, sort_keys=True))
    return outcome.exit_code


def cmd_guard(args) -> int:
    """番人の高速経路 — 連邦を読まず covenants.json だけを読む。

    実地試験の限界5: 橋(常駐)の起動 15〜45秒の間 fail-open だった。
    この経路は Register だけを読むので、凍結バイナリでも秒台で返り、
    フックは橋なしで直接呼べる(fail-open の窓が消える)。
    """
    import sys as _sys

    from .covenant import (Covenant, Register, bake_inferred,
                           extract_covenants, extract_releases, self_check)

    store_path = Path(args.store or DEFAULT_STORE)
    cov_path = store_path.with_name(store_path.stem + ".covenants.json")
    reg = Register.load(cov_path)
    op = args.guard_op
    payload = {}
    if not _sys.stdin.isatty():
        raw = _sys.stdin.read().strip()
        if raw:
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"text": raw}
    def _mk_covenant():
        return Covenant(
            name=str(payload.get("name", ""))[:60] or "covenant",
            requires=list(payload.get("requires", [])),
            forbids=list(payload.get("forbids", [])),
            topic=list(payload.get("topic", [])),
            said_at_turn=int(payload.get("turn", -1)),
            quote=str(payload.get("quote", "")),
            origin=str(payload.get("origin", "")))

    def _bake(c):
        # ③ 書かれていない禁止 — 登録・採用の時だけ店を読む(check の
        # 速い道を守る)。店が無ければ何も焼かない(推測しない)。
        if not payload.get("infer"):
            return None
        if not store_path.is_file():
            return {"verdict": "UNKNOWN_NO_STORE", "path": str(store_path)}
        return bake_inferred(c, CrossStore.load(store_path),
                             store_name=store_path.name,
                             store_path=store_path)

    if op == "extract":
        _text = str(payload.get("text", ""))
        out = {"candidates": extract_covenants(
            _text, turn=int(payload.get("turn", -1))),
            "releases": extract_releases(_text)}
    elif op == "set":
        c = _mk_covenant()
        if c.origin == "regex":
            # 戻り止め(2026-08-21、誤遮断の実測)。閉じた抽出規則が読んだ
            # 約束は、どの入口から入っても執行には入れない — `No new
            # dependencies` → forbids=["new"] が返答を遮断した実測があり、
            # 規則を足して被覆を上げる道は閉じないと分かっている。
            # フックは propose を呼ぶが、別の配管が set を呼んでも法が
            # 破れないよう、ここでも隔離席へ落とす。**黙って落とさない**:
            # 隔離席に入れたことを返り値で名指す。
            reg.propose(c)
            reg.save(cov_path)
            out = {"verdict": "ANSWER", "candidate": c.as_dict(),
                   "routed_to_quarantine": True,
                   "note": "規則が読んだ約束は執行に入れない — shadow で"
                           "照合されるだけ。採用は adopt(門)"}
        else:
            reg.add(c)
            baked = _bake(c)
            reg.save(cov_path)
            out = {"verdict": "ANSWER", "covenant": c.as_dict(),
                   "in_force": len([x for x in reg.covenants
                                    if not x.retired
                                    and x.status == "adopted"])}
            if baked:
                out["inference"] = baked
    elif op == "propose":
        # ① 隔離席 — LLM の候補は shadow で照合されるだけで執行されない。
        c = _mk_covenant()
        if not (c.forbids or c.requires):
            out = {"verdict": "UNKNOWN_EMPTY_CANDIDATE",
                   "note": "禁止も要求も無い候補は約束にならない"}
        else:
            reg.propose(c)
            reg.save(cov_path)
            out = {"verdict": "ANSWER", "candidate": c.as_dict()}
    elif op == "adopt":
        d = reg.adopt(str(payload.get("name", "")))
        if d is None:
            out = {"verdict": "UNKNOWN_NO_SUCH_CANDIDATE"}
        else:
            c = next(x for x in reg.covenants if x.name == d["name"])
            baked = _bake(c)
            reg.save(cov_path)
            out = {"verdict": "ANSWER", "adopted": c.as_dict()}
            if baked:
                out["inference"] = baked
    elif op == "witness":
        _ok = payload.get("ok", None)
        out = reg.witness(str(payload.get("tool", "")),
                          detail=str(payload.get("detail", "")),
                          turn=int(payload.get("turn", -1)),
                          ok=None if _ok is None else bool(_ok))
        reg.save(cov_path)
    elif op == "prune":
        # 台帳を有界に。**消さず書庫へ移す**(PREREG9)。
        out = reg.prune(path=cov_path,
                        max_history=int(payload.get("max_history", 200)),
                        max_live=int(payload.get("max_live", 300)))
        reg.save(cov_path)
    elif op == "promote":
        # 推薦だけ — 採用は adopt(門)のまま。保存も要らない。
        out = reg.promotion_review(
            min_checks=int(payload.get("min_checks", 8)),
            max_fire_rate=float(payload.get("max_fire_rate", 0.5)))
    elif op == "doctor":
        # 導入直後に叩く自己検査(PREREG5)。**利用者の台帳には触らない** —
        # 一時の台帳で保証を実演し、環境は stat と実時間だけを見る。
        import os as _os
        import time as _time

        out = self_check()
        t0 = _time.time()
        _probe = Register()
        _probe.add(Covenant(name="_speed", quote="q", forbids=["絵文字"]))
        for _ in range(200):
            _probe.check("できました。")
        per_check_ms = round((_time.time() - t0) / 200 * 1000, 4)
        frozen = bool(getattr(_sys, "frozen", False))
        env = {
            "path": "frozen-binary" if frozen else "source",
            "per_check_ms": per_check_ms,
            "covenants_ledger": str(cov_path),
            "ledger_exists": cov_path.is_file(),
            "ledger_writable": _os.access(
                cov_path if cov_path.is_file() else cov_path.parent,
                _os.W_OK),
            "covenants_in_force": len([c for c in reg.covenants
                                       if not c.retired
                                       and c.status == "adopted"]),
            "candidates_in_quarantine": len([c for c in reg.covenants
                                             if c.status == "candidate"]),
        }
        notes = []
        if not env["ledger_writable"]:
            notes.append("台帳に書けない — 約束を登録できない(DEGRADED)")
        if frozen and per_check_ms > 50:
            notes.append("1照合が遅い — onedir 凍結かソース直呼びを勧める")
        out["environment"] = env
        if out["verdict"] == "OK" and notes:
            out["verdict"] = "DEGRADED"
        out["notes"] = notes
    elif op == "stale":
        out = reg.stale(store_path)      # stat のみ — 店は読まない
    elif op == "rebake":
        dry = bool(payload.get("dry_run", False))
        if not store_path.is_file():
            out = {"verdict": "UNKNOWN_NO_STORE", "path": str(store_path)}
        else:
            out = reg.rebake(CrossStore.load(store_path),
                             store_path=store_path, dry_run=dry)
            if not dry and out.get("verdict") == "ANSWER":
                reg.save(cov_path)
    elif op == "boundary":
        out = reg.boundary(turn=int(payload.get("turn", -1)))
        reg.save(cov_path)
    elif op == "audit":
        out = reg.audit()
    elif op == "check":
        out = reg.check(str(payload.get("reply", "")),
                        asked=str(payload.get("asked", "")))
        reg.save(cov_path)          # 履歴(風化の材料)を残す
    elif op == "fading":
        out = reg.fading(window=int(payload.get("window", 5)))
    elif op == "retire":
        r = reg.retire(str(payload.get("name", "")),
                       quote=str(payload.get("quote", "")),
                       turn=int(payload.get("turn", -1)))
        if r is None:
            out = {"verdict": "UNKNOWN_NO_SUCH_COVENANT"}
        else:
            reg.save(cov_path)
            out = {"verdict": "ANSWER", "retired": r}
    elif op == "list":
        out = {"covenants": [c.as_dict() for c in reg.covenants]}
    else:
        out = {"verdict": "UNKNOWN_OP", "op": op}
    _print(out)
    # doctor だけは終了コードで答える — 導入の自動確認に使えるように。
    if op == "doctor" and out.get("verdict") == "BROKEN":
        return 1
    return 0


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="vera", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", default=None,
                    help="store path (default: config, else vera_store.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pour", help="stream a corpus into the store")
    p.add_argument("--source", default="synthetic")
    p.add_argument("--max-rows", type=int, default=20000)
    p.add_argument("--max-sentences", type=int, default=None)
    p.add_argument("--checkpoint-every", type=int, default=100000)
    p.add_argument("--no-two-pass", action="store_true")
    p.set_defaults(fn=cmd_pour)

    p = sub.add_parser("remember", help="teach one sentence")
    p.add_argument("text")
    p.set_defaults(fn=cmd_remember)

    p = sub.add_parser("forget", help="delete a core (really deletes)")
    p.add_argument("core")
    p.set_defaults(fn=cmd_forget)

    p = sub.add_parser("ask", help="one-shot question (typed verdict)")
    p.add_argument("query")
    p.add_argument("--mode", choices=["legacy", "round5"], default="legacy",
                   help="explicit raw-request route; round5 can read --document inputs")
    p.add_argument("--document", action="append", default=[],
                   help="source document for --mode round5 (repeatable; this slice accepts one source event)")
    p.add_argument("--engine", action="store_true",
                   help="本線(engine.ask)を通す — 公開連合・文書扉・"
                        "門つき。既定は手元の店のみ")
    p.add_argument("--federation", default="",
                   help="公開連合の場所(既定 $VERA_CORPUS_ROOT/build/vera.db)")
    p.add_argument("--request-kind", choices=["factual", "creative", "paraphrase", "style", "example"],
                   default="factual",
                   help="事実を問う依頼(factual、既定)か、事実を主張しない依頼か(根拠の方針 W6-a)")
    p.add_argument("--human-present", action="store_true",
                   help="人が居る場面。生成コーパスにしか根拠が無いとき、問いとして返す")
    p.add_argument("--show-generated-reference", action="store_true",
                   help="参考欄(生成コーパス由来・事実の証拠ではない)を別の鍵で出す。既定は出さない")
    p.add_argument("--confirm", nargs=2, metavar=("ID", "yes|no"), default=None,
                   help="問い返しへの答え。yes は人が書いた記録としてソブリンに追記する")
    p.add_argument("--layer", default=None, help="W10-f05: a placement layer (a name in $VERA_PLACEMENT_LAYER_ROOT, or a path) put on the base placement: it answers only for the words the base leaves undecided. Sets VERA_PLACEMENT_LAYER.")
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser(
        "index",
        help="does this already exist? one search over doors, commands, "
             "modules, forks and every prereg/result — derived, never listed")
    p.add_argument("index_op", choices=["search", "build", "markdown"])
    p.add_argument("query", nargs="*", default=[])
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--out", default="")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser(
        "read-events",
        help="read one sentence and return its event crosses (predicate = centre, "
             "roles = arms, words = fillers) as one line; same output as "
             "`python -m verantyx.semantic_read --text=... --events`")
    p.add_argument("--text", default=None)
    p.add_argument("--lang", default=None)
    p.set_defaults(fn=cmd_read_events)

    p = sub.add_parser(
        "read",
        help="read one sentence (same output as `python -m verantyx.semantic_read`); with --holes a sentence the reader "
             "abstains on because of a filler's placement is returned with its typed holes (docs/FUSION.md section 6)")
    p.add_argument("--text", default=None)
    p.add_argument("--lang", default=None)
    p.add_argument("--placement", default=None, help="the placement directory (without it: VERA_PLACEMENT)")
    p.add_argument("--holes", action="store_true", help="W10-f04: add holes_status / holes / partial / display")
    p.add_argument("--max-holes", type=int, default=2, dest="max_holes", help="W10-f04: at most this many holes in one sentence (default 2)")
    p.add_argument("--layer", default=None, help="W10-f05: a placement layer (a name in $VERA_PLACEMENT_LAYER_ROOT, or a path) put on the base placement: it answers only for the words the base leaves undecided. Sets VERA_PLACEMENT_LAYER.")
    p.add_argument("--strict-read", action="store_true", dest="strict_read", help="W3-e2: read strictly (no assumed reading). Without it, VERA_READ_MODE=strict|assume; the default is assume: a sentence that stops only on a premise (a name's type, a coined verb, an unplaced noun's type) is read with the assumption put out in the answer")
    p.add_argument("--ledger-file", default=None, dest="ledger_file", help="W3-e2: the testimony ledger: every assumption is written to it (kind assumption), and its promotable rows are a source of an assumption")
    p.add_argument("--backend", default=None, dest="assume_backend", choices=["ollama", "openai"], help="W3-e2: source (e) of an assumption: ask this back end twice (the sentence is never sent). Needs --model")
    p.add_argument("--model", default=None, dest="assume_model", help="W3-e2: the model of --backend")
    p.set_defaults(fn=cmd_read)

    p = sub.add_parser(
        "ledger",
        help="W10-f04: the testimony ledger of LLM candidates (append-only, hash-chained): list | show <id> | confirm <id> (a human confirms)")
    p.add_argument("ledger_op", choices=["list", "show", "confirm", "promote"])
    p.add_argument("id", nargs="?", default=None)
    p.add_argument("--ledger-file", required=True, dest="ledger_file")
    p.add_argument("--promote-n", type=int, default=3, dest="promote_n", help="reread_agreed rows needed to be promotable (default 3)")
    p.add_argument("--json", action="store_true", help="list as one json line")
    p.add_argument("--layer", default=None, help="W10-f05: promote: the placement layer (a name or a path) the promotable rows are written into")
    p.add_argument("--placement", default=None, help="W10-f05: promote: the base placement directory (without it: VERA_PLACEMENT); a word it already decides is not promoted")
    p.set_defaults(fn=cmd_ledger)

    p = sub.add_parser(
        "realize",
        help="validate a cross-token line and realize one supported event cross as a sentence",
    )
    p.add_argument("tokens", nargs="?", default="-",
                   help="one canonical line from `verantyx.cross_tokens` (default: stdin)")
    p.add_argument("--lang", choices=["ja", "en"], default="ja")
    p.add_argument("--placement", default=None, help="placement used for the required reread check")
    p.add_argument("--forms", default=None,
                   help="a user's forms table laid over the base table (VERA_REALIZE_FORMS is read too); it may only add styles/roles/order entries")
    p.set_defaults(fn=cmd_realize)

    p = sub.add_parser(
        "observe",
        help="observe a structure from a viewpoint (anchor, direction, range, ledger state) and realize "
             "what is seen as one json line; every clause carries its coordinate (docs/OBSERVATION.md)")
    p.add_argument("--anchor-text", default=None, help="the anchor sentence (a seed, or a question with --anchor-kind question)")
    p.add_argument("--anchor-record", default=None, help="the id of a sentence of --structure as the anchor")
    p.add_argument("--anchor-kind", default="seed", choices=["seed", "question"])
    p.add_argument("--anchor-cross", type=int, default=None, help="which cross of the anchor sentence (needed when it has several)")
    p.add_argument("--lang", default=None)
    p.add_argument("--direction", default="", help="moves in order, e.g. FACE_SWAP:agent,EDGE:cause")
    p.add_argument("--range", type=int, default=None, help="how many leading moves may be applied (default: all)")
    p.add_argument("--structure", default=None, help="jsonl of {id, text} sentences")
    p.add_argument("--index", default=None, help="corpus index directory (default: the default index root)")
    p.add_argument("--index-family", action="append", default=None, help="index family (repeatable; default: pro)")
    p.add_argument("--no-index", action="store_true", help="do not ask the corpus index (occupancy of unattested cells is UNKNOWN_NO_INDEX)")
    p.add_argument("--placement", default=None, help="one json file of placements and neighbours")
    p.add_argument("--ledger", default=None, help="ledger file (jsonl): observe in its state, then append the turn")
    p.set_defaults(fn=cmd_observe)

    p = sub.add_parser(
        "route",
        help="read a human's free-text explanation of the agents and route one job "
             "(reading -> event cross -> relations -> records -> router); one line out, "
             "'undecided' (typed) whenever any sentence could not be read")
    p.add_argument("--explanation", required=True, help="path of the explanation (UTF-8 text)")
    p.add_argument("--task", required=True,
                   help='json text {"role","kind","size"[,"touches","already_used","running",...]} or the path of a file holding it')
    p.set_defaults(fn=cmd_route)

    p = sub.add_parser(
        "mcp-config",
        help="print (or install) the MCP snippet pointing a client at this "
             "binary and this store")
    p.add_argument("--client", default="claude-code",
                   choices=list(_MCP_CLIENTS) + ["all"])
    p.add_argument("--install", action="store_true",
                   help="write it into the client config (merges, replacing "
                        "only the vera-memory entry)")
    p.set_defaults(fn=cmd_mcp_config)

    p = sub.add_parser(
        "tool", help="call any of the MCP doors from the CLI (same doors, "
                     "second entrance — nothing is rewritten per command)")
    p.add_argument("tool_op", choices=["list", "show", "call"])
    p.add_argument("name", nargs="?", default="")
    p.add_argument("--json", default="", help="arguments as a JSON object")
    p.add_argument("--arg", action="append",
                   help="key=value (repeatable), typed from the door")
    p.set_defaults(fn=cmd_tool)

    p = sub.add_parser(
        "documents",
        help="load documents into the store from the CLI — PDF, Word, "
             "HTML, CSV, JSON, text; a directory is walked")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-ingest", action="store_true",
                   help="read and register the documents without ingesting")
    p.set_defaults(fn=cmd_documents)

    p = sub.add_parser("domain", help="register/inspect domain vocabularies")
    p.add_argument("domain_op",
                   choices=["list", "add", "pending", "accept", "reject"])
    p.add_argument("name", nargs="?", default="")
    p.add_argument("path", nargs="?", default="")
    p.add_argument("--index", type=int, default=None)
    p.set_defaults(fn=cmd_domain)

    p = sub.add_parser(
        "doctor",
        help="self-check both faces on THIS machine: the covenant guard "
             "(G1-G4) and the standalone device (S1-S4). Exit 1 if broken")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("stats", help="store statistics")
    p.set_defaults(fn=cmd_stats)

    from .agent_routing import TASK_KINDS

    p = sub.add_parser(
        "conduct",
        help="read a project frame (.md or .jsonl) and start an implementation agent; "
             "exit 0 ok/planned, 1 incomplete, 2 typed refusal, 3 internal error")
    p.add_argument("--frame", required=True, help="project frame: Markdown DSL or JSONL memory log")
    p.add_argument("--repo", required=True, help="git repository the agent works in (a worktree is made from HEAD)")
    p.add_argument("--adapter", default=None, choices=["codex", "claude", "fake"],
                   help="required unless the frame has an [agents] table; with one, omit it (the router chooses "
                        "the agents from the frame's records; docs/AGENT_ROUTING.md)")
    p.add_argument("--task-kind", default=None,
                   choices=list(TASK_KINDS),
                   help="what kind of job this is, for a frame with an [agents] table (overrides the frame's task_kind)")
    p.add_argument("--dry-run", action="store_true",
                   help="codex/claude: write the command that would start to the ledger and start nothing")
    p.add_argument("--state-dir", default=None, help="ledger and run files (default: <repo>/.verantyx-conduct)")
    p.add_argument("--model", default=None, help="model name (overrides the frame's agent_settings)")
    p.add_argument("--effort", default=None, help="reasoning effort level (overrides the frame)")
    p.add_argument("--max-concurrency", type=int, default=None,
                   help="upper bound on simultaneous agents (overrides the frame; the conductor runs one at a time)")
    p.add_argument("--codex-bin", default="codex", help="codex executable (default: codex from PATH)")
    p.add_argument("--claude-bin", default="claude", help="claude executable (default: claude from PATH)")
    p.add_argument("--agent-timeout-seconds", type=int, default=None,
                   help="upper bound on the agent's run time in seconds (overrides the frame's "
                        "agent_timeout_seconds; default 1800 when neither is given)")
    p.add_argument("--acceptance-timeout-seconds", type=int, default=None,
                   help="upper bound on each acceptance command in seconds (overrides the frame; default 600)")
    p.add_argument("--permission-mode", default=None,
                   help="claude only: --permission-mode passed to claude -p, e.g. acceptEdits "
                        "(overrides the frame's claude_permission_mode; bypassPermissions and auto are refused)")
    p.add_argument("--allowed-tools", default=None,
                   help="claude only: comma-separated tool names for --allowedTools, e.g. Edit,Write "
                        "(overrides the frame's claude_allowed_tools)")
    p.add_argument("--verifier-adapter", default=None, choices=["codex", "claude", "none"],
                   help="verification is required by default: after the acceptance commands pass, a read-only verifier "
                        "agent of this kind is started and the conductor re-runs its claims (overrides the frame's "
                        "verifier_adapter). With no verifier configured the run stops as VERIFIER_NOT_CONFIGURED; "
                        "use '--verifier-adapter none' to skip verification on purpose (it is recorded)")
    p.add_argument("--verifier-model", default=None, help="verifier model name (overrides the frame's verifier_model)")
    p.add_argument("--verifier-effort", default=None, help="verifier reasoning effort (overrides the frame's verifier_effort)")
    p.add_argument("--verifier-timeout-seconds", type=int, default=None,
                   help="upper bound on the verifier's run time in seconds (overrides verifier_timeout_seconds; "
                        "default 900 when a verifier is configured)")
    p.add_argument("--verification-retries", type=int, default=None,
                   help="how many times a confirmed finding sends the implementer back to redo the work, 0 to 5 "
                        "(overrides verification_retries; default 2 when a verifier is configured)")
    p.set_defaults(fn=cmd_conduct)

    p = sub.add_parser(
        "guard",
        help="covenant guard fast path: no federation load, covenants.json "
             "only — for Claude Code hooks (stdin: JSON payload)")
    p.add_argument("guard_op",
                   choices=["extract", "set", "check", "fading", "retire", "list",
                            "propose", "adopt", "witness", "boundary", "audit",
                            "promote", "stale", "rebake",
                            "doctor", "prune"])
    p.set_defaults(fn=cmd_guard)

    p = sub.add_parser(
        "heartbeat",
        help="Milestone M: scan growth signals, draft+verify candidate "
             "domain modules, queue for human review (never auto-activates)",
    )
    p.add_argument("--llm-model", default="", dest="llm_model",
                    help="Ollama model to draft with; omit to only report candidates")
    p.set_defaults(fn=cmd_heartbeat)

    p = sub.add_parser(
        "propose-ai-facts",
        help="quarantine sentence candidates from an AI's FINAL text "
             "(never thinking/chain-of-thought)",
    )
    p.add_argument("text")
    p.add_argument("--source", default="ai_output")
    p.set_defaults(fn=cmd_propose_ai_facts)

    p = sub.add_parser(
        "review-ai-facts",
        help="review quarantined AI-proposed facts (arrow-key accept/reject)",
    )
    p.add_argument("--list", action="store_true", help="print pending, no prompts")
    p.set_defaults(fn=cmd_review_ai_facts)

    p = sub.add_parser("chat", help="interactive REPL (lab | hybrid | round5)")
    p.add_argument("--strict-read", action="store_true", dest="strict_read", help="W3-e2: `/read` reads strictly (no assumed reading); the default is assume (VERA_READ_MODE=strict|assume)")
    p.add_argument("--mode", choices=["lab", "hybrid", "round5"], default="lab",
                   help="lab: deterministic only; hybrid: local LLM; round5: explicit experimental one.Vera.ask route")
    p.add_argument("--document", action="append", default=[],
                   help="source file/folder for --mode round5 (repeatable; loaded for this session only)")
    p.add_argument("--request-kind", choices=["factual", "creative", "paraphrase", "style", "example"],
                   default="factual", help="round5 chat request kind (same basis policy as `vera ask`)")
    p.add_argument("--human-present", action="store_true",
                   help="round5 chat policy: a human is present in this scene")
    p.add_argument("--show-generated-reference", action="store_true",
                   help="round5 chat policy: show generated material in its separate reference field")
    p.add_argument("--placement", default=None,
                   help="round5 chat /gen: one JSON file of placements and neighbours, as in `vera observe`")
    p.add_argument("--json", action="store_true", help="round5 chat: print raw result dictionaries")
    p.add_argument("--llm", default="llama3.2",
                   help="Ollama model name for hybrid mode")
    p.add_argument("--lang", default="auto",
                   help="auto | en | ja | es | fr | de | latin")
    p.add_argument("--no-auto-memory", action="store_true",
                   help="disable the native always-on memory harness")
    p.add_argument("--engine", action="store_true",
                   help="本線(engine.ask)を通す — 公開連合・文書扉・門つき。"
                        "連合は起動時に一度だけ読む。自動記憶は既定で切れる")
    p.add_argument("--federation", default="",
                   help="公開連合の場所(既定 $VERA_CORPUS_ROOT/build/vera.db)")
    p.add_argument("--layer", default=None, help="W10-f05: a placement layer (a name in $VERA_PLACEMENT_LAYER_ROOT, or a path) put on the base placement: it answers only for the words the base leaves undecided. Sets VERA_PLACEMENT_LAYER.")
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("math", help="wire arithmetic / typed equations")
    p.add_argument("query")
    p.set_defaults(fn=cmd_math)

    p = sub.add_parser("simplify", help="term rewriting (algebra rules)")
    p.add_argument("expr")
    p.set_defaults(fn=cmd_simplify)

    p = sub.add_parser("code", help="code reasoning: ingest / ask")
    p.add_argument("action", choices=["ingest", "ask"])
    p.add_argument("target")
    p.set_defaults(fn=cmd_code)

    p = sub.add_parser(
        "compile", help="read your documents into a checkable store (no training)")
    p.add_argument("paths", nargs="+", help=".txt/.md files or folders")
    p.add_argument("--out", default="vera_docs.db")
    p.set_defaults(fn=cmd_compile)

    p = sub.add_parser(
        "verify", help="check what an AI wrote against your compiled documents")
    p.add_argument("--store", default="vera_docs.db")
    p.add_argument("text", nargs="?", help="text to check (or --file, or stdin)")
    p.add_argument("--file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser(
        "hub", help="speak across centre edges (core to core), no model")
    p.add_argument("subject")
    p.add_argument("--hops", type=int, default=4)
    p.add_argument("--no-carry", action="store_true",
                   help="do not require later cores to share the subject")
    p.set_defaults(fn=cmd_hub)

    p = sub.add_parser("lab", help="run fork self-test suites")
    p.set_defaults(fn=cmd_lab)

    p = sub.add_parser("mcp", help="start MCP server (stdio)")
    p.set_defaults(fn=cmd_mcp)

    p = sub.add_parser(
        "field",
        help="the full local app for a municipal desk (127.0.0.1, no network)")
    p.add_argument("--port", type=int, default=8900)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(fn=cmd_field)

    p = sub.add_parser(
        "lexicon",
        help="ask the configured static dictionary about a word")
    p.add_argument("words", nargs="+")
    p.set_defaults(fn=cmd_lexicon)

    p = sub.add_parser(
        "self-evolve",
        help="prove defects from the documents themselves, repair, and keep")
    p.add_argument("paths", nargs="+")
    p.add_argument("--write", action="store_true",
                   help="write an accepted repair to the overlay")
    p.add_argument("--overlay", default=None,
                   help="default ~/.verantyx-audit/grammar.json")
    p.set_defaults(fn=cmd_self_evolve)

    p = sub.add_parser(
        "placement",
        help="simulate which facts go on the faces, before shipping a store")
    p.add_argument("store")
    p.add_argument("--queries",
                   help="one anticipated question per line; strongly "
                        "preferred over the synthetic stand-in")
    p.add_argument("--n-queries", type=int, default=120)
    p.add_argument("--demand", choices=("zipf", "uniform"), default="zipf",
                   help="how synthetic questions pick a facet; zipf models "
                        "concentrated stable demand, uniform models none")
    p.add_argument("--weight", type=float, default=0.0,
                   help="discrimination weight; measured as unhelpful at "
                        "one arm per query, see verantyx/placement.py")
    p.add_argument("--sweep", action="store_true",
                   help="measure the weight instead of using it")
    p.add_argument("--write", metavar="OUT",
                   help="bake the placement into a copy of the store")
    # W10-f05: `vera placement grow|growth` (the first argument is then `grow` or `growth`, not a store)
    p.add_argument("--documents", nargs="+", default=None, help="W10-f05 grow: the documents (files or folders) whose vocabulary grows the layer")
    p.add_argument("--layer", default=None, help="W10-f05 grow|growth: the placement layer (a name in $VERA_PLACEMENT_LAYER_ROOT, or a path)")
    p.add_argument("--backend", choices=["ollama", "openai", "fake"], default=None, help="W10-f05 grow: the back end that is asked for declarations")
    p.add_argument("--model", default=None, help="W10-f05 grow: the model (not needed for --backend fake)")
    p.add_argument("--ledger-file", default=None, dest="ledger_file", help="W10-f05 grow|growth: the testimony ledger every declaration is written to")
    p.add_argument("--placement", default=None, help="W10-f05 grow|growth: the BASE placement directory (without it: VERA_PLACEMENT)")
    p.add_argument("--min-sources", type=int, default=1, dest="min_sources", help="W10-f05 grow: documents that must back a declaration (default 1; the thresholds themselves are not lowered)")
    p.add_argument("--max-words", type=int, default=200, dest="max_words", help="W10-f05 grow: candidate words asked (more are counted as skipped_budget)")
    p.add_argument("--batch-size", type=int, default=10, dest="batch_size", help="W10-f05 grow: words per question")
    p.add_argument("--send-sentences", action="store_true", dest="send_sentences", help="W10-f05 grow: send the sentences themselves to the back end (default: only typed shapes; the ledger marks it)")
    p.add_argument("--fake-table", default=None, dest="fake_table", help="W10-f05 grow --backend fake: a JSON table word -> declaration")
    p.add_argument("--fake-script", default=None, dest="fake_script", help="W10-f05 grow --backend fake: a jsonl script (llm_backend.FakeBackend)")
    p.add_argument("--dump-sent", default=None, dest="dump_sent", help="W10-f05 grow: write what was sent to the back end (jsonl)")
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434", dest="ollama_url", help="W10-f05 grow: the Ollama server (local only)")
    p.add_argument("--llm-timeout", type=float, default=180.0, dest="llm_timeout", help="W10-f05 grow: seconds to wait for the back end")
    p.add_argument("--api-base", default=None, dest="api_base", help="W10-f05 grow --backend openai: the API base (else VERA_LLM_API_BASE)")
    p.add_argument("--list", action="store_true", help="W10-f05 growth: list the words of the layer")
    p.set_defaults(fn=cmd_placement)

    p = sub.add_parser(
        "sovereign",
        help="build one federated node from documents, stage by stage")
    p.add_argument("--domain", action="append", metavar="NAME=PATH",
                   help="a field and the folder its documents live in")
    p.add_argument("--ask", action="append", default=[],
                   help="a question to descend after the build")
    p.add_argument("--questions", help="a file of questions, one per line")
    p.add_argument("--n-queries", type=int, default=200)
    p.add_argument("--name", default="主権")
    p.add_argument("--out", help="write the build record as JSON")
    p.set_defaults(fn=cmd_sovereign)
    p.set_defaults(sovereign_parser=p)

    # memory sovereign (W4-m): operations nested under `sovereign`. Every dest starts with
    # `sov_` so that none of them can overwrite the build options above.
    sov_ops = p.add_subparsers(dest="sovereign_op", metavar="OP")

    def _sov_common(q, store_required=True):
        q.add_argument("--root", dest="sov_root", required=True,
                       help="the folder the sovereign registry and files live in (no default)")
        q.add_argument("--store-id", dest="sov_store_id", required=store_required,
                       help="the sovereign's name")
        return q

    q = _sov_common(sov_ops.add_parser(
        "create", help="記憶のソブリン: create one independent store (one file, append-only inside)"))
    q.add_argument("--owner", dest="sov_owner", required=True, help="who the store belongs to")
    q.add_argument("--consent-promote", dest="sov_consent_promote", action="store_true",
                   help="allow repeated observations to be promoted (off unless given)")
    q = _sov_common(sov_ops.add_parser(
        "consent", help="記憶のソブリン: record a consent change (appended; the latest row wins)"))
    q.add_argument("--promote", dest="sov_promote", choices=["on", "off"], required=True)
    q = _sov_common(sov_ops.add_parser(
        "append", help="記憶のソブリン: append one event to the conversation ledger"))
    q.add_argument("--kind", dest="sov_kind", required=True,
                   choices=["utterance", "observation", "decision"])
    q.add_argument("--payload", dest="sov_payload", required=True,
                   help="the event payload, one line of json")
    q = _sov_common(sov_ops.add_parser(
        "events", help="記憶のソブリン: print the ledger, one event per line"))
    q.add_argument("--since", dest="sov_since",
                   help="an event id; print only the events after it")
    _sov_common(sov_ops.add_parser(
        "status", help="記憶のソブリン: list the registered stores and their state"),
        store_required=False)
    _sov_common(sov_ops.add_parser(
        "detach", help="記憶のソブリン: cut the reference so the store cannot be read (the file stays)"))
    q = _sov_common(sov_ops.add_parser(
        "attach", help="記憶のソブリン: read a detached store again, or register an exported file in place"),
        store_required=False)
    q.add_argument("--file", dest="sov_file", help="an exported file to register where it is")
    q = _sov_common(sov_ops.add_parser(
        "export", help="記憶のソブリン: copy the store out as one file with its hash"))
    q.add_argument("--to", dest="sov_to", required=True,
                   help="where to write the copy (must not exist)")
    q = _sov_common(sov_ops.add_parser(
        "release", help="記憶のソブリン: let the store go, cutting the reference and keeping the hash (the file stays)"))
    q.add_argument("--confirm", dest="sov_confirm", required=True,
                   help="the store id again, exactly, as the explicit instruction")
    q = _sov_common(sov_ops.add_parser(
        "promote", help="記憶のソブリン: promote repeated observations to the structure (needs consent)"))
    q.add_argument("--min-count", dest="sov_min_count", type=int)
    q.add_argument("--min-days", dest="sov_min_days", type=int)
    q = _sov_common(sov_ops.add_parser(
        "promotions", help="記憶のソブリン: list the promotions that are still active"),
        store_required=False)
    q.add_argument("--all", dest="sov_all", action="store_true",
                   help="include the retired ones, with their retire rows")

    p = sub.add_parser(
        "self-audit",
        help="find structural signals of defects, with no person reading")
    p.add_argument("paths", nargs="+")
    p.add_argument("--file-gaps", action="store_true",
                   help="record what it finds in the local gap graph")
    p.set_defaults(fn=cmd_self_audit)

    p = sub.add_parser(
        "audit",
        help="drop documents in a browser and read what the engine did")
    p.add_argument("--port", type=int, default=8899)
    p.add_argument("--no-open", action="store_true",
                   help="do not launch a browser")
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser(
        "serve",
        help="Milestone N: HTTP+SSE daemon (Vera as harness, not an MCP tool) "
             "— POST /agent/run, GET /events?run_id=, GET /agent/run/<id>",
    )
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--llm", default=None, help="Ollama model; falls back to config's llm_model")
    p.add_argument("--jgen-endpoint", default=None, dest="jgen_endpoint",
                    help="e.g. http://127.0.0.1:8766 — the IDE's JGenAgentServer (N4), "
                         "only needed if a request sets \"backend\": \"jgen\"")
    # W10-f01: one entrance for OpenAI-compatible (/v1/chat/completions) and Ollama-compatible (/api/chat) clients (docs/FUSION.md).
    # NOT `--store`: the top-level --store (CrossStore path) would be overwritten by a sub-parser default (D1); the sovereign is named by the two options below.
    p.add_argument("--backend", choices=["ollama", "openai"], default=None,
                   help="W10-f01: put Vera in front of a local LLM (layer 0: the LLM answers, every sentence is typed record/testimony/constructed/unread)")
    p.add_argument("--model", default=None, help="W10-f01: the Ollama model the entrance calls (required with --backend)")
    p.add_argument("--document", action="append", default=None, help="W10-f01: a document (file or folder) that is the record; repeatable")
    p.add_argument("--strict", action="store_true", help="W10-f01: layer 1 -- bind the LLM with a grammar built from the record; nothing outside the grammar is said")
    p.add_argument("--free", action="store_true", help="W10-f01: layer 0 spelled out (the default); cannot be combined with --strict")
    p.add_argument("--sovereign-root", default=None, dest="sovereign_root", help="W10-f01: VERA_SOVEREIGN_ROOT for the basis policy")
    p.add_argument("--sovereign-store", default=None, dest="sovereign_store", help="W10-f01: VERA_SOVEREIGN_STORE for the basis policy")
    p.add_argument("--placement", default=None, help="W10-f01: sets VERA_PLACEMENT (the placement directory; without it a factual question has no typed candidate)")
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434", dest="ollama_url", help="W10-f01: the Ollama server")
    p.add_argument("--llm-timeout", type=float, default=180.0, dest="llm_timeout", help="W10-f01: seconds to wait for the LLM before LLM_UNAVAILABLE (TIMEOUT)")
    p.add_argument("--api-base", default=None, dest="api_base", help="W10-f04: the OpenAI-compatible API base for --backend openai (else VERA_LLM_API_BASE); the key is VERA_LLM_API_KEY")
    # W10-f04 (docs/FUSION.md section 6): the candidate mouth. Off unless --fill: without it nothing in any output changes.
    p.add_argument("--fill", action="store_true", help="W10-f04: ask the LLM for candidates for typed holes (testimony only, written to --ledger-file; never a record)")
    p.add_argument("--ledger-file", default=None, dest="ledger_file", help="W10-f04: the testimony ledger (append-only, hash-chained); required with --fill")
    p.add_argument("--fill-model", default=None, dest="fill_model", help="W10-f04: the model that proposes candidates (default: --model)")
    p.add_argument("--no-mask-user-text", action="store_true", dest="no_mask_user_text", help="W10-f04: send the user's sentence to the backend (the default is to send only the hole, the types and the roles)")
    p.add_argument("--fill-max-holes", type=int, default=30, dest="fill_max_holes", help="W10-f04: holes asked when the documents are loaded (more are counted as skipped_holes)")
    p.add_argument("--layer", default=None, help="W10-f05: a placement layer (a name in $VERA_PLACEMENT_LAYER_ROOT, or a path) put on the base placement: it answers only for the words the base leaves undecided. Sets VERA_PLACEMENT_LAYER." + " `vera.placement_layer` is added to each response.")
    p.add_argument("--strict-read", action="store_true", dest="strict_read", help="W3-e2: re-read the sentences of the LLM's reply strictly (no assumed reading). Without it (and VERA_READ_MODE) the default is assume: a sentence that stops only on a premise is read with the assumption put out in `vera.provenance` (an arm of kind `assumed`; never a record). NOT the layer-1 `--strict`")
    # W12-c1 (docs/INITIAL_LAYERS.md section 6): the entrance that never calls an LLM. Without --no-llm none of these does anything (--profile and --tier are refused).
    p.add_argument("--no-llm", action="store_true", dest="no_llm", help="W12-c1: never call an LLM: a record answers, everything else is a typed abstention; `vera.confidence_tiers` is added to each response")
    p.add_argument("--profile", choices=["strict", "assume"], default=None, help="W12-c1 (with --no-llm): strict (default) or assume (the assumed reading arrives with W3-e3: until then the answer is strict's and says assumptions_status)")
    p.add_argument("--tier", action="append", default=None, help="W12-c1 (with --no-llm): NAME=SPEC, a stage of the staircase (vocab=<vocab.sqlite>, law=<layer>, law+user=<layer>); repeatable. The base stage is implicit.")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("setup", help="interactive settings (LLM, allocation)")
    p.set_defaults(fn=cmd_setup)

    p = sub.add_parser("wizard", help="guided data-placement (arrow keys)")
    p.set_defaults(fn=cmd_wizard)

    p = sub.add_parser("agent", help="agent mode: tools + ReAct + approvals")
    p.add_argument("task", nargs="?", default=None)
    p.add_argument("--llm", default=None)
    p.add_argument("--yes", action="store_true", help="auto-approve (careful)")
    p.set_defaults(fn=cmd_agent)

    p = sub.add_parser(
        "obfuscate",
        help="reversible identifier obfuscation, mapping encrypted with a "
             "key derived from your store's personal state",
    )
    p.add_argument("file")
    p.add_argument("--export-key", default=None,
                   help="also export a portable recovery key to this path")
    p.set_defaults(fn=cmd_obfuscate)

    p = sub.add_parser("deobfuscate", help="restore original names")
    p.add_argument("obf_file")
    p.add_argument("map_file")
    p.add_argument("--key-file", default=None,
                   help="use an exported recovery key instead of --store")
    p.set_defaults(fn=cmd_deobfuscate)

    p = sub.add_parser(
        "watermark",
        help="leak attribution: register an owner's naming-variant, or "
             "identify candidate owners of an obfuscated file (evidence, "
             "not proof — see docs/WATERMARK.md)",
    )
    p.add_argument("action", choices=["register", "identify"])
    p.add_argument("registry", help="path to the watermark registry JSON file")
    p.add_argument("--owner-id", default=None, help="required for register")
    p.add_argument("--file", default=None, help="obfuscated .obf file, required for identify")
    p.set_defaults(fn=cmd_watermark)

    # W16-t6 (K601): vera attest
    p = sub.add_parser("attest", help="check a report's completion claims against what actually happened (sha256, collected tests, exit codes, numbers)")
    p.add_argument("report", help="the report (the completion section and/or an attest JSON block)")
    p.add_argument("--tree", required=True, help="the work tree to check the claims against")
    p.add_argument("--ledger", default=None, help="a T7 events ledger (jsonl): test_run / process_exit events give exit codes")
    p.add_argument("--rerun", action="store_true", help="re-run an allowed form (pytest / python -m pytest on tests/*.py) when no ledger event exists")
    p.add_argument("--base", default=None, help="git rev: a 'changed' claim must differ from it")
    p.add_argument("--rev", default=None, help="git rev: check file sha256 against that revision instead of the work tree")
    p.add_argument("--record", default=None, help="append the results to this testimony ledger as kind: attestation")
    p.add_argument("--extractor", choices=["structured", "V", "a", "b", "all"], default="structured")
    p.add_argument("--partial-tree", dest="partial_tree", action="store_true", help="a file missing from the tree is evidence-not-in-tree, not a mismatch (replay)")
    p.add_argument("--search-dir", dest="search_dir", action="append", default=None, help="where to look for a bare file name (relative to the tree); repeatable")
    p.add_argument("--history", action="store_true", help="a sha256 that matches a past git version is MATCHES_PAST_VERSION, not a mismatch")
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=lambda a: __import__("verantyx.attest", fromlist=["cli_main"]).cli_main(a))

    p = sub.add_parser("push-store", help="upload the store to HuggingFace")
    p.add_argument("--repo", default=None)
    p.add_argument("--private", action="store_true")
    p.set_defaults(fn=cmd_push_store)

    from .placement_fetch import dispatch as cmd_placement_dispatch
    p = sub.choices["placement"]
    p.add_argument("--from", dest="source", default=None,
                   help="fetch: tar URL。隣に .sha256 sidecar が必要です")
    p.add_argument("--dest", default=None,
                   help="fetch: 存在しない展開先 directory")
    p.set_defaults(fn=cmd_placement_dispatch)

    args = ap.parse_args(argv)
    if getattr(args, "cmd", None) in ("read", "ask", "chat", "serve") and getattr(args, "layer", None):
        import os
        os.environ["VERA_PLACEMENT_LAYER"] = args.layer       # W10-f05: read before any placement or document is read, like --sovereign-root
    # resolve store: --store > config > default
    if getattr(args, "store", None) is None:
        from .config import VeraConfig

        args.store = VeraConfig.load().store or DEFAULT_STORE
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
