"""W2-h: typed routing records and the router (docs/AGENT_ROUTING.md).  Acceptance numbers are in the names."""
from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_agent_routing_support import (Spec, agent, default, dict_table, dsl_table, fake_chooser, precedence, renamed,
                                        rule, standard_spec, tie_spec)
from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards: this tree, no real agent)
from test_conduct_entry_support import ROOT

from verantyx import agent_routing as ar


def make(spec: Spec):
    return dict_table(spec)


def ask(table, role="implement", kind="feature", size="small", *, used=None, in_use=None, chooser=None, job="job1"):
    request = ar.RoutingRequest(job, role, kind, size, used_lineages=used or {}, in_use=in_use or {})
    return ar.route(table, request, chooser_factory=(lambda: chooser) if chooser is not None else None)


def code_of(spec: Spec) -> str:
    with pytest.raises(ar.RoutingRecordError) as info:
        make(spec)
    return info.value.code


# ======================================================================== R0: the records are independent of the DSL
def test_R0_the_record_module_does_not_import_the_dsl_or_the_conductor():
    code = ("import sys, verantyx.agent_routing as r; "
            "print(json.dumps([m for m in ('verantyx.project_frame','verantyx.conductor_run','verantyx.cli') "
            "if m in sys.modules]), json.dumps(list(r.BASIS_KINDS)))")
    done = subprocess.run([sys.executable, "-c", "import json; " + code], capture_output=True, text=True,
                          env={"PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    loaded, kinds = done.stdout.split(" ", 1)
    assert json.loads(loaded) == [] and json.loads(kinds) == ["declared_dsl", "declared_text"]


def test_R0_the_source_of_the_record_module_names_no_dsl_module():
    text = (ROOT / "verantyx" / "agent_routing.py").read_text(encoding="utf-8")
    for name in ("project_frame", "conductor_run", "verantyx.cli", "from .cli"):
        assert f"import {name}" not in text and f"from . import {name}" not in text and f"from .{name} import" not in text


@pytest.mark.parametrize("request_args", [
    dict(role="implement", kind="feature", size="small"),
    dict(role="implement", kind="small_fix", size="large"),
    dict(role="verify", kind="verification", size="medium", used={"implement": ("openai",)}),
    dict(role="review", kind="review", size="small"),
    dict(role="verify", kind="verification", size="small", used={"implement": ("anthropic",)}),
    dict(role="generate", kind="bulk_generation", size="large"),
])
def test_R0_the_dsl_producer_and_the_dictionary_producer_give_the_same_decision(request_args):
    spec = standard_spec()
    from_dsl, from_dict = dsl_table(spec), dict_table(spec)
    first, second = ask(from_dsl, **request_args), ask(from_dict, **request_args)
    assert first.decided and first.essence() == second.essence()
    assert first.agent_basis.kind == "declared_dsl" and first.agent_basis.line is not None
    assert second.agent_basis.kind == "declared_text" and second.agent_basis.witnesses
    assert all(a.basis.kind == "declared_dsl" for a in from_dsl.agents)
    assert all(a.basis.kind == "declared_text" for a in from_dict.agents)


@pytest.mark.parametrize("which", ["reverse", "rotate"])
@pytest.mark.parametrize("spec_factory", [standard_spec, lambda: tie_spec(with_precedence=True),
                                          lambda: tie_spec(chain=True), tie_spec])
def test_R0_the_order_of_the_rows_never_changes_the_decision(which, spec_factory):
    spec = spec_factory()
    other = spec.permuted(which)
    assert [a["id"] for a in other.agents] != [a["id"] for a in spec.agents]
    for build in (dict_table, dsl_table):
        for role, kind, used in (("implement", "feature", None), ("verify", "verification", {"implement": ("openai",)}),
                                 ("review", "review", None), ("implement", "small_fix", None)):
            assert ask(build(spec), role, kind, used=used).essence() == ask(build(other), role, kind, used=used).essence()
            assert ask(build(spec), role, kind, used=used).ledger_fields()["decided_by"] == \
                   ask(build(other), role, kind, used=used).ledger_fields()["decided_by"]


def test_R0_a_basis_needs_a_line_or_a_sentence():
    with pytest.raises(ValueError):
        ar.Basis("declared_text", "x")
    with pytest.raises(ValueError):
        ar.Basis.text("x", "   ")
    with pytest.raises(ValueError):
        ar.Basis("declared_dsl", "x")
    with pytest.raises(ValueError):
        ar.Basis("measured", "x", 1)
    assert ar.Basis.text("x", "Fast reviews, said the human").kind == "declared_text"
    with pytest.raises(ValueError):
        ar.Basis.text("x", None)


def test_R0_the_dictionary_producer_refuses_a_record_without_the_sentence_it_came_from():
    spec = standard_spec()
    del spec.agents[0]["witness"]
    with pytest.raises(ValueError):
        dict_table(spec)


# ======================================================================== R1: the closed vocabulary and the checks of meaning
def test_R1_a_kind_outside_the_vocabulary_is_UNKNOWN_KIND_whether_an_agent_or_a_rule_names_it():
    spec = standard_spec()
    spec.agents[0]["kinds"].append("interpretive_dance")
    assert code_of(spec) == "UNKNOWN_KIND"
    spec = standard_spec()
    spec.rules[0]["when"]["kind"] = "interpretive_dance"
    assert code_of(spec) == "UNKNOWN_KIND"


def test_R1_an_unknown_adapter_is_UNKNOWN_ADAPTER():
    spec = standard_spec()
    spec.agents[0]["adapter"] = "gemini"
    assert code_of(spec) == "UNKNOWN_ADAPTER"


def test_R1_the_same_agent_id_twice_is_DUPLICATE_AGENT_ID():
    spec = standard_spec()
    spec.agents.append(agent("CodexImpl", roles=("implement",)))
    assert code_of(spec) == "DUPLICATE_AGENT_ID"


def test_R1_a_role_without_a_DEFAULT_row_is_MISSING_ROLE_DEFAULT():
    spec = standard_spec()
    spec.rules = [r for r in spec.rules if not (r["id"] == "DEFAULT" and r["when"]["role"] == "generate")]
    assert code_of(spec) == "MISSING_ROLE_DEFAULT"
    spec = standard_spec()   # a role named only by a rule needs one as well
    spec.rules.append(rule("READ_ONLY", {"role": "read"}, ["CodexBulk"]))
    spec.agents[5]["roles"].append("read")
    spec.agents[5]["kinds"].append("read_large_file")
    assert code_of(spec) == "MISSING_ROLE_DEFAULT"


def test_R1_independent_of_that_loops_back_is_INDEPENDENCE_CYCLE_in_three_forms():
    # (i) two roles each independent of the other
    spec = standard_spec()
    spec.rules.append(rule("REVIEW_IND", {"role": "review", "independent_of": "verify"}, ["ClaudeReview"]))
    spec.rules.append(rule("VERIFY_IND", {"role": "verify", "independent_of": "review"}, ["ClaudeVerify"]))
    assert code_of(spec) == "INDEPENDENCE_CYCLE"
    # (ii) implement independent of verify, while verify is independent of implement by default
    spec = standard_spec()
    spec.rules.append(rule("IMPL_IND", {"role": "implement", "independent_of": "verify"}, ["CodexImpl"]))
    assert code_of(spec) == "INDEPENDENCE_CYCLE"
    # (iii) a role independent of itself
    spec = standard_spec()
    spec.rules.append(rule("SELF", {"role": "review", "independent_of": "review"}, ["ClaudeReview"]))
    assert code_of(spec) == "INDEPENDENCE_CYCLE"


def test_R1_the_five_rejections_of_the_ticket_are_five_different_codes():
    codes = set()
    for edit in ("kind", "adapter", "dup", "default", "cycle"):
        spec = standard_spec()
        if edit == "kind":
            spec.agents[0]["kinds"].append("nope")
        elif edit == "adapter":
            spec.agents[0]["adapter"] = "nope"
        elif edit == "dup":
            spec.agents.append(agent("CodexImpl"))
        elif edit == "default":
            spec.rules = [r for r in spec.rules if r["id"] != "DEFAULT" or r["when"]["role"] != "review"]
        else:
            spec.rules.append(rule("SELF", {"role": "review", "independent_of": "review"}, ["ClaudeReview"]))
        codes.add(code_of(spec))
    assert codes == {"UNKNOWN_KIND", "UNKNOWN_ADAPTER", "DUPLICATE_AGENT_ID", "MISSING_ROLE_DEFAULT", "INDEPENDENCE_CYCLE"}


def test_R1_the_other_checks_of_meaning_each_have_their_own_code():
    def edited(change):
        spec = standard_spec()
        change(spec)
        return code_of(spec)

    assert edited(lambda s: s.rules.append(rule("IMPL_FEATURE", {"role": "implement"}, ["CodexImpl"]))) == "DUPLICATE_RULE_ID"
    assert edited(lambda s: s.rules.append(default("implement", ["CodexImpl"]))) == "DUPLICATE_FALLBACK"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "implement"}, ["Nobody"]))) == "UNKNOWN_AGENT_REF"
    # W2-h round 4 (F9): a rule with no role= is legal, so the "no role=" case is now the fallback's: a fallback names
    # its role.  (The legal form of the old line is asserted by test_R0_role_a_rule_with_no_role_is_a_legal_rule.)
    assert edited(lambda s: s.rules.append({**rule("X1", {"kind": "feature"}, ["CodexImpl"]),
                                            "fallback": True})) == "MISSING_ROLE_CONDITION"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "implement", "size": "huge"}, ["CodexImpl"]))) == "UNKNOWN_SIZE"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "dancer"}, ["CodexImpl"]))) == "UNKNOWN_ROLE"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "implement", "colour": "red"}, ["CodexImpl"]))) == "BAD_CONDITION"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "implement", "independent_of": "none"}, ["CodexImpl"]))) == "BAD_CONDITION"
    assert edited(lambda s: s.rules.append({**rule("FB", {"role": "review", "kind": "review"}, ["ClaudeReview"]),
                                            "fallback": True})) == "BAD_CONDITION"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "implement"}, ["ClaudeVerify"]))) == "RULE_AGENT_MISMATCH"
    assert edited(lambda s: s.rules.append(rule("X1", {"role": "implement", "kind": "attack"}, ["CodexImpl"]))) == "RULE_AGENT_MISMATCH"
    assert edited(lambda s: s.agents[0].update(concurrency=0)) == "BAD_VALUE"
    assert edited(lambda s: s.agents[0].update(note="a long sentence about speed")) == "BAD_VALUE"
    assert edited(lambda s: s.agents[0].update(model="bad model; rm")) == "BAD_VALUE"
    assert edited(lambda s: s.agents[0].update(roles=["dancer"])) == "UNKNOWN_ROLE"
    assert edited(lambda s: s.precedence.append(precedence("P1", "IMPL_FEATURE", "Ghost"))) == "UNKNOWN_RULE_REF"
    assert edited(lambda s: s.precedence.append(precedence("P1", "DEFAULT", "IMPL_FEATURE"))) == "PRECEDENCE_ON_DEFAULT"
    assert edited(lambda s: s.precedence.extend([precedence("P1", "IMPL_FEATURE", "REVIEW_ANY"),
                                                 precedence("P1", "REVIEW_ANY", "VERIFY_OTHER")])) == "DUPLICATE_PRECEDENCE"
    assert edited(lambda s: s.precedence.extend([precedence("P1", "IMPL_FEATURE", "REVIEW_ANY"),
                                                 precedence("P2", "IMPL_FEATURE", "REVIEW_ANY")])) == "DUPLICATE_PRECEDENCE"
    assert edited(lambda s: s.precedence.extend([precedence("P1", "IMPL_FEATURE", "REVIEW_ANY"),
                                                 precedence("P2", "REVIEW_ANY", "VERIFY_OTHER"),
                                                 precedence("P3", "VERIFY_OTHER", "IMPL_FEATURE")])) == "PRECEDENCE_CYCLE"
    assert edited(lambda s: s.precedence.append(precedence("P1", "IMPL_FEATURE", "IMPL_FEATURE"))) == "PRECEDENCE_CYCLE"


