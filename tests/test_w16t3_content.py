"""W16-t3 第 3 ラウンド: 内容語の被覆（規則 3b）と文書の決め方（R6）。
検査データ artifacts/w16-t3/r3/cases.jsonl は、コードを直す前に R1〜R6 から手で期待を決めて凍結したもの（sha256 を確かめる）。
第 3 ラウンドのレビュー（M1・M2）の訂正 R1′・R6′ の検査データ artifacts/w16-t3/r3b/cases_r3b.jsonl（51 件のうち R6-2 の期待だけ変え、新しい 9 件を足した）も同じく凍結。試験のパラメータは r3b から取る。"""
import hashlib
import json
import os

import pytest

from verantyx import decode_grammar as G
from verantyx import quote_check as QC

R3 = os.path.join(os.path.dirname(__file__), "..", "artifacts", "w16-t3", "r3")
R3B = os.path.join(os.path.dirname(__file__), "..", "artifacts", "w16-t3", "r3b")
CASES = [json.loads(l) for l in open(os.path.join(R3B, "cases_r3b.jsonl"), encoding="utf-8") if l.strip()]
# 誤答の型 = C1〜C3（第 3 ラウンドの 27 件）と N1・N2・N3 の期待が anchored でないもの。C4-b（正しい言い換えの偽の錨なし）と R6 は数えない
WRONG_TYPES = ("C1", "C2", "C3", "N1", "N2", "N3")


def test_cases_are_frozen():
    for d, name, sha in ((R3, "cases.jsonl", "cases.sha256"), (R3B, "cases_r3b.jsonl", "cases_r3b.sha256")):
        want = open(os.path.join(d, sha)).read().split()[0]
        got = hashlib.sha256(open(os.path.join(d, name), "rb").read()).hexdigest()
        assert got == want, name
    assert len(CASES) >= 40
    wrong = [c for c in CASES if c["type"] in WRONG_TYPES and c["expect"] != "anchored"]
    assert len(wrong) >= 30, len(wrong)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case, tmp_path):
    paths = []
    for name, body in case["docs"].items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body + "\n", encoding="utf-8")
        paths.append(str(p))
    rec = G.load_records(paths)
    res = QC.check(case["answer"], case["quotes"], rec, question=case["question"])
    d = res.to_dict()
    assert d["verdict"] == case["expect"], (d, case["note"])
    if case["expect_reason_prefix"]:
        assert (d.get("reason") or "").startswith(case["expect_reason_prefix"]), d
