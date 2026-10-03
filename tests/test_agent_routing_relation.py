"""W2-h round 4 (F8): lineage as a relation between agents.  A label is the producer's own partition (same label =
same lineage, two labels = two lineages); what a human said about two agents ("A and B are different lineages") is
a ``LineageRelation``.  The router judges a candidate against the *agents* already used."""
from __future__ import annotations

import json

import pytest

from test_agent_routing_support import dict_table, dsl_table, standard_spec
from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards: this tree, no real agent)

from verantyx import agent_routing as ar


def plain(agent_id: str, roles=None, lineage=None, adapter: str = "codex") -> dict:
    """An agent whose human description gave no lineage name (and, unless asked, no role)."""
    item = {"id": agent_id, "adapter": adapter, "model": "gpt-6-luna", "effort": "low",
            "witness": f"{agent_id} のことを人間が書いた。"}
    if roles is not None:
        item["roles"] = list(roles)
    if lineage is not None:
        item["lineage"] = lineage
    return item


def relation(a: str, b: str, kind: str, witness: str | None = None) -> dict:
    return {"a": a, "b": b, "relation": kind, "witness": witness or f"{a} と {b} は {kind}。"}


def fallback(role: str, prefer, rule_id: str | None = None) -> dict:
    return {"id": rule_id or f"d_{role}", "when": {"role": role}, "prefer": list(prefer), "fallback": True,
            "witness": f"{role} は {', '.join(prefer)}。"}


def verify_request(table, used_agents=None, used_lineages=None, kind="verification"):
    request = ar.RoutingRequest("job1", "verify", kind, "small", used_agents=used_agents or {},
                                used_lineages=used_lineages or {})
    return ar.route(table, request)


def code_of(build) -> str:
    with pytest.raises(ar.RoutingRecordError) as info:
        build()
    return info.value.code


def two(relations, *, labels=(None, None)):
    """Sonnet implements, luna verifies; whatever the human said about their lineage is in ``relations``."""
    return ar.table_from_dicts(
        [plain("Sonnet", ["implement"], labels[0], "claude"), plain("luna", ["verify"], labels[1])],
        [fallback("implement", ["Sonnet"]), fallback("verify", ["luna"])], lineage_relations=relations)


