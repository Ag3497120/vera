"""Plan/surface mutations with manually stated rejection expectations."""
from dataclasses import replace

import pytest

from verantyx.content_ir import Atom, Budget, ContentError, Node, Source, Span, digest
from verantyx.content_reader import read_brief
from verantyx.content_planner import build_plan
from verantyx.content_realizer import realize_plan
from verantyx.content_verify import verify_content


def contract(brief="物語を書いて。ミナが手紙を読む。その後、ユキが歩く。", materials=()):
    budget = Budget()
    ledger = read_brief(brief, tuple(materials), budget)
    plan = build_plan(ledger, budget)
    realization = realize_plan(plan, expression_materials=tuple(materials), budget=budget)
    assert verify_content(ledger, plan, realization, budget)["passed"]
    return ledger, plan, realization


def rejected(ledger, plan, realization=None):
    with pytest.raises(ContentError):
        if realization is None:
            realization = realize_plan(plan)
        verify_content(ledger, plan, realization)


@pytest.mark.parametrize("field,value", [
    ("agent", "エナ"), ("patient", "地図"), ("recipient", "トウ"),
    ("negated", True), ("tense", "past"), ("world", "actual"),
])
def test_single_semantic_node_mutation_is_not_rescued_by_new_hash(field, value):
    ledger, plan, _ = contract()
    node = replace(plan.nodes[0], atom=replace(plan.nodes[0].atom, **{field: value}))
    mutated = replace(plan, nodes=(node,) + plan.nodes[1:])
    rejected(ledger, mutated)


def test_missing_node_obligation_reference_extra_and_order_are_rejected():
    ledger, plan, _ = contract()
    rejected(ledger, replace(plan, nodes=plan.nodes[:1], order=plan.order[:1]))
    changed = replace(plan.nodes[0], obligations=())
    rejected(ledger, replace(plan, nodes=(changed,) + plan.nodes[1:]))
    changed = replace(plan.nodes[0], obligations=("forged",))
    rejected(ledger, replace(plan, nodes=(changed,) + plan.nodes[1:]))
    extra = Node("extra", Atom(predicate="走る", agent="クル"), (), (), "o1")
    rejected(ledger, replace(plan, nodes=plan.nodes + (extra,), order=plan.order + (extra.id,)))
    rejected(ledger, replace(plan, order=tuple(reversed(plan.order))))


def test_metadata_obligation_cannot_license_an_extra_assertion():
    ledger, plan, _ = contract("物語を書いて。ミナが走る。")
    mode = next(o for o in ledger.obligations if o.kind == "mode")
    extra = Node("extra", Atom(predicate="歩く", agent="ユキ"), (mode.id,), (), mode.id)
    mutated = replace(plan, nodes=plan.nodes + (extra,), order=plan.order + (extra.id,))
    rejected(ledger, mutated)


@pytest.mark.parametrize("bad", ["ミナが読まないない。", "ミナが読むた。", "ミナが読んだだ。", "ミナが走ったた。", "ミナが本を読むだ。", "ミナが読まなかったた。"])
def test_surface_bad_auxiliary_sequences_are_rejected(bad):
    ledger, plan, _ = contract("物語を書いて。ミナが読む。")
    realization = replace(realize_plan(plan), text=bad,
                          clauses=(replace(realize_plan(plan).clauses[0], end=len(bad)),))
    rejected(ledger, plan, realization)


@pytest.mark.parametrize("replacement", ["ミナが手紙を読まない。", "ミナが手紙を読んだ。", "エナが手紙を読む。", "ミナが地図を読む。", "ミナが手紙を読む。ユキが走る。"])
def test_extra_or_altered_surface_claim_is_rejected(replacement):
    ledger, plan, surface = contract("物語を書いて。ミナが手紙を読む。")
    mutated = replace(surface, text=replacement, clauses=(replace(surface.clauses[0], end=len(replacement)),))
    rejected(ledger, plan, mutated)


