"""第 2 ラウンドの修正の検査: 出自が確かめられない子プロセス・規則 0 個の回答・数値の符号と %。"""
import json
import sys
from pathlib import Path

import pytest

from tools.bank_score import checks as C
from tools.bank_score import cli
from tools.bank_score.normalize import norm
from tools.bank_score.score import score_observation
from tools.bank_score.strategies import observe_strategy
from tools.bank_score import schema

P, F, U = C.PASS, C.FAIL, C.UNJUDGED
FIX = Path(__file__).parent / "fixtures"


def _b2_items(tmp_path: Path, n: int = 2) -> Path:
    items = [{"id": f"u{i}", "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1,
              "turns": [{"role": "user", "text": f"質問{i}"}],
              "expect": {"behavior": "answer", "must_contain_any": [["月曜"]]}, "rationale": "r"}
             for i in range(1, n + 1)]
    p = tmp_path / "items.jsonl"
    p.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    return p


def _tree(tmp_path: Path, cli_src: str) -> Path:
    t = tmp_path / "tree" / "verantyx"
    t.mkdir(parents=True)
    (t / "__init__.py").write_text("")
    (t / "cli.py").write_text(cli_src)
    return tmp_path / "tree"


def _run(tmp_path: Path, tree: Path) -> int:
    return cli.main(["--bank", "B2", "--items", str(_b2_items(tmp_path)), "--tree", str(tree),
                     "--out", str(tmp_path / "out"), "--python", sys.executable])


# ---- 必須 1: 出自を確かめられなかった子プロセスの答えは採点しない ------------------------------------

def test_provenance_unverified_answer_from_outside_module_stops_with_exit_3(tmp_path):
    """ツリー内の cli.py がツリー外のモジュールを読み込み、型つき JSON を出して os._exit(0) で出自を書かずに終わる。"""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "verantyx_ext.py").write_text("ANSWER = '月曜日です。'\n")
    tree = _tree(tmp_path,
                 "import json, os, sys\n"
                 "if __name__ == '__main__':\n"  # 事前検査（import）では何もしない。ask として走るときだけ
                 f"    sys.path.insert(0, {str(outside)!r})\n"
                 "    import verantyx_ext\n"
                 "    print(json.dumps({'kind': 'answer', 'verdict': 'ANSWER', 'text': verantyx_ext.ANSWER,"
                 " 'evidence': [{'e': 1}]}))\n"
                 "    sys.stdout.flush()\n"
                 "    os._exit(0)\n")
    out = tmp_path / "out"
    assert _run(tmp_path, tree) == 3
    inv = json.loads((out / "INVALID.json").read_text(encoding="utf-8"))
    assert inv["verdict"] == "INVALID_PROVENANCE"
    assert inv["reason"] == "PROVENANCE_UNVERIFIED" and inv["stage"].startswith("item:")
    assert not (out / "summary.json").exists() and not (out / "summary.md").exists()
    assert not (out / "results.jsonl").exists()


def test_provenance_unverified_nonjson_or_crash_children_are_runtime_errors_and_never_scored(tmp_path):
    """出力を採点に使わない種類の失敗（異常終了）は runtime_error のまま続け、出自不明として数える。"""
    tree = _tree(tmp_path,
                 "import json, os, sys\n"
                 "if __name__ == '__main__':\n"
                 "    print(json.dumps({'kind': 'answer', 'verdict': 'ANSWER', 'text': '月曜日です。'}))\n"
                 "    sys.stdout.flush()\n"
                 "    os._exit(3)\n")
    out = tmp_path / "out"
    assert _run(tmp_path, tree) == 0
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["class"] for r in rows] == ["runtime_error", "runtime_error"]
    assert all(r["reason"] == "NONZERO_EXIT" and r["reason_detail"] == ["PROVENANCE_UNVERIFIED"] for r in rows)
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summ["runtime_error_provenance_unverified"] == 2 and summ["classes"]["correct"]["count"] == 0
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["provenance_total"]["processes_unverified"] == 2


# ---- 必須 2: 規則が 0 個の回答側の問題は空出力でも正答にしない ----------------------------------------

