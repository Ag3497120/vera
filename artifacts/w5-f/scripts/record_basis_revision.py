from __future__ import annotations

import ast
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGETS = {
    "entry": ("tests/test_basis_policy_entry.py", {
        "test_a_mix_of_human_and_generated_sources_abstains",
        "test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note",
    }),
    "form": ("tests/test_basis_policy_form.py", {"test_other_routes_do_not_attempt_the_borrowing"}),
    "table": ("tests/test_basis_policy_table.py", {
        "test_decide_accepts_a_classification_result_as_the_basis",
        "test_rule3_human_confirmed_origin_is_human",
        "test_human_and_generated_together_is_mixed",
    }),
    "w5c": ("tests/test_basis_policy_w5c.py", {
        "test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them",
        "test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis",
        "test_w5c_the_versions_and_the_table_are_as_registered",
        "test_w5c_the_policy_note_carries_the_new_versions_and_numbers",
    }),
    "w5c_r3": ("tests/test_basis_policy_w5c_r3.py", {
        "test_r3_the_request_text_and_a_declared_human_confirmation_do_not_depend_on_user_documents",
        "test_r3_the_versions_are_as_registered",
        "test_r3_the_policy_note_carries_the_classify_version_3",
    }),
    "w5e": ("tests/test_basis_policy_w5e.py", {
        "test_a3_the_classify_version_is_4_and_the_note_carries_it",
        "test_a3_the_sovereigns_records_are_human",
        "test_h4_controls_that_are_really_human_still_answer",
    }),
}


def extract(path: Path, names: set[str]) -> list[tuple[str, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            found.append((node.name, "\n".join(source.splitlines()[start - 1:node.end_lineno])))
    if {name for name, _ in found} != names:
        raise SystemExit(f"expected {sorted(names)}, found {sorted(name for name, _ in found)}")
    return found


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in TARGETS or sys.argv[2] not in ("before", "after"):
        raise SystemExit("usage: record_basis_revision.py <entry|form|table|w5c|w5c_r3|w5e> <before|after>")
    group, phase = sys.argv[1:]
    relpath, names = TARGETS[group]
    sections = extract(ROOT / relpath, names)
    doc = ROOT / "docs/BASIS_POLICY.md"
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    with doc.open("a", encoding="utf-8") as out:
        out.write(f"\n\n### W5-f S5 {group}: {phase}（{timestamp}）\n\n")
        for name, text in sections:
            out.write(f"#### `{relpath}::{name}`\n\n```python\n{text}\n```\n\n")


if __name__ == "__main__":
    main()