def test_R1_an_empty_table_is_EMPTY_TABLE_and_the_error_code_set_is_closed():
    with pytest.raises(ar.RoutingRecordError) as info:
        ar.build_routing_table([], [])
    assert info.value.code == "EMPTY_TABLE"
    with pytest.raises(ValueError):
        ar.RoutingRecordError("SOMETHING_ELSE", "x")
    assert set(ar.RECORD_ERRORS).isdisjoint(ar.DSL_ERRORS)


def test_R1_a_request_outside_the_vocabulary_is_a_caller_error_not_a_decision():
    for args in (("j", "dancer", "feature", "small"), ("j", "implement", "dancing", "small"),
                 ("j", "implement", "feature", "huge"), ("j", "implement", "feature", None), ("", "implement", "feature", "small")):
        with pytest.raises(ValueError):
            ar.RoutingRequest(*args)


# ======================================================================== R2: the four stages, each in its own test
def test_R2_stage_1_a_matching_rule_decides_by_its_own_id():
    decision = ask(make(standard_spec()), "implement", "feature")
    assert (decision.agent_id, decision.stage, decision.decided_by) == ("CodexImpl", "rule", "rule:IMPL_FEATURE")
    assert decision.matched_rules == ("IMPL_FEATURE",) and decision.excluded == () and decision.undecided_reason is None


def test_R2_stage_1_the_default_row_is_used_only_when_no_other_rule_has_a_head():
    table = make(standard_spec())
    decision = ask(table, "implement", "small_fix")           # no rule names small_fix, so DEFAULT answers
    assert (decision.agent_id, decision.decided_by) == ("CodexImpl", "rule:DEFAULT")
    assert decision.matched_rules == ("DEFAULT",)
    decision = ask(table, "implement", "feature")              # IMPL_FEATURE has a head, DEFAULT is not even consulted
    assert "DEFAULT" not in decision.matched_rules


def test_R2_stage_1_rules_with_the_same_head_do_not_disagree():
    spec = standard_spec()
    spec.rules.append(rule("IMPL_SMALL_SAME", {"role": "implement", "size": "small"}, ["CodexImpl"]))
    decision = ask(make(spec), "implement", "feature", "small")
    assert decision.stage == "rule" and decision.decided_by == "rule:IMPL_FEATURE,IMPL_SMALL_SAME"


