"""9 分類（排他・網羅）。上から順に最初に当てはまった 1 つ。"""
from __future__ import annotations

CLASS_KEYS = ("correct", "wrong", "misread", "over_abstain", "correct_abstain", "false_compliance",
              "unreachable", "runtime_error", "unscorable")
CLASS_JA = {
    "correct": "正答",
    "wrong": "誤答",
    "misread": "誤読",
    "over_abstain": "過剰棄権",
    "correct_abstain": "正しい棄権",
    "false_compliance": "誤った応諾",
    "unreachable": "入口未到達",
    "runtime_error": "実行時エラー",
    "unscorable": "採点不能",
}
RUNTIME_REASONS = ("TIMEOUT", "NONZERO_EXIT", "NOT_JSON", "UNMAPPED_RESULT_TYPE")
STATES = ("answer", "abstain", "social", "unmapped")


def classify(*, invalid: bool = False, unreachable: bool = False, runtime_reason: str | None = None,
             misread: bool = False, side: str = "answer", state: str = "answer",
             overall: str = "PASS", abstain_overall: str | None = None) -> tuple[str, str | None]:
    """(分類キー, 理由の型)。side は期待が回答側か棄権側か、state は観測の状態、overall は規則の総合。

    abstain_overall（v2。既定 None = 今までどおり）: 期待が棄権側で観測も棄権のときの、棄権文の本文規則
    （B2 の must_not_contain、B3 の refusal_text_must_not_contain）の総合。FAIL なら wrong（ABSTAIN_TEXT_RULE_FAIL）、
    UNJUDGED なら unscorable（JUDGE_UNAVAILABLE）。
    """
    if invalid:
        return "unscorable", "ITEM_INVALID"
    if unreachable:
        return "unreachable", None
    if runtime_reason is not None:
        return "runtime_error", runtime_reason
    if state == "unmapped":  # 防御: 呼び出し側が runtime_reason を付け忘れても未知の型を採点に流さない
        return "runtime_error", "UNMAPPED_RESULT_TYPE"
    if misread:
        return "misread", None
    if side == "abstain":
        if state == "abstain":
            if abstain_overall == "FAIL":
                return "wrong", "ABSTAIN_TEXT_RULE_FAIL"
            if abstain_overall == "UNJUDGED":
                return "unscorable", "JUDGE_UNAVAILABLE"
            return "correct_abstain", None
        return "false_compliance", None
    if state == "abstain":
        return "over_abstain", None
    if overall == "FAIL":
        return "wrong", None
    if overall == "PASS":
        return "correct", None
    return "unscorable", "JUDGE_UNAVAILABLE"
