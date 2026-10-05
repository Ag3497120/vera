#!/usr/bin/env python
"""Compare final pytest failures with the pinned dev baseline."""
from pathlib import Path


root = Path(__file__).resolve().parents[1]
baseline = Path("/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_bfb17b8_failures.txt")
result = root / "pytest_full.txt"


def ids(path):
    found = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            found.add(line.split(" ", 1)[1].split(" - ", 1)[0])
    return found


before, after = ids(baseline), ids(result)
new, fixed = sorted(after - before), sorted(before - after)
(root / "after_failures.txt").write_text("".join(x + "\n" for x in sorted(after)), encoding="utf-8")
(root / "new_failures.txt").write_text("".join(x + "\n" for x in new), encoding="utf-8")
(root / "fixed_failures.txt").write_text("".join(x + "\n" for x in fixed), encoding="utf-8")
c1 = {
    "tests/coarse_place/test_coarse_place_types.py::test_inventory_only_grows",
    "tests/test_gen_coarse_evidence_pred.py::test_the_predicate_prompt_lists_the_closed_inventories_from_coarse_types_and_no_test_word",
    "tests/test_gen_coarse_evidence_pred.py::test_the_schema_is_closed_and_its_enums_are_the_inventories",
    "tests/test_semantic_read_w3b1.py::test_the_expected_types_of_a_role_are_those_of_the_event_cross_table",
    "tests/test_semantic_read_w3b4.py::test_the_roles_that_the_event_cross_types_have_the_same_types_and_patient_is_the_fourteen_types",
}
env_prefixes = ("tests/test_one_trace.py::", "tests/test_p4_abilities.py::test_speech_act_drafts",
                "tests/test_s6_", "tests/test_gen_coarse_evidence.py::test_the_stop_signal")
lines = []
for test in new:
    if test in c1:
        why = "C1: NOUN_TYPES追加との凍結試験の衝突。詳細と提案は frozen_conflicts.md。"
    elif test.startswith("tests/test_conduct_"):
        why = "未解決: conduct系。全体実行の台帳にはsandbox-exec Operation not permittedがあるが、--tb=noのためこの失敗IDとの個別因果対応は未確認。sandbox_full_evidence.txt参照。"
    elif "test_s6_two_runs_agree_except_timing_and_recount_matches" in test:
        why = "指示書 §0.3・§4 N7 の環境由来候補として記載。基線との比較および18型実験にも現れた。"
    elif test.startswith(env_prefixes):
        why = "指示書に環境由来の失敗候補として記載。test_s6は差分基線・指示書の実験にも現れる。"
    else:
        why = "未説明の新規失敗。修正が必要。"
    lines.append(test + "\t" + why + "\n")
# r3 (M6): new_failures_explained.txt is NOT written any more. This script carries fixed explanations for other tickets; the file in artifacts/ is hand-maintained for W12-c1.
print("baseline", len(before), "after", len(after), "new", len(new), "fixed", len(fixed))
