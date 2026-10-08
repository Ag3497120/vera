"""W5-f: registered gates for quoted focus particles, relational fillers and coordination."""
import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from verantyx import semantic_read as SR
from verantyx import semantic_reader as R


TREE = Path(__file__).resolve().parents[1]
DATA = TREE / "tests" / "reading_soundness" / "w5f_gates.jsonl"
DATA_R3 = TREE / "tests" / "reading_soundness" / "w5f_gates_r3.jsonl"
DATA_R3B = TREE / "tests" / "reading_soundness" / "w5f_gates_r3b.jsonl"
NARROWED_F2 = TREE / "tests" / "reading_soundness" / "w5f_gates_f2_narrowed.json"
NARROWED_R3 = TREE / "tests" / "reading_soundness" / "w5f_gates_r3_narrowed.json"
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")
CHECKER = TREE / "tests" / "reading_soundness" / "w5f_gates_check.py"


def _load_attack_w3b4():
    path = TREE / "tests" / "attack" / "test_attack_w3b4.py"
    spec = importlib.util.spec_from_file_location("w5f_attack_w3b4", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_fakes():
    path = TREE / "tests" / "reading_soundness" / "w3b1_fakes.py"
    spec = importlib.util.spec_from_file_location("w5f_read_fakes", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_frozen():
    # later manifests win for the same path (W5-f r3 appended frozen_r3.sha256; the older ones are history)
    digests = {}
    for name in ("frozen.sha256", "frozen_sup.sha256", "frozen_r3.sha256", "frozen_r3b.sha256", "frozen_r3c.sha256"):
        for line in (TREE / "artifacts" / "w5-f" / name).read_text(encoding="utf-8").splitlines():
            digest, relative = line.split(None, 1)
            digests[relative.strip()] = digest
    for relative, digest in digests.items():
        assert hashlib.sha256((TREE / relative).read_bytes()).hexdigest() == digest, relative


def _checker(mode, out_path):
    env = {"HOME": os.environ.get("HOME", ""), "PATH": "/usr/bin:/bin",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(TREE), "TMPDIR": "/tmp"}
    result = subprocess.run([sys.executable, str(CHECKER), "--mode", mode, "--out", str(out_path)],
                            cwd=str(TREE), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(Path(out_path).read_text(encoding="utf-8")), result.stdout


def test_registered_data_is_frozen_and_balanced():
    _assert_frozen()
    rows = _read_jsonl(DATA) + _read_jsonl(DATA_R3) + _read_jsonl(DATA_R3B)
    assert len({row["id"] for row in rows}) == len(rows)
    groups = sorted({row["group"] for row in rows})
    assert groups == ["F1", "F2", "F3"]
    for group in groups:
        expectations = [row["expect"] for row in rows if row["group"] == group]
        if group == "F2":
            # W5-f r3 review r2: the frozen rows are not rewritten; the narrowing is a separate record
            assert not [row for row in rows if row["expect"] == "deferred_w3b6"]
            recorded = sorted(json.loads(NARROWED_F2.read_text(encoding="utf-8"))["rows"])
            assert recorded == ["W5F-F2-%03d" % number for number in range(1, 19)]
            by_id = {row["id"]: row for row in rows}
            assert all(by_id[row_id]["group"] == "F2" and by_id[row_id]["expect"] == "abstain" for row_id in recorded)
            assert expectations.count("read_or_abstain") >= 16
            continue
        judged = expectations.count("abstain") + expectations.count("read_or_abstain")
        assert judged >= 20
        assert abs(expectations.count("abstain") - expectations.count("read_or_abstain")) <= 2


@pytest.mark.parametrize("mode", ["fake", "none"])
def test_registered_reading_data_has_no_misread(mode, tmp_path):
    summary, _ = _checker(mode, tmp_path / (mode + ".json"))
    assert summary["misread"] == 0


def test_registered_reading_data_has_no_misread_with_r8(tmp_path):
    if not R8.is_dir():
        pytest.skip("ENV_MISSING[r8_placement]: %s" % R8)
    summary, _ = _checker("r8", tmp_path / "r8.json")
    assert summary["misread"] == 0


@pytest.mark.parametrize("case_id", ["A054", "A059"])
@pytest.mark.parametrize("placement_kind", ["fake", "r8"])
def test_quoted_focus_cases_abstain_with_the_registered_reason(case_id, placement_kind):
    attack = _load_attack_w3b4()
    probe = next(item for item in attack.probes() if item.case_id == case_id)
    placement = attack.query_for(probe) if placement_kind == "fake" else str(R8)
    if placement_kind == "r8" and not R8.is_dir():
        pytest.skip("ENV_MISSING[r8_placement]: %s" % R8)
    out = SR.read(probe.text, "ja", placement=placement)
    explanation = SR.typed_explain_ja(probe.text, placement)
    assert not out["readable"], out
    assert explanation["w3b2"] == "PLACEMENT_QUOTED_PARTICLE_AFTER_CASE:へ", explanation


def test_the_retracted_relational_filler_gate_is_kept_but_never_called(monkeypatch):
    # W5-f r3: the auditor retracted F-2 (2026-10-04 13:30); the function is kept as the K261 record and is never called.
    assert callable(R.typed_relational_filler_ja)
    calls = []
    real = R.typed_relational_filler_ja
    monkeypatch.setattr(R, "typed_relational_filler_ja", lambda *args, **kwargs: calls.append(args) or real(*args, **kwargs))
    fakes = _load_fakes()
    rows = _read_jsonl(TREE / "tests" / "reading_soundness" / "w5f_f2_de_cases.jsonl")
    de_row = ("place", ("で",), ("PLACE",), "adjunct")
    for pred_type in ("P_ACT", "P_CREATE", "P_EMOTION"):
        monkeypatch.setitem(R.TYPED_FRAMES_W3B4, pred_type,
                            tuple(R.TYPED_FRAMES_W3B4[pred_type]) + (de_row,))

    for row in rows:
        query = fakes.MapQuery({term: fakes.answer(kind, term=term) for term, kind in row["placement"].items()})
        SR.read(row["text"], "ja", placement=query)
        explanation = SR.typed_explain_ja(row["text"], query)
        assert not str(explanation["w3b2"]).startswith("RELATIONAL_NOUN_FILLER"), (row["id"], explanation)
    assert calls == []


def test_the_new_focus_gate_leaves_only_the_registered_morphological_misses():
    attack = _load_attack_w3b4()
    expected = {"A026", "A027", "A028", "A029", "A030", "A046", "A050",
                "C002", "C006", "C016", "C020", "C026", "C030", "C036", "C038"}
    misses = set()
    for probe in attack.probes():
        if probe.category not in ("after-he", "after-other-case"):
            continue
        clause = SimpleNamespace(span=SimpleNamespace(start=0, end=len(probe.text), text=probe.text))
        toks = R._tokens(probe.text)
        if R.typed_focus_after_case_ja(toks, clause) is None and R.typed_quoted_focus_after_case_ja(toks, clause) is None:
            misses.add(probe.case_id)
    assert misses == expected


def test_new_gate_functions_use_only_registered_pos_particle_and_reason_literals():
    allowed = {
        "補助記号", "空白", "記号", "助詞", "格助詞", "係助詞", "副助詞", "括弧開", "括弧閉", "読点", "句点",
        "PLACEMENT_FOCUS_PARTICLE_AFTER_CASE", "PLACEMENT_QUOTED_PARTICLE_AFTER_CASE",
        "PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:%s:%s", "PLACEMENT_QUOTED_PARTICLE_AFTER_CASE:%s",
        "place", "goal", "source", "で", "名詞", "普通名詞", "副詞可能", "RELATIONAL_NOUN_FILLER",
        "RELATIONAL_NOUN_FILLER:%s", "roles",
        "と", "や", "か", "も", "とも", "接尾辞", "COORDINATION_UNDETERMINED", "DISJUNCTION_UNDETERMINED",
        "value", "entity",
    }
    functions = (R.typed_quoted_focus_after_case_ja, R._quoted_focus_after_case_reason, R.typed_relational_filler_ja,
                 R._coordination_in_value, R._coordination_tomo)
    for function in functions:
        tree = ast.parse(inspect.getsource(function))
        definition = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        body = definition.body[1:] if ast.get_docstring(definition) else definition.body
        literals = {node.value for node in ast.walk(ast.Module(body=body, type_ignores=[]))
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        assert literals <= allowed, (function.__name__, literals - allowed)


GATE_REASON_PREFIXES = ("PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:", "PLACEMENT_QUOTED_PARTICLE_AFTER_CASE:")


def _all_reasons(out):
    reasons = list((out.get("abstain") or {}).get("reasons") or ())
    for item in out.get("unsupported") or ():
        reasons.extend(item.get("reasons") or ())
    return reasons


def _gate_reason(text):
    return R._quoted_focus_after_case_reason(R._tokens(text), 0, len(text), text, separated_only=True)


@pytest.mark.parametrize("mode", ["none", "fake", "r8"])
def test_r3_separated_focus_particles_abstain_on_the_public_entry(mode, monkeypatch):
    # W5-f r3 review r1 (must-fix 1): exact sets, no threshold. A row is either refused with the F-1 gate reason on the
    # public entry, or it is recorded in w5f_gates_r3_narrowed.json with the reason that actually stopped it.
    if mode == "r8":
        if not R8.is_dir():
            pytest.skip("ENV_MISSING[r8_placement]: %s" % R8)
        monkeypatch.setenv("VERA_PLACEMENT", str(R8))
    else:
        monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    fakes = _load_fakes()
    narrowed = json.loads(NARROWED_R3.read_text(encoding="utf-8"))["rows"]
    rows = [row for row in _read_jsonl(DATA_R3) + _read_jsonl(DATA_R3B) if row["expect"] == "abstain"]
    assert len(rows) >= 12
    without_gate_reason, gate_fires, gate_kinds = set(), set(), set()
    for row in rows:
        if mode == "fake" and row["placement"] is not None:
            placement = fakes.MapQuery({term: fakes.answer(kind, term=term) for term, kind in row["placement"].items()})
            out = SR.read(row["text"], "ja", placement=placement)
        elif mode == "r8":
            out = SR.read(row["text"], "ja")
        else:
            out = SR.read(row["text"], "ja", placement=None)
        assert not out["readable"], (mode, row["id"], out)
        reasons = _all_reasons(out)
        gate = _gate_reason(row["text"])
        if gate:
            gate_fires.add(row["id"])
        if any(reason.startswith(GATE_REASON_PREFIXES) for reason in reasons):
            assert row["id"] not in narrowed, (mode, row["id"], reasons)
            gate_kinds.add(next(r for r in reasons if r.startswith(GATE_REASON_PREFIXES)).split(":")[1])
        else:
            without_gate_reason.add(row["id"])
            assert row["id"] in narrowed, (mode, row["id"], reasons)
            assert any(reason.startswith(narrowed[row["id"]]["stopped_by"]) for reason in reasons), (mode, row["id"], reasons)
    assert without_gate_reason == set(narrowed), (mode, without_gate_reason ^ set(narrowed))
    # the gate function itself: fires on every abstain row except the recorded hole, with the recorded prefix
    holes = {row_id for row_id, record in narrowed.items() if record["gate"] is None}
    assert holes == {"W5F-F1-114"}
    assert gate_fires == {row["id"] for row in rows} - holes
    for row in rows:
        record = narrowed.get(row["id"])
        if record and record["gate"]:
            assert _gate_reason(row["text"]).startswith(record["gate"]), (row["id"], _gate_reason(row["text"]))
    # case particles for which the gate itself decided on the public entry (not a narrowed row): at least three kinds
    assert gate_kinds >= {"から", "で", "に"}, gate_kinds


@pytest.mark.parametrize("mode", ["none", "fake", "r8"])
def test_r3_without_the_public_gate_exactly_the_non_narrowed_rows_become_readable(mode, monkeypatch):
    # the rows not in the narrowed record are the ones the F-1 gate decides: remove the public gate and they are read
    if mode == "r8":
        if not R8.is_dir():
            pytest.skip("ENV_MISSING[r8_placement]: %s" % R8)
        monkeypatch.setenv("VERA_PLACEMENT", str(R8))
    else:
        monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    monkeypatch.setattr(R, "_quoted_focus_public_gate", lambda entry, text, out: out)
    fakes = _load_fakes()
    narrowed = set(json.loads(NARROWED_R3.read_text(encoding="utf-8"))["rows"])
    rows = [row for row in _read_jsonl(DATA_R3) + _read_jsonl(DATA_R3B) if row["expect"] == "abstain"]
    readable = set()
    for row in rows:
        if mode == "fake" and row["placement"] is not None:
            placement = fakes.MapQuery({term: fakes.answer(kind, term=term) for term, kind in row["placement"].items()})
            out = SR.read(row["text"], "ja", placement=placement)
        elif mode == "r8":
            out = SR.read(row["text"], "ja")
        else:
            out = SR.read(row["text"], "ja", placement=None)
        if out["readable"]:
            readable.add(row["id"])
    assert readable == {row["id"] for row in rows} - narrowed, (mode, readable ^ ({row["id"] for row in rows} - narrowed))


def test_r3_the_public_gate_does_not_refuse_an_unseparated_particle():
    text = "姉が駅でも走った。"
    toks = R._tokens(text)
    assert R._quoted_focus_after_case_reason(toks, 0, len(text), text, separated_only=True) is None
    reason = R._quoted_focus_after_case_reason(toks, 0, len(text), text, separated_only=False)
    assert reason is not None and reason.startswith("PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:"), reason


def test_r3_half_width_space_is_a_separation():
    text = "兄が荷車を倉庫から も押した。"
    toks = R._tokens(text)
    assert not any(word.surface.strip() == "" for word, _start, _end in toks if word.feature.pos1 != "空白")
    assert all(word.surface != " " for word, _start, _end in toks)
    reason = R._quoted_focus_after_case_reason(toks, 0, len(text), text, separated_only=True)
    assert reason is not None and reason.startswith("PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:から"), reason