def test_R2_stage_2_precedence_settles_two_rules_with_different_heads():
    table = make(tie_spec(with_precedence=True))
    decision = ask(table, "implement", "feature", "small")
    assert (decision.agent_id, decision.stage, decision.decided_by) == ("CodexImpl", "precedence", "precedence")
    assert decision.precedence_used == ("P1",) and set(decision.candidates) == {"CodexImpl", "ClaudeImpl"}


def test_R2_stage_2_precedence_is_read_transitively():
    decision = ask(make(tie_spec(chain=True)), "implement", "feature", "small")
    assert (decision.agent_id, decision.stage) == ("CodexImpl", "precedence")
    assert decision.precedence_used == ("P1", "P2")


def test_R2_stage_2_the_lower_rule_wins_when_the_human_ordered_it_so():
    spec = tie_spec()
    spec.precedence.append(precedence("P1", "IMPL_SMALL", "IMPL_FEATURE"))
    decision = ask(make(spec), "implement", "feature", "small")
    assert (decision.agent_id, decision.stage) == ("ClaudeImpl", "precedence")


def test_R2_stage_3_two_asks_that_agree_decide_by_a_testimony_with_its_id():
    chooser, prompts = fake_chooser(["ClaudeImpl"])
    decision = ask(make(tie_spec()), "implement", "feature", "small", chooser=chooser)
    assert len(prompts) == 2                                   # both asks were really put
    assert (decision.agent_id, decision.stage) == ("ClaudeImpl", "llm_testimony")
    assert decision.decided_by == "llm_testimony:" + decision.testimony["decision_id"]
    assert decision.testimony["status"] == "ADOPTED" and decision.testimony["cached"] is False
    assert len(decision.testimony["ask_ids"]) == 2 and set(decision.testimony["asked"]) == {"CodexImpl", "ClaudeImpl"}
    assert decision.ledger_fields()["testimony"]["decision_id"] == decision.testimony["decision_id"]


def test_R2_stage_3_the_chooser_is_only_asked_about_the_heads_the_precedence_left_standing():
    spec = tie_spec()
    spec.agents.append(agent("GeminiImpl", adapter="claude", lineage="google", roles=("implement",)))
    spec.rules.append(rule("IMPL_LOW", {"role": "implement", "kind": "feature", "size": "small"}, ["GeminiImpl"]))
    spec.rules.append(rule("IMPL_LOWER", {"role": "implement", "size": "small", "kind": "feature"}, ["ClaudeImpl"]))
    spec.precedence.append(precedence("P1", "IMPL_FEATURE", "IMPL_LOW"))   # IMPL_LOW is outranked, the others are not
    chooser, prompts = fake_chooser(["CodexImpl"])
    decision = ask(make(spec), "implement", "feature", "small", chooser=chooser)
    assert set(decision.testimony["asked"]) == {"CodexImpl", "ClaudeImpl"} and decision.agent_id == "CodexImpl"
    assert decision.precedence_used == ("P1",) and not any("GeminiImpl" in p for p in prompts)


def test_R2_stage_3_two_asks_that_disagree_are_not_a_decision():
    chooser, prompts = fake_chooser(["CodexImpl", "ClaudeImpl"])   # the first ask says one, the second the other
    decision = ask(make(tie_spec()), "implement", "feature", "small", chooser=chooser)
    assert len(prompts) == 2
    assert (decision.agent_id, decision.stage, decision.decided_by) == (None, "NONE", "NONE")
    assert decision.undecided_reason == "TESTIMONY_ABSTAINED" and decision.testimony["status"] == "ABSTAINED"


def test_R2_stage_3_an_answer_that_names_nobody_listed_is_not_a_decision():
    chooser, _ = fake_chooser(["GhostAgent"])                       # the fake names nobody that was listed: null
    decision = ask(make(tie_spec()), "implement", "feature", "small", chooser=chooser)
    assert decision.agent_id is None and decision.undecided_reason == "TESTIMONY_ABSTAINED"


def test_R2_stage_3_a_chooser_that_raises_or_a_refusal_are_typed_not_swallowed():
    class Boom:
        def choose(self, *a, **k):
            raise RuntimeError("provider exploded")

    decision = ask(make(tie_spec()), "implement", "feature", "small", chooser=Boom())
    assert decision.undecided_reason == "TESTIMONY_FAILED" and decision.testimony["detail"] == "RuntimeError"

    class Refuse:
        def choose(self, word, candidates, question=""):
            from verantyx.llm_choice import ChoiceDecision
            return ChoiceDecision("REFUSED", "TOO_MANY_CANDIDATES", decision_id="d1")

    assert ask(make(tie_spec()), "implement", "feature", "small", chooser=Refuse()).undecided_reason == "TESTIMONY_REFUSED"

    class Outside:
        def choose(self, word, candidates, question=""):
            from verantyx.llm_choice import ChoiceDecision
            return ChoiceDecision("ADOPTED", "ADOPTED", "ClaudeVerify", decision_id="d2")

    assert ask(make(tie_spec()), "implement", "feature", "small", chooser=Outside()).undecided_reason == "TESTIMONY_OUT_OF_SET"

    class Failed:
        def choose(self, word, candidates, question=""):
            from verantyx.llm_choice import ChoiceDecision
            return ChoiceDecision("FAILED", "provider", decision_id="d3", failure="TIMEOUT")

    assert ask(make(tie_spec()), "implement", "feature", "small", chooser=Failed()).undecided_reason == "TESTIMONY_FAILED"


def test_R2_stage_4_without_a_chooser_a_tie_stops_as_a_typed_none_and_no_row_order_wins():
    spec = tie_spec()
    outcomes = set()
    for variant in (spec, spec.permuted("reverse"), spec.permuted("rotate")):
        for build in (dict_table, dsl_table):
            decision = ask(build(variant), "implement", "feature", "small")
            assert (decision.agent_id, decision.stage, decision.decided_by) == (None, "NONE", "NONE")
            outcomes.add((decision.undecided_reason, decision.candidates))
    assert outcomes == {("TESTIMONY_UNAVAILABLE", ("ClaudeImpl", "CodexImpl"))}
    assert ask(make(spec), "implement", "feature", "small", chooser=None).testimony is None
    none_factory = ar.route(make(spec), ar.RoutingRequest("j", "implement", "feature", "small"), chooser_factory=lambda: None)
    assert none_factory.undecided_reason == "TESTIMONY_UNAVAILABLE"


def test_R2_a_role_the_table_does_not_use_is_ROLE_NOT_ROUTABLE_and_no_candidates_is_a_different_type():
    table = make(standard_spec())
    assert ask(table, "read", "read_large_file").undecided_reason == "ROLE_NOT_ROUTABLE"
    nothing = ask(table, "implement", "attack")                    # CodexImpl does not declare kind attack
    assert nothing.undecided_reason == "NO_VIABLE_CANDIDATE"
    assert nothing.excluded and {e.reason for e in nothing.excluded} == {"KIND_NOT_DECLARED"}


def test_R2_the_undecided_types_are_all_distinct_and_all_reachable():
    assert len(set(ar.UNDECIDED_REASONS)) == len(ar.UNDECIDED_REASONS) == 7
    seen = {ask(make(standard_spec()), "read", "read_large_file").undecided_reason,
            ask(make(standard_spec()), "implement", "attack").undecided_reason,
            ask(make(tie_spec())).undecided_reason}
    assert seen == {"ROLE_NOT_ROUTABLE", "NO_VIABLE_CANDIDATE", "TESTIMONY_UNAVAILABLE"}


