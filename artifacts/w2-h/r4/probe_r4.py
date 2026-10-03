"""Round 4 probes (read-only): the ticket's own example sentences become records without inventing values.

(a1)(a2): F9, a job assigned with no role named.  (b1)(b2)(b3'): F8, lineage as a relation between agents.
Run:  PYTHONPATH=<tree> python probe_r4.py
"""
import json

from verantyx import agent_routing as ar

W = "チケットの例文"


def attempt(label, fn):
    try:
        out = fn()
        print(f"{label}: ok -> {out}")
    except ar.RoutingRecordError as exc:
        print(f"{label}: {exc.code} {exc.message}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: {type(exc).__name__} {exc}")


def fallback(rule_id, role, prefer):
    return {"id": rule_id, "when": {"role": role}, "prefer": prefer, "fallback": True, "witness": "x"}


# (a1) 「攻撃と大きなファイルの読解は codex gpt-6-luna xhigh」: kinds are said, no role is said.
def kind_only_agent():
    table = ar.table_from_dicts(
        [{"id": "gpt-6-luna xhigh", "adapter": "codex", "model": "gpt-6-luna", "effort": "xhigh",
          "kinds": ["attack", "read_large_file"], "witness": W}],
        [{"id": "r_attack", "when": {"kind": "attack"}, "prefer": ["gpt-6-luna xhigh"], "witness": W}])
    decision = ar.route(table, ar.RoutingRequest("j", "review", "attack", "small"))
    return (decision.agent_id, decision.stage, decision.decided_by, decision.role_fit)


attempt("(a1) agent with kinds only, rule kind=attack only: role=review kind=attack", kind_only_agent)


# (a2) a rule `kind=attack => luna` for an agent that declares its roles (ticket grammar: role= is not required).
def kind_only_rule_with_roles():
    agents = [{"id": "luna", "adapter": "codex", "roles": ["review", "read"], "kinds": ["attack", "read_large_file"],
               "witness": W}]
    rules = [{"id": "r_attack", "when": {"kind": "attack"}, "prefer": ["luna"], "witness": W},
             fallback("fb_review", "review", ["luna"]), fallback("fb_read", "read", ["luna"])]
    table = ar.table_from_dicts(agents, rules)
    decision = ar.route(table, ar.RoutingRequest("j", "review", "attack", "small"))
    return (decision.agent_id, decision.decided_by, decision.role_fit)


attempt("(a2) rule with kind=attack and no role, agent declares roles", kind_only_rule_with_roles)

REL = "Sonnet と luna は別系統。"


# (b1) 「Sonnet と luna は別系統」: a relation, no lineage name said.
def relation_only():
    agents = [{"id": "Sonnet", "adapter": "claude", "roles": ["implement"], "witness": REL},
              {"id": "luna", "adapter": "codex", "roles": ["verify"], "witness": REL}]
    rules = [fallback("fi", "implement", ["Sonnet"]), fallback("fv", "verify", ["luna"])]
    table = ar.table_from_dicts(agents, rules, lineage_relations=[
        {"a": "Sonnet", "b": "luna", "relation": "distinct", "witness": REL}])
    decision = ar.route(table, ar.RoutingRequest("j", "verify", "verification", "small",
                                                 used_agents={"implement": ("Sonnet",)}))
    basis = decision.independence_basis["implement"][0]
    return (decision.agent_id, decision.independence, basis["verdict"], basis["labels"],
            basis["relations"][0]["basis"]["witnesses"])


attempt("(b1) only the relation said (no lineage names): verify after Sonnet", relation_only)


# (b2) three agents, only A!=B and A!=C said: B versus C is not said, and is not made up either way.
def three():
    agents = [{"id": "A", "adapter": "claude", "roles": ["implement"], "witness": "A と B、A と C は別系統。"},
              {"id": "B", "adapter": "codex", "roles": ["implement"], "witness": "A と B は別系統。"},
              {"id": "C", "adapter": "codex", "roles": ["verify"], "witness": "A と C は別系統。"}]
    rules = [fallback("fi", "implement", ["B"]), fallback("fv", "verify", ["C"])]
    table = ar.table_from_dicts(agents, rules, lineage_relations=[
        {"a": "A", "b": "B", "relation": "distinct", "witness": "A と B は別系統。"},
        {"a": "A", "b": "C", "relation": "distinct", "witness": "A と C は別系統。"}])
    decision = ar.route(table, ar.RoutingRequest("j", "verify", "verification", "small",
                                                 used_agents={"implement": ("B",)}))
    return (decision.agent_id, decision.undecided_reason, [(e.agent_id, e.reason) for e in decision.excluded],
            ar.lineage_relation(table, "B", "C").verdict)


attempt("(b2) A!=B and A!=C only: verify candidate C after implementer B", three)


# (b3') a producer that cannot tell whether two names are one lineage gives no label and passes the relation.
def alias_by_relation():
    agents = [{"id": "Sonnet", "adapter": "claude", "roles": ["implement"], "witness": "Sonnet は Claude系。"},
              {"id": "Opus", "adapter": "claude", "roles": ["verify"], "witness": "Opus は Anthropic系。"}]
    rules = [fallback("fi", "implement", ["Sonnet"]), fallback("fv", "verify", ["Opus"])]
    table = ar.table_from_dicts(agents, rules, lineage_relations=[
        {"a": "Sonnet", "b": "Opus", "relation": "same", "witness": "Claude系 と Anthropic系 は同じ系統。"}])
    decision = ar.route(table, ar.RoutingRequest("j", "verify", "verification", "small",
                                                 used_agents={"implement": ("Sonnet",)}))
    return (decision.agent_id, decision.undecided_reason, [(e.agent_id, e.reason, e.detail) for e in decision.excluded])


attempt("(b3') no labels, relation same: verify after Sonnet", alias_by_relation)


# note: labelling both names (Claude系 / Anthropic系) is an input that breaks the labels-are-a-partition promise
def alias_by_two_labels():
    agents = [{"id": "Sonnet", "adapter": "claude", "roles": ["implement"], "lineage": "Claude系", "witness": "x"},
              {"id": "Opus", "adapter": "claude", "roles": ["verify"], "lineage": "Anthropic系", "witness": "x"}]
    rules = [fallback("fi", "implement", ["Sonnet"]), fallback("fv", "verify", ["Opus"])]
    table = ar.table_from_dicts(agents, rules)
    decision = ar.route(table, ar.RoutingRequest("j", "verify", "verification", "small",
                                                 used_agents={"implement": ("Sonnet",)}))
    return (decision.agent_id, decision.independence, "(a broken promise: two labels mean two lineages)")


attempt("(b3-note) both names given as labels", alias_by_two_labels)


# the broken promise is caught when a relation then contradicts the labels
def labels_and_same():
    agents = [{"id": "Sonnet", "adapter": "claude", "roles": ["implement"], "lineage": "Claude系", "witness": "x"},
              {"id": "Opus", "adapter": "claude", "roles": ["verify"], "lineage": "Anthropic系", "witness": "x"}]
    rules = [fallback("fi", "implement", ["Sonnet"]), fallback("fv", "verify", ["Opus"])]
    return ar.table_from_dicts(agents, rules, lineage_relations=[
        {"a": "Sonnet", "b": "Opus", "relation": "same", "witness": "同じ系統。"}])


attempt("(b3-conflict) both labelled and a same relation between them", labels_and_same)
print(json.dumps({"relation_vocabulary": list(ar.LINEAGE_RELATIONS), "verdicts": list(ar.LINEAGE_VERDICTS)},
                 ensure_ascii=False))
