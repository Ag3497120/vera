"""T5: 本物の `vera ask`（このツリーの verantyx、--mode round5）で自作の見本を end-to-end で 1 回流す。
正答数は assert しない（製品の弱さは採点器の不合格ではない）。落ちずに summary.md ができ、runtime_error = 0、出自の外が 0 であること。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.bank_score import cli, recount

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures" / "B7"


def test_b7_end_to_end_with_the_real_vera(tmp_path, capsys):
    out = tmp_path / "out"
    code = cli.main(["--profile", "v2", "--bank", "B7", "--items", str(FIX / "items.jsonl"), "--tree", str(ROOT),
                     "--out", str(out), "--python", sys.executable])
    assert code == 0
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    n_items = len([l for l in (FIX / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()])
    assert (out / "summary.md").is_file()
    assert summ["classes"]["runtime_error"]["count"] == 0
    assert summ["class_sum"] == summ["total"] == n_items
    assert summ["classes"]["misread"]["count"] == 0
    assert meta["provenance_total"]["outside_count"] == 0 and meta["provenance_total"]["processes_unverified"] == 0
    assert meta["vera_calls"] == n_items - 1  # ITEM_INVALID の見本 1 問は Vera を呼ばない
    assert set(summ["baselines"]["strategies"]) == {"b7_a_human_sources", "b7_b_human_present", "b7_c_kind_then_a",
                                                    "b7_d_always_abstain", "b7_e_reference_over_c"}
    # 観測された outcome は 6 値か OUTCOME_MISSING か（観測なし）だけ
    seen = {o for e in summ["by_expect"].values() for o in e["observed_outcomes"]}
    assert seen <= {"ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "CONSTRUCTED", "CONFIRM_REQUEST",
                    "REFERENCE_GENERATED", "ABSTAIN", "OUTCOME_MISSING", "(none)"}
    assert recount.main([str(out)]) == 0