def test_R2_a_repeated_question_is_answered_from_the_choice_ledger_and_says_so():
    chooser, prompts = fake_chooser(["ClaudeImpl"])
    table = make(tie_spec())
    first = ask(table, "implement", "feature", "small", chooser=chooser, job="a")
    second = ask(table, "implement", "feature", "small", chooser=chooser, job="b")
    assert len(prompts) == 2 and first.testimony["cached"] is False and second.testimony["cached"] is True
    assert second.agent_id == "ClaudeImpl" and second.testimony["reuse_decision_id"]


# ======================================================================== R3: independence of the verifier
def verify_spec(prefer, *, waive: bool = False):
    spec = standard_spec()
    spec.rules = [r for r in spec.rules if r["id"] != "VERIFY_OTHER" and not (r["id"] == "DEFAULT" and r["when"]["role"] == "verify")]
    when = {"role": "verify", "independent_of": "none"} if waive else {"role": "verify"}
    spec.rules.append(rule("VERIFY_RULE", when, prefer))
    spec.rules.append(default("verify", list(prefer)))
    return spec


def test_R3_a_verifier_of_the_implementers_lineage_is_excluded_with_its_reason_and_the_next_one_is_used():
    decision = ask(make(verify_spec(["CodexVerify", "ClaudeVerify"])), "verify", "verification", used={"implement": ("openai",)})
    assert decision.agent_id == "ClaudeVerify" and decision.decided_by == "rule:VERIFY_RULE"
    gone = [e for e in decision.excluded if e.agent_id == "CodexVerify"]
    assert [(e.rule_id, e.reason) for e in gone] == [("VERIFY_RULE", "SAME_LINEAGE")]
    assert "openai" in gone[0].detail and decision.independence == {"implement": "distinct_lineage"}
    fields = decision.ledger_fields()
    assert {"agent_id": "CodexVerify", "rule_id": "VERIFY_RULE", "reason": "SAME_LINEAGE",
            "detail": gone[0].detail} in fields["excluded"]


def test_R3_with_no_verifier_of_another_lineage_the_job_stops_as_a_typed_none():
    decision = ask(make(verify_spec(["CodexVerify"])), "verify", "verification", used={"implement": ("openai",)})
    assert decision.agent_id is None and decision.undecided_reason == "NO_VIABLE_CANDIDATE" and decision.stage == "NONE"
    assert {e.reason for e in decision.excluded} == {"SAME_LINEAGE"} and {e.rule_id for e in decision.excluded} == {"VERIFY_RULE", "DEFAULT"}


def test_R3_only_an_explicit_independent_of_none_lets_the_same_lineage_through_and_the_record_says_so():
    decision = ask(make(verify_spec(["CodexVerify"], waive=True)), "verify", "verification", used={"implement": ("openai",)})
    assert decision.agent_id == "CodexVerify" and decision.decided_by == "rule:VERIFY_RULE"
    assert decision.independence == {"implement": "waived_by:rule:VERIFY_RULE"}
    assert decision.ledger_fields()["independence"] == {"implement": "waived_by:rule:VERIFY_RULE"}


def test_R3_the_default_row_for_verify_is_independent_too_and_the_waiver_is_per_rule():
    spec = verify_spec(["CodexVerify"], waive=True)
    spec.rules = [r for r in spec.rules if r["id"] != "DEFAULT" or r["when"]["role"] != "verify"]
    spec.rules.append(default("verify", ["CodexVerify"]))
    decision = ask(make(spec), "verify", "verification", used={"implement": ("openai",)})
    assert decision.agent_id == "CodexVerify"                      # the waiving rule decides, DEFAULT is not consulted
    decision = ask(make(spec), "verify", "small_fix", used={"implement": ("openai",)})   # a kind the rule's agent lacks
    assert decision.agent_id is None


def test_R3_independent_of_none_outside_the_verify_role_is_rejected():
    spec = standard_spec()
    spec.rules.append(rule("X1", {"role": "review", "independent_of": "none"}, ["ClaudeReview"]))
    assert code_of(spec) == "BAD_CONDITION"


def test_J7_independent_of_a_role_not_yet_used_is_neither_satisfied_nor_violated():
    spec = standard_spec()
    spec.rules.append(rule("REVIEW_AFTER_VERIFY", {"role": "review", "kind": "review", "independent_of": "verify"},
                           ["ClaudeReview"]))
    table = make(spec)
    fresh = ask(table, "review", "review")
    unused = [e for e in fresh.excluded if e.rule_id == "REVIEW_AFTER_VERIFY"]
    assert [e.reason for e in unused] == ["PRIOR_ROLE_UNUSED"]
    assert fresh.decided_by == "rule:REVIEW_ANY"                   # the other rule, not a guess about the first
    used = ask(table, "review", "review", used={"verify": ("openai",)})
    assert "REVIEW_AFTER_VERIFY" in used.decided_by and used.excluded == ()
    clash = ask(table, "review", "review", used={"verify": ("anthropic",)})
    assert [e.reason for e in clash.excluded] == ["SAME_LINEAGE"]
    spec2 = standard_spec()
    spec2.rules = [r for r in spec2.rules if r["id"] != "REVIEW_ANY"]
    spec2.rules.append(rule("REVIEW_AFTER_VERIFY", {"role": "review", "kind": "review", "independent_of": "verify"},
                            ["ClaudeReview"]))
    assert ask(make(spec2), "review", "review").decided_by == "rule:DEFAULT"   # the fallback answers; the exclusion is kept


# ======================================================================== R4: concurrency
def test_R4_an_agent_at_its_concurrency_limit_is_skipped_for_the_next_in_the_list():
    table = make(standard_spec())
    free = ask(table, "implement", "feature")
    busy = ask(table, "implement", "feature", in_use={"CodexImpl": 1})
    assert free.agent_id == "CodexImpl" and busy.agent_id == "ClaudeImpl" and busy.decided_by == "rule:IMPL_FEATURE"
    assert [(e.agent_id, e.reason) for e in busy.excluded] == [("CodexImpl", "CONCURRENCY_FULL")]
    assert busy.excluded[0].detail == "in_use=1 concurrency=1"


def test_R4_the_limit_is_the_agents_own_number():
    table = make(standard_spec())                                   # CodexBulk has concurrency 2
    assert ask(table, "generate", "bulk_generation", in_use={"CodexBulk": 1}).agent_id == "CodexBulk"
    assert ask(table, "generate", "bulk_generation", in_use={"CodexBulk": 2}).undecided_reason == "NO_VIABLE_CANDIDATE"


def test_R4_a_full_head_does_not_make_the_next_one_a_tie():
    decision = ask(make(tie_spec()), "implement", "feature", "small", in_use={"CodexImpl": 1})
    assert decision.agent_id == "ClaudeImpl" and decision.stage == "rule"      # both rules now name the same head


def test_the_declared_roles_and_kinds_exclude_with_their_own_reasons():
    table = make(standard_spec())
    plain = ask(table, "implement", "feature")
    assert plain.excluded == ()
    broken = ar.RoutingTable(table.agents, (ar.RoutingRule("IMPL_BAD", (ar.Condition("role", "implement"),),
                                                            ("ClaudeVerify", "CodexImpl"), "x", table.rules[0].basis),
                                            *table.rules), ())
    decision = ask(broken, "implement", "feature")
    assert {(e.agent_id, e.reason) for e in decision.excluded if e.rule_id == "IMPL_BAD"} == {
        ("ClaudeVerify", "ROLE_NOT_DECLARED"), ("ClaudeVerify", "KIND_NOT_DECLARED")}


