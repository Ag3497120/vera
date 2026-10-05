"""W16-t3b: 役割の助詞（R13）・時制（R14）・1 つの引用で支える（R15）・出典の名前（R16）。
検査データ artifacts/w16-t3b/cases.jsonl は、事前登録 docs/FUSION.md §10 の規則から手で期待を決め、コードを直す前に凍結したもの（sha256 を確かめる）。"""
import collections
import hashlib
import json
import os

import pytest

from verantyx import decode_grammar as G
from verantyx import quote_check as QC

ART = os.path.join(os.path.dirname(__file__), "..", "artifacts", "w16-t3b")
# cases.jsonl（第 1 ラウンドの凍結）・cases_b.jsonl（訂正。H-05 は穴を固定する期待なので試験の対象から外した）は赤の記録に残す。
# 試験の対象は第 2 ラウンドの cases_c.jsonl（docs §10.12。R15 の項目の改訂より前に凍結）。誤答が anchored であることを assert する試験は置かない。
CASES = [json.loads(l) for l in open(os.path.join(ART, "cases_c.jsonl"), encoding="utf-8") if l.strip()]


# 正しい対照（anchored が正しい行）の id
CONTROLS = {"RO-05", "RO-06", "TE-05", "TE-06", "SP-04", "SP-09"}


def test_cases_are_frozen():
    for shafile in ("cases.sha256", "cases_b.sha256", "cases_c.sha256", "prereg.sha256", "prereg2.sha256"):
        for line in open(os.path.join(ART, shafile)):
            if not line.strip():
                continue
            sha, name = line.split()
            assert hashlib.sha256(open(os.path.join(ART, name), "rb").read()).hexdigest() == sha, name


def test_cases_counts():
    n = collections.Counter(c["type"] for c in CASES)
    # チケットの文のとおり、4 つの型（H を除く）の合計で 24 件以上（H を数えに入れない）
    assert sum(n[t] for t in ("RO", "TE", "SP", "SR")) >= 24, n
    for t in ("RO", "TE", "SP", "SR"):
        assert n[t] >= 4, t
        controls = [c for c in CASES if c["type"] == t and (c["expect"] == "anchored" and (t != "SR" or c["expect_found"] == ["exact"]))]
        assert len(controls) >= 1, t
    # 攻撃の Q01〜Q04 の形
    ids = {c["id"] for c in CASES}
    assert {"RO-01", "TE-01", "SP-01", "SR-01"} <= ids
    # 誤答が anchored であることを期待する試験を置かない（SP・RO・TE の誤答の期待は unanchored）
    assert not [c["id"] for c in CASES if c["type"] in ("RO", "TE", "SP") and c["expect"] == "anchored" and c["id"] not in CONTROLS], "anchored を期待する行は正しい対照だけ"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case, tmp_path):
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
    else:
        assert d["verdict"] != "anchored" or d.get("reason") is None, d
    if case.get("expect_found") is not None:
        assert [x["found"] for x in d["quotes"]] == case["expect_found"], d
    if case.get("expect_source_record") is not None:
        assert [x.get("source_record") for x in d["quotes"]] == [case["expect_source_record"]], d
        assert [x.get("source_claimed") for x in d["quotes"]] == [case["quotes"][0]["source"]], d
