"""not_strict: 参考例のうち主分類が correct でない回答側の問題を 1 問ずつ表にする（自作の行だけで確かめる）。"""
import json

from tools.bank_score import not_strict


def row(id_, klass, side="answer", probe="reference", checks=None, approx=None, line=1):
    return {"id": id_, "line": line, "probe": probe, "side": side, "class": klass, "reason": "JUDGE_UNAVAILABLE" if klass == "unscorable" else None,
            "class_approx": approx, "checks": checks or {}}


def unj(reason="NEEDS_READER", approx="PASS"):
    return {"result": "UNJUDGED", "detail": {"reason": reason, "surface_approx": approx}}


def test_only_answer_side_reference_rows_that_are_not_correct_are_listed_with_rules_and_codes():
    rows = [row("a", "correct", checks={"r": {"result": "PASS", "detail": {}}}, line=1),
            row("b", "unscorable", checks={"must_express": unj(), "order": unj("LEMMA_NOT_FOUND"),
                                            "non_empty": {"result": "PASS", "detail": {}}}, approx="correct", line=2),
            row("c", "wrong", checks={"max_chars": {"result": "FAIL", "detail": {}}}, approx="wrong", line=3),
            row("d", "correct_abstain", side="abstain", line=4),
            row("e", "unscorable", probe="alt_answers", checks={"must_express": unj()}, line=5)]
    lines, agg = not_strict.build(rows)
    assert lines[0].split("\t")[0] == "id" and len(lines) == 3  # 見出し + b + c
    b = lines[1].split("\t")
    assert b[0] == "b" and b[5] == "must_express:NEEDS_READER,order:LEMMA_NOT_FOUND" and b[6] == "must_express=PASS,order=PASS"
    c = lines[2].split("\t")
    assert c[0] == "c" and c[4] == "max_chars" and c[5] == "-"
    assert agg["n"] == 2 and agg["per_rule"] == {"must_express": 1, "order": 1}
    assert agg["per_combo"] == {"must_express + order": 1, "(なし)": 1}


def test_cli_writes_tsv_and_aggregate_files_and_free_text_codes_are_redacted(tmp_path):
    d = tmp_path / "j"
    d.mkdir()
    rows = [row("x", "unscorable", checks={"must_express": unj("自由文の理由")}, approx="correct")]
    (d / "results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    assert not_strict.main([str(d), "--tsv", str(tmp_path / "o.tsv"), "--agg", str(tmp_path / "a.txt")]) == 0
    t = (tmp_path / "o.tsv").read_text(encoding="utf-8")
    assert "must_express:<redacted>" in t and "自由文の理由" not in t
    assert len(t.splitlines()) == 2
    assert "n=1" in (tmp_path / "a.txt").read_text(encoding="utf-8")