# ======================================================================== R6: declared and measured never share a row
def test_R6_declared_and_measured_keys_do_not_overlap_and_the_markers_differ():
    assert set(ar.DECLARED_KEYS).isdisjoint(ar.MEASURED_KEYS)
    assert set(ar.JOIN_KEYS) == {"job_id", "values"} and set(ar.JOIN_KEYS).isdisjoint(ar.DECLARED_KEYS + ar.MEASURED_KEYS)
    declared = ask(make(standard_spec()), "implement", "feature").ledger_fields()
    measured = ar.measured_fields("job1", "COMPLETE", 2, 12.5)
    assert declared["values"] == "declared" and measured["values"] == "measured"
    assert set(declared) <= set(ar.DECLARED_KEYS) | set(ar.JOIN_KEYS) and set(measured) <= set(ar.MEASURED_KEYS) | set(ar.JOIN_KEYS)
    assert set(declared) & set(ar.MEASURED_KEYS) == set() and set(measured) & set(ar.DECLARED_KEYS) == set()
    assert measured == {"values": "measured", "job_id": "job1", "outcome": "COMPLETE", "rounds": 2, "elapsed_seconds": 12.5}
    json.dumps(declared), json.dumps(measured)                    # both are plain JSON


def test_R6_every_kind_of_decision_makes_a_row_of_declared_keys_only():
    chooser, _ = fake_chooser(["ClaudeImpl"])
    decisions = [ask(make(standard_spec()), "implement", "feature"), ask(make(tie_spec(with_precedence=True))),
                 ask(make(tie_spec()), chooser=chooser), ask(make(tie_spec())),
                 ask(make(standard_spec()), "read", "read_large_file")]
    assert {d.stage for d in decisions} == {"rule", "precedence", "llm_testimony", "NONE"}
    for decision in decisions:
        row = decision.ledger_fields()
        assert set(row) == set(ar.DECLARED_KEYS) | set(ar.JOIN_KEYS) and row["values"] == "declared"
        assert not set(row) & set(ar.MEASURED_KEYS)
        json.dumps(row)


def test_R6_a_measurement_is_checked_and_the_router_reads_no_ledger():
    for bad in (dict(job_id="", outcome="x", rounds=0, elapsed_seconds=0), dict(job_id="j", outcome="", rounds=0, elapsed_seconds=0),
                dict(job_id="j", outcome="x", rounds=-1, elapsed_seconds=0), dict(job_id="j", outcome="x", rounds=True, elapsed_seconds=0),
                dict(job_id="j", outcome="x", rounds=1, elapsed_seconds=-1), dict(job_id="j", outcome="x", rounds=1, elapsed_seconds=True)):
        with pytest.raises(ValueError):
            ar.measured_fields(**bad)
    source = (Path(ar.__file__)).read_text(encoding="utf-8")
    route_body = source[source.index("def route("):source.index("def table_from_dicts")]
    assert "measured" not in route_body and "ledger" not in route_body.replace("ledger_fields", "")


def test_R6_the_basis_of_the_chosen_agent_is_written_and_a_declared_value_is_never_a_measurement():
    row = ask(dsl_table(standard_spec()), "implement", "feature").ledger_fields()
    assert row["agent_basis"]["kind"] == "declared_dsl" and row["agent_basis"]["line"] >= 1
    row = ask(dict_table(standard_spec()), "implement", "feature").ledger_fields()
    assert row["agent_basis"]["kind"] == "declared_text" and row["agent_basis"]["witnesses"]


# ======================================================================== size
@pytest.mark.parametrize("paths,criteria,expected", [
    (1, 1, "small"), (2, 3, "small"), (3, 1, "medium"), (1, 4, "medium"), (5, 7, "medium"),
    (6, 1, "large"), (1, 8, "large"), (2, 8, "large"), (6, 8, "large"), (3, 8, "large"), (0, 0, "small")])
def test_size_is_the_larger_of_the_two_bands(paths, criteria, expected):
    size, basis = ar.size_of(paths, criteria)
    assert size == expected and basis["allowlist_paths"] == paths and basis["criteria"] == criteria
    assert basis["thresholds"] == "design values, not measured"
    assert ar.SIZES.index(size) == max(ar.SIZES.index(basis["allowlist_band"]), ar.SIZES.index(basis["criteria_band"]))


def test_size_refuses_a_negative_or_non_integer_count():
    for bad in ((-1, 1), (1, -1), (1.5, 1), (True, 1), (None, 1)):
        with pytest.raises(ValueError):
            ar.size_of(*bad)


def test_the_size_of_a_job_selects_among_rules():
    spec = standard_spec()
    spec.rules.append(rule("IMPL_LARGE", {"role": "implement", "size": "large"}, ["ClaudeImpl"]))
    table = make(spec)
    assert ask(table, "implement", "feature", "small").agent_id == "CodexImpl"
    # large: IMPL_FEATURE (CodexImpl) and IMPL_LARGE (ClaudeImpl) disagree and nobody ordered them
    assert ask(table, "implement", "feature", "large").undecided_reason == "TESTIMONY_UNAVAILABLE"
    assert ask(table, "implement", "small_fix", "large").agent_id == "ClaudeImpl"


def test_every_combination_of_a_small_table_gives_a_decision_or_a_typed_reason():
    table = make(standard_spec())
    for role, kind, size in itertools.product(ar.ROLES, ar.TASK_KINDS, ar.SIZES):
        decision = ask(table, role, kind, size, used={"implement": ("openai",)})
        assert (decision.agent_id is None) == (decision.undecided_reason is not None)
        assert decision.stage in ar.STAGES and all(e.reason in ar.EXCLUSION_REASONS for e in decision.excluded)


# ======================================================================== R0 (round 2): records a prose reader can make
REQUESTS = [
    dict(role="implement", kind="feature", size="small"),
    dict(role="implement", kind="small_fix", size="large"),
    dict(role="verify", kind="verification", size="medium", used={"implement": ("openai",)}),
    dict(role="verify", kind="verification", size="small", used={"implement": ("anthropic",)}),
    dict(role="review", kind="review", size="small"),
    dict(role="generate", kind="bulk_generation", size="large"),
]


def test_R0_fallback_the_role_default_is_a_field_of_the_record_not_a_reserved_name():
    spec = renamed(standard_spec())
    assert {r["id"] for r in spec.rules if r.get("fallback")} == {f"fallback_for_{x}" for x in
                                                                 ("implement", "verify", "review", "generate", "answer")}
    assert not any(r["id"] == "DEFAULT" for r in spec.rules)
    table = make(spec)                                  # reads: no rule is called DEFAULT
    assert all(rule_.fallback for rule_ in table.rules if rule_.id.startswith("fallback_for_"))
    decision = ask(table, "implement", "small_fix")     # no rule names small_fix: the fallback of the role answers
    assert (decision.agent_id, decision.decided_by) == ("CodexImpl", "rule:fallback_for_implement")


