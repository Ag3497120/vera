"""分類の拡張（abstain_overall）・要約のバグ修正・v2 の要約欄・recount・Vera を呼ばない判定の入口（judge）。"""
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

import v2_util as U
from tools.bank_score import cli, judge, recount, report
from tools.bank_score.classify import CLASS_KEYS, classify
from v2_util import b1_item, b2_item, b3_item, b5_item, clause, obs

TREE = Path(__file__).resolve().parents[2]


def test_classify_abstain_overall_default_is_unchanged_and_new_combinations_are_exhaustive():
    for side, state, overall in itertools.product(("answer", "abstain"), ("answer", "abstain", "social"),
                                                  ("PASS", "FAIL", "UNJUDGED")):
        a = classify(side=side, state=state, overall=overall)
        assert a == classify(side=side, state=state, overall=overall, abstain_overall=None)
        for ab in ("PASS", "FAIL", "UNJUDGED"):
            k, r = classify(side=side, state=state, overall=overall, abstain_overall=ab)
            assert k in CLASS_KEYS
            if side == "abstain" and state == "abstain":
                assert (k, r) == {"PASS": ("correct_abstain", None), "FAIL": ("wrong", "ABSTAIN_TEXT_RULE_FAIL"),
                                  "UNJUDGED": ("unscorable", "JUDGE_UNAVAILABLE")}[ab]
            else:
                assert (k, r) == a  # 他の組み合わせには影響しない
    # 優先順は今までどおり（入口未到達・誤読などが先）
    assert classify(unreachable=True, side="abstain", state="abstain", abstain_overall="FAIL")[0] == "unreachable"
    assert classify(misread=True, side="abstain", state="abstain", abstain_overall="FAIL")[0] == "misread"


def row(klass, reason=None, **kw):
    r = {"id": "x", "line": 1, "bank": "B2", "lang": "ja", "category": "c", "difficulty": 1, "class": klass,
         "class_ja": "", "reason": reason, "reason_detail": [], "entry": "e", "capability": None, "checks": {},
         "notes": [], "unknown_expect_keys": []}
    r.update(kw)
    return r


def test_unscorable_rate_among_reached_counts_only_judge_unavailable_and_never_exceeds_100_percent():
    rows = [row("unscorable", "ITEM_INVALID") for _ in range(8)] + [row("unscorable", "JUDGE_UNAVAILABLE"),
                                                                    row("correct"), row("unreachable")]
    s = report.build_summary("B2", rows, {}, {"count": 0, "ids": [], "not_in_items": []})
    u = s["classes"]["unscorable"]
    assert u["count"] == 9 and u["rate_all"] == round(9 / 11, 6)
    assert u["rate_reached"] == round(1 / 2, 6)  # 到達 = 11 − 未到達 1 − ITEM_INVALID 8 = 2、分子は JUDGE_UNAVAILABLE の 1
    assert all(c["rate_reached"] is None or c["rate_reached"] <= 1 for c in s["classes"].values())
    assert s["unscorable_breakdown"] == {"ITEM_INVALID": 8, "JUDGE_UNAVAILABLE": 1}
    assert "profile" not in s  # w1s の要約には新しい欄を足さない（W1-s の出力の recount が一致のままであるため）


