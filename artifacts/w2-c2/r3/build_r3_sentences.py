"""Round 3 (W2-c3, step 6/7): move the sentences of the round-1/2 tests, mechanically, into tests/conduct_ask/w2c2/r3_sentences.jsonl.

Run once, with the round-2 version of tests/test_conduct_ask_w2c2.py (the file as it was before this round's rewrite; a copy is
kept next to this script as r2_test_conduct_ask_w2c2.py.txt).  The (frame_id, question, options) triples of the parametrize tables are
read with ``ast`` -- nothing is retyped.  Rows from the two mapping-gate tests carry ``"script": "good_d3"``
(tests/conduct_ask/w2c2/r3_scripts/good_d3.json, the GOOD_D3 of that file).
"""
import ast
import json
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

ORIGINS = [
    ("test_form_trap_with_positive_evidence", "fp", None),
    ("test_form_trap_without_positive_evidence_is_none", "fn", None),
    ("test_a_path_is_a_write_target_only_right_after_or_before_a_write_verb", "pt", None),
    ("test_the_gate_hands_up_a_mapped_answer_to_a_question_with_positive_evidence", "gh", "good_d3"),
    ("test_the_gate_lets_a_mapped_answer_through_when_there_is_no_positive_evidence", "gp", "good_d3"),
]
NAMES = {"F1": "z01_seedswap", "F4": "z04_kiln", "YN_JA": ["はい", "いいえ"], "YN_EN": ["Yes", "No"]}


def val(node):
    try:
        return ast.literal_eval(node)
    except ValueError:
        return eval(compile(ast.Expression(node), "<expr>", "eval"), {"__builtins__": {}}, NAMES)


tree = ast.parse(SRC.read_text(encoding="utf-8"))
rows = []
for name, short, script in ORIGINS:
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    deco = next(d for d in fn.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "parametrize")
    table = val(deco.args[1])
    for k, t in enumerate(table, 1):
        if short in ("fp", "fn", "pt"):
            frame_id, question = t[0], t[1]
            options = t[2] if short in ("fp", "fn") else None
        else:                                  # gate tests: (frame, question, options[, detail])
            frame_id, question, options = t[0], t[1], t[2]
        row = {"id": f"r3s-{short}-{k:02d}", "frame_id": frame_id, "question": question, "options": options, "origin": name}
        if script:
            row["script"] = script
        rows.append(row)
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(f"wrote {len(rows)} sentences to {OUT}")