# --------------------------------------------------------------------------------------------------- R3: a relation decides
def test_R3_relation_a_distinct_relation_with_no_labels_lets_the_verifier_through_and_is_the_recorded_ground():
    table = two([relation("Sonnet", "luna", "distinct", "Sonnet と luna は別系統。")])
    assert all(item.lineage is None for item in table.agents)
    decision = verify_request(table, used_agents={"implement": ("Sonnet",)})
    assert decision.agent_id == "luna" and decision.independence == {"implement": "distinct_lineage"}
    entries = decision.independence_basis["implement"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["used_agent"] == "Sonnet" and entry["verdict"] == "distinct" and entry["labels"] is None
    assert entry["relations"][0]["basis"]["witnesses"] == ["Sonnet と luna は別系統。"]
    assert entry["relations"][0]["basis"]["kind"] == "declared_text"
    fields = decision.ledger_fields()
    assert fields["independence_basis"] == {"implement": entries}
    json.dumps(fields)
    assert set(decision.independence_basis) == {r for r, v in decision.independence.items() if v == "distinct_lineage"}


def test_R3_relation_a_relation_nobody_said_is_not_made_up_for_three_agents():
    """A differs from B and from C (and nothing else is said): B versus C is unknown, not distinct and not the same."""
    table = ar.table_from_dicts(
        [plain("A", ["implement"]), plain("B", ["implement"]), plain("C", ["verify"])],
        [fallback("implement", ["B", "A"]), fallback("verify", ["C"])],
        lineage_relations=[relation("A", "B", "distinct"), relation("A", "C", "distinct")])
    decision = verify_request(table, used_agents={"implement": ("B",)})
    assert decision.agent_id is None and decision.undecided_reason == "NO_VIABLE_CANDIDATE"
    assert [(e.agent_id, e.reason) for e in decision.excluded] == [("C", "LINEAGE_UNDECLARED")]
    assert "B" in decision.excluded[0].detail
    assert verify_request(table, used_agents={"implement": ("A",)}).agent_id == "C"      # what was said works


def test_R3_relation_a_same_relation_with_no_labels_excludes_with_the_relation_as_the_ground():
    table = two([relation("Sonnet", "luna", "same", "Sonnet と luna は同じ系統。")])
    decision = verify_request(table, used_agents={"implement": ("Sonnet",)})
    assert decision.agent_id is None and decision.undecided_reason == "NO_VIABLE_CANDIDATE"
    assert [(e.agent_id, e.reason) for e in decision.excluded] == [("luna", "SAME_LINEAGE")]
    assert "'same' relation" in decision.excluded[0].detail and "Sonnet/luna" in decision.excluded[0].detail


def test_R3_relation_a_chain_of_same_relations_makes_the_ends_one_lineage():
    table = ar.table_from_dicts(
        [plain("X", ["implement"]), plain("Y", ["verify"]), plain("Z", ["verify"])],
        [fallback("implement", ["X"]), fallback("verify", ["Z", "Y"])],
        lineage_relations=[relation("X", "Y", "same"), relation("Y", "Z", "same")])
    decision = verify_request(table, used_agents={"implement": ("X",)})
    assert decision.agent_id is None
    assert {(e.agent_id, e.reason) for e in decision.excluded} == {("Y", "SAME_LINEAGE"), ("Z", "SAME_LINEAGE")}
    assert ar.lineage_relation(table, "X", "Z").verdict == "same"


def test_R3_relation_the_same_agent_as_the_implementer_is_the_same_lineage():
    table = ar.table_from_dicts([plain("Both", ["implement", "verify"]), plain("Other", ["verify"])],
                                [fallback("implement", ["Both"]), fallback("verify", ["Both", "Other"])],
                                lineage_relations=[relation("Both", "Other", "distinct")])
    decision = verify_request(table, used_agents={"implement": ("Both",)})
    assert decision.agent_id == "Other"
    assert [(e.agent_id, e.reason) for e in decision.excluded] == [("Both", "SAME_LINEAGE")]
    assert "same agent" in decision.excluded[0].detail
    assert ar.lineage_relation(table, "Both", "Both").verdict == "same"


def test_R3_relation_labels_alone_decide_as_before_and_say_so():
    table = two([], labels=("Claude系", "OpenAI系"))
    decision = verify_request(table, used_agents={"implement": ("Sonnet",)})
    assert decision.agent_id == "luna"
    entry = decision.independence_basis["implement"][0]
    assert entry["verdict"] == "distinct" and entry["labels"] == ["OpenAI系", "Claude系"] and entry["relations"] == []


def test_R3_relation_a_label_and_a_relation_are_both_recorded_when_both_hold():
    table = two([relation("Sonnet", "luna", "distinct", "別系統と言った。")], labels=("Claude系", "OpenAI系"))
    entry = verify_request(table, used_agents={"implement": ("Sonnet",)}).independence_basis["implement"][0]
    assert entry["labels"] == ["OpenAI系", "Claude系"] and len(entry["relations"]) == 1
    assert entry["relations"][0]["basis"]["witnesses"] == ["別系統と言った。"]


@pytest.mark.parametrize("implementer", ["CodexImpl", "ClaudeImpl"])
def test_R3_relation_a_labels_only_table_decides_the_same_whether_agents_or_lineages_are_named(implementer):
    lineage_of = {"CodexImpl": "openai", "ClaudeImpl": "anthropic"}[implementer]

    def summary(decision):
        return (decision.agent_id, decision.stage, decision.decided_by, decision.independence,
                {(e.agent_id, e.rule_id, e.reason) for e in decision.excluded})

    for table in (dict_table(standard_spec()), dsl_table(standard_spec())):
        by_agent = verify_request(table, used_agents={"implement": (implementer,)})
        by_label = verify_request(table, used_lineages={"implement": (lineage_of,)})
        assert summary(by_agent) == summary(by_label) and by_agent.agent_id is not None
        assert set(by_agent.independence_basis) == {"implement"}


# --------------------------------------------------------------------------------------------------- the three-valued verdict
def test_R3_relation_lineage_relation_gives_same_distinct_or_undeclared_with_its_grounds():
    table = ar.table_from_dicts(
        [plain("P", lineage="L1"), plain("Q", lineage="L1"), plain("R", lineage="L2"), plain("S"), plain("T"),
         plain("U")],
        [fallback("implement", ["P"])], lineage_relations=[relation("S", "T", "same"), relation("R", "S", "distinct")])
    labelled = ar.lineage_relation(table, "P", "Q")
    assert (labelled.verdict, labelled.labels, labelled.relations, labelled.joined_by) == ("same", ("L1", "L1"), (), ())
    by_labels = ar.lineage_relation(table, "P", "R")
    assert (by_labels.verdict, by_labels.labels, by_labels.relations) == ("distinct", ("L1", "L2"), ())
    by_relation = ar.lineage_relation(table, "T", "R")                       # T = S, and S differs from R
    assert by_relation.verdict == "distinct" and by_relation.labels is None
    assert [item.pair() for item in by_relation.relations] == [frozenset(("R", "S"))]
    assert [item.pair() for item in by_relation.joined_by] == [frozenset(("S", "T"))]
    for left, right in (("U", "P"), ("U", "S"), ("P", "S")):
        assert ar.lineage_relation(table, left, right).verdict == "undeclared"
    assert ar.lineage_relation(table, "S", "T").verdict == "same"
    assert ar.lineage_relation(table, "U", "U").verdict == "same"
    assert ar.LINEAGE_VERDICTS == ("same", "distinct", "undeclared")
    with pytest.raises(ValueError):
        ar.lineage_relation(table, "U", "Nobody")
    json.dumps(by_relation.as_dict())


# --------------------------------------------------------------------------------------------------- R1: what contradicts
def conflict_code(agents, relations):
    return code_of(lambda: ar.table_from_dicts(agents, [fallback("implement", [agents[0]["id"]])],
                                               lineage_relations=relations))


def test_R1_relation_same_and_distinct_for_one_pair_are_a_conflict():
    agents = [plain("A", ["implement"]), plain("B", ["implement"])]
    assert conflict_code(agents, [relation("A", "B", "same"), relation("B", "A", "distinct")]) == "LINEAGE_CONFLICT"


def test_R1_relation_a_same_relation_between_two_different_labels_is_a_conflict():
    agents = [plain("A", ["implement"], "Claude系"), plain("B", ["implement"], "Anthropic系")]
    assert conflict_code(agents, [relation("A", "B", "same")]) == "LINEAGE_CONFLICT"


def test_R1_relation_a_distinct_relation_between_two_agents_of_one_label_is_a_conflict():
    agents = [plain("A", ["implement"], "Claude系"), plain("B", ["implement"], "Claude系")]
    assert conflict_code(agents, [relation("A", "B", "distinct")]) == "LINEAGE_CONFLICT"


def test_R1_relation_a_distinct_relation_across_a_chain_of_same_relations_is_a_conflict():
    agents = [plain("X", ["implement"]), plain("Y", ["implement"]), plain("Z", ["implement"])]
    chain = [relation("X", "Y", "same"), relation("Y", "Z", "same")]
    assert conflict_code(agents, chain + [relation("Z", "X", "distinct")]) == "LINEAGE_CONFLICT"
    assert conflict_code(agents, [relation("Z", "X", "distinct")] + chain[::-1]) == "LINEAGE_CONFLICT"


def test_R1_relation_the_two_names_of_one_lineage_given_as_labels_are_two_lineages_not_one():
    """A producer that cannot tell Claude系 from Anthropic系 must not label both: the labels say two lineages."""
    table = two([], labels=("Claude系", "Anthropic系"))
    assert ar.lineage_relation(table, "Sonnet", "luna").verdict == "distinct"


def test_R1_relation_the_other_checks_of_a_relation_each_have_their_own_code():
    agents = [plain("A", ["implement"]), plain("B", ["implement"])]
    assert conflict_code(agents, [relation("A", "Ghost", "distinct")]) == "UNKNOWN_AGENT_REF"
    assert conflict_code(agents, [relation("Ghost", "A", "same")]) == "UNKNOWN_AGENT_REF"
    assert conflict_code(agents, [relation("A", "A", "same")]) == "BAD_VALUE"
    assert conflict_code(agents, [relation("A", "B", "similar")]) == "BAD_VALUE"
    assert conflict_code(agents, [relation("A", "B", "same"), relation("A", "B", "same")]) == "DUPLICATE_LINEAGE_RELATION"
    assert conflict_code(agents, [relation("A", "B", "distinct"), relation("B", "A", "distinct")]) == \
        "DUPLICATE_LINEAGE_RELATION"
    basis = ar.Basis.text("t", "x")
    bad_basis = ar.LineageRelation("A", "B", "distinct", "not a basis")          # type: ignore[arg-type]
    records = [ar.AgentRecord(item["id"], "codex", frozenset({"implement"}), basis) for item in agents]
    fallbacks = [ar.RoutingRule("D", (ar.Condition("role", "implement"),), ("A",), None, basis, True)]
    assert code_of(lambda: ar.build_routing_table(records, fallbacks, (), [bad_basis])) == "BAD_VALUE"
    assert {"LINEAGE_CONFLICT", "DUPLICATE_LINEAGE_RELATION"} <= set(ar.RECORD_ERRORS)


def test_R1_relation_a_table_that_says_no_relation_is_built_as_before():
    table = ar.build_routing_table(
        [ar.AgentRecord("A", "codex", frozenset({"implement"}), ar.Basis.text("t", "x"))],
        [ar.RoutingRule("D", (ar.Condition("role", "implement"),), ("A",), None, ar.Basis.text("t", "x"), True)])
    assert table.lineage_relations == ()


# --------------------------------------------------------------------------------------------------- order and direction
def rich_agents():
    return [plain("X", ["implement"]), plain("Y", ["verify"]), plain("Z", ["verify"]), plain("W", ["verify"])]


def rich_relations(*, swapped: bool, reverse: bool):
    items = [relation("X", "Y", "same", "X と Y は同じ。"), relation("Z", "Y", "distinct", "Z は Y と別。"),
             relation("W", "X", "distinct", "W は X と別。")]
    if swapped:
        items = [{**item, "a": item["b"], "b": item["a"]} for item in items]
    return items[::-1] if reverse else items


def rich_table(**kind):
    return ar.table_from_dicts(rich_agents(), [fallback("implement", ["X"]), fallback("verify", ["Z", "W"])],
                               lineage_relations=rich_relations(**kind))


def canonical(basis):
    return {role: sorted(json.dumps(item, sort_keys=True) for item in items) for role, items in basis.items()}


def test_R1_relation_the_order_and_direction_of_the_relations_change_neither_the_decision_nor_its_grounds():
    results = []
    for swapped in (False, True):
        for reverse in (False, True):
            decision = verify_request(rich_table(swapped=swapped, reverse=reverse), used_agents={"implement": ("X",)})
            results.append((decision.agent_id, decision.essence(), canonical(decision.independence_basis),
                            [e.as_dict() for e in decision.excluded]))
    assert results[0][0] == "Z" and all(item == results[0] for item in results)
    entry = verify_request(rich_table(swapped=False, reverse=False),
                           used_agents={"implement": ("X",)}).independence_basis["implement"][0]
    assert [item["relation"] for item in entry["relations"]] == ["distinct"] and len(entry["joined_by"]) == 1


def test_R1_relation_the_closure_does_not_depend_on_the_order_of_the_agents_either():
    forward = ar.lineage_relation(rich_table(swapped=False, reverse=False), "Z", "X")
    agents = rich_agents()[::-1]
    backward = ar.table_from_dicts(agents, [fallback("implement", ["X"]), fallback("verify", ["Z", "W"])],
                                   lineage_relations=rich_relations(swapped=True, reverse=True))
    assert ar.lineage_relation(backward, "Z", "X").as_dict() == forward.as_dict()


# --------------------------------------------------------------------------------------------------- the request
def test_R3_relation_a_request_may_not_name_one_role_in_both_used_agents_and_used_lineages():
    with pytest.raises(ValueError):
        ar.RoutingRequest("j", "verify", "verification", "small", used_agents={"implement": ("A",)},
                          used_lineages={"implement": ("openai",)})
    ok = ar.RoutingRequest("j", "verify", "verification", "small", used_agents={"implement": ("A",)},
                           used_lineages={"review": ("openai",)})
    assert ok.used_agents == {"implement": ("A",)}
    with pytest.raises(ValueError):
        ar.RoutingRequest("j", "verify", "verification", "small", used_agents={"implement": ("",)})


def test_R3_relation_a_used_agent_that_is_not_in_the_table_is_a_callers_mistake():
    table = two([relation("Sonnet", "luna", "distinct")])
    with pytest.raises(ValueError):
        verify_request(table, used_agents={"implement": ("Ghost",)})


def test_R3_relation_an_unused_role_is_still_prior_role_unused_not_undeclared():
    decision = verify_request(two([relation("Sonnet", "luna", "distinct")]))
    assert {e.reason for e in decision.excluded} == {"PRIOR_ROLE_UNUSED"}


def test_R3_relation_every_used_agent_of_the_candidates_lineage_is_named_none_is_picked():
    table = ar.table_from_dicts(
        [plain("X", ["implement"]), plain("Y", ["implement"]), plain("Z", ["verify"])],
        [fallback("implement", ["X", "Y"]), fallback("verify", ["Z"])],
        lineage_relations=[relation("X", "Z", "same"), relation("Y", "Z", "same")])
    decision = verify_request(table, used_agents={"implement": ("Y", "X")})
    assert decision.agent_id is None
    detail = decision.excluded[0].detail
    assert decision.excluded[0].reason == "SAME_LINEAGE" and "X (" in detail and "Y (" in detail


def test_R1_relation_every_conflict_is_in_the_message_of_the_one_error():
    agents = [plain("A", ["implement"], "L1"), plain("B", ["implement"], "L2"), plain("C", ["implement"], "L3"),
              plain("D", ["implement"], "L3")]
    with pytest.raises(ar.RoutingRecordError) as info:
        ar.table_from_dicts(agents, [fallback("implement", ["A"])],
                            lineage_relations=[relation("A", "B", "same"), relation("C", "D", "distinct")])
    assert info.value.code == "LINEAGE_CONFLICT"
    assert "L1" in info.value.message and "'distinct' between C and D" in info.value.message