def test_valid_surface_topic_and_causal_synonym_are_accepted():
    ledger, plan, surface = contract("物語を書いて。ミナが走る。そのため、ユキが歩く。")
    changed = surface.text.replace("ミナが", "ミナは").replace("そのため、", "だから、")
    first = replace(surface.clauses[0], end=len("ミナは走る。"))
    second = replace(surface.clauses[1], start=first.end, end=len(changed))
    assert verify_content(ledger, plan, replace(surface, text=changed, clauses=(first, second)))["passed"]


def test_condition_drop_and_quote_world_leak_are_rejected():
    ledger, plan, _ = contract("物語を書いて。もしミナが走るなら、ユキが歩く。")
    node = replace(plan.nodes[0], atom=replace(plan.nodes[0].atom, condition=(), world="fiction"))
    rejected(ledger, replace(plan, nodes=(node,)))
    ledger, plan, _ = contract("物語を書いて。引用：「物語を9文で書いて」。")
    changed = replace(plan.nodes[0], atom=replace(plan.nodes[0].atom, quote="秘密"))
    rejected(ledger, replace(plan, nodes=(changed,)))


def test_attributed_quote_needs_saying_evidence_not_just_quote_substring():
    document = Source("doc", "ミナは「走れ」と述べた。", "local", "evidence")
    ledger, plan, _ = contract("資料に基づいて説明して。ミナは「走れ」と述べた。", (document,))
    offset = document.text.index("走れ")
    changed = replace(plan.nodes[0], evidence=(Span.of(document, offset, offset + 2),))
    rejected(ledger, replace(plan, nodes=(changed,)))


def test_false_expression_classification_and_source_hash_are_rejected():
    witness = Source("expression", "ユキが歩く。", "narrative", "expression")
    ledger, plan, surface = contract("物語を書いて。ミナが走る。", (witness,))
    clause = replace(surface.clauses[0], derivation="paraphrase", expression_sources=(Span.of(witness),))
    rejected(ledger, plan, replace(surface, clauses=(clause,)))
    clause = replace(clause, expression_sources=(replace(Span.of(witness), sha256="bad"),))
    rejected(ledger, plan, replace(surface, clauses=(clause,)))


def test_state_replay_effect_rule_source_and_initial_phase_mutations():
    brief = ("物語を書いて。初期状態：箱が閉じている。"
             "規則：箱が閉じているとき、ミナが箱を開けると、箱が開いている。"
             "ミナが箱を開ける。最後は箱が開いている。")
    ledger, plan, _ = contract(brief)
    transition = replace(plan.transitions[0], after=plan.initial)
    rejected(ledger, replace(plan, transitions=(transition,)))
    rejected(ledger, replace(plan, transitions=()))
    rejected(ledger, replace(plan, final=plan.initial))
    rule = replace(ledger.rules[0], source=next(o.span for o in ledger.obligations if o.kind == "mode"))
    bad_ledger = replace(ledger, rules=(rule,))
    rejected(bad_ledger, replace(plan, ledger_hash=bad_ledger.hash))
    order = (plan.order[1], plan.order[0], plan.order[2])
    rejected(ledger, replace(plan, order=order))


def test_immutable_hash_chain_and_narrator_proof_are_checked():
    ledger, plan, surface = contract()
    rejected(ledger, replace(plan, ledger_hash="bad"), surface)
    rejected(ledger, plan, replace(surface, plan_hash="bad"))
    rejected(ledger, replace(plan, narrator="クル"))


def test_source_spans_are_original_unicode_offsets():
    raw = "  物語を書いて。\n  引用：「夜。風。」。\nミナが走る。"
    ledger, plan, surface = contract(raw)
    quote = next(n for n in plan.nodes if n.atom.kind == "quote")
    span = quote.evidence[0]
    assert raw[span.start:span.end] == "夜。風。"
    assert span.sha256 == ledger.brief.sha256