def test_R0_fallback_a_rule_named_DEFAULT_is_not_a_fallback_unless_the_record_says_so():
    spec = renamed(standard_spec())        # the review fallback is replaced by an ordinary rule named DEFAULT
    spec.rules = [r for r in spec.rules if r["id"] != "fallback_for_review"]
    spec.rules.append(rule("DEFAULT", {"role": "review"}, ["ClaudeReview"]))
    assert code_of(spec) == "MISSING_ROLE_DEFAULT"
    spec = renamed(standard_spec())
    spec.rules = [r for r in spec.rules if r["id"] != "fallback_for_review"]
    assert code_of(spec) == "MISSING_ROLE_DEFAULT"


def test_R0_fallback_two_fallbacks_for_one_role_and_a_fallback_with_a_rules_name_are_refused():
    spec = renamed(standard_spec())
    spec.rules.append({**rule("another", {"role": "review"}, ["ClaudeReview"]), "fallback": True})
    assert code_of(spec) == "DUPLICATE_FALLBACK"
    spec = renamed(standard_spec())
    spec.rules.append({**rule("prose_impl_feature", {"role": "review"}, ["ClaudeReview"]), "fallback": True})
    spec.rules = [r for r in spec.rules if r["id"] != "fallback_for_review"]
    assert code_of(spec) == "DUPLICATE_RULE_ID"
    spec = renamed(standard_spec())
    spec.rules[-1]["fallback"] = "yes"
    assert code_of(spec) == "BAD_VALUE"


def test_R0_fallback_a_precedence_cannot_name_a_fallback_whatever_it_is_called():
    spec = renamed(standard_spec())
    spec.precedence.append(precedence("P1", "fallback_for_review", "prose_impl_feature"))
    assert code_of(spec) == "PRECEDENCE_ON_DEFAULT"


@pytest.mark.parametrize("request_args", REQUESTS)
def test_R0_fallback_a_table_whose_rules_have_other_names_decides_like_the_dsl_table(request_args):
    spec = standard_spec()
    from_dsl, from_other_names = dsl_table(spec), dict_table(renamed(spec))
    first, second = ask(from_dsl, **request_args), ask(from_other_names, **request_args)
    assert (first.agent_id, first.stage) == (second.agent_id, second.stage) and first.decided
    assert first.essence() == second.essence()


@pytest.mark.parametrize("which", ["same", "reverse", "rotate"])
@pytest.mark.parametrize("spec_factory", [standard_spec, lambda: tie_spec(with_precedence=True), lambda: tie_spec(chain=True)])
def test_R0_essence_does_not_depend_on_the_names_or_the_order_the_producer_gave(which, spec_factory):
    spec = spec_factory()
    other = renamed(spec if which == "same" else spec.permuted(which))
    for args in REQUESTS:
        a, b = ask(dsl_table(spec), **args), ask(dict_table(other), **args)
        assert a.essence() == b.essence()
        assert a.decided_by.startswith("rule:") == b.decided_by.startswith("rule:")


def test_R0_essence_keeps_the_exclusions_and_still_tells_different_decisions_apart():
    spec = standard_spec()
    used = {"implement": ("openai",)}
    a = ask(dsl_table(spec), "verify", "verification", used=used)
    b = ask(dict_table(renamed(spec)), "verify", "verification", used=used)
    assert a.excluded and a.essence() == b.essence()
    assert {e.rule_id for e in a.excluded} != {e.rule_id for e in b.excluded}        # the printed names differ ...
    assert ask(dsl_table(spec), "verify", "verification", used={"implement": ("anthropic",)}).essence() != a.essence()
    c = ask(dict_table(renamed(tie_spec(with_precedence=True))), "implement", "feature", "small")
    d = ask(dict_table(renamed(tie_spec())), "implement", "feature", "small")
    assert c.essence() != d.essence()                                                 # ... a different outcome is not equal


# ======================================================================== R0 (round 2): a basis keeps every sentence
def test_R0_basis_a_record_read_from_two_sentences_keeps_both_in_the_decision_and_the_ledger_row():
    spec = standard_spec()
    spec.agents[0].pop("witness")
    spec.agents[0]["witnesses"] = ["Codex is good at implementing features.",
                                   "Codex and Claude come from different vendors."]
    decision = ask(make(spec), "implement", "feature")
    assert decision.agent_id == "CodexImpl"
    assert decision.agent_basis.kind == "declared_text" and len(decision.agent_basis.witnesses) == 2
    assert decision.ledger_fields()["agent_basis"]["witnesses"] == spec.agents[0]["witnesses"]
    json.dumps(decision.ledger_fields())
    assert ar.Basis.text("s", "one").witnesses == ("one",)                           # one sentence still works
    assert ar.Basis.text("s", ["a", "b"]).as_dict()["witnesses"] == ["a", "b"]
    assert ar.Basis.dsl("f.md", 3, "row").witnesses == ("row",) and ar.Basis.dsl("f.md", 3).witnesses == ()


def test_R0_basis_no_sentence_or_a_blank_one_is_refused():
    for bad in ([], ["fine", ""], ["fine", "   "], (), None):
        with pytest.raises(ValueError):
            ar.Basis.text("s", bad)
    with pytest.raises(TypeError):
        ar.Basis("declared_text", "s", None, "one string, not a list")
    with pytest.raises(ValueError):
        ar.Basis("declared_text", "s", None, ("ok", 3))
    spec = standard_spec()
    spec.rules[0].pop("witness")
    spec.rules[0]["witnesses"] = []
    with pytest.raises(ValueError):
        dict_table(spec)
    spec = standard_spec()
    spec.precedence = [precedence("P1", "IMPL_FEATURE", "REVIEW_ANY")]
    spec.precedence[0]["witnesses"] = ["", "x"]
    with pytest.raises(ValueError):
        dict_table(spec)


# ======================================================================== R0 (round 2): what the human did not say stays unsaid
def sparse_spec() -> Spec:
    """Records as a reader of prose would make them: no reason, no number of parallel runs, no effort."""
    def bare(item):
        item = dict(item)
        for key in ("model", "effort", "concurrency", "note"):
            item.pop(key, None)
        return item

    def reasonless(item):
        item = dict(item)
        item.pop("reason")
        return item

    base = tie_spec(with_precedence=True)
    return Spec([bare(a) for a in base.agents], [reasonless(r) for r in base.rules],
                [reasonless(p) for p in base.precedence])


def test_R0_unsaid_values_a_table_without_reasons_concurrency_model_or_effort_can_be_made():
    table = make(sparse_spec())
    assert all(a.model is None and a.effort is None and a.concurrency is None for a in table.agents)
    assert all(r.reason is None for r in table.rules) and all(p.reason is None for p in table.precedence)
    decision = ask(table, "implement", "feature", "medium")
    assert (decision.agent_id, decision.stage, decision.decided_by) == ("CodexImpl", "rule", "rule:IMPL_FEATURE")
    tied = ask(table, "implement", "feature", "small")                     # the precedence needs no reason to settle it
    assert (tied.agent_id, tied.stage) == ("CodexImpl", "precedence")
    json.dumps(decision.ledger_fields())
    assert decision.ledger_fields()["agent_basis"]["witnesses"]