def test_v2_summary_has_profile_approx_by_unit_and_evidence_blocks_and_headline_excludes_approx():
    rows = [row("correct", unit="U1", class_approx="correct", evidence_match="PASS"),
            row("correct", unit="U1", class_approx="correct", evidence_match="FAIL"),
            row("correct", unit="U2", class_approx="correct", evidence_match="NOT_REQUIRED"),
            row("unscorable", "JUDGE_UNAVAILABLE", unit="U2", class_approx="correct", evidence_match="UNJUDGED",
                checks={"r": {"result": "UNJUDGED", "detail": {"reason": "NEEDS_READER", "surface_approx": "PASS"}}})]
    s = report.build_summary("B2", rows, {}, {"count": 0, "ids": [], "not_in_items": []}, "v2")
    assert s["profile"] == "v2"
    assert s["classes"]["correct"]["count"] == 3  # 見出しは主分類だけ
    assert s["approx"]["classes"]["correct"] == 4 and s["approx"]["rows_changed"] == 1
    assert s["approx"]["changed_by_transition"] == {"unscorable->correct": 1}
    assert s["evidence_strict"]["correct"] == 3 and s["evidence_strict"]["correct_and_evidence_ok"] == 2
    assert s["by_unit"]["U1"]["correct"] == 2 and s["by_unit"]["U2"]["unscorable"] == 1
    assert s["headline"]["correct_rate"]["all"] == round(3 / 4, 6)
    md = report.render_md(s)
    assert "表層近似を当てた分類" in md and "根拠" in md and "単位別" in md


# ---- 偽ツリーで v2 の CLI を通し、recount が一致すること --------------------------------------------------------
TABLE = {
    "q-correct": {"kind": "answer", "verdict": "ANSWER", "text": "六時に点灯します。",
                  "evidence": "港の灯台は、毎朝六時に点灯される。"},
    "q-abstain": {"kind": "unknown", "verdict": "UNKNOWN_UNREAD", "text": "確認できません。"},
    "q-constructed": {"kind": "x", "verdict": "EXPLAINED_BY_UNITS", "constructed": True, "text": "構成した候補の文です。"},
}
FAKE = ("import json, sys\nTABLE = %r\n"
        "def main(argv=None):\n    print(json.dumps(TABLE[sys.argv[-1]], ensure_ascii=False)); return 0\n"
        "if __name__ == '__main__':\n    raise SystemExit(main())\n") % (TABLE,)


def fake_tree(tmp_path):
    t = tmp_path / "tree" / "verantyx"
    t.mkdir(parents=True)
    (t / "__init__.py").write_text("")
    (t / "cli.py").write_text(FAKE)
    return tmp_path / "tree"


def run_cli(bank, items, tmp_path, name="out", extra=()):
    ip = U.write_jsonl(tmp_path / f"{name}.jsonl", items)
    out = tmp_path / name
    code = cli.main(["--profile", "v2", "--bank", bank, "--items", str(ip), "--tree", str(fake_tree(tmp_path)),
                     "--out", str(out), "--python", sys.executable, *extra])
    assert code == 0
    return out, [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]


def test_v2_cli_b2_run_has_class_approx_unit_evidence_and_recount_matches(tmp_path):
    e = dict(must_contain_any=[["六時"]], evidence=["港の灯台は、毎朝六時に点灯される。"], evidence_required=True)
    items = [b2_item("B2J-AAA-01", query="q-correct", **e), b2_item("B2J-AAA-02", query="q-correct", must_contain_any=[["七時"]]),
             b2_item("B2J-BBB-01", query="q-abstain", behavior="abstain")]
    out, rows = run_cli("B2", items, tmp_path)
    by = {r["id"]: r for r in rows}
    assert by["B2J-AAA-01"]["class"] == "correct" and by["B2J-AAA-01"]["evidence_match"] == "PASS"
    assert by["B2J-AAA-02"]["class"] == "wrong" and by["B2J-AAA-02"]["unit"] == "B2J-AAA"
    assert by["B2J-BBB-01"]["class"] == "correct_abstain" and by["B2J-BBB-01"]["class_approx"] == "correct_abstain"
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["profile"] == "v2" and len(meta["items_sha256"]) == 64 and meta["quarantine_sha256"] is None
    assert "fugashi" in meta
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summ["profile"] == "v2" and summ["evidence_strict"]["correct_and_evidence_ok"] == 1
    assert set(summ["by_unit"]) == {"B2J-AAA", "B2J-BBB"}
    assert recount.main([str(out)]) == 0


