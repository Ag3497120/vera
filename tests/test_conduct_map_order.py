"""The order route and the value answer of the record mapping (W2-g, review 1 must-fix 1), with made-up providers only.

Order route: the model names the two phases a question speaks of (a closed multi-select over the frame's phase names), the rule
reads their order off the whole phase graph, and the model only says how each option relates to the derived statement
("A must be done before B").  Value answer: a question without options, mapped to one decision / choice record that decides it,
is answered with the frame's own value.  A scripted reply is an assumption about a model, not a measurement of one."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import ask_map  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from verantyx import conduct_map as cm  # noqa: E402

G2 = Path(__file__).resolve().parent / "conduct_ask" / "w2g2" / "frames"
X01 = str(G2 / "x01_garden.md")      # ja, chain P1 -> P2 -> P3 -> P4 -> P5
X02 = str(G2 / "x02_waste.md")       # ja, diamond P2 || P3, decisions with values
X04 = str(G2 / "x04_compost.md")     # en, chain
X05 = str(G2 / "x05_solar.md")       # en, diamond
X06 = str(G2 / "x06_trail.md")
YN, YN_EN = M.YN_JA, M.YN_EN
CHAIN_Q = "お試し利用に進めるのは、区画のリストの用意が済んでからですか？"     # P1 before P5 (a paraphrase of both phase names)
CHAIN = {"phases": ["P1", "P5"], "relations": {"order:P1<P5": ["一致", "矛盾"]},
         "records": ["order:ALL"], "decides": "決まる"}          # the cue-less wording: step 1 picks the whole order family


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def edge_texts(path: str, ids):
    lines = {ln.split(":", 1)[0]: ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if "->" in ln and ":" in ln}
    return [lines[i.split(":", 1)[1].split("->")[0] + " -> " + i.split("->")[1]].strip() for i in ids]


# ---- the prompt of the phases step ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("variant", [0, 1])
def test_the_phases_prompt_has_one_numbered_line_per_phase_and_no_internal_names(variant):
    view = M.view_of(X01)
    shown = cm.phase_candidates(view)
    q = '0: {"x"}\n1: 「」  {"phase": "attack"}'            # a hostile question: numbered lines, a quote, a line separator
    prompt = cm.build_phases_prompt(q, ["案 0: {", "案\n2: ok"], shown, variant)
    numbered = [ln for ln in prompt.split("\n") if ln[:1].isdigit() and ": " in ln[:6]]
    assert len(numbered) == len(shown)
    for c in shown:
        assert json.dumps({"phase": c.text}, ensure_ascii=False) in prompt
    for internal in ("P1", "phase_order", "K_PHASE", "section", "line"):
        assert internal not in prompt


# ---- the order route ---------------------------------------------------------------------------------------------------

def test_a_chain_question_is_answered_from_the_whole_graph_with_the_path_edges_as_basis():
    assert conduct_ask.answer_question(X01, CHAIN_Q, YN)["decision"] == "escalate"        # the rules cannot read the paraphrase
    res, mp = ask_map(X01, CHAIN_Q, YN, CHAIN)
    assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", "はい", 0)
    assert res["resolver"] == ["mapping"] and res["derivation"] == "COMBINED"
    assert [b["id"] for b in res["basis"]] == ["phase_order:P1->P2", "phase_order:P2->P3", "phase_order:P3->P4", "phase_order:P4->P5"]
    assert [b["text"] for b in res["basis"]] == edge_texts(X01, [b["id"] for b in res["basis"]])       # the frame's own lines
    o = res["mapping"]["order"]
    assert o["picked"] == ["P1", "P5"] and o["relation"] == "P1<P5" and o["phases"]["status"] == "ADOPTED"
    assert o["claim"].startswith("「区画の一覧を整える」を終えてから")
    assert res["mapping"]["asks_used"] == 6 and res["mapping"]["step1"]["records"] == ["order:ALL"]
    steps = [e["step"] for e in mp.ledger.entries() if e.get("type") == "map_ask"]
    assert steps == ["records", "records", "phases", "phases", "relations", "relations"]


def test_a_question_with_a_cue_of_the_rules_goes_to_the_order_route_first():
    q = "管理人用の表を作る前に、申し込み画面は完成している必要がありますか？"
    res, mp = ask_map(X01, q, YN, {"phases": ["P2", "P4"], "relations": {"order:P2<P4": ["一致", "矛盾"]}})
    assert (res["decision"], res["answer"]) == ("answer", "はい") and res["mapping"]["asks_used"] == 4 and res["mapping"]["step1"] is None
    assert [e["step"] for e in mp.ledger.entries() if e.get("type") == "map_ask"] == ["phases", "phases", "relations", "relations"]


def test_the_phases_may_be_named_in_either_order_and_the_option_decides_the_answer():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "phases": ["P5", "P1"], "relations": {"order:P1<P5": ["矛盾", "一致"]}})
    assert (res["answer"], res["answer_option_index"]) == ("いいえ", 1)


def test_two_options_that_name_the_phases_are_judged_against_the_derived_statement():
    q = "Which comes first, the bin categories or the trial week?"
    opts = ["Run the trial week with volunteers", "Define the bin categories"]
    res, _ = ask_map(X04, q, opts, {**CHAIN, "phases": ["P5", "P1"], "relations": {"order:P1<P5": ["矛盾", "一致"]}})
    assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", "Define the bin categories", 1)
    assert [b["id"] for b in res["basis"]] == ["phase_order:P1->P2", "phase_order:P2->P3", "phase_order:P3->P4", "phase_order:P4->P5"]


def test_one_edge_is_a_direct_derivation():
    res, _ = ask_map(X01, "申し込み画面の次に、お知らせの自動メールを作りますか？", YN, {**CHAIN, "phases": ["P2", "P3"], "relations": {"order:P2<P3": ["一致", "矛盾"]}})
    assert res["derivation"] == "DIRECT" and [b["id"] for b in res["basis"]] == ["phase_order:P2->P3"]


def test_two_unordered_phases_are_a_silent_frame_not_a_pick():
    q = "Which gets built first, the daily chart or the fault alert?"
    res, _ = ask_map(X05, q, ["Build the fault alert", "Build the daily chart"], {"phases": ["P2", "P3"]})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "UNORDERED")
    assert [b["id"] for b in res["basis"]] == ["P2", "P3"] and res["mapping"]["order"]["relation"] == "UNORDERED"
    assert res["mapping"]["asks_used"] == 2          # a cue of the rules: the phases step first; nothing asked about the options


def test_a_disagreement_on_the_phases_hands_the_question_up():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "phases2": ["P1", "P4"]})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "PHASES_DISAGREE")
    assert res["answer"] is None and res["mapping"]["asks_used"] == 4


@pytest.mark.parametrize("kind", ["TIMEOUT", "LIMIT_REACHED"])
def test_a_failed_phases_step_is_typed(kind):
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "fail_phases2": kind})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", f"PHASES_FAILED:{kind}")


def test_an_invalid_phases_reply_is_a_typed_abstention():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "raw_phases": '{"phases": [0], "answer": "はい"}'})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "PHASES_INVALID_ANSWER")


def test_a_failed_relations_step_is_typed():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "fail_relations": "TIMEOUT"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP2_FAILED:TIMEOUT")


def test_relations_that_say_unrelated_do_not_decide():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "relations": {"order:P1<P5": ["無関係", "無関係"]}})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAPPED_NO_OPTION_RELATED")
    assert [b["id"] for b in res["basis"]][0] == "phase_order:P1->P2"


def test_both_options_contradicting_the_derived_statement_is_no_option_allowed():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "relations": {"order:P1<P5": ["矛盾", "矛盾"]}})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("NO_OPTION_ALLOWED", "MAPPED_NO_OPTION_AGREES")


def test_several_phases_that_all_precede_one_of_them_give_one_statement():
    q = "管理人用の表を作る前に、申し込み画面と区画のリストは完成している必要がありますか？"
    res, _ = ask_map(X01, q, YN, {"phases": ["P1", "P2", "P4"], "relations": {"order:P1+P2<P4": ["一致", "矛盾"]}})
    assert (res["decision"], res["answer"]) == ("answer", "はい")
    assert [b["id"] for b in res["basis"]] == ["phase_order:P1->P2", "phase_order:P2->P3", "phase_order:P3->P4"]
    assert res["mapping"]["order"]["relation"] == "P1+P2<P4" and res["derivation"] == "COMBINED"


def test_several_phases_without_one_last_phase_are_a_silent_frame():
    res, _ = ask_map(X05, "Is the monthly summary built after the feed, the daily chart and the fault alert?", YN_EN,
                     {"phases": ["P1", "P2", "P3"]})            # P2 and P3 are parallel: no single last phase has all the others before it
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "UNORDERED")
    res, _ = ask_map(X05, "Does the monthly summary come after the daily chart and the fault alert?", YN_EN, {"phases": ["P2", "P3", "P4"], "relations": {"order:P2+P3<P4": ["一致", "矛盾"]}})
    assert res["decision"] == "answer" and [b["id"] for b in res["basis"]] == ["phase_order:P2->P4", "phase_order:P3->P4"]


def test_five_phases_named_is_not_an_order_question_the_route_takes():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "phases": ["P1", "P2", "P3", "P4", "P5"]})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "ORDER_NOT_RESOLVED")
    assert res["mapping"]["order"]["relation"] == "NOT_APPLICABLE:5_PHASES" and res["mapping"]["asks_used"] == 4


def test_no_phase_named_after_the_whole_order_family_was_picked_is_unsettled():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "phases": []})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "ORDER_NOT_RESOLVED")
    assert res["mapping"]["order"]["phases"]["status"] == "NONE"


def test_no_phase_named_for_a_question_with_a_cue_continues_with_the_records_route():
    q = "管理人用の表を作る前に、申し込み画面は完成している必要がありますか？"
    res, _ = ask_map(X01, q, YN, {"phases": [], "records": ["order:ALL"], "decides": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert res["mapping"]["order"]["phases"]["status"] == "NONE" and res["mapping"]["step1"]["status"] == "ADOPTED"


def test_the_order_family_picked_together_with_another_record_is_unsettled():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "records": ["order:ALL", "D5"]})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "ORDER_MIXED_WITH_OTHER_RECORDS")
    assert res["mapping"]["order"] is None and res["mapping"]["asks_used"] == 2


def test_the_order_family_that_does_not_decide_is_handed_up_before_the_phases_are_asked():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "decides": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert [b["id"] for b in res["basis"]][0] == "phase_order:P1->P2" and res["mapping"]["asks_used"] == 2


def test_the_single_edges_are_not_candidates_of_step_1_unless_a_rule_answer_needs_them():
    res, mp = ask_map(X01, CHAIN_Q, YN, CHAIN)
    ids = [c["id"] for c in res["mapping"]["candidates"]]
    assert "order:ALL" in ids and not any(i.startswith("phase_order:") for i in ids)
    res, _ = ask_map(X01, RULE_Q, YN, {"phases": ["P2", "P4"], "relations": {"order:P2<P4": ["一致", "矛盾"]}})
    assert res["mapping"]["outcome"] == "CORROBORATED"


def test_an_order_question_without_options_is_not_answered_from_the_mapping_alone():
    res, _ = ask_map(X01, "お試し利用に進めるのは、区画のリストの用意が済んでからですか？", None, CHAIN)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("ANSWER_FORM_UNSUPPORTED", "MAPPING_NEEDS_OPTIONS")


# ---- a rule answer to an order question is corroborated through the same route ---------------------------------------------

RULE_Q = "管理人用の利用表を作るより前に、予約画面を作ってもよいですか？"       # the rules answer "はい" from P2->P3, P3->P4


def test_the_rules_answer_the_order_question_by_themselves():
    res = conduct_ask.answer_question(X01, RULE_Q, YN)
    assert (res["decision"], res["answer"]) == ("answer", "はい") and [b["id"] for b in res["basis"]] == ["phase_order:P2->P3", "phase_order:P3->P4"]


def test_a_rule_order_answer_is_corroborated_when_the_pair_and_the_option_agree():
    res, _ = ask_map(X01, RULE_Q, YN, {"phases": ["P2", "P4"], "relations": {"order:P2<P4": ["一致", "矛盾"]}})
    assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", "はい", 0)
    assert res["mapping"]["outcome"] == "CORROBORATED" and res["mapping"]["route"] == "CORROBORATE"
    assert res["resolver"] != ["mapping"] and [b["id"] for b in res["basis"]] == ["phase_order:P2->P3", "phase_order:P3->P4"]


def test_a_rule_order_answer_is_handed_up_when_the_mapped_phases_are_another_pair():
    res, _ = ask_map(X01, RULE_Q, YN, {"phases": ["P1", "P4"], "relations": {"order:P1<P4": ["一致", "矛盾"]}})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "RULE_BASIS_NOT_MAPPED")


def test_a_rule_order_answer_is_handed_up_when_the_mapped_option_is_another():
    res, _ = ask_map(X01, RULE_Q, YN, {"phases": ["P2", "P4"], "relations": {"order:P2<P4": ["矛盾", "一致"]}})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "RULE_ANSWER_NOT_MAPPED")
    assert res["answer"] is None


# ---- the value answer ------------------------------------------------------------------------------------------------------

VQ = "知らせは何時に出しますか？"


def test_a_question_without_options_mapped_to_one_deciding_decision_is_answered_with_the_frames_value():
    res, _ = ask_map(X02, VQ, None, {"records": ["D1"], "decides": "決まる"})
    assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", "前日の午後六時", None)
    assert res["resolver"] == ["mapping"] and res["derivation"] == "DIRECT"
    assert [b["id"] for b in res["basis"]] == ["D1"] and res["basis"][0]["text"] == M.frame_line(X02, res["basis"][0]["line"])


def test_a_choice_policy_gives_its_value_too():
    res, _ = ask_map(X02, "住民への連絡はどんな方法で届けますか？", None, {"records": ["D5"], "decides": "決まる"})
    assert (res["decision"], res["answer"]) == ("answer", "アプリ内の通知")


def test_the_value_is_the_frames_not_a_string_of_the_reply():
    # a reply that carries its own answer text is invalid (closed form), and a valid one never contributes text
    res, _ = ask_map(X02, VQ, None, {"raw": '{"records": [0], "decides": "決まる", "answer": "午後九時"}'})
    assert res["decision"] == "escalate" and "午後九時" not in json.dumps(res, ensure_ascii=False)
    res, _ = ask_map(X02, VQ, None, {"records": ["D1"], "decides": "決まる"})
    assert "午後九時" not in json.dumps(res, ensure_ascii=False)


def test_a_value_record_that_does_not_decide_is_not_answered():
    res, _ = ask_map(X02, "知らせは何通まで出しますか？", None, {"records": ["D1"], "decides": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")


def test_two_records_or_a_record_without_a_value_do_not_answer_without_options():
    res, _ = ask_map(X02, VQ, None, {"records": ["D1", "D5"], "decides": "決まる"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("ANSWER_FORM_UNSUPPORTED", "MAPPING_NEEDS_OPTIONS")
    res, _ = ask_map(X02, "収集日の変更の告知は範囲に入りますか？", None, {"records": ["D3"], "decides": "決まる"})        # a scope record
    assert (res["escalate_reason"], res["escalate_detail"]) == ("ANSWER_FORM_UNSUPPORTED", "MAPPING_NEEDS_OPTIONS")


def test_decide_answers_a_single_value_record_only():
    cands = {c.id: c for c in cm.all_candidates(M.view_of(X02))}
    out = cm.decide([cands["D1"]], "決まる", None, None)
    assert (out.decision, out.answer, out.index, out.derivation, out.resolvers, out.layer) == ("answer", "前日の午後六時", None, "DIRECT", ("mapping",), "mapping")
    assert [r.id for r in out.basis] == ["D1"]
    assert cm.decide([cands["D3"]], "決まる", None, None).detail == "MAPPING_NEEDS_OPTIONS"
    assert cm.decide([cands["D1"], cands["D5"]], "決まる", None, None).detail == "MAPPING_NEEDS_OPTIONS"
    assert cm.decide([cands["D1"]], "決まらない", None, None).detail == "MAP_RECORD_DOES_NOT_DECIDE"


# ---- the gates stand in front of a corroborated rule answer too -------------------------------------------------------------

def test_a_rule_yes_to_an_advice_question_is_not_corroborated_into_an_answer():
    q = "Should we include volunteer sign-up in the project?"
    assert conduct_ask.answer_question(X06, q, YN_EN)["answer"] == "Yes"                  # off: the known hole of the rules
    res, _ = ask_map(X06, q, YN_EN, {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "ADVICE_NOT_PERMISSION")
    assert res["mapping"]["exit_check"] == "FRAME_SILENT/ADVICE_NOT_PERMISSION"


# ---- the ledger and the reuse ------------------------------------------------------------------------------------------------

def test_the_phases_ask_is_in_the_ledger_with_every_field_and_is_not_asked_twice():
    res, mp = ask_map(X01, CHAIN_Q, YN, CHAIN)
    rows = [e for e in mp.ledger.entries() if e.get("type") == "map_ask" and e["step"] == "phases"]
    assert len(rows) == 2 and sorted(r["ask_index"] for r in rows) == [0, 1]
    for r in rows:
        for k in ("id", "decision_id", "frame_sha256", "question", "options", "candidates", "order", "shown", "variant", "provider",
                  "prompt", "prompt_sha256", "raw_reply", "verdict", "parsed", "elapsed_ms", "ts"):
            assert k in r, k
        assert r["verdict"] == "PICK" and r["parsed"]["phases"] == ["P1", "P5"]
    assert rows[0]["order"] != rows[1]["order"] and rows[0]["variant"] != rows[1]["variant"]
    first, second = (p for p in mp.providers)
    before = first.calls + second.calls
    res2 = conduct_ask.answer_question(X01, CHAIN_Q, YN, vocab_llm="fake", mapper=mp)
    assert first.calls + second.calls == before and res2["answer"] == "はい"
    types = [e["type"] for e in mp.ledger.entries()]
    assert types.count("map_reuse") == 3                  # step 1, the phases step and the relations step
    assert [e for e in mp.ledger.entries() if e["type"] == "map_decision" and e["step"] == "phases"][0]["counts_as_evidence"] is False


# ---- the pure parts: the derived statement and the folded candidate -------------------------------------------------------------

def _graph(path):
    view = M.view_of(path)
    return view, conduct_ask.Graph(view)


def test_order_statement_gives_only_true_statements():
    view, g = _graph(X02)                                    # P1 -> P2, P1 -> P3, P2 -> P4, P3 -> P4, P4 -> P5
    claim, edges, rel = cm.order_statement(view, g, ["P5", "P1"])
    assert rel == "P1<P5" and claim.id == "order:P1<P5" and len(edges) == 5            # every edge lies on a path from P1 to P5
    claim, edges, rel = cm.order_statement(view, g, ["P2", "P3"])
    assert (claim, edges, rel) == (None, [], "UNORDERED")                              # parallel: no statement
    claim, edges, rel = cm.order_statement(view, g, ["P2", "P3", "P4"])
    assert rel == "P2+P3<P4" and sorted(e.ref.id for e in edges) == ["phase_order:P2->P4", "phase_order:P3->P4"]
    claim, edges, rel = cm.order_statement(view, g, ["P1", "P2", "P3"])
    assert claim is None and rel == "UNORDERED"                                        # no single last phase
    assert "「" in cm.order_statement(view, g, ["P2", "P4"])[0].text


def test_the_order_family_is_one_candidate_that_stands_for_every_edge_line():
    view = M.view_of(X01)
    agg = cm.order_aggregate(view)
    assert agg.id == "order:ALL" and agg.kind == cm.K_ORDER and [r.id for r in cm._refs([agg])] == [e.ref.id for e in view.edges]
    universe = cm.all_candidates(view)
    folded = cm.fold_order(universe, agg, keep_single=False)
    assert [c.id for c in folded].count("order:ALL") == 1 and not any(c.id.startswith("phase_order:") for c in folded)
    assert len(folded) == len(universe) - len(view.edges) + 1
    assert [c.id for c in cm.fold_order(universe, agg, keep_single=True)] == [c.id for c in universe]


def test_a_frame_without_edges_has_no_order_family():
    view = M.view_of(str(G2.parent.parent / "fixtures" / "frames" / "f01_loan.md"))
    assert (cm.order_aggregate(view) is None) == (not view.edges)


# ---- review 2, must-fix 1: the order route asks "does the order of these phases alone settle the question" too ------------------

DISTRICT_Q = "In a neighbouring site's project, is the weekly report built before the handbook page?"      # another subject's project
DISTRICT = {"phases": ["P3", "P4"], "relations": {"order:P3<P4": ["一致", "矛盾"]}}


def test_a_scripted_model_that_says_the_order_decides_gives_the_answer_the_order_route_always_gave():
    res, _ = ask_map(X04, DISTRICT_Q, YN_EN, DISTRICT)             # the hole of the previous round: no closed decides was asked
    assert (res["decision"], res["answer"]) == ("answer", "Yes")


def test_a_question_about_another_subject_is_handed_up_when_the_two_readings_say_the_order_does_not_decide():
    res, mp = ask_map(X04, DISTRICT_Q, YN_EN, {**DISTRICT, "decides_phases": "決まらない"})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert res["answer"] is None and [b["id"] for b in res["basis"]] == ["phase_order:P3->P4"]
    assert res["mapping"]["asks_used"] == 2 and res["mapping"]["step2"] == []            # the options were never asked about
    assert res["mapping"]["order"]["decides"] == "決まらない" and res["mapping"]["order"]["phases"]["decides"] == "決まらない"
    rows = [e for e in mp.ledger.entries() if e.get("type") == "map_ask"]
    assert [r["step"] for r in rows] == ["phases", "phases"] and all(r["parsed"]["decides"] == "決まらない" for r in rows)
    dec = [e for e in mp.ledger.entries() if e.get("type") == "map_decision"][0]
    assert dec["result"] == {"phases": ["P3", "P4"], "decides": "決まらない"} and dec["counts_as_evidence"] is False


def test_two_readings_that_differ_only_in_decides_do_not_agree():
    res, _ = ask_map(X04, DISTRICT_Q, YN_EN, {**DISTRICT, "decides_phases": "決まる", "decides_phases2": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "PHASES_DISAGREE")
    assert res["answer"] is None and res["mapping"]["asks_used"] == 2


def test_the_decides_is_part_of_the_closed_form_of_the_phases_reply():
    res, _ = ask_map(X04, DISTRICT_Q, YN_EN, {**DISTRICT, "raw_phases": '{"phases": [2, 3]}'})            # no decides: invalid
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "PHASES_INVALID_ANSWER")
    res, _ = ask_map(X04, DISTRICT_Q, YN_EN, {**DISTRICT, "raw_phases": '{"phases": [2, 3], "decides": "決まる", "answer": "Yes"}'})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "PHASES_INVALID_ANSWER") and res["answer"] is None


def test_a_rule_order_answer_is_not_corroborated_when_the_order_does_not_decide():
    res, _ = ask_map(X01, RULE_Q, YN, {"phases": ["P2", "P4"], "relations": {"order:P2<P4": ["一致", "矛盾"]}, "decides_phases": "決まらない"})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert res["answer"] is None and res["mapping"]["route"] == "CORROBORATE" and res["mapping"]["outcome"].startswith("ESCALATED:")


def test_the_order_family_picked_by_step_1_is_also_checked_with_the_phases_decides():
    res, _ = ask_map(X01, CHAIN_Q, YN, {**CHAIN, "decides_phases": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert res["mapping"]["step1"]["decides"] == "決まる" and res["mapping"]["order"]["decides"] == "決まらない"
    assert res["mapping"]["asks_used"] == 4


def test_no_phase_named_is_recorded_as_the_fall_back_to_the_records_route():
    q = "管理人用の表を作る前に、申し込み画面は完成している必要がありますか？"
    res, _ = ask_map(X01, q, YN, {"phases": [], "records": ["order:ALL"], "decides": "決まらない"})
    assert res["mapping"]["order"]["fallback"] == "RECORDS_ROUTE:NO_PHASE_NAMED"


def test_a_phases_decision_cached_in_the_older_form_is_not_reused():
    from verantyx.llm_choice import ChoiceLedger
    view = M.view_of(X04)
    mp = M.mapper_for(X04, YN_EN, DISTRICT)
    sess = mp.session("0" * 64, DISTRICT_Q, YN_EN)
    phases = cm.phase_candidates(view)
    old = {"type": "map_decision", "decision_id": "old", "key": json.dumps(
        {"protocol": cm.PROTOCOL, "step": "phases", "frame_sha256": "0" * 64, "question": conduct_ask.nz(DISTRICT_Q), "options": list(YN_EN),
         "candidates": sorted([c.id, c.text] for c in phases), "record_id": None}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
           "step": "phases", "status": "ADOPTED", "reason": "ADOPTED", "result": {"phases": ["P3", "P4"]}, "ask_ids": []}
    assert mp._key("phases", sess, phases, None) != old["key"]


# ---- review 2, must-fix 2: a derived statement over several phases leaves no pair out -------------------------------------

def test_a_chain_of_three_phases_says_the_order_of_every_pair():
    view, g = _graph(X04)
    claim, edges, rel = cm.order_statement(view, g, ["P1", "P2", "P3"])
    assert rel == "P1+P2<P3" and claim.id == "order:P1+P2<P3"
    n = {p.id: p.name for p in view.phases}
    for a, b in (("P1", "P2"), ("P1", "P3"), ("P2", "P3")):
        assert f"「{n[a]}」を終えてからでなければ「{n[b]}」には進めない" in claim.text, (a, b)
    assert "どちらが先とも決まっていない" not in claim.text
    assert [e.ref.id for e in edges] == ["phase_order:P1->P2", "phase_order:P2->P3"] and [r.id for r in claim.refs] == ["phase_order:P1->P2", "phase_order:P2->P3"]


def test_two_parallel_phases_among_several_are_stated_as_undecided():
    view, g = _graph(X02)                                    # P1 -> P2, P1 -> P3, P2 -> P4, P3 -> P4, P4 -> P5
    claim, edges, rel = cm.order_statement(view, g, ["P4", "P3", "P2"])
    n = {p.id: p.name for p in view.phases}
    assert rel == "P2+P3<P4"
    assert f"「{n['P2']}」と「{n['P3']}」はどちらが先とも決まっていない" in claim.text
    assert f"「{n['P2']}」を終えてからでなければ「{n['P4']}」には進めない" in claim.text
    assert f"「{n['P3']}」を終えてからでなければ「{n['P4']}」には進めない" in claim.text
    assert sorted(e.ref.id for e in edges) == ["phase_order:P2->P4", "phase_order:P3->P4"]


def test_the_options_of_a_three_phase_question_are_judged_against_a_statement_that_keeps_the_earlier_pair():
    q = "Which comes first: bin categories, log form, weekly report?"
    opts = ["Define the bin categories", "Build the drop-off log form", "Add the weekly weight report"]
    script = {"phases": ["P1", "P2", "P3"], "relations": {"order:P1+P2<P3": ["一致", "矛盾", "矛盾"]}, "records": ["order:ALL"], "decides": "決まる"}
    res, mp = ask_map(X04, q, opts, script)
    n = {p.id: p.name for p in M.view_of(X04).phases}
    claim = res["mapping"]["order"]["claim"]
    assert f"「{n['P1']}」を終えてからでなければ「{n['P2']}」には進めない" in claim           # the pair the previous statement left out
    prompts = [e["prompt"] for e in mp.ledger.entries() if e.get("type") == "map_ask" and e["step"] == "relations"]
    assert len(prompts) == 2 and all(claim in p for p in prompts)
    assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", opts[0], 0)
    assert [b["id"] for b in res["basis"]] == ["phase_order:P1->P2", "phase_order:P2->P3"]


@pytest.mark.parametrize("variant", [0, 1])
def test_the_phases_prompt_asks_the_closed_decides_in_both_wordings_and_shows_no_order_record(variant):
    view = M.view_of(X04)
    prompt = cm.build_phases_prompt(DISTRICT_Q, YN_EN, cm.phase_candidates(view), variant)
    assert '"決まる"' in prompt and '"決まらない"' in prompt and '{"phases": []}' in prompt
    assert "別の事業" in prompt or "だれの事業" in prompt                          # the other-subject case is named to the model
    for e in view.edges:                                                           # the model is shown phases, never an order line
        assert e.ref.text not in prompt