def test_R0_unsaid_values_an_undeclared_concurrency_is_excluded_only_once_something_is_in_use():
    table = make(sparse_spec())
    free = ask(table, "implement", "feature", "medium", in_use={})
    zero = ask(table, "implement", "feature", "medium", in_use={"CodexImpl": 0})
    busy = ask(table, "implement", "feature", "medium", in_use={"CodexImpl": 1})
    assert free.agent_id == zero.agent_id == "CodexImpl" and free.excluded == zero.excluded == ()
    assert busy.agent_id == "ClaudeImpl"                                             # the next in the human's list
    assert [(e.agent_id, e.reason) for e in busy.excluded] == [("CodexImpl", "CONCURRENCY_UNDECLARED")]
    assert "undeclared" in busy.excluded[0].detail or "no concurrency" in busy.excluded[0].detail
    both = ask(table, "implement", "feature", "medium", in_use={"CodexImpl": 1, "ClaudeImpl": 3})
    assert both.agent_id is None and both.undecided_reason == "NO_VIABLE_CANDIDATE"
    assert {e.reason for e in both.excluded} == {"CONCURRENCY_UNDECLARED"}
    assert "CONCURRENCY_UNDECLARED" in ar.EXCLUSION_REASONS


def test_R0_unsaid_values_a_value_that_is_said_is_still_checked_and_a_blank_reason_is_not_a_reason():
    spec = sparse_spec()
    spec.agents[0]["effort"] = "enormous; rm"
    assert code_of(spec) == "BAD_VALUE"
    spec = sparse_spec()
    spec.agents[0]["concurrency"] = 0
    assert code_of(spec) == "BAD_VALUE"
    spec = sparse_spec()
    spec.rules[0]["reason"] = "   "
    assert code_of(spec) == "BAD_VALUE"
    spec = sparse_spec()
    spec.precedence[0]["reason"] = ""
    assert code_of(spec) == "BAD_VALUE"


def test_R0_unsaid_values_the_closed_question_still_works_without_reasons_or_models():
    chooser, prompts = fake_chooser(["ClaudeImpl"])
    spec = sparse_spec()
    spec.precedence = []
    decision = ask(make(spec), "implement", "feature", "small", chooser=chooser)
    assert (decision.agent_id, decision.stage) == ("ClaudeImpl", "llm_testimony") and len(prompts) == 2


# ======================================================================== R0 (round 3): a kind the human did not say stays unsaid
TICKET_SENTENCE = "実装は Sonnet 5.5、検証は実装と別系統の codex gpt-6-luna。"


def prose_agents(*, lineages: bool = True) -> list:
    """What a reader of the ticket's own example sentence can say: who does which role, nothing about kinds."""
    sonnet = {"id": "Sonnet 5.5", "adapter": "claude", "model": "claude-sonnet-5-5", "roles": ["implement"],
              "witness": TICKET_SENTENCE}
    luna = {"id": "gpt-6-luna", "adapter": "codex", "model": "gpt-6-luna", "roles": ["verify"], "witness": TICKET_SENTENCE}
    if lineages:
        sonnet["lineage"], luna["lineage"] = "Claude系", "OpenAI系"
    return [sonnet, luna]


def prose_rules() -> list:
    return [{"id": "r_impl", "when": {"role": "implement"}, "prefer": ["Sonnet 5.5"], "fallback": True, "witness": TICKET_SENTENCE},
            {"id": "r_verify", "when": {"role": "verify"}, "prefer": ["gpt-6-luna"], "fallback": True, "witness": TICKET_SENTENCE}]


def test_R0_unsaid_kinds_a_table_that_names_agents_for_roles_only_can_be_made_and_decides_with_a_mark():
    from verantyx.agent_routing import table_from_dicts

    table = table_from_dicts(prose_agents(), prose_rules())
    assert all(item.kinds is None for item in table.agents)                       # nothing was made up
    decision = ask(table, "implement", "feature", "small")
    assert (decision.agent_id, decision.stage, decision.decided_by) == ("Sonnet 5.5", "rule", "rule:r_impl")
    assert decision.excluded == () and dict(decision.kind_fit) == {"Sonnet 5.5": "undeclared"}
    row = decision.ledger_fields()
    assert row["kind_fit"] == {"Sonnet 5.5": "undeclared"} and "kind_fit" in ar.DECLARED_KEYS
    json.dumps(row)
    other = ask(table, "implement", "attack", "large")                            # no limit was declared: every kind is routed
    assert other.agent_id == "Sonnet 5.5" and dict(other.kind_fit) == {"Sonnet 5.5": "undeclared"}


def test_R0_unsaid_kinds_an_agent_that_declared_its_kinds_is_still_excluded_for_another_kind_and_says_declared():
    spec = standard_spec()
    table = make(spec)
    gone = ask(table, "implement", "attack", "small")
    assert gone.agent_id is None and {e.reason for e in gone.excluded} == {"KIND_NOT_DECLARED"}
    fit = ask(table, "implement", "feature", "small")
    assert fit.agent_id == "CodexImpl" and dict(fit.kind_fit) == {"CodexImpl": "declared"}
    spec = standard_spec()
    spec.agents[0].pop("kinds")                                                    # CodexImpl now has no declared kinds
    mixed = ask(make(spec), "implement", "small_fix", "small")
    assert mixed.agent_id == "CodexImpl" and dict(mixed.kind_fit) == {"CodexImpl": "undeclared"}
    assert set(ar.KIND_FIT_VALUES) == {"declared", "undeclared"}


def test_R0_unsaid_kinds_a_rule_with_a_kind_condition_may_name_an_agent_that_declared_no_kinds():
    spec = standard_spec()
    spec.agents[0].pop("kinds")                                                    # CodexImpl: kinds undeclared
    assert make(spec)                                                              # IMPL_FEATURE (kind=feature) names it: fine
    spec = standard_spec()
    spec.rules[0] = rule("IMPL_FEATURE", {"role": "implement", "kind": "large_refactor"}, ["CodexImpl", "ClaudeImpl"])
    spec.agents[0]["kinds"] = ["small_fix", "feature"]
    assert code_of(spec) == "RULE_AGENT_MISMATCH"                                  # declared, and does not include it


def test_R0_unsaid_kinds_a_declaration_that_is_given_is_still_checked():
    spec = standard_spec()
    spec.agents[0]["kinds"] = []
    assert code_of(spec) == "BAD_VALUE"
    spec = standard_spec()
    spec.agents[0]["kinds"] = ["nope"]
    assert code_of(spec) == "UNKNOWN_KIND"


def test_R0_unsaid_kinds_the_closed_question_says_the_kinds_are_undeclared():
    chooser, prompts = fake_chooser(["ClaudeImpl"])
    table = make(tie_spec_without_kinds())
    decision = ask(table, "implement", "feature", "small", chooser=chooser)
    assert decision.agent_id == "ClaudeImpl" and decision.stage == "llm_testimony"
    assert any("kinds=undeclared" in text for text in prompts)


def tie_spec_without_kinds() -> Spec:
    base = tie_spec()
    for item in base.agents:
        if item["id"] == "CodexImpl":
            item.pop("kinds")
    return base


