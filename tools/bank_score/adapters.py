"""バンク × 入口: 問題 → 呼び出し引数、Vera の型つき結果 → 採点用の観測。到達表。

Vera の内部関数は呼ばない。入口は `python -m verantyx.cli`（= `vera`）の `ask` だけ。
既定の入口から届かない能力は「入口未到達」として採点する（内部関数で代用しない）。
"""
from __future__ import annotations

# 入口の決め方: README が最初に案内する `vera` CLI のうち、そのバンクの入力（文書・依頼・会話）を
# 受け取り、型つきの結果を返す最初のサブコマンド。
ENTRIES = {
    "B1": ("cli",),
    "B2": ("cli-ask-round5", "cli-ask"),
    "B3": ("cli-ask-round5",),
    "B5": ("cli",),
}
DEFAULT_ENTRY = {"B1": "cli", "B2": "cli-ask-round5", "B3": "cli-ask-round5", "B5": "cli"}

# 結果型 → 状態の対応表。`verantyx/one.py` 18-20 行の写し（tests が ast で一致を確かめる）。
REFUSAL_KINDS = {"unknown", "not_yet", "cannot", "unreadable"}
REFUSAL_PREFIXES = ("UNKNOWN", "ABSTAIN", "AMBIGUOUS", "NOT_IN_DOCS", "UNCONFIRMED", "TIED", "UNGROUNDED",
                    "DOCUMENT_NOT_SPECIFIED")
ANSWER_VERDICTS = {"ANSWER", "CREATED"}
ANSWER_KINDS = {"answer", "skill", "created"}

# 入口に無い能力（既定の入口から未到達）。値は人が読む理由。
CAPABILITY_REASONS = {
    "sentence_structure": "節構造（述語・役割・極性・量化・節間関係）を返す口が CLI・MCP 扉・README の公開 API に無い",
    "frame_question_answer": "枠ファイルを読み込ませて質問に答える口が CLI・MCP 扉・README の公開 API に無い",
    "conversation_history": "ask は 1 発話しか受け取らず、先行ターン（会話履歴）を渡す口が無い",
    "documents": "legacy の ask は文書を受け取れない（--document は --mode round5 専用）",
}


def check_entry(bank: str, entry: str | None) -> str:
    """表に無い入口は ValueError（近い入口に寄せない）。None なら既定。"""
    if entry is None:
        return DEFAULT_ENTRY[bank]
    if entry not in ENTRIES[bank]:
        raise ValueError(f"{bank} の入口は {list(ENTRIES[bank])} のどれか（指定: {entry!r}）")
    return entry


def reachability(bank: str, entry: str, case: dict) -> dict:
    """到達表。missing が空なら reachable。"""
    missing: list[str] = []
    if bank == "B1":
        missing = ["sentence_structure"]
    elif bank == "B5":
        missing = ["frame_question_answer"]
    elif bank == "B2":
        if len(case["turns"]) > 1:
            missing.append("conversation_history")
        if entry == "cli-ask" and case["docs"]:
            missing.append("documents")
    return {"reachable": not missing, "capability": "+".join(missing) if missing else None,
            "missing": missing, "reasons": [CAPABILITY_REASONS[m] for m in missing]}


def build_call(bank: str, entry: str, case: dict) -> dict:
    """到達できる問題の呼び出し: argv（ask 以降）とそれに必要な文書ファイル。"""
    if bank == "B2":
        query = case["last_user"]
    elif bank == "B3":
        query = case["brief"]
    else:  # pragma: no cover - B1/B5 は到達しない
        raise ValueError(f"{bank} は {entry} から呼べない")
    argv = ["ask"]
    if entry == "cli-ask-round5":
        argv += ["--mode", "round5"]
        for d in case["docs"]:
            argv += ["--document", d["filename"]]
    argv += ["--", query]  # query が - で始まっても option と誤読させない
    return {"argv": argv, "files": [{"filename": d["filename"], "text": d["text"]} for d in case["docs"]]}


def _state(raw: dict) -> str:
    verdict, kind, status = raw.get("verdict"), raw.get("kind"), raw.get("status")
    if status == "PARTIAL_COMPLETENESS_UNVERIFIED" or verdict == "PARTIAL":
        return "answer"
    if (isinstance(verdict, str) and verdict in ANSWER_VERDICTS) or (isinstance(kind, str) and kind in ANSWER_KINDS):
        return "answer"
    if kind == "social":
        return "social"
    if (isinstance(kind, str) and kind in REFUSAL_KINDS) or (
            isinstance(verdict, str) and verdict.startswith(REFUSAL_PREFIXES)):
        return "abstain"
    return "unmapped"


def observe(bank: str, raw: dict, entry: str, argv: list[str], exit_code: int, raw_item: dict | None = None) -> dict:
    """Vera の型つき結果 → 観測。状態は型（kind / verdict / status）だけから決める。本文の文言は見ない。"""
    state = _state(raw)
    verdict = raw.get("verdict") if isinstance(raw.get("verdict"), str) else None
    label_override = False
    if (bank == "B2" and raw_item is not None and verdict == "NOT_IN_DOCS"
            and str(raw_item["expect"].get("reference", "")).strip().upper() in ("SUPPORTED", "REFUTED", "NOT_IN_DOCS")
            and raw_item["expect"].get("behavior") != "abstain"):
        # 文のチェック問題では NOT_IN_DOCS は棄権でなく「未記載」というラベルの回答（one.py は棄権側の接頭辞に入れている）
        state = "answer"
        label_override = True
    text = raw.get("text") if isinstance(raw.get("text"), str) else ""
    created = raw.get("created") is True or raw.get("kind") == "created" or verdict == "CREATED"
    return {
        "state": state,
        "status": raw.get("status"),
        "verdict": verdict,
        "kind": raw.get("kind"),
        "door": raw.get("door"),
        "text": text,
        "values": raw.get("values"),
        "partial": raw.get("status") == "PARTIAL_COMPLETENESS_UNVERIFIED" or verdict == "PARTIAL",
        "declared_constructed": bool(created),
        "has_evidence": bool(raw.get("evidence") or raw.get("sources")),
        "label_override": label_override,
        "exit_code": exit_code,
        "entry": entry,
        "argv": argv,
    }
