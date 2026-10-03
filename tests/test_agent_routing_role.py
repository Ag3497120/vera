"""W2-h round 4 (F9): a job can be assigned without naming a role ("attack goes to Luna"), and an agent can be
described without naming its roles.  The record layer and the router; no DSL here (tests/test_agent_routing_dsl.py)."""
from __future__ import annotations

import json

import pytest

from test_agent_routing_support import Spec, agent, default, dict_table, standard_spec, rule
from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards: this tree, no real agent)

from verantyx import agent_routing as ar

LUNA = "gpt-6-luna xhigh"


def luna(**extra):
    """The ticket's own example: attack and large-file reading go to codex gpt-6-luna xhigh.  No role is said."""
    return {"id": LUNA, "adapter": "codex", "model": "gpt-6-luna", "effort": "xhigh",
            "kinds": ["attack", "read_large_file"], "witness": "攻撃と大きなファイルの読解は codex gpt-6-luna xhigh。", **extra}


def attack_rule():
    return {"id": "r_attack", "when": {"kind": "attack"}, "prefer": [LUNA],
            "witness": "攻撃と大きなファイルの読解は codex gpt-6-luna xhigh。"}


def ask(table, role, kind, size="small", *, used_agents=None, used_lineages=None, chooser=None):
    request = ar.RoutingRequest("job1", role, kind, size, used_agents=used_agents or {},
                                used_lineages=used_lineages or {})
    return ar.route(table, request, chooser_factory=(lambda: chooser) if chooser is not None else None)


def code_of(build) -> str:
    with pytest.raises(ar.RoutingRecordError) as info:
        build()
    return info.value.code


def code_of_spec(spec: Spec) -> str:
    return code_of(lambda: dict_table(spec))


# ------------------------------------------------------------------------------------------ R0: nothing about a role is said
def test_R0_role_unsaid_an_agent_and_a_rule_that_name_no_role_make_a_table_and_the_router_chooses_by_kind():
    table = ar.table_from_dicts([luna()], [attack_rule()])           # no fallback: no role is named anywhere
    assert table.agents[0].roles is None and table.rules[0].role is None
    decision = ask(table, "review", "attack")
    assert (decision.agent_id, decision.stage, decision.decided_by) == (LUNA, "rule", "rule:r_attack")
    assert decision.role_fit == {LUNA: "undeclared"}
    fields = decision.ledger_fields()
    assert fields["role_fit"] == {LUNA: "undeclared"} and fields["kind_fit"] == {LUNA: "declared"}
    json.dumps(fields)
    # the same record serves any role the request names; for verify the implicit independence of implement still applies
    verify = ask(table, "verify", "attack")
    assert verify.agent_id is None and {e.reason for e in verify.excluded} == {"PRIOR_ROLE_UNUSED"}
    assert ask(table, "read", "attack").agent_id == LUNA


def test_R0_role_unsaid_a_request_the_rule_does_not_match_is_not_routable_not_undecided():
    table = ar.table_from_dicts([luna()], [attack_rule()])
    decision = ask(table, "read", "read_large_file")
    assert decision.agent_id is None and decision.undecided_reason == "ROLE_NOT_ROUTABLE"
    assert ar.routable(table, ar.RoutingRequest("j", "read", "read_large_file", "small")) is False
    assert ar.routable(table, ar.RoutingRequest("j", "read", "attack", "small")) is True


def test_R0_role_a_rule_with_no_role_is_a_legal_rule():
    """The old line `rule("X1", {"kind": "feature"}, ["CodexImpl"])` -> MISSING_ROLE_CONDITION is now legal (F9)."""
    spec = standard_spec()
    spec.rules.append(rule("X1", {"kind": "feature"}, ["CodexImpl"]))
    table = dict_table(spec)
    decision = ask(table, "implement", "feature")
    assert decision.agent_id == "CodexImpl" and set(decision.matched_rules) == {"IMPL_FEATURE", "X1"}
    assert decision.decided_by == "rule:IMPL_FEATURE,X1"


def test_R0_role_unsaid_roles_none_is_not_the_same_as_an_empty_list():
    spec = Spec([agent("A", roles=("implement",))], [default("implement", ["A"])])
    spec.agents[0]["roles"] = []
    assert code_of_spec(spec) == "BAD_VALUE"
    spec.agents[0].pop("roles")                                      # not said: fine, and it can still be routed
    table = dict_table(spec)
    assert table.agents[0].roles is None
    assert ask(table, "implement", "feature").role_fit == {"A": "undeclared"}


