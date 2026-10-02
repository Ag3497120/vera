"""自明な戦略（Vera を呼ばない）。同じ checks / classify にかけて、バンクの弱さを毎回見えるようにする。"""
from __future__ import annotations

from pathlib import Path

STRATEGIES = ("empty", "always_abstain", "echo_input", "echo_documents", "all_labels", "first_option")

STRATEGY_JA = {
    "empty": "空出力",
    "always_abstain": "常に棄権",
    "echo_input": "入力の丸写し",
    "echo_documents": "文書の丸写し",
    "all_labels": "全ラベル列挙",
    "first_option": "常に最初の選択肢",
}

_NA = {
    ("B1", "echo_documents"): "B1 の問題には文書が無い",
    ("B1", "all_labels"): "B1 にはラベルの選択肢が無い",
    ("B1", "first_option"): "B1 には選択肢が無い",
    ("B2", "first_option"): "B2 には選択肢が無い",
    ("B3", "all_labels"): "B3 にはラベルが無い",
    ("B3", "first_option"): "B3 には選択肢が無い",
}


def not_applicable(bank: str, strategy: str) -> str | None:
    """対象外ならその理由、対象なら None（黙って省かず要約に理由を出す）。"""
    return _NA.get((bank, strategy))


def _blank(state: str, **kw: object) -> dict:
    o = {"state": state, "status": None, "verdict": None, "kind": None, "door": None, "text": "", "values": None,
         "partial": False, "declared_constructed": False, "has_evidence": False, "label_override": False,
         "exit_code": None, "entry": "strategy", "argv": []}
    o.update(kw)
    return o


def observe_strategy(bank: str, strategy: str, case: dict) -> dict:
    """戦略の観測を作る。構成物の申告も根拠も付けない。"""
    if bank == "B1":
        if strategy == "empty":
            return _blank("answer", readable=True, clauses=[], relations=[])
        if strategy == "always_abstain":
            return _blank("abstain", readable=False, clauses=[], relations=[])
        if strategy == "echo_input":
            return _blank("answer", readable=True, clauses=[{"predicate": case["input"], "roles": {}}], relations=[])
    elif bank in ("B2", "B3"):
        docs = [d["text"] for d in case["docs"]]
        text = None
        if strategy == "empty":
            text = ""
        elif strategy == "always_abstain":
            return _blank("abstain")
        elif strategy == "echo_input":
            text = case["last_user"] if bank == "B2" else case["brief"]
        elif strategy == "echo_documents":
            text = "\n".join(docs)
        elif strategy == "all_labels" and bank == "B2":
            text = "SUPPORTED REFUTED NOT_IN_DOCS"
        if text is not None:
            return _blank("answer", text=text)
    elif bank == "B5":
        opts = case.get("options") or []
        if strategy == "empty":
            return _blank("answer", decision="answer", answer="", answer_option_index=None, vocab_mapping=None)
        if strategy == "always_abstain":
            return _blank("abstain", decision="escalate", answer=None, answer_option_index=None, vocab_mapping=None)
        if strategy == "echo_input":
            return _blank("answer", decision="answer", answer=case["question"], answer_option_index=None,
                          vocab_mapping=None)
        if strategy == "echo_documents":
            try:
                body = Path(case["frame_path"]).read_text(encoding="utf-8")
            except (OSError, TypeError):
                body = ""
            return _blank("answer", decision="answer", answer=body, answer_option_index=None, vocab_mapping=None)
        if strategy == "all_labels":
            return _blank("answer", decision="answer", answer="\n".join(opts), answer_option_index=None,
                          vocab_mapping=None)
        if strategy == "first_option":
            return _blank("answer", decision="answer", answer=opts[0] if opts else "",
                          answer_option_index=0 if opts else None, vocab_mapping=None)
    raise ValueError(f"対象外の戦略: {bank}/{strategy}")
