"""Adversarial probes preregistered in PREREG.md; never starts a real provider."""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import json
import multiprocessing
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "conduct_ask"))
sys.path.insert(0, str(ROOT / "tests" / "coarse_place"))
import map_helpers as M  # noqa: E402
import test_coarse_place_build as CPB  # noqa: E402
from verantyx import conduct_ask as ca  # noqa: E402
from verantyx import coarse_place as cp  # noqa: E402
from verantyx import llm_choice as lc  # noqa: E402
from verantyx import observe as O  # noqa: E402
from verantyx import routing_from_text as rt  # noqa: E402
from verantyx import sovereign as sov  # noqa: E402
from verantyx.llm_choice import ChoiceLedger  # noqa: E402

_spec = importlib.util.spec_from_file_location("w5b_attack_observe_fakes", ROOT / "tests" / "observe" / "fakes.py")
observe_fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(observe_fakes)

FRAME = M.w2g("w02_absence")
MAP_QUESTION = "授業料の請求の処理も今回の開発に入りますか？"
MAP_SCRIPT = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["矛盾", "一致"]}}
MAP_OPTIONS = M.YN_JA


def _map_run(ledger):
    return M.ask_map(FRAME, MAP_QUESTION, MAP_OPTIONS, MAP_SCRIPT, ledger=ledger)


def _map_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def _write_map_rows(path, rows):
    Path(path).write_text("".join(lc._canonical(row) + "\n" for row in rows), encoding="utf-8")


def _expect_ledger_refusal(path, attack_id):
    map_file = Path(path).with_suffix(".map.json")
    map_file.write_text(json.dumps(MAP_SCRIPT, ensure_ascii=False), encoding="utf-8")
    result = ca.answer_question(FRAME, MAP_QUESTION, MAP_OPTIONS, vocab_llm="fake",
                                map_fake=str(map_file), vocab_ledger=str(path))
    actual = {"decision": result["decision"], "reason": result["escalate_reason"],
              "detail": result["escalate_detail"], "answer": result["answer"],
              "mapping_outcome": result.get("mapping", {}).get("outcome"),
              "ledger_replay": result.get("mapping", {}).get("ledger_replay")}
    print(f"OBS {attack_id} {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual == {"decision": "escalate", "reason": "MAPPING_UNSETTLED",
                      "detail": "LEDGER_INTEGRITY", "answer": None,
                      "mapping_outcome": "ESCALATED:MAPPING_UNSETTLED/LEDGER_INTEGRITY",
                      "ledger_replay": None}


# M1–M3: ledger-only edits must not become a replay.
@pytest.mark.parametrize("attack", ["M1_REORDER", "M2_DUPLICATE", "M3_TRUNCATE"])
def test_manifest_detects_reorder_duplicate_and_truncation(tmp_path, attack):
    path = tmp_path / f"{attack}.jsonl"
    first, _ = _map_run(ChoiceLedger(path))
    assert first["decision"] == "answer"
    rows = _map_rows(path)
    assert rows[-1]["type"].startswith("map_")
    if attack == "M1_REORDER":
        raw = Path(path).read_text(encoding="utf-8").splitlines()
        Path(path).write_text("\n".join(raw[::-1]) + "\n", encoding="utf-8")
    elif attack == "M2_DUPLICATE":
        _write_map_rows(path, rows + [copy.deepcopy(rows[-1])])
    else:
        _write_map_rows(path, rows[:-1])
    _expect_ledger_refusal(path, attack)


# K1: two spellings each have their own, disagreeing direct evidence.
def test_two_decided_kana_variants_keep_their_own_direct_types(tmp_path):
    source = tmp_path / "kana.jsonl"
    records = [
        {"title": "ヒナタ丸", "text": "ヒナタ丸は日本の道具である。", "source": "fixture", "sha": "k1",
         "split": "train"},
        {"title": "ひなた丸", "text": "ひなた丸は日本の会社である。", "source": "fixture", "sha": "k2",
         "split": "train"},
    ]
    source.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    placement = tmp_path / "placement"
    assert CPB.build(placement, jawiki=source) == 0
    kata, hira = cp.query("ヒナタ丸", placement=str(placement)), cp.query("ひなた丸", placement=str(placement))
    actual = {"kata": [kata["state"], kata["top"], kata["origin"], kata["estimate_basis"], kata["spelling"]["why"]],
              "hira": [hira["state"], hira["top"], hira["origin"], hira["estimate_basis"], hira["spelling"]["why"]]}
    print(f"OBS K1 {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual == {"kata": ["DECIDED", ["ARTIFACT"], "direct", None, "KANA_VARIANT_DIFFERS"],
                      "hira": ["DECIDED", ["GROUP_ORG"], "direct", None, "KANA_VARIANT_DIFFERS"]}