def test_v2_cli_b3_constructed_result_and_main_class_vs_approx(tmp_path):
    mx = [{"predicate": ["点灯する"], "agent": ["灯台"], "patient": None, "polarity": "+"}]
    items = [b3_item("fx-1", brief="q-constructed", state="constructed", outside="constructed_only", materials=[]),
             b3_item("fx-2", brief="q-correct", state="answer", must_express=mx)]
    out, rows = run_cli("B3", items, tmp_path)
    by = {r["id"]: r for r in rows}
    assert by["fx-1"]["class"] == "correct"  # constructed: true の型は answer 状態・b3_state=constructed として採点される
    assert by["fx-2"]["class"] == "unscorable" and by["fx-2"]["reason"] == "JUDGE_UNAVAILABLE"
    assert by["fx-2"]["class_approx"] in ("correct", "wrong")
    s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert s["classes"]["unscorable"]["count"] == 1 and s["approx"]["rows_changed"] == 1
    assert s["classes"]["unscorable"]["rate_reached"] == round(1 / 2, 6)
    assert recount.main([str(out)]) == 0


def test_w1s_default_profile_output_is_unchanged_in_shape(tmp_path):
    ip = U.write_jsonl(tmp_path / "w.jsonl", [{"id": "w1", "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1,
                                               "turns": [{"role": "user", "text": "q-correct"}],
                                               "expect": {"behavior": "answer", "must_contain_any": [["六時"]]},
                                               "rationale": "r"}])
    out = tmp_path / "o"
    assert cli.main(["--bank", "B2", "--items", str(ip), "--tree", str(fake_tree(tmp_path)), "--out", str(out),
                     "--python", sys.executable]) == 0
    row = json.loads((out / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "class_approx" not in row and "unit" not in row and row["class"] == "correct"
    assert "profile" not in json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert json.loads((out / "run_meta.json").read_text(encoding="utf-8"))["profile"] == "w1s"
    assert recount.main([str(out)]) == 0


# ---- judge（Vera を呼ばない） ----------------------------------------------------------------------------------
@pytest.fixture
def no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("judge は子プロセスを起動してはならない")
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)


def run_judge(bank, items, tmp_path, probe, frames=None, name=None):
    ip = U.write_jsonl(tmp_path / f"{bank}_{probe}.jsonl", items)
    out = tmp_path / (name or f"j_{bank}_{probe}")
    args = ["--bank", bank, "--profile", "v2", "--items", str(ip), "--probe", probe, "--out", str(out)]
    if frames:
        args += ["--frames", str(frames)]
    assert judge.main(args) == 0
    return json.loads((out / "summary.json").read_text(encoding="utf-8")), out


def test_judge_reference_for_each_bank_without_starting_a_subprocess(tmp_path, no_subprocess):
    b1 = [b1_item("a", "文一", [clause("行く", {"agent": "甲"})]), b1_item("b", "ぬるぷ", [], readable=False,
                                                                       must_not=[{"readable": True}])]
    s, _ = run_judge("B1", b1, tmp_path, "reference")
    r = s["probes"]["reference"]
    assert (r["answer_side_total"], r["correct_strict"], r["abstain_side_total"], r["abstain_side_correct"]) == (1, 1, 1, 1)
    assert r["rate_with_approx"] == 1.0 and r["not_correct"] == []
    mx = {"predicate": ["止まる"], "agent": ["ポンプ"], "patient": None, "polarity": "+"}
    b3i = [b3_item("p", must_contain_all=["ポンプ"]), b3_item("q", must_express=[mx], must_contain_all=["ポンプ"]),
           b3_item("r", behavior="refuse", state="refuse", refusal_text_must_not_contain=["作り話"]),
           b3_item("s", state="constructed", outside="constructed_only")]
    for it, ref in zip(b3i, ("ポンプが回る。", "ポンプが止まる。", "お答えできません。", "構成した候補です。")):
        it["expect"]["reference"] = ref
    s3, _ = run_judge("B3", b3i, tmp_path, "reference")
    r3 = s3["probes"]["reference"]
    assert (r3["answer_side_total"], r3["correct_strict"], r3["correct_approx_only"]) == (3, 2, 1)  # 近似に頼った件数を別に出す
    assert r3["approx_only_ids"] == ["q"] and r3["rate_strict"] == round(2 / 3, 6) and r3["rate_with_approx"] == 1.0
    assert (r3["abstain_side_total"], r3["abstain_side_correct"]) == (1, 1)
    assert s3["classes"]["unscorable"]["count"] == 1  # 主分類の見出しは近似を含まない
    fr = U.frames_dir(tmp_path)
    b5 = [b5_item("a", options=["案を採る", "案を採らない"], index=1), b5_item("b", options=[], must_contain_any=[["決定値"]]),
          b5_item("c", options=["案を採る", "案を採らない"], decision="escalate")]
    s5, _ = run_judge("B5", b5, tmp_path, "reference", frames=fr)
    r5 = s5["probes"]["reference"]
    assert (r5["answer_side_total"], r5["correct_strict"], r5["abstain_side_correct"]) == (2, 2, 1)


def test_judge_b2_alt_answers_and_wrong_answers_blocks(tmp_path, no_subprocess):
    a = b2_item("a", must_contain_any=[["六時"]], must_not_contain=["七時"], reference="六時です。")
    a["alt_answers"] = ["毎朝六時に点灯します。", "点灯は午前六時です。"]
    a["wrong_answers"] = [{"state": "answer", "text": "七時です。", "why": "w"}, {"state": "abstain", "text": "", "why": "w"},
                          {"state": "answer", "text": "六時です。", "why": "実は正答になってしまう誤答例"}]
    s, _ = run_judge("B2", [a], tmp_path, "alt_answers")
    assert s["probes"]["alt_answers"] == {"probes": 2, "correct": 2, "not_correct": []}
    w, _ = run_judge("B2", [a], tmp_path, "wrong_answers")
    pw = w["probes"]["wrong_answers"]
    assert pw["probes"] == 3 and pw["passed_wrongly"] == [{"id": "a", "index": 2, "class": "correct"}]
    ab = b2_item("b", behavior="abstain", must_not_contain=["七時に点灯"], reference="分かりません。")
    ab["alt_answers"] = ["確認できません。", "七時に点灯します。"]
    s2, _ = run_judge("B2", [ab], tmp_path, "alt_answers", name="j_ab")
    assert s2["probes"]["alt_answers"]["correct"] == 1
    assert s2["probes"]["alt_answers"]["not_correct"][0]["class"] == "wrong"


def test_judge_observations_mode_scores_given_observations_and_rejects_unknown_ids(tmp_path, no_subprocess):
    it = b2_item("a", must_contain_any=[["六時"]])
    ip = U.write_jsonl(tmp_path / "i.jsonl", [it])
    op = tmp_path / "o.jsonl"
    op.write_text(json.dumps({"id": "a", "observation": {"state": "answer", "text": "六時です。"}}, ensure_ascii=False) + "\n",
                  encoding="utf-8")
    out = tmp_path / "out"
    assert judge.main(["--bank", "B2", "--profile", "v2", "--items", str(ip), "--observations", str(op), "--out", str(out)]) == 0
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["class"] == "correct" and rows[0]["probe"] == "observations"
    op.write_text(json.dumps({"id": "zzz", "observation": {"state": "answer"}}) + "\n", encoding="utf-8")
    assert judge.main(["--bank", "B2", "--profile", "v2", "--items", str(ip), "--observations", str(op), "--out", str(out)]) == 2
    op.write_text(json.dumps({"id": "a", "observation": {"state": "maybe"}}) + "\n", encoding="utf-8")
    assert judge.main(["--bank", "B2", "--profile", "v2", "--items", str(ip), "--observations", str(op), "--out", str(out)]) == 2
