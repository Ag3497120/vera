"""W16-t3 第 4 ラウンド: 極性（3d）・はい／いいえ（3c）・選択の問い（R11）。
検査データ artifacts/w16-t3/r4/cases_r4.jsonl は、事前登録 docs/FUSION.md §9.13 の規則から手で期待を決め、コードを直す前に凍結したもの（sha256 を確かめる）。"""
import collections
import hashlib
import json
import os

import pytest

from verantyx import decode_grammar as G
from verantyx import quote_check as QC

R4 = os.path.join(os.path.dirname(__file__), "..", "artifacts", "w16-t3", "r4")
# 第 5 ラウンド: J-R5-1（§9.16）。試験の対象を cases_r4.jsonl（最初に凍結した版。O-02 の期待は unanchored／NO_CONTENT_TO_CHECK）に戻した。cases_r4b.jsonl は残す（凍結の検査は両方）
CASES = [json.loads(l) for l in open(os.path.join(R4, "cases_r4.jsonl"), encoding="utf-8") if l.strip()]


def test_cases_r4_are_frozen():
    for name, sha in (("cases_r4.jsonl", "cases_r4.sha256"), ("cases_r4b.jsonl", "cases_r4b.sha256")):
        want = open(os.path.join(R4, sha)).read().split()[0]
        assert hashlib.sha256(open(os.path.join(R4, name), "rb").read()).hexdigest() == want, name


def test_cases_r4_counts():
    n = collections.Counter(c["type"] for c in CASES)
    assert len(CASES) >= 24
    assert n["P"] + n["PC"] + n["YP"] >= 10 and n["PC"] >= 4
    assert n["Y"] + n["YP"] >= 6
    assert n["S"] + n["SC"] >= 6
    assert n["O"] >= 2


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


# ---- 第 4 ラウンドのレビュー M1（§9.13c）: 応答の語＋問いの語の繰り返しだけの答えは確かめられない ----
# 第 5 ラウンド: J-R5-1（§9.16）。YC-02 の期待だけ強めた r5/cases_r4c_r5.jsonl を読む（元の cases_r4c.jsonl の凍結の検査は下のとおり）
CASES_C = [json.loads(l) for l in open(os.path.join(R4, "..", "r5", "cases_r4c_r5.jsonl"), encoding="utf-8") if l.strip()]


def test_cases_r4c_are_frozen():
    want = open(os.path.join(R4, "cases_r4c.sha256")).read().split()[0]
    assert hashlib.sha256(open(os.path.join(R4, "cases_r4c.jsonl"), "rb").read()).hexdigest() == want


def test_cases_r4c_counts():
    n = collections.Counter(c["type"] for c in CASES_C)
    assert len(CASES_C) >= 8
    assert n["YQ"] >= 4 and n["F"] >= 1 and n["YC"] >= 3


@pytest.mark.parametrize("case", CASES_C, ids=[c["id"] for c in CASES_C])
def test_case_r4c(case, tmp_path):
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
