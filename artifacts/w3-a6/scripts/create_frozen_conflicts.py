#!/usr/bin/env python
"""Write the unchanged test bodies and proposed C1 adaptations for auditor review."""
import ast
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[1]
out = []
out.append("# C1: 18型追加に伴う凍結テストの衝突\n\n")
out.append("これらの関数は変更していない。以下の後段は統合監査役向けの提案であり、作業ツリーには適用していない。\n")

cases = [
    ("tests/coarse_place/test_coarse_place_types.py", "test_inventory_only_grows", '''def test_inventory_only_grows():
    assert FROZEN_NOUN_TYPES <= set(ct.NOUN_TYPES)
    assert FROZEN_PRED_TYPES <= set(ct.PRED_TYPES)
    assert set(ct.type_ids("N")) == set(ct.NOUN_TYPES)
    assert set(ct.type_ids("P")) == set(ct.PRED_TYPES)
    assert all(t.startswith("P_") for t in ct.PRED_TYPES)
    assert not any(t.startswith("P_") for t in ct.NOUN_TYPES)
    assert ct.type_namespace("P_GIVE") == "P" and ct.type_namespace("PLACE") == "N"
    assert set(ct.FRAME_NOUN_TYPES) == FROZEN_NOUN_TYPES
    assert list(ct.NOUN_TYPES) == list(ct.FRAME_NOUN_TYPES) + ["RELATIVE_POSITION"]
    assert 18 == len(ct.NOUN_TYPES) and 13 == len(ct.PRED_TYPES)'''),
    ("tests/test_gen_coarse_evidence_pred.py", "test_the_predicate_prompt_lists_the_closed_inventories_from_coarse_types_and_no_test_word", '''def test_the_predicate_prompt_lists_the_closed_inventories_from_coarse_types_and_no_test_word():
    h = gce.PRED_PROMPT_HEAD
    for k, v in ct.PRED_TYPES.items():
        assert "- %s: %s" % (k, v) in h
    for k, v in ct.FRAME_NOUN_TYPES.items():
        assert "- %s: %s" % (k, v) in h
    assert len(re.findall(r"^- P_[A-Z]+:", h, re.M)) == 13
    assert len(re.findall(r"^- [A-Z_]+: ", h, re.M)) == 13 + 17
    assert "RELATIVE_POSITION" not in h
    assert "が を に で へ と から まで より" in h
    p = gce.build_prompt_pred(["アア", "イイ"])
    assert p.splitlines()[-1] == 'WORDS_JSON: ["アア", "イイ"]'
    assert gce.prompt_template_sha256_pred() == gce.sha256_text(gce.PRED_PROMPT_HEAD + gce.WORDS_PREFIX)
    assert gce.prompt_template_sha256_pred() != gce.prompt_template_sha256()
    fz = TREE / "tests/coarse_place/data"
    terms = set()
    for name in ("typed_vocab", "unknown_words", "dev_vocab", "dev_unknown", "predicate_check",
                 "dev_verbs", "verb_check_300"):
        for line in (fz / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            terms.add(json.loads(line)["term"])
    for t in sorted(terms):
        if len(t) >= 2:
            assert t not in h.replace("、", " ").replace("（", " ").replace("）", " ").split(), t
    spans = re.findall(r"[<]([^>]*)[>]", h)
    assert not [t for t in terms if t in spans]'''),
    ("tests/test_gen_coarse_evidence_pred.py", "test_the_schema_is_closed_and_its_enums_are_the_inventories", '''def test_the_schema_is_closed_and_its_enums_are_the_inventories():
    s = gce.PRED_SCHEMA
    item = s["properties"]["items"]["items"]
    assert s["additionalProperties"] is False and item["additionalProperties"] is False
    assert item["required"] == ["word", "ptype", "frame"]
    assert set(item["properties"]["ptype"]["enum"]) == set(ct.PRED_TYPES) | {None}
    fr = item["properties"]["frame"]["items"]
    assert fr["additionalProperties"] is False and fr["required"] == ["particle", "types"]
    assert fr["properties"]["particle"]["enum"] == list(ct.CASE_PARTICLES_9)
    assert len(fr["properties"]["particle"]["enum"]) == 9
    assert fr["properties"]["types"]["items"]["enum"] == list(ct.FRAME_NOUN_TYPES)
    assert len(ct.FRAME_NOUN_TYPES) == 17 and len(ct.NOUN_TYPES) == 18'''),
    ("tests/test_semantic_read_w3b1.py", "test_the_expected_types_of_a_role_are_those_of_the_event_cross_table", '''def test_the_expected_types_of_a_role_are_those_of_the_event_cross_table():
    from verantyx import event_cross as EC
    seen = set()
    for t, rows in R.TYPED_FRAMES.items():
        for role, parts, exp, kind in rows:
            if role in EC.EXPECTED_TYPES:
                seen.add(role)
                assert set(exp) == set(EC.EXPECTED_TYPES[role]), (t, role)
    docs_roles = {row[1] for row in block('w3b1_frames')}
    assert seen == {role for role in docs_roles if role in EC.EXPECTED_TYPES}
    assert seen == {'agent', 'place', 'time'}
    patient = [exp for rows in R.TYPED_FRAMES.values() for role, parts, exp, kind in rows if role == 'patient'][0]
    assert set(patient) == set(CT.FRAME_NOUN_TYPES) - {'TIME', 'QUANTITY', 'PLACE'} and len(patient) == 14
    assert set(EC.NOUN_TYPE_IDS) == set(CT.FRAME_NOUN_TYPES)'''),
    ("tests/test_semantic_read_w3b4.py", "test_the_roles_that_the_event_cross_types_have_the_same_types_and_patient_is_the_fourteen_types", '''def test_the_roles_that_the_event_cross_types_have_the_same_types_and_patient_is_the_fourteen_types():
    fourteen = tuple(t for t in CT.FRAME_NOUN_TYPES if t not in ('TIME', 'QUANTITY', 'PLACE'))
    assert len(fourteen) == 14
    for t, rows in R.typed_frames_v2().items():
        for role, parts, exp, kind in rows:
            if role in EC.EXPECTED_TYPES: assert frozenset(exp) == EC.EXPECTED_TYPES[role], (t, role)
            if role == 'patient': assert set(exp) == set(fourteen), t
            if role == 'goal' or role == 'source': assert exp == ('PLACE',)'''),
]

for filename, function, proposal in cases:
    source = subprocess.run(["git", "show", "0041606:" + filename], check=True,
                            capture_output=True, text=True).stdout
    lines = source.splitlines()
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    before = "\n".join(lines[node.lineno - 1:node.end_lineno])
    out.append("\n## " + filename + "::" + function + "\n\n")
    out.append("### 前（0041606の全文）\n\n```python\n" + before + "\n```\n")
    out.append("\n### 後（監査役が統合時に検討する提案。未適用）\n\n```python\n" + proposal + "\n```\n")

(root / "frozen_conflicts.md").write_text("".join(out), encoding="utf-8")
print("cases", len(cases), "output", root / "frozen_conflicts.md")