def _raw(bank, **kw):
    base = {"id": "x", "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1, "rationale": "r"}
    base.update(kw)
    return base


def _score_text(bank, expect, text, **obs_kw):
    raw = _raw(bank, expect=expect, **({"turns": [{"role": "user", "text": "q"}]} if bank == "B2"
                                       else {"brief": "依頼"}))
    errs, case = schema.validate_item(bank, raw, None)
    assert errs == [], errs
    obs = {"state": "answer", "text": text, "verdict": "ANSWER", "kind": "answer", "has_evidence": False,
           "declared_constructed": False, **obs_kw}
    return score_observation(bank, raw, case, obs)


@pytest.mark.parametrize("bank,expect", [
    ("B2", {"behavior": "answer"}),
    ("B2", {"behavior": "social"}),
    ("B3", {"behavior": "generate"}),
    ("B3", {"behavior": "generate", "outside": "derivable", "constraints": {}}),
])
def test_no_rules_vacuous_pass_is_not_a_correct_answer(bank, expect):
    for text in ("", "なにか答えた文です。"):
        sc = _score_text(bank, expect, text)
        assert sc["class"] == "unscorable" and sc["reason"] == "JUDGE_UNAVAILABLE", (bank, expect, text, sc)
        assert sc["checks"]["no_rules"] == {"result": U, "detail": {"reason": "NO_RULES"}}


def test_no_rules_does_not_change_items_that_have_a_rule():
    sc = _score_text("B2", {"behavior": "answer", "must_contain_any": [["月曜"]]}, "月曜日です。")
    assert sc["class"] == "correct" and "no_rules" not in sc["checks"]
    sc = _score_text("B2", {"behavior": "answer", "must_contain_any": [["月曜"]]}, "")
    assert sc["class"] == "wrong"
    # 棄権側の期待には回答規則が無いのが普通。no_rules を足さない（誤った応諾の判定は型だけ）
    sc = _score_text("B2", {"behavior": "abstain"}, "断定します。")
    assert sc["class"] == "false_compliance" and "no_rules" not in sc["checks"]


def test_no_rules_empty_strategy_does_not_get_correct_on_vacuous_items():
    raw = _raw("B3", brief="依頼", expect={"behavior": "generate"})
    errs, case = schema.validate_item("B3", raw, None)
    assert errs == []
    sc = score_observation("B3", raw, case, observe_strategy("B3", "empty", case))
    assert sc["class"] == "unscorable" and sc["reason"] == "JUDGE_UNAVAILABLE"


def test_no_rules_is_reported_under_judge_unavailable_reasons():
    from tools.bank_score import report
    sc = _score_text("B2", {"behavior": "answer"}, "")
    row = {"class": sc["class"], "reason": sc["reason"], "checks": sc["checks"], "reason_detail": [],
           "category": "c", "lang": "ja", "difficulty": 1, "entry": "e", "capability": None, "observation": None,
           "unknown_expect_keys": [], "id": "x", "line": 1, "bank": "B2", "class_ja": sc["class_ja"]}
    s = report.build_summary("B2", [row], {}, {"count": 0, "ids": [], "not_in_items": []})
    assert s["judge_unavailable_reasons"] == {"NO_RULES": 1} and s["class_sum"] == s["total"] == 1


# ---- 必須 3: 数値の符号と % を正規化で落とさない ----------------------------------------------------

def test_norm_keeps_leading_sign_and_trailing_percent_but_still_strips_other_punct():
    assert norm("-2") == "-2" and norm("50%") == "50%" and norm("－３") == "-3" and norm("５０％") == "50%"
    assert norm("「月曜日」！") == "月曜日" and norm("-abc-") == "abc" and norm("(50%)") == "50%"
    assert norm("100%.") == "100%" and norm("--5") == "-5" and norm("%") == "" and norm("-") == ""


def test_must_contain_sign_and_percent_are_not_dropped_by_normalization():
    # 偽の PASS だった 4 例。符号・% が落ちないので、それぞれ FAIL / FAIL / FAIL / PASS になる
    assert C.check_must_contain_any([["-2"]], "答えは2です")["result"] == F
    assert C.check_must_contain_any([["-2"]], "The answer is 12.")["result"] == F
    assert C.check_must_contain_all(["50%"], "参加者は150人")["result"] == F
    assert C.check_must_not_contain(["-3"], "13時に開始")["result"] == P
    # 合格例: 本当に符号・% が書かれているときは PASS（文末の句点があっても）
    assert C.check_must_contain_any([["-2"]], "答えは-2です。")["result"] == P
    assert C.check_must_contain_any([["-2"]], "答えは -2.")["result"] == P
    assert C.check_must_contain_all(["50%"], "参加者の50%が賛成")["result"] == P
    assert C.check_must_not_contain(["-3"], "答えは-3です")["result"] == F