def test_R0_role_unsaid_the_testimony_summary_says_roles_undeclared_instead_of_failing():
    from test_agent_routing_support import fake_chooser

    other = {**luna(), "id": "Other", "witness": "もう 1 体。"}
    table = ar.table_from_dicts([luna(), other], [
        attack_rule(), {"id": "r_other", "when": {"kind": "attack"}, "prefer": ["Other"], "witness": "Other も。"}])
    chooser, prompts = fake_chooser([LUNA])
    decision = ask(table, "review", "attack", chooser=chooser)
    assert decision.stage == "llm_testimony" and decision.agent_id == LUNA
    assert any("roles=undeclared" in prompt for prompt in prompts)


# ------------------------------------------------------------------------------------------ R3: independence by the request's role
def role_less_verify_spec(*, with_claude: bool = True) -> Spec:
    """No ``role=verify`` rule except the fallback; the verify-by-kind rule names no role."""
    claude = [agent("ClaudeVerify", adapter="claude", lineage="anthropic", model="claude-sonnet-5-5",
                    roles=("verify",), kinds=("verification",))] if with_claude else []
    prefer = ["CodexVerify"] + (["ClaudeVerify"] if with_claude else [])
    return Spec(
        [agent("CodexImpl", roles=("implement",), kinds=("feature",)),
         agent("CodexVerify", roles=("verify",), kinds=("verification",)), *claude],
        [rule("VERIFY_BY_KIND", {"kind": "verification"}, prefer),
         default("implement", ["CodexImpl"]), default("verify", prefer[-1:])])


def test_R3_role_a_rule_with_no_role_still_makes_a_verify_request_independent_of_the_implementer():
    table = dict_table(role_less_verify_spec())
    decision = ask(table, "verify", "verification", used_lineages={"implement": ("openai",)})
    assert decision.agent_id == "ClaudeVerify" and decision.decided_by == "rule:VERIFY_BY_KIND"
    assert [(e.agent_id, e.reason) for e in decision.excluded] == [("CodexVerify", "SAME_LINEAGE")]
    assert decision.independence == {"implement": "distinct_lineage"}
    by_agent = ask(table, "verify", "verification", used_agents={"implement": ("CodexImpl",)})
    assert (by_agent.agent_id, by_agent.independence) == ("ClaudeVerify", {"implement": "distinct_lineage"})
    assert [(e.agent_id, e.reason) for e in by_agent.excluded] == [("CodexVerify", "SAME_LINEAGE")]


def test_R3_role_with_no_verifier_of_another_lineage_a_rule_with_no_role_stops_as_a_typed_none():
    table = dict_table(role_less_verify_spec(with_claude=False))
    for used in (dict(used_lineages={"implement": ("openai",)}), dict(used_agents={"implement": ("CodexImpl",)})):
        decision = ask(table, "verify", "verification", **used)
        assert decision.agent_id is None and decision.undecided_reason == "NO_VIABLE_CANDIDATE"
        assert {e.reason for e in decision.excluded} == {"SAME_LINEAGE"}


def test_R3_role_an_implement_request_is_not_made_independent_by_a_rule_with_no_role():
    spec = role_less_verify_spec()
    spec.rules.append(rule("ANY_FEATURE", {"kind": "feature"}, ["CodexImpl"]))
    decision = ask(dict_table(spec), "implement", "feature")
    assert decision.agent_id == "CodexImpl" and decision.independence == {}


def test_R3_role_the_independence_of_verify_is_not_judged_before_an_implementer_was_used():
    decision = ask(dict_table(role_less_verify_spec()), "verify", "verification")
    assert decision.agent_id is None
    assert {e.reason for e in decision.excluded} == {"PRIOR_ROLE_UNUSED"}


def test_R3_role_only_a_rule_written_role_verify_with_independent_of_none_waives_it():
    spec = role_less_verify_spec(with_claude=False)
    spec.rules.append(rule("WAIVE", {"role": "verify", "independent_of": "none"}, ["CodexVerify"]))
    decision = ask(dict_table(spec), "verify", "verification", used_lineages={"implement": ("openai",)})
    assert decision.agent_id == "CodexVerify"
    assert decision.independence == {"implement": "waived_by:rule:WAIVE"} and decision.independence_basis == {}


