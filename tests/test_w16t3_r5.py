"""W16-t3 第 5 ラウンド: 確かめる中身の無い答え（R12／規則 3e、K654）。
検査データ artifacts/w16-t3/r5/cases_r5.jsonl は、事前登録 docs/FUSION.md §9.16 の規則から手で期待を決め、コードを直す前に凍結したもの（sha256 を確かめる）。"""
import collections
import hashlib
import json
import os

import pytest

from verantyx import decode_grammar as G
from verantyx import quote_check as QC

R5 = os.path.join(os.path.dirname(__file__), "..", "artifacts", "w16-t3", "r5")
# cases_r5.jsonl は直す前の赤の記録に使った凍結版（残す）。SO-03 の理由だけ訂正した cases_r5b.jsonl が試験の対象（§9.16b）
CASES = [json.loads(l) for l in open(os.path.join(R5, "cases_r5b.jsonl"), encoding="utf-8") if l.strip()]


def test_cases_r5_are_frozen():
    for shafile in ("cases_r5.sha256", "cases_r5b.sha256"):
        for line in open(os.path.join(R5, shafile)):
            if not line.strip():
                continue
            sha, name = line.split()
            assert hashlib.sha256(open(os.path.join(R5, name), "rb").read()).hexdigest() == sha, name


def test_cases_r5_counts():
    n = collections.Counter(c["type"] for c in CASES)
    assert len(CASES) >= 12
    # SO-03（左様です。）は R12 の項目ではない（直す前も後も ANSWER_CONTENT_NOT_IN_QUOTE。§9.16c）ので、R12 の型の SO は id の集合で除いて数える
    r12_so = [c for c in CASES if c["type"] == "SO" and c["id"] != "SO-03"]
    assert len(r12_so) >= 3
    assert n["SO"] >= 3 and n["QO"] >= 3 and n["PR"] >= 4 and n["C"] >= 2
    assert sum(1 for c in CASES if c["type"] == "PR" and c["expect"] == "anchored") >= 2


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_r5(case, tmp_path):
    paths = []
    for name, body in case["docs"].items():
        p = tmp_path / name
        p.write_text(body + "\n", encoding="utf-8")
        paths.append(str(p))
    rec = G.load_records(paths)
    d = QC.check(case["answer"], case["quotes"], rec, question=case["question"]).to_dict()
    assert d["verdict"] == case["expect"], (d, case["note"])
    if case["expect_reason_prefix"]:
        assert (d.get("reason") or "").startswith(case["expect_reason_prefix"]), d


def test_r12_no_content_reason_precedes_polarity(tmp_path):
    """コードの後に書いた特性の試験（凍結データではない。レビュー r1 の M2、§9.16c）。
    述語が 非自立可能（ある・できる）だけの否定の答え × 肯定の引用は、印の順で 3e が 3d より先なので、
    第 4 ラウンドの POLARITY_DIFFERS ではなく NO_CONTENT_TO_CHECK になる（verdict は unanchored のまま。polarity は計算される）。"""
    p = tmp_path / "doc.txt"
    p.write_text("予備の鍵は事務室にあります。\n", encoding="utf-8")
    rec = G.load_records([str(p)])
    quotes = [{"source": "doc.txt", "line": 1, "text": "予備の鍵は事務室にあります。"}]
    for ans in ("ありません。", "いいえ、ありません。"):
        r = QC.check(ans, quotes, rec, question="予備の鍵はありますか")
        assert r.verdict == "unanchored", ans
        assert r.to_dict()["reason"] == "NO_CONTENT_TO_CHECK", ans
        assert r.polarity is not None, ans
