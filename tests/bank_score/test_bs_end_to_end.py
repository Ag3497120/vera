"""CLI 全体: 引数の誤り、隔離、S3（出力ファイルから 9 分類の合計）、S6（2 回走らせて一致）、recount。"""
import json
import sys
from pathlib import Path

import pytest

from tools.bank_score import cli, compare, recount
from tools.bank_score.classify import CLASS_KEYS

TREE = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
PY = sys.executable


def run(bank, items, out, *extra, frames=None):
    args = ["--bank", bank, "--items", str(items), "--tree", str(TREE), "--out", str(out), "--python", PY, *extra]
    if frames:
        args += ["--frames", str(frames)]
    return cli.main(args)


def rows_of(out):
    return [json.loads(l) for l in (Path(out) / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def test_argument_errors_exit_2(tmp_path):
    items = FIX / "B2" / "items.jsonl"
    assert run("B2", items, tmp_path / "a", "--entry", "nope") == 2
    assert run("B2", items, tmp_path / "b", frames=FIX / "B5" / "frames") == 2  # B5 以外の --frames は黙って無視しない
    assert run("B5", FIX / "B5" / "items.jsonl", tmp_path / "c") == 2  # B5 は --frames 必須
    assert run("B2", tmp_path / "missing.jsonl", tmp_path / "d") == 2
    bad_q = tmp_path / "q.json"
    bad_q.write_text('{"x": 1}')
    assert run("B2", items, tmp_path / "e", "--quarantine", str(bad_q)) == 2
    assert run("B2", items, tmp_path / "f", "--timeout", "0") == 2


@pytest.mark.parametrize("bank", ["B1", "B5"])
def test_s3_class_sum_equals_total_from_output_files(bank, tmp_path):
    items = FIX / bank / "items.jsonl"
    out = tmp_path / "o"
    assert run(bank, items, out, frames=FIX / "B5" / "frames" if bank == "B5" else None) == 0
    rows = rows_of(out)
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert {r["class"] for r in rows} <= set(CLASS_KEYS)
    nonblank = sum(1 for l in items.read_text(encoding="utf-8").splitlines() if l.strip())
    assert len(rows) == nonblank == summ["total"] == summ["class_sum"]
    assert sum(c["count"] for c in summ["classes"].values()) == summ["total"]
    for s in ("empty", "always_abstain", "echo_input"):
        br = [json.loads(l) for l in (out / "baselines" / s / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(br) == nonblank and {r["class"] for r in br} <= set(CLASS_KEYS)
    assert recount.main([str(out)]) == 0


def test_invalid_items_appear_as_rows_not_silently_dropped(tmp_path):
    items = FIX / "invalid" / "B1.jsonl"
    out = tmp_path / "o"
    assert run("B1", items, out) == 0
    rows = rows_of(out)
    nonblank = sum(1 for l in items.read_text(encoding="utf-8").splitlines() if l.strip())
    assert len(rows) == nonblank
    assert all(r["class"] == "unscorable" and r["reason"] == "ITEM_INVALID" for r in rows)
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summ["unscorable_breakdown"] == {"ITEM_INVALID": nonblank}
    assert summ["item_invalid_codes"]["DUPLICATE_ID"] == 2 and summ["item_invalid_codes"]["BAD_JSON"] == 1


def test_quarantine_excludes_from_denominator_and_reports_unknown_ids(tmp_path):
    q = tmp_path / "q.json"
    q.write_text(json.dumps(["b1s-001", "b1s-002", "no-such-id"]))
    out = tmp_path / "o"
    assert run("B1", FIX / "B1" / "items.jsonl", out, "--quarantine", str(q)) == 0
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summ["total"] == 24
    assert summ["quarantine"] == {"count": 2, "ids": ["b1s-001", "b1s-002"], "not_in_items": ["no-such-id"]}
    assert "隔離: 2 件" in (out / "summary.md").read_text(encoding="utf-8")
    assert "b1s-001" not in {r["id"] for r in rows_of(out)}


def subset(tmp_path, ids):
    src = [json.loads(l) for l in (FIX / "B2" / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    p = tmp_path / "subset.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in src if r["id"] in ids) + "\n", encoding="utf-8")
    return p


def test_s6_two_runs_agree_except_timing_and_recount_matches(tmp_path):
    items = subset(tmp_path, {"b2s-001", "b2s-003", "b2s-008", "b2s-020"})
    a, b = tmp_path / "a", tmp_path / "b"
    assert run("B2", items, a) == 0 and run("B2", items, b) == 0
    assert compare.main([str(a), str(b)]) == 0
    assert recount.main([str(a)]) == 0
    rows = rows_of(a)
    assert [r["class"] for r in rows if r["id"] == "b2s-020"] == ["unreachable"]
    assert sum(1 for r in rows if r["entry"] == "cli-ask-round5") == 4
    meta = json.loads((a / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["provenance_total"]["outside_count"] == 0 and meta["vera_calls"] == 3
    assert meta["child_env"]["HOME"] == "<WORK>/home" and meta["verantyx_untouched"] is True
    assert "timing" in meta


def test_compare_detects_a_real_difference(tmp_path):
    items = subset(tmp_path, {"b2s-001"})
    a, b = tmp_path / "a", tmp_path / "b"
    assert run("B2", items, a) == 0 and run("B2", items, b) == 0
    rows = rows_of(b)
    rows[0]["class"] = "correct"
    (b / "results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
                                     encoding="utf-8")
    assert compare.main([str(a), str(b)]) == 1
    assert recount.main([str(b)]) == 1  # summary を手で直した結果と食い違えば recount も検出する


def test_cli_ask_legacy_entry_marks_documents_unreachable(tmp_path):
    items = subset(tmp_path, {"b2s-001", "b2s-003"})
    out = tmp_path / "o"
    assert run("B2", items, out, "--entry", "cli-ask") == 0
    by_id = {r["id"]: r for r in rows_of(out)}
    assert by_id["b2s-003"]["class"] == "unreachable" and by_id["b2s-003"]["capability"] == "documents"
    assert by_id["b2s-001"]["entry"] == "cli-ask" and by_id["b2s-001"]["class"] != "unreachable"


def test_dash_query_item_in_a_full_run_is_typed_not_a_runtime_error(tmp_path):
    p = tmp_path / "dash.jsonl"
    p.write_text(json.dumps({"id": "d1", "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1,
                             "turns": [{"role": "user", "text": "-5 と 3 の和は？"}],
                             "expect": {"behavior": "answer", "must_contain_any": [["-2"]]}, "rationale": "r"},
                            ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "o"
    assert run("B2", p, out) == 0
    assert rows_of(out)[0]["class"] != "runtime_error"