# ------------------------------------------------------------------------------------------ R1: what is rejected, and as what
@pytest.mark.parametrize("value", ["implement", "none"])
def test_R1_role_a_rule_with_no_role_may_not_say_independent_of(value):
    spec = standard_spec()
    spec.rules.append(rule("X1", {"kind": "feature", "independent_of": value}, ["CodexImpl"]))
    with pytest.raises(ar.RoutingRecordError) as info:
        dict_table(spec)
    assert info.value.code == "BAD_CONDITION" and "any role" in info.value.message


def test_R1_role_two_role_conditions_are_still_one_too_many():
    basis = ar.Basis.text("t", "x")
    agents = [ar.AgentRecord("A", "codex", frozenset({"implement", "review"}), basis)]
    two = ar.RoutingRule("R", (ar.Condition("role", "implement"), ar.Condition("role", "review")), ("A",), None, basis)
    fallbacks = [ar.RoutingRule("D1", (ar.Condition("role", "implement"),), ("A",), None, basis, True),
                 ar.RoutingRule("D2", (ar.Condition("role", "review"),), ("A",), None, basis, True)]
    assert code_of(lambda: ar.build_routing_table(agents, [two, *fallbacks])) == "BAD_CONDITION"


def test_R1_role_a_fallback_must_name_its_role():
    spec = standard_spec()
    spec.rules.append({**rule("X1", {"kind": "feature"}, ["CodexImpl"]), "fallback": True})
    assert code_of_spec(spec) == "MISSING_ROLE_CONDITION"
    spec = standard_spec()
    spec.rules.append({**rule("X1", {"kind": "feature"}, ["CodexImpl"]), "fallback": "yes"})
    assert code_of_spec(spec) == "BAD_VALUE"          # not a boolean: a different mistake, a different type


def test_R1_role_a_rule_with_no_role_asks_for_no_fallback_but_a_declared_role_still_does():
    only_rules = ar.table_from_dicts([luna()], [attack_rule()])
    assert only_rules.rules[0].role is None
    declared = {**luna(), "roles": ["review"]}
    assert code_of(lambda: ar.table_from_dicts([declared], [attack_rule()])) == "MISSING_ROLE_DEFAULT"


def test_R1_role_independence_cycle_through_a_rule_with_no_role():
    spec = standard_spec()
    spec.rules.append(rule("ANY", {"kind": "feature"}, ["CodexImpl"]))
    spec.rules.append(rule("LOOP", {"role": "implement", "independent_of": "verify"}, ["CodexImpl"]))
    assert code_of_spec(spec) == "INDEPENDENCE_CYCLE"


# ------------------------------------------------------------------------------------------ roles declared vs unsaid
def test_R1_role_a_declared_role_still_excludes_and_an_unsaid_one_does_not_mismatch():
    declared = agent("Impl", roles=("implement",), kinds=("attack",))
    table = ar.table_from_dicts([declared], [{"id": "r_any", "when": {"kind": "attack"}, "prefer": ["Impl"],
                                              "witness": "攻撃は Impl。"}, {**default("implement", ["Impl"]),
                                                                          "witness": "実装は Impl。"}])
    decision = ask(table, "review", "attack")
    assert decision.agent_id is None and decision.undecided_reason == "NO_VIABLE_CANDIDATE"
    assert [(e.agent_id, e.reason) for e in decision.excluded] == [("Impl", "ROLE_NOT_DECLARED")]
    assert ask(table, "implement", "attack").role_fit == {"Impl": "declared"}
    # the other way: a rule written role=review may name an agent that did not say its roles
    unsaid = ar.table_from_dicts([luna()], [{"id": "r_review", "when": {"role": "review", "kind": "attack"},
                                             "prefer": [LUNA], "witness": "レビューの攻撃は Luna。"},
                                            {"id": "d_review", "when": {"role": "review"}, "prefer": [LUNA],
                                             "fallback": True, "witness": "レビューは Luna。"}])
    assert ask(unsaid, "review", "attack").agent_id == LUNA


def test_R0_role_a_rule_with_no_role_and_one_with_the_same_content_are_compared_by_their_content():
    first = dict_table(Spec([luna_agent()], [rule("A1", {"kind": "attack"}, ["Luna"])]))
    second = dict_table(Spec([luna_agent()], [rule("another_name", {"kind": "attack"}, ["Luna"])]))
    one, two = ask(first, "review", "attack"), ask(second, "review", "attack")
    assert one.essence() == two.essence() and one.decided_by != two.decided_by


def luna_agent():
    item = agent("Luna", roles=("review",), kinds=("attack",))
    item.pop("roles")
    return item