# S1: two promoters and a releaser start at the same barrier; check the final durable state.
def _day(n):
    return datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=n)


def _seed_sovereign(root):
    assert sov.create(root, "w5attack", "owner", consent_promote=True, now=lambda: _day(0))["verdict"] == "CREATED"
    ledger = sov.open_ledger(root, "w5attack", now=lambda: _day(0))
    for phrase in ("alpha", "beta", "gamma"):
        for n in (0, 1, 1):
            ledger._now = lambda n=n: _day(n)
            ledger.append({"kind": "utterance", "payload": {"phrase": phrase}})


def _race_one(root, action, gate, output):
    gate.wait(30)
    if action == "release":
        verdict = sov.release(root, "w5attack", "w5attack", now=lambda: _day(4))["verdict"]
    else:
        verdict = sov.promote(root, "w5attack", now=lambda: _day(3))["verdict"]
    output.put((action, verdict))


def test_two_promoters_and_a_third_process_release_never_leave_active_rows(tmp_path):
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("race probe requires the local fork start method")
    ctx = multiprocessing.get_context("fork")
    for i in range(5):
        root = tmp_path / f"sovereign-{i}"
        _seed_sovereign(root)
        gate, output = ctx.Barrier(3), ctx.Queue()
        processes = [ctx.Process(target=_race_one, args=(str(root), action, gate, output))
                     for action in ("promote-a", "promote-b", "release")]
        for process in processes:
            process.start()
        verdicts = [output.get(timeout=60) for _ in processes]
        for process in processes:
            process.join(30)
            assert process.exitcode == 0
        state = sov.describe(root, "w5attack").status
        active = sov.active_promotions(root, "w5attack")
        with sqlite3.connect(str(root / "structure.sqlite")) as conn:
            ids = [row[0] for row in conn.execute("SELECT promotion_id FROM promotion_log ORDER BY seq")]
        actual = {"run": i, "verdicts": sorted(verdicts), "status": state,
                  "active": len(active), "promotions": len(ids), "unique_ids": len(set(ids))}
        print(f"OBS S1 {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
        assert state == "RELEASED" and active == [] and len(ids) == len(set(ids))


# O1: a surviving coordinate is valid, but the carried set is incomplete.
def test_reobserve_catches_a_missing_coordinate_from_a_merged_cell():
    clauses = [observe_fakes.clause("行く", {"agent": "太郎"}),
               observe_fakes.clause("買う", {"agent": "花子"})]
    relation = [{"type": "cause", "from": 0, "to": 1}]
    reading = observe_fakes.read_out(clauses, relation)
    twin = observe_fakes.read_out(clauses, relation)
    viewpoint = O.Viewpoint(O.AnchorText("seed", "x", None, 0, reading), (O.Edge("cause"),))
    structure = O.Structure.from_injected([{"id": "twin", "reading": twin}], None, None)
    observed = O.observe(viewpoint, structure)
    element = next(e.to_dict() for rank in observed.ranks for e in rank if len(e.to_dict()["coords"]) == 2)
    altered = copy.deepcopy(element)
    altered["coords"].pop()
    result = O.reobserve(altered, viewpoint, structure)
    print(f"OBS O1 {json.dumps(result, ensure_ascii=False, sort_keys=True)}")
    assert result == {"status": "MISMATCH", "reason": "COORDS_INCOMPLETE"}


# R1: the default Japanese reader, no placement lookup, and a common noun as subject.
def test_japanese_common_noun_without_placement_is_not_routed_as_an_agent():
    explained = rt.explain("チームがテストを書く。\n", "attack.md")
    result = rt.route_task(explained, {"role": "implement", "kind": "test_authoring", "size": "medium"})
    unit = explained.extraction.units[0]
    actual = {"unit_status": unit.status, "reasons": unit.reasons,
              "agents": [dataclasses.asdict(agent) for agent in explained.records.agents],
              "decision": result["decision"], "agent": result["agent"],
              "common_noun_check": result["reading"].get("common_noun_check")}
    print(f"OBS R1 {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert unit.status != "MAPPED" and result["agent"] is None


# R2: parsed relations are supplied explicitly so this probe isolates addendum-marker interpretation.
def _clause(predicate, roles):
    return {"predicate": predicate, "roles": roles, "polarity": "+", "tense": "nonpast",
            "modality": None, "voice": "active"}


def _reading_for_assignment(_sentence):
    return {"schema": "verantyx.semantic_read/1", "lang": "ja", "readable": True,
            "clauses": [_clause("任せる", {"recipient": "ハル", "patient": "実装"})],
            "relations": [], "abstain": None, "unsupported": [], "clause_meta": [{"rule": "injected", "span": [0, 1]}]}


def test_yappari_sonomama_does_not_turn_an_addendum_into_replacement():
    first = "実装はハルに任せる。"
    second = "やっぱりそのまま、実装はハルに任せる。"
    explained = rt.explain(f"{first}\n追記：{second}\n", "attack.md", reader=_reading_for_assignment)
    actual = {"statuses": [unit.status for unit in explained.extraction.units],
              "auto_resolved": explained.extraction.auto_resolved,
              "superseded_by": [relation.superseded_by for relation in explained.extraction.relations],
              "additions_kept": explained.extraction.additions_kept}
    print(f"OBS R2 {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual == {"statuses": ["MAPPED", "MAPPED"], "auto_resolved": 0,
                      "superseded_by": [None, None], "additions_kept": 1}


LEDGER_FRAME = """# Ledger service
[goal]
project: Ledger service
statement: Keep the books and answer audits

[philosophy_invariants]
I1: Audit data stays internal

[completion_criteria]
C1: The totals are readable | human-judged

[phases]
P1: Collect the entries
P2: Check the totals

[phase_order]
P1 -> P2: Check starts after collection

[decisions]
D1: CHOICE | invoice | PDF
D2: CHOICE | notice language | Japanese
D3: SCOPE | refund handling | in scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
none: none

[forbidden_actions]
none: none
"""


def _attribute_frame(tmp_path):
    frame = tmp_path / "ledger.md"
    frame.write_text(LEDGER_FRAME, encoding="utf-8")
    return str(frame)


def _script(record, relations):
    return {"records": [record], "decides": "決まる", "relations": {record: relations}}


def _ask_map(frame, question, options, script):
    mapper = M.mapper_for(frame, options, script)
    return ca.answer_question(frame, question, options, vocab_llm="fake", mapper=mapper)


def _typed(result):
    return result["decision"], result["escalate_reason"], result["escalate_detail"]


# A1/A2: unrecorded and compound attributes must not flow through a mapping answer.
@pytest.mark.parametrize("question", [
    "What’s the language of the invoice archive?",
    "Which language for the invoice archive?",
    "Which billing-language should we use for the invoice archive?",
])
def test_wh_and_compound_attribute_variants_cannot_answer_from_an_unrelated_record(tmp_path, question):
    frame = _attribute_frame(tmp_path)
    result = _ask_map(frame, question, ["English", "Japanese"], _script("D1", ["一致", "矛盾"]))
    actual = {"question": question, "typed": _typed(result), "answer": result["answer"],
              "wider_phrase": result["trace"]["resolver_outcomes"].get("wider_phrase"),
              "mapping_exit": result.get("mapping", {}).get("exit_check")}
    print(f"OBS A {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual["typed"] == ("escalate", "FRAME_SILENT", "TERM_IN_WIDER_PHRASE")
    assert actual["answer"] is None and "ATTRIBUTE_" in actual["wider_phrase"]


# Q1/Q2: a prohibition request cannot become approval; an if-possible request must be approved by a human.
def test_negated_request_is_not_answered_and_conditional_request_is_raised(tmp_path):
    frame = _attribute_frame(tmp_path)
    negative = ca.answer_question(frame, "ログを削除しないでください。")
    conditional = ca.answer_question(frame, "もし可能なら、ログを削除してください。")
    actual = {"negative": {"decision": negative["decision"], "reason": negative.get("escalate_reason"),
                           "detail": negative.get("escalate_detail"), "answer": negative["answer"]},
              "conditional": {"decision": conditional["decision"], "reason": conditional.get("escalate_reason"),
                              "detail": conditional.get("escalate_detail"), "answer": conditional["answer"]}}
    print(f"OBS Q {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual["negative"]["decision"] != "answer" and actual["negative"]["answer"] is None
    assert (actual["conditional"]["decision"], actual["conditional"]["reason"],
            actual["conditional"]["detail"], actual["conditional"]["answer"]) == (
                "escalate", "HUMAN_APPROVAL_REQUIRED", "BUILTIN_PROTECTED", None)