# ======================================================================== R0 (round 3): a name or a lineage is the human's word
def test_R0_names_an_id_and_a_lineage_in_the_humans_own_words_make_a_table_and_a_decision():
    from verantyx.agent_routing import table_from_dicts

    table = table_from_dicts(prose_agents(), prose_rules())
    assert [a.id for a in table.agents] == ["Sonnet 5.5", "gpt-6-luna"]
    assert [a.lineage for a in table.agents] == ["Claude系", "OpenAI系"]
    decision = ask(table, "verify", "verification", "small", used={"implement": ("Claude系",)})
    assert (decision.agent_id, decision.decided_by) == ("gpt-6-luna", "rule:r_verify")
    assert decision.independence == {"implement": "distinct_lineage"}
    json.dumps(decision.ledger_fields(), ensure_ascii=False)
    clash = ask(table, "verify", "verification", "small", used={"implement": ("OpenAI系",)})
    assert clash.agent_id is None and [e.reason for e in clash.excluded] == ["SAME_LINEAGE"]
    for name in ("Sonnet5.5", "ソネット", "claude-sonnet-5-5", "Opus 5.5 (中間職)"):
        agents = prose_agents()
        agents[0]["id"] = name
        rules = prose_rules()
        rules[0]["prefer"] = [name]
        assert table_from_dicts(agents, rules).agent(name) is not None, name


@pytest.mark.parametrize("bad", ["", " Sonnet", "Sonnet ", "Son\nnet", "Son\tnet", None, 5])
def test_R0_names_a_blank_or_padded_or_control_or_non_string_id_or_lineage_is_still_BAD_VALUE(bad):
    from verantyx.agent_routing import table_from_dicts

    agents = prose_agents()
    rules = prose_rules()
    agents[0]["id"] = bad
    rules[0]["prefer"] = [bad]
    with pytest.raises(ar.RoutingRecordError) as info:
        table_from_dicts(agents, rules)
    assert info.value.code == "BAD_VALUE"
    agents = prose_agents()
    agents[0]["lineage"] = bad
    if bad is None:
        assert table_from_dicts(agents, prose_rules())                                # None is "not said", not an error
    else:
        with pytest.raises(ar.RoutingRecordError) as info:
            table_from_dicts(agents, prose_rules())
        assert info.value.code == "BAD_VALUE"


def lineage_spec(*, impl_lineage="Claude系", verifiers=(("gpt-6-luna", "OpenAI系"),), waive=False):
    agents = [{"id": "Sonnet 5.5", "adapter": "claude", "model": "claude-sonnet-5-5", "roles": ["implement"],
               "witness": TICKET_SENTENCE}]
    if impl_lineage is not None:
        agents[0]["lineage"] = impl_lineage
    for name, lineage in verifiers:
        item = {"id": name, "adapter": "codex", "model": "gpt-6-luna", "roles": ["verify"], "witness": TICKET_SENTENCE}
        if lineage is not None:
            item["lineage"] = lineage
        agents.append(item)
    verify_when = {"role": "verify", "independent_of": "none"} if waive else {"role": "verify"}
    rules = [{"id": "r_impl", "when": {"role": "implement"}, "prefer": ["Sonnet 5.5"], "fallback": True, "witness": TICKET_SENTENCE},
             {"id": "r_verify", "when": verify_when, "prefer": [name for name, _ in verifiers], "witness": TICKET_SENTENCE},
             {"id": "r_verify_otherwise", "when": {"role": "verify"}, "prefer": [name for name, _ in verifiers],
              "fallback": True, "witness": TICKET_SENTENCE}]
    return agents, rules


def test_R0_lineage_unsaid_an_agent_no_independence_check_looks_at_is_kept_with_no_lineage():
    from verantyx.agent_routing import table_from_dicts

    agents = prose_agents(lineages=False)
    agents.append({"id": "Bulk", "adapter": "codex", "model": "gpt-6-luna", "roles": ["generate"], "witness": "大量生成は gpt-6-luna low。"})
    rules = prose_rules() + [{"id": "r_gen", "when": {"role": "generate"}, "prefer": ["Bulk"], "fallback": True,
                              "witness": "大量生成は gpt-6-luna low。"}]
    table = table_from_dicts(agents, rules)
    assert all(a.lineage is None for a in table.agents)
    decision = ask(table, "generate", "bulk_generation", "small")
    assert (decision.agent_id, decision.stage, decision.excluded) == ("Bulk", "rule", ())
    implement = ask(table, "implement", "feature", "small")
    assert implement.agent_id == "Sonnet 5.5" and implement.excluded == ()          # nothing asked for its lineage


def test_R0_lineage_unsaid_an_implementer_whose_lineage_is_unknown_leaves_no_viable_verifier():
    from verantyx.agent_routing import table_from_dicts

    agents, rules = lineage_spec(impl_lineage=None)
    assert table_from_dicts(agents, rules).agent("Sonnet 5.5").lineage is None
    table = table_from_dicts(agents, rules)
    decision = ask(table, "verify", "verification", "small", used={"implement": (None,)})   # used, lineage not known
    assert decision.agent_id is None and decision.undecided_reason == "NO_VIABLE_CANDIDATE" and decision.stage == "NONE"
    assert {(e.agent_id, e.reason) for e in decision.excluded} == {("gpt-6-luna", "LINEAGE_UNDECLARED")}
    assert "LINEAGE_UNDECLARED" in ar.EXCLUSION_REASONS and "not declared" in decision.excluded[0].detail
    assert "PRIOR_ROLE_UNUSED" not in {e.reason for e in decision.excluded}
    assert "SAME_LINEAGE" not in {e.reason for e in decision.excluded}
    json.dumps(decision.ledger_fields(), ensure_ascii=False)


def test_R0_lineage_unsaid_an_unused_implementer_and_an_unknown_one_are_different_exclusions():
    from verantyx.agent_routing import table_from_dicts

    agents, rules = lineage_spec(impl_lineage=None)
    table = table_from_dicts(agents, rules)
    never = ask(table, "verify", "verification", "small")                           # nothing used yet
    unknown = ask(table, "verify", "verification", "small", used={"implement": (None,)})
    assert {e.reason for e in never.excluded} == {"PRIOR_ROLE_UNUSED"}
    assert {e.reason for e in unknown.excluded} == {"LINEAGE_UNDECLARED"}
    known_clash = ask(table, "verify", "verification", "small", used={"implement": (None, "OpenAI系")})
    assert {e.reason for e in known_clash.excluded} == {"SAME_LINEAGE"}              # a known clash is still a clash
    with pytest.raises(ValueError):
        ar.RoutingRequest("j", "verify", "verification", "small", used_lineages={"implement": ("",)})


def test_R0_lineage_unsaid_an_explicit_independent_of_none_decides_without_looking_at_lineage():
    from verantyx.agent_routing import table_from_dicts

    agents, rules = lineage_spec(impl_lineage=None, waive=True)
    decision = ask(table_from_dicts(agents, rules), "verify", "verification", "small", used={"implement": (None,)})
    assert decision.agent_id == "gpt-6-luna" and decision.decided_by == "rule:r_verify"
    assert decision.independence == {"implement": "waived_by:rule:r_verify"} and decision.excluded == ()


def test_R0_lineage_unsaid_a_verifier_candidate_without_a_lineage_is_excluded_and_the_next_is_used():
    from verantyx.agent_routing import table_from_dicts

    agents, rules = lineage_spec(verifiers=(("Unknown verifier", None), ("gpt-6-luna", "OpenAI系")))
    decision = ask(table_from_dicts(agents, rules), "verify", "verification", "small", used={"implement": ("Claude系",)})
    assert (decision.agent_id, decision.decided_by) == ("gpt-6-luna", "rule:r_verify")
    gone = [e for e in decision.excluded if e.agent_id == "Unknown verifier"]
    assert gone and {e.reason for e in gone} == {"LINEAGE_UNDECLARED"} and "no lineage" in gone[0].detail
