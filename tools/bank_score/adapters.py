"""バンク × 入口: 問題 → 呼び出し引数、Vera の型つき結果 → 採点用の観測。到達表。

Vera の内部関数は呼ばない。入口は `python -m verantyx.cli`（= `vera`）の `ask` だけ。
既定の入口から届かない能力は「入口未到達」として採点する（内部関数で代用しない）。
"""
from __future__ import annotations

# 入口の決め方: README が最初に案内する `vera` CLI のうち、そのバンクの入力（文書・依頼・会話）を
# 受け取り、型つきの結果を返す最初のサブコマンド。
ENTRIES = {
    # B1 の "mod-semantic-read" (W1-a2): 読解の入口 `python -m verantyx.semantic_read --text=<文>`（1 問ずつ別プロセス）。既定の入口は cli のまま。
    "B1": ("cli", "mod-semantic-read"),
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


# 入口が走らせるモジュール（子プロセス）。閉じた集合。ここに無いモジュールは走らせない（runner.ALLOWED_MODULES と同じ）。
ENTRY_MODULES = {"cli": "verantyx.cli", "cli-ask": "verantyx.cli", "cli-ask-round5": "verantyx.cli",
                 "mod-semantic-read": "verantyx.semantic_read"}
ENTRY_NOTES = {
    "mod-semantic-read": "B1 の読解の入口: python -m verantyx.semantic_read --text=<入力の文字列だけ>（言語・分類名・現象・誤読の型は渡さない。言語は入口が文字種で決める）",
}
DEFAULT_ENTRY_NOTE = "既定: README が最初に案内する vera CLI のうち、そのバンクの入力を受け取り型つきの結果を返す最初のサブコマンド"
CHILD_ARGV_TEMPLATES = {
    "mod-semantic-read": ["<python>", "-c", "<BOOTSTRAP: runpy.run_module('verantyx.semantic_read', run_name='__main__')>",
                          "run_module", "verantyx.semantic_read", "--text=<入力>"],
}
DEFAULT_CHILD_ARGV_TEMPLATE = ["<python>", "-c", "<BOOTSTRAP: runpy.run_module('verantyx.cli', run_name='__main__')>",
                               "run", "ask", "[--mode round5] [--document <file>...] -- <query>"]


def entry_module(entry: str) -> str:
    return ENTRY_MODULES[entry]


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
        missing = [] if entry == "mod-semantic-read" else ["sentence_structure"]
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
    if bank == "B1" and entry == "mod-semantic-read":
        # 入力の文字列だけを渡す（規約 §1）。--lang も、分類名・現象・誤読の型も渡さない。`--text=` の形なので - で始まる文も option と誤読されない
        return {"module": "verantyx.semantic_read", "argv": ["--text=" + case["input"]], "files": []}
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
    return {"module": "verantyx.cli", "argv": argv, "files": [{"filename": d["filename"], "text": d["text"]} for d in case["docs"]]}


def _state(raw: dict, profile: str = "w1s", bank: str | None = None) -> str:
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
    if profile == "v2" and bank == "B3" and raw.get("constructed") is True:
        # v2 の B3: 閉包外の構成物（constructed: true）で、verdict が回答でも棄権でもない型（EXPLAINED_BY_UNITS など）は
        # 構成した答えとして扱う（型の区別は b3_state が観測の型から行う。D9）
        return "answer"
    return "unmapped"


def evidence_texts(raw: dict) -> list[str]:
    """Vera の結果から根拠の文字列を集める（v2 の B2 の根拠照合用）。形が読めないものは集めない。"""
    out: list[str] = []

    def take(x: object) -> None:
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            if isinstance(x.get("text"), str):
                out.append(x["text"])
        elif isinstance(x, list):
            for e in x:
                take(e)
    take(raw.get("evidence"))
    take(raw.get("sources"))
    return out


def observe(bank: str, raw: dict, entry: str, argv: list[str], exit_code: int, raw_item: dict | None = None,
            profile: str = "w1s") -> dict:
    """Vera の型つき結果 → 観測。状態は型（kind / verdict / status）だけから決める。本文の文言は見ない。"""
    if bank == "B1" and entry == "mod-semantic-read":
        return _observe_semantic_read(raw, entry, argv, exit_code)
    state = _state(raw, profile, bank)
    verdict = raw.get("verdict") if isinstance(raw.get("verdict"), str) else None
    label_override = False
    if profile == "v2":
        if (bank == "B2" and raw_item is not None and verdict == "NOT_IN_DOCS"
                and raw_item.get("category") == "sentence_check" and raw_item["expect"].get("behavior") != "abstain"):
            state = "answer"  # 文のチェック問題では NOT_IN_DOCS は棄権でなく「未記載」というラベルの回答
            label_override = True
    elif (bank == "B2" and raw_item is not None and verdict == "NOT_IN_DOCS"
            and str(raw_item["expect"].get("reference", "")).strip().upper() in ("SUPPORTED", "REFUTED", "NOT_IN_DOCS")
            and raw_item["expect"].get("behavior") != "abstain"):
        # 文のチェック問題では NOT_IN_DOCS は棄権でなく「未記載」というラベルの回答（one.py は棄権側の接頭辞に入れている）
        state = "answer"
        label_override = True
    text = raw.get("text") if isinstance(raw.get("text"), str) else ""
    created = raw.get("created") is True or raw.get("kind") == "created" or verdict == "CREATED"
    obs = {
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
    if profile == "v2":
        obs["constructed"] = raw.get("constructed") is True
        obs["evidence_texts"] = evidence_texts(raw)
    return obs


def _observe_semantic_read(raw: dict, entry: str, argv: list[str], exit_code: int) -> dict:
    """読解の入口（B1）の出力 → 観測。`readable` は型付きの真偽: 真は answer、偽は abstain。真偽でなければ unmapped（実行時エラー
    UNMAPPED_RESULT_TYPE）。readable・clauses・relations を v2/score.py:b1_output がそのまま読む。文言は見ない。"""
    readable = raw.get("readable")
    state = "answer" if readable is True else "abstain" if readable is False else "unmapped"
    return {"state": state, "status": None, "verdict": None, "kind": None, "door": None, "text": "", "values": None,
            "partial": False, "declared_constructed": False, "has_evidence": False, "label_override": False,
            "exit_code": exit_code, "entry": entry, "argv": argv, "constructed": False, "evidence_texts": [],
            "readable": readable if isinstance(readable, bool) else None,
            "clauses": raw.get("clauses") if isinstance(raw.get("clauses"), list) else [],
            "relations": raw.get("relations") if isinstance(raw.get("relations"), list) else []}
