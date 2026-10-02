"""v2 の隔離リスト（辞書型の 2 形と配列）: 受け入れ、食い違い・件数違い・形の誤りの拒否、理由の文を写さないこと。"""
import json
import sys
from pathlib import Path

import pytest

import v2_util as U
from tools.bank_score import cli, schema

TREE = Path(__file__).resolve().parents[2]


def w(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_three_shapes_are_read_with_their_shape_names(tmp_path):
    a = schema.load_quarantine_info(w(tmp_path, "a.json", ["x", "y"]))
    assert a == {"ids": ["x", "y"], "shape": "list", "n_declared": None}
    b = schema.load_quarantine_info(w(tmp_path, "b.json", {"quarantined": [{"id": "x", "reason": "r"}, {"id": "y"}]}))
    assert b["ids"] == ["x", "y"] and b["shape"] == "quarantined"
    c = schema.load_quarantine_info(w(tmp_path, "c.json", {"ids": ["x", "y"], "n_quarantined": 2, "reasons": {"x": "r"}}))
    assert c["ids"] == ["x", "y"] and c["shape"] == "ids" and c["n_declared"] == 2
    # B5 の実際の形: quarantined が id の文字列の配列（理由は別の鍵）
    d = schema.load_quarantine_info(w(tmp_path, "d.json", {"quarantined": ["x", "y"], "n_quarantined": 2, "reasons": {}}))
    assert d["ids"] == ["x", "y"] and d["shape"] == "quarantined"
    assert schema.load_quarantine(w(tmp_path, "a2.json", ["x"])) == ["x"]  # 既存の関数は id の配列を返すまま
    assert schema.load_quarantine_info(None) == {"ids": [], "shape": None, "n_declared": None}


@pytest.mark.parametrize("data", [
    {"ids": ["x", "y"], "n_quarantined": 3},                      # 件数違い
    {"quarantined": [{"id": "x"}], "ids": ["x", "y"]},            # 両方の鍵があって食い違う
    {"a": 1},                                                      # どの形でもない
    [1, 2],                                                        # id が文字列でない
    {"quarantined": [{"reason": "x"}]},                            # id が無い
    {"quarantined": [{"id": 3}]},                                  # id が文字列でない
    {"quarantined": "x"},                                          # 配列でない
    {"ids": [1]},
    ["x", "x"],                                                    # 重複
    "x",
])
def test_bad_shapes_raise_input_error(tmp_path, data):
    with pytest.raises(schema.InputError):
        schema.load_quarantine_info(w(tmp_path, "bad.json", data))


def test_both_keys_that_agree_are_accepted(tmp_path):
    r = schema.load_quarantine_info(w(tmp_path, "ok.json", {"quarantined": [{"id": "y"}, {"id": "x"}], "ids": ["x", "y"]}))
    assert sorted(r["ids"]) == ["x", "y"] and r["shape"] == "quarantined"


def test_cli_with_dict_quarantine_excludes_items_and_run_meta_has_shape_but_no_reason_text(tmp_path):
    items = [U.b1_item("fx-1", "文一です。", [U.clause("行く", {"agent": "太郎"})]),
             U.b1_item("fx-2", "文二です。", [U.clause("行く", {"agent": "花子"})]),
             U.b1_item("fx-3", "文三です。", [U.clause("行く", {"agent": "次郎"})])]
    ip = U.write_jsonl(tmp_path / "items.jsonl", items)
    qp = w(tmp_path, "q.json", {"quarantined": [{"id": "fx-2", "reason": "この理由の文は出力に写してはならない"}]})
    out = tmp_path / "out"
    code = cli.main(["--profile", "v2", "--bank", "B1", "--items", str(ip), "--quarantine", qp, "--tree", str(TREE),
                     "--out", str(out), "--python", sys.executable])
    assert code == 0
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["quarantine"] == {"count": 1, "ids": ["fx-2"], "not_in_items": [], "shape": "quarantined"}
    assert meta["profile"] == "v2"
    for f in ("run_meta.json", "summary.json", "summary.md", "results.jsonl"):
        assert "この理由の文" not in (out / f).read_text(encoding="utf-8")
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["fx-1", "fx-3"]


def test_cli_ids_shape_with_wrong_count_exits_2(tmp_path):
    ip = U.write_jsonl(tmp_path / "items.jsonl", [U.b1_item("fx-1", "文です。", [U.clause("行く")])])
    qp = w(tmp_path, "q.json", {"ids": ["fx-1"], "n_quarantined": 5})
    code = cli.main(["--profile", "v2", "--bank", "B1", "--items", str(ip), "--quarantine", qp, "--tree", str(TREE),
                     "--out", str(tmp_path / "o"), "--python", sys.executable])
    assert code == 2


@pytest.mark.parametrize("name, shape", [("quarantine_list.json", "list"), ("quarantine_quarantined_dicts.json", "quarantined"),
                                         ("quarantine_quarantined_strings.json", "quarantined"), ("quarantine_ids.json", "ids")])
def test_fixture_files_in_the_four_real_world_shapes_all_give_the_same_ids(name, shape):
    info = schema.load_quarantine_info(str(U.FIX / name))
    assert info["ids"] == ["fx-1", "fx-2"] and info["shape"] == shape
