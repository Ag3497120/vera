"""Unit tests of verantyx.conduct_map: candidates, prompts, the rule decision, the closed retry list, the mapper."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import w2g  # noqa: E402
from verantyx import conduct_ask as ca  # noqa: E402
from verantyx import conduct_map as cm  # noqa: E402
from verantyx.llm_choice import ChoiceLedger, ProviderReply  # noqa: E402


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


F1 = w2g("w01_shelfcheck")
F2 = w2g("w02_absence")


# ---------------------------------------------------------------------------------------------- candidates
def test_candidates_cover_the_content_records_and_carry_the_original_line():
    view = M.view_of(F1)
    cands = cm.all_candidates(view)
    kinds = [c.kind for c in cands]
    assert kinds.count(cm.K_ORDER) == 3 and kinds.count(cm.K_SCOPE) == 2 and kinds.count(cm.K_CONFIRM) == 1
    assert kinds.count(cm.K_CHOICE) == 2 and kinds.count(cm.K_DECISION) == 1 and kinds.count(cm.K_FORBIDDEN) == 1
    assert kinds.count(cm.K_PROTECTED) == 1 and kinds.count(cm.K_CRITERION) == 2 and kinds.count(cm.K_INVARIANT) == 1
    assert kinds.count(cm.K_ALLOW) == 2 and kinds.count(cm.K_ESCALATION) == 0
    by = {c.id: c for c in cands}
    assert len(by) == len(cands)                                                  # ids are unique
    assert by["D3"].ref.text == "D3: SCOPE | 郷土資料の点検 | in scope" and by["D3"].text == "SCOPE | 郷土資料の点検 | in scope"
    assert "phase_order:P1->P2" in by and by["phase_order:P1->P2"].text.startswith("「書架の区分を決める」を終えてから「点検画面を作る」に進む")
    assert "画面は書架の区分に沿って作る" in by["phase_order:P1->P2"].text
    assert by["C1"].text.endswith("（コマンドで検査する）") and by["C2"].text.endswith("（人が判定する）") and "command_exit" not in by["C1"].text
    for c in cands:                                                                # no internal id leaks into a display sentence
        assert not re.search(r"\b[DCIWP]\d+:|phase_order|forbidden_actions|protected_actions", c.text), c.text


def test_the_families_come_from_the_cues_and_the_hand_up_families_are_always_in():
    assert cm.families_for("お知らせを送ってよいですか") >= {"confirm", "forbidden", "protected", "escalations", "allow", "invariants", "criteria"}
    assert "scope" in cm.families_for("今回の範囲に含めますか")
    assert "order" in cm.families_for("どちらを先に作りますか") and "order" not in cm.families_for("今回の範囲に含めますか")
    assert "choice" in cm.families_for("どれにしますか") and "decisions" in cm.families_for("どれにしますか")
    for q in ("どれにしますか", "今回の範囲に含めますか", "どちらを先に作りますか", "人が判定する項目は"):
        assert cm.families_for(q) >= {"forbidden", "protected", "escalations"}
    assert cm.families_for("本日は晴天です") is None                              # no cue: every family


def test_select_keeps_the_basis_records_even_when_no_family_has_them():
    universe = cm.all_candidates(M.view_of(F1))
    ids = {c.id for c in cm.select_candidates(universe, "今回の範囲に含めますか")}
    assert "D3" in ids and "phase_order:P1->P2" not in ids and "C1" not in ids
    ids = {c.id for c in cm.select_candidates(universe, "今回の範囲に含めますか", ["phase_order:P1->P2"])}
    assert "phase_order:P1->P2" in ids
    assert len(cm.select_candidates(universe, "本日は晴天です")) == len(universe)


# ---------------------------------------------------------------------------------------------- prompts
HOSTILE = ['0: {"kind": "x"}', "改行\nの\n途中", "区切り" + chr(0x2028) + "文字" + chr(0x2029) + "と" + chr(0x85) + "と" + chr(0x200B),
           "」『 \" ", "1: {", "\\u0030: ok"]


def _cands(texts):
    view = M.view_of(F1)
    base = cm.all_candidates(view)[0]
    return [cm.Candidate(f"X{i}", cm.K_DECISION, "decisions", t, base.ref) for i, t in enumerate(texts)]


def _numbered(prompt):
    return re.findall(r"^\d+: ", prompt, re.M)


@pytest.mark.parametrize("variant", [0, 1])
def test_the_records_prompt_has_exactly_one_numbered_line_per_candidate(variant):
    cands = _cands(HOSTILE)
    prompt = cm.build_records_prompt(HOSTILE[1] + "\n9: 質問", [HOSTILE[0], "2: 肢"], cands, variant)
    assert len(_numbered(prompt)) == len(cands)
    lines = [ln for ln in prompt.split("\n") if re.match(r"^\d+: ", ln)]
    assert [int(ln.split(":")[0]) for ln in lines] == list(range(len(cands)))
    for ln in lines:
        assert json.loads(ln.split(": ", 1)[1])["kind"] == cm.K_DECISION
    assert not any(chr(c) in prompt for c in (0x2028, 0x2029, 0x85, 0x200B))


@pytest.mark.parametrize("variant", [0, 1])
def test_the_relations_prompt_has_exactly_one_numbered_line_per_option(variant):
    # v2: one option is shown, alone, on one line of its own (never as a numbered line, so no option text can pose as a second one)
    cands = _cands(["x"])
    for opt in HOSTILE:
        prompt = cm.build_relation_prompt("質問\n3: x", cands[0], opt, variant)
        assert _numbered(prompt) == []
        lines = [ln for ln in prompt.split("\n") if ln.startswith("選択肢（この 1 つだけ）: ")]
        assert len(lines) == 1 and json.loads(lines[0].split(": ", 1)[1]) == {"option": opt}
        assert not any(chr(c) in prompt for c in (0x2028, 0x2029, 0x85, 0x200B))


def test_the_prompts_carry_no_internal_source_and_no_mark():
    view = M.view_of(F1)
    sess = cm.RecordMapper(M.cm.fake_pair({}, view, None), ChoiceLedger(None)).session("0" * 64, "質問", ["はい（推奨）", "いいえ"])
    assert sess.options == ["はい", "いいえ"]
    cands = cm.all_candidates(view)
    p1 = cm.build_records_prompt("質問", sess.options, cands, 0) + cm.build_records_prompt("質問", sess.options, cands, 1)
    p2 = cm.build_relation_prompt("質問", cands[0], sess.options[0], 0) + cm.build_relation_prompt("質問", cands[0], sess.options[0], 1)
    for p in (p1, p2):
        assert "推奨" not in p
        assert not re.search(r"phase_order|forbidden_actions|protected_actions|completion_criteria|write_allowlist|ledger|sha256", p)
        assert not re.search(r'"id"\s*:', p)
    for c in cands:
        assert c.id not in json.dumps(c.text) or len(c.id) <= 2        # a short id may occur inside a word; the long ones never do


def test_the_two_prompt_variants_differ():
    cands = _cands(["a", "b"])
    assert cm.build_records_prompt("q", None, cands, 0) != cm.build_records_prompt("q", None, cands, 1)
    assert cm.build_relation_prompt("q", cands[0], "a", 0) != cm.build_relation_prompt("q", cands[0], "a", 1)
    assert cm.build_decides_prompt("q", ["x"], 0) != cm.build_decides_prompt("q", ["x"], 1)
    assert cm.build_phases_prompt("q", None, cands, 0) != cm.build_phases_prompt("q", None, cands, 1)


# ---------------------------------------------------------------------------------------------- the rule decision
def C(i, kind=cm.K_DECISION):
    base = cm.all_candidates(M.view_of(F1))[0]
    return cm.Candidate(i, kind, "x", f"text {i}", ca.Ref(i, "decisions", 1, f"{i}: text"))


OPTS = ["はい（推奨）", "いいえ", "どちらでもない"]


def test_decide_rule_1_no_record_is_a_silent_frame():
    out = cm.decide([], "決まる", {}, OPTS)
    assert (out.decision, out.reason, out.detail) == ("escalate", "FRAME_SILENT", "MAP_NONE")


def test_decide_rule_2_records_that_do_not_decide():
    out = cm.decide([C("a")], "決まらない", {"a": ["一致", "矛盾", "矛盾"]}, OPTS)
    assert (out.reason, out.detail) == ("FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE") and [r.id for r in out.basis] == ["a"]


@pytest.mark.parametrize("kind", [cm.K_PROTECTED, cm.K_ESCALATION])
def test_decide_rule_3_a_record_that_needs_a_human(kind):
    out = cm.decide([C("a"), C("p", kind)], "決まる", {}, OPTS)
    assert (out.reason, out.detail) == ("HUMAN_APPROVAL_REQUIRED", "MAPPED_PROTECTED")


def test_decide_rule_4_no_options():
    out = cm.decide([C("a")], "決まる", None, None)
    assert (out.reason, out.detail) == ("ANSWER_FORM_UNSUPPORTED", "MAPPING_NEEDS_OPTIONS")


def test_decide_rule_5_one_record_agrees_and_another_contradicts_the_same_option():
    out = cm.decide([C("a"), C("b")], "決まる", {"a": ["一致", "矛盾", "無関係"], "b": ["矛盾", "一致", "無関係"]}, OPTS)
    assert (out.reason, out.detail) == ("FRAME_CONFLICT", "MAPPED_RECORDS_DISAGREE")


def test_decide_rule_6_one_supported_option_is_answered_with_the_callers_text_and_the_records_as_basis():
    out = cm.decide([C("a")], "決まる", {"a": ["一致", "矛盾", "無関係"]}, OPTS)
    assert (out.decision, out.answer, out.index, out.derivation, out.resolvers, out.layer) == ("answer", "はい（推奨）", 0, "DIRECT", ("mapping",), "mapping")
    assert [r.id for r in out.basis] == ["a"]
    out = cm.decide([C("a"), C("b")], "決まる", {"a": ["矛盾", "一致", "無関係"], "b": ["無関係", "一致", "無関係"]}, OPTS)
    assert (out.answer, out.index, out.derivation) == ("いいえ", 1, "COMBINED") and [r.id for r in out.basis] == ["a", "b"]


def test_decide_rule_7_two_supported_options_are_a_tie():
    out = cm.decide([C("a"), C("b")], "決まる", {"a": ["一致", "無関係", "無関係"], "b": ["無関係", "一致", "無関係"]}, OPTS)
    assert (out.reason, out.detail) == ("FRAME_SILENT", "TIE") and out.answer is None


def test_decide_rule_8_nothing_supported():
    out = cm.decide([C("a")], "決まる", {"a": ["矛盾", "矛盾", "矛盾"]}, OPTS)
    assert (out.reason, out.detail) == ("NO_OPTION_ALLOWED", "MAPPED_NO_OPTION_AGREES")
    out = cm.decide([C("a")], "決まる", {"a": ["矛盾", "無関係", "矛盾"]}, OPTS)
    assert (out.reason, out.detail) == ("FRAME_SILENT", "MAPPED_NO_OPTION_RELATED")
    out = cm.decide([C("a"), C("b")], "決まる", {"a": ["矛盾", "無関係", "無関係"], "b": ["無関係", "矛盾", "矛盾"]}, OPTS)
    assert (out.reason, out.detail) == ("NO_OPTION_ALLOWED", "MAPPED_NO_OPTION_AGREES")


def test_decide_a_missing_relation_is_not_an_unrelated_option():
    out = cm.decide([C("a")], "決まる", {}, OPTS)
    assert (out.reason, out.detail) == ("FRAME_SILENT", "MAP_RELATIONS_MISSING")
    out = cm.decide([C("a")], "決まる", {"a": ["一致"]}, OPTS)
    assert out.decision == "escalate"


def test_decide_uses_no_priority_and_no_order():
    # the same two supported options in either order give the same typed result: no winner by position
    a = cm.decide([C("a"), C("b")], "決まる", {"a": ["一致", "無関係", "無関係"], "b": ["無関係", "一致", "無関係"]}, OPTS)
    b = cm.decide([C("b"), C("a")], "決まる", {"a": ["一致", "無関係", "無関係"], "b": ["無関係", "一致", "無関係"]}, OPTS)
    assert (a.reason, a.detail) == (b.reason, b.detail) == ("FRAME_SILENT", "TIE")


# ---------------------------------------------------------------------------------------------- the closed retry list
@pytest.mark.parametrize("reason,detail,yes", [
    ("VOCAB_UNMAPPED", "VOCAB_LLM_OFF", True), ("VOCAB_UNMAPPED", "NO_ROLE", True), ("VOCAB_UNMAPPED", "LLM_FAILED:TIMEOUT", True),
    ("VOCAB_UNMAPPED", "LLM_CHOICE_IS_NARROWER_OR_WIDER", True), ("VOCAB_UNMAPPED", "AMBIGUOUS_TERM", True),
    ("FRAME_SILENT", "NO_RECORD_DECIDES", True), ("FRAME_SILENT", "NO_RECORD_DECIDES_AFTER_MAPPING", True),
    ("QUESTION_UNREADABLE", "PREDICATE_UNREADABLE", True), ("QUESTION_UNREADABLE", "ORDER_PHASES_UNCLEAR", True),
    ("QUESTION_UNREADABLE", "ORDER_CLAUSE_UNCLEAR", True), ("QUESTION_UNREADABLE", "TARGET_PHASE_UNCLEAR", True),
    ("FRAME_SILENT", "UNORDERED", False), ("FRAME_SILENT", "TIE", False), ("FRAME_SILENT", "NO_STATE", False),
    ("FRAME_SILENT", "OUTSIDE_ALLOWLIST", False), ("FRAME_SILENT", "TERM_IN_WIDER_PHRASE", False),
    ("FRAME_SILENT", "CONTEXT_SENTENCE_UNREAD", False), ("FRAME_SILENT", "PERMISSION_FOR_ANOTHER_OPERATION", False),
    ("QUESTION_UNREADABLE", "NEGATED_QUESTION", False), ("QUESTION_UNREADABLE", "MULTIPLE_QUESTIONS", False),
    ("QUESTION_UNREADABLE", "REQUIREMENT_OF_PERMISSION", False), ("QUESTION_UNREADABLE", "RECORD_STANCE_UNREADABLE", False),
    ("QUESTION_UNREADABLE", "BAD_ARGUMENTS", False), ("HUMAN_APPROVAL_REQUIRED", "BUILTIN_PROTECTED", False),
    ("FRAME_CONFLICT", "RESOLVERS_DISAGREE", False), ("OUT_OF_RANGE", "STATE_OR_REQUEST_QUESTION", False),
    ("NO_OPTION_ALLOWED", "X", False), ("ANSWER_FORM_UNSUPPORTED", "X", False), ("FRAME_UNUSABLE", "X", False),
    ("INTERNAL_ERROR", "X", False), ("MAPPING_UNSETTLED", "STEP1_DISAGREE", False), (None, None, False),
])
def test_the_retry_list_is_closed(reason, detail, yes):
    assert cm.retry_allowed(reason, detail) is yes


# ---------------------------------------------------------------------------------------------- the mapper
def _sess(mp, options=("はい", "いいえ")):
    return mp.session("a" * 64, "地元の歴史に関する資料も、確認する本に入りますか？", list(options) if options else None)


def test_the_two_orders_differ_even_when_the_order_source_repeats_itself():
    mp = M.mapper_for(F1, ["はい", "いいえ"], {"records": ["D3"], "decides": "決まる"}, order_source=M.fixed_order)
    cands = cm.all_candidates(M.view_of(F1))
    r = mp.step1(_sess(mp), cands)
    rows = [e for e in mp.ledger.entries() if e["type"] == "map_ask"]
    assert r.status == "ADOPTED" and rows[0]["order"] != rows[1]["order"]
    assert sorted(rows[0]["order"]) == sorted(rows[1]["order"]) == list(range(len(cands)))
    assert rows[0]["variant"] == 0 and rows[1]["variant"] == 1 and rows[0]["prompt"] != rows[1]["prompt"]
    assert rows[0]["parsed"]["records"] == rows[1]["parsed"]["records"] == ["D3"]            # the original numbers, not the shown ones


def test_the_two_asks_run_at_the_same_time():
    barrier = threading.Barrier(2, timeout=10)

    class Together:
        name = "together"

        def ask(self, prompt):
            barrier.wait()                                  # both must be in flight, or this raises and the ask fails
            return ProviderReply.success("なし", provider="together")
    mp = M.mapper_for(F1, None, providers=(Together(), Together()))
    r = mp.step1(_sess(mp, None), cm.all_candidates(M.view_of(F1)))
    assert r.status == "NONE" and r.reason == "NONE_SELECTED"


def test_the_two_asks_use_the_two_providers_in_order():
    p1, p2 = M.TextProvider("なし"), M.TextProvider("なし")
    mp = M.mapper_for(F1, None, providers=(p1, p2))
    mp.step1(_sess(mp, None), cm.all_candidates(M.view_of(F1)))
    assert (p1.calls, p2.calls) == (1, 1) and p1.prompts[0] != p2.prompts[0]


def test_the_ledger_rows_are_in_a_fixed_order_and_use_only_the_three_types():
    script = {"records": ["D2", "D3"], "decides": "決まる", "relations": {"D2": ["矛盾", "一致"], "D3": ["一致", "矛盾"]}}
    mp = M.mapper_for(F1, ["はい", "いいえ"], script)
    cands = cm.all_candidates(M.view_of(F1))
    s = _sess(mp)
    r1 = mp.step1(s, cands)
    recs = [c for c in cands if c.id in r1.records]
    d = mp.decides_step(s, [(c.id, c.kind, c.ref.text) for c in recs])
    assert d.status == "ADOPTED" and d.decides == "決まる"
    results = mp.relation_step(s, [(c, i) for c in recs for i in (0, 1)])
    assert [x.relation for x in results] == ["矛盾", "一致", "一致", "矛盾"]
    rows = mp.ledger.entries()
    assert {e["type"] for e in rows} == {"map_ask", "map_decision"}
    seq = [(e["type"], e.get("step"), e.get("record_id"), e.get("option_index"), e.get("ask_index")) for e in rows]
    # the asks of a round are written together (in problem order, slot 0 then slot 1), the decisions after them, in problem order
    assert seq == [("map_ask", "records", None, None, 0), ("map_ask", "records", None, None, 1), ("map_decision", "records", None, None, None),
                   ("map_ask", "decides", None, None, 0), ("map_ask", "decides", None, None, 1), ("map_decision", "decides", None, None, None),
                   ("map_ask", "relation", "D2", 0, 0), ("map_ask", "relation", "D2", 0, 1),
                   ("map_ask", "relation", "D2", 1, 0), ("map_ask", "relation", "D2", 1, 1),
                   ("map_ask", "relation", "D3", 0, 0), ("map_ask", "relation", "D3", 0, 1),
                   ("map_ask", "relation", "D3", 1, 0), ("map_ask", "relation", "D3", 1, 1),
                   ("map_decision", "relation", "D2", None, None), ("map_decision", "relation", "D2", None, None),
                   ("map_decision", "relation", "D3", None, None), ("map_decision", "relation", "D3", None, None)]
    assert s.used == 2 + 2 + 8 and s.retries == 0


def test_a_step_that_would_pass_the_ask_cap_is_refused_and_asks_nothing():
    mp = M.mapper_for(F1, ["はい", "いいえ"], {"records": []}, max_asks=3)
    s = _sess(mp)
    s.used = 2
    r = mp.step1(s, cm.all_candidates(M.view_of(F1)))
    assert (r.status, r.reason) == ("REFUSED", "ASK_BUDGET")
    assert [e["type"] for e in mp.ledger.entries()] == ["map_decision"] and s.used == 2


def test_the_scripted_provider_answers_an_unknown_record_with_an_invalid_reply():
    mp = M.mapper_for(F1, ["はい", "いいえ"], {"records": ["D3"], "decides": "決まる", "relations": {"D2": ["一致", "矛盾"]}})
    cands = cm.all_candidates(M.view_of(F1))
    s = _sess(mp)
    mp.step1(s, cands)
    r = mp.relation_step(s, [(c, 0) for c in cands if c.id == "D3"])[0]
    assert r.status == "ABSTAINED" and r.reason == "INVALID_ANSWER"      # no relations scripted for D3: invalid (also when asked again), never "unrelated"
    assert r.retries == 2
    mp2 = M.mapper_for(F1, None, {"records": ["no-such-record"], "decides": "決まる"})
    assert mp2.step1(_sess(mp2, None), cands).reason == "INVALID_ANSWER"


def test_a_ledger_that_is_broken_refuses_before_any_ask(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ChoiceLedger(path)
    p = M.TextProvider("なし")
    mp = M.mapper_for(F1, None, providers=(p, p), ledger=ledger)
    mp.step1(_sess(mp, None), cm.all_candidates(M.view_of(F1)))
    assert p.calls == 2
    path.write_text(path.read_text(encoding="utf-8")[:-5] + "x\n", encoding="utf-8")
    r = mp.step1(mp.session("b" * 64, "別の質問", None), cm.all_candidates(M.view_of(F1)))
    assert (r.status, r.reason) == ("REFUSED", "LEDGER_INTEGRITY") and p.calls == 2


def test_the_real_mapper_builds_its_providers_without_starting_a_process(monkeypatch):
    mp = cm.build_real_mapper("codex", "claude", None, 8)
    assert [type(p).__name__ for p in mp.providers] == ["CodexProvider", "ClaudeProvider"]
    assert (mp.providers[0].model, mp.providers[0].effort) == ("gpt-6-luna", "low")
    assert (mp.providers[1].model, mp.providers[1].effort) == ("claude-sonnet-5-5", "low")
    mp = cm.build_real_mapper("claude", None, None, 6)
    assert [type(p).__name__ for p in mp.providers] == ["ClaudeProvider", "ClaudeProvider"] and mp.providers[0] is not mp.providers[1]
    assert mp.max_asks == 6
    with pytest.raises(ValueError):
        cm.build_real_mapper("fake", None, None)
