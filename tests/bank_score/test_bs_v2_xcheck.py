"""xcheck: 設計者のスクリプトは別プロセスで関数だけを呼ぶ（main は呼ばない）・バンクのハッシュ検査・verantyx を読んだら失敗。"""
import json
from pathlib import Path

import pytest

import v2_util as U
from tools.bank_score import xcheck
from v2_util import b1_item, b2_item, clause

DESIGNER_OK = '''
import json, sys

def judge(item, text, state):
    beh = item["expect"]["behavior"]
    if beh == "abstain":
        return (state == "abstain"), ([] if state == "abstain" else ["not abstain state"])
    ok = state != "abstain" and "六時" in text
    return ok, ([] if ok else ["missing any[...]"])

def main():
    # main を呼ぶと baseline.json を上書きしてしまうバンクがある。xcheck は main を呼んではならない。
    open(__file__ + ".baseline.json", "w").write("{}")

if __name__ == "__main__":
    main()
'''


def setup_bank(tmp_path, designer_src=DESIGNER_OK):
    root = tmp_path / "bank" / "v2"
    (root / "audit").mkdir(parents=True)
    items = [b2_item("a", must_contain_any=[["六時"]], reference="六時です。"),
             b2_item("b", behavior="abstain", reference="分かりません。")]
    U.write_jsonl(root / "items.jsonl", items)
    (root / "audit" / "score.py").write_text(designer_src, encoding="utf-8")
    return root


def run(root, out, probes="reference,strategies"):
    return xcheck.main(["--bank", "B2", "--items", str(root / "items.jsonl"), "--designer", str(root / "audit" / "score.py"),
                        "--probes", probes, "--out", str(out)])


def test_agreement_counts_and_main_is_never_called_and_bank_files_are_untouched(tmp_path):
    root = setup_bank(tmp_path)
    before = xcheck.sha_tree(root)
    code = run(root, tmp_path / "x")
    assert code == 0
    assert xcheck.sha_tree(root) == before  # main を呼んでいない（baseline.json が書かれていない）
    assert not (root / "audit" / "score.py.baseline.json").exists()
    ag = json.loads((tmp_path / "x" / "agreement.json").read_text(encoding="utf-8"))
    assert ag["bank_files_unchanged"] is True and ag["child_loaded_verantyx"] is False
    assert ag["probes"]["reference/pass"] == {"n": 2, "agree": 2, "disagree": 0, "by_strategy": {}}
    st = ag["probes"]["strategies/pass"]
    assert st["n"] == 2 * 5 and st["disagree"] == 0  # B2 の対象の戦略は 5 つ
    assert (tmp_path / "x" / "mismatches.jsonl").read_text(encoding="utf-8") == ""


def test_disagreements_are_listed_one_by_one_with_only_the_first_word_of_the_designers_reason(tmp_path):
    src = DESIGNER_OK.replace('"missing any[...]"', '"missing any[この中身は写してはならない]"') \
        .replace('ok = state != "abstain" and "六時" in text', 'ok = False')
    root = setup_bank(tmp_path, src)
    assert run(root, tmp_path / "x", "reference") == 0
    rows = [json.loads(l) for l in (tmp_path / "x" / "mismatches.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["a"] and rows[0]["probe"] == "reference"
    assert rows[0]["ours"] is True and rows[0]["designer"] is False
    assert rows[0]["designer_reason"] == "missing"
    assert "この中身" not in (tmp_path / "x" / "mismatches.jsonl").read_text(encoding="utf-8")


def test_exit_3_when_the_designer_script_changes_a_bank_file(tmp_path):
    src = DESIGNER_OK.replace("def judge(item, text, state):", "def judge(item, text, state):\n"
                                                              "    open(%r, 'a').write('x')" % "@@PATH@@")
    root = setup_bank(tmp_path)
    (root / "audit" / "score.py").write_text(src.replace("@@PATH@@", str(root / "items.jsonl")), encoding="utf-8")
    assert run(root, tmp_path / "x", "reference") == 3


def test_exit_1_when_the_child_process_loads_verantyx(tmp_path):
    src = "import verantyx\n" + DESIGNER_OK
    root = setup_bank(tmp_path, src)
    assert run(root, tmp_path / "x", "reference") == 1


def test_b1_designer_verdicts_map_onto_our_classes(tmp_path):
    designer = '''
def judge(item, out):
    if not item["expect"]["readable"]:
        return ("correct", None) if not out.get("readable") else ("misread", "structured an unreadable input")
    if not out.get("readable"):
        return "abstain", None
    cl = out.get("clauses") or []
    return ("correct", None) if cl and cl[0].get("predicate") == "行く" else ("incomplete", "clause count")
'''
    root = tmp_path / "b1" / "v2"
    (root / "audit").mkdir(parents=True)
    U.write_jsonl(root / "items.jsonl", [b1_item("a", "文", [clause("行く", {"agent": "甲"})]),
                                         b1_item("b", "ぬるぷ", [], readable=False, must_not=[{"readable": True}])])
    (root / "audit" / "score.py").write_text(designer, encoding="utf-8")
    code = xcheck.main(["--bank", "B1", "--items", str(root / "items.jsonl"), "--designer", str(root / "audit" / "score.py"),
                        "--probes", "reference,strategies", "--out", str(tmp_path / "x")])
    assert code == 0
    ag = json.loads((tmp_path / "x" / "agreement.json").read_text(encoding="utf-8"))
    assert ag["probes"]["reference/b1_verdict"]["agree"] == 2
    assert ag["probes"]["strategies/b1_verdict"]["n"] == 6 and ag["probes"]["strategies/b1_verdict"]["disagree"] == 0


def test_first_word_keeps_only_ascii_words():
    assert xcheck.first_word("missing all[中身]") == "missing"
    assert xcheck.first_word("forbidden[x]") == "forbidden"
    assert xcheck.first_word("日本語の理由") == "<non-ascii>"
    assert xcheck.first_word(None) is None
