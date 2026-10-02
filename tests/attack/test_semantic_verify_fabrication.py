from dataclasses import replace

import pytest

from verantyx.semantic_ir import Meter, Proof, ProofNode, Span, Variable
from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_verify import Checker, Conflict, Rejected, license_clause


def _view(text):
    view = document_view({"doc": text}, sovereigns={"doc": "doc"})
    assert not view.invalid
    return view


def _request_plan():
    request = read_request("何が花子を見た？")
    assert len(request.plans) == 1
    return request, request.plans[0]


def _proof(request, clause, source_clause=None):
    plan = request.plans[0]
    bind = next(op for op in plan.nodes if op.op == "Bind")
    env = {}
    for role_name, term in bind.pattern.roles:
        if isinstance(term, Variable):
            role = next(role for role in clause.roles if role.name == role_name)
            env[term.name] = role.term
    bindings = tuple(sorted(env.items()))
    proof_nodes = [ProofNode("source", "Source", clause=source_clause or clause)]
    plan_ids = {}
    covers = {}
    for op in plan.nodes:
        parents = ("source",) if op.op == "Bind" else tuple(plan_ids[i] for i in op.inputs)
        inherited = set(op.obligations)
        for parent in op.inputs:
            inherited.update(covers[parent])
        answer = ()
        if op.op == "Project":
            answer = tuple((out.label, env[out.term.name] if isinstance(out.term, Variable) else out.term)
                           for out in op.outputs)
        proof_id = "proof_" + op.id
        proof_nodes.append(ProofNode(proof_id, op.op, plan_node=op.id, parents=parents,
                                     bindings=bindings, covers=tuple(sorted(inherited)), answer=answer))
        plan_ids[op.id] = proof_id
        covers[op.id] = inherited
    return Proof(tuple(proof_nodes), plan_ids[plan.root], clause.sovereign)


def test_original_frame_clause_is_licensed_against_its_source():
    view = _view("太郎は花子を見た。")
    clause = view.clauses[0]

    assert clause.span.text == "太郎は花子を見た。"
    license_clause(clause, view)


def test_swapped_frame_entities_are_rejected_even_when_spans_follow_them():
    view = _view("太郎は花子を見た。")
    clause = view.clauses[0]
    agent = next(role for role in clause.roles if role.name == "agent")
    patient = next(role for role in clause.roles if role.name == "patient")
    roles = tuple(
        replace(role,
                term=patient.term if role.name == "agent" else agent.term,
                span=patient.span if role.name == "agent" else agent.span)
        if role.name in ("agent", "patient") else role
        for role in clause.roles
    )
    forged = replace(clause, roles=roles)
    forged_view = replace(view, clauses=(forged,))

    with pytest.raises(Rejected):
        license_clause(forged, forged_view)


def test_negative_source_cannot_be_relabelled_as_positive():
    view = _view("太郎は花子を見なかった。")
    clause = view.clauses[0]
    assert clause.polarity == "-"
    license_clause(clause, view)

    forged = replace(clause, polarity="+")
    forged_view = replace(view, clauses=(forged,))
    with pytest.raises(Rejected):
        license_clause(forged, forged_view)


def test_partial_sentence_span_is_not_a_licensed_event_source():
    text = "太郎は花子を見た。"
    view = _view(text)
    clause = view.clauses[0]
    partial_text = clause.span.text[:-1]
    partial = Span(clause.span.source, clause.span.start, clause.span.end - 1, partial_text)
    forged = replace(clause, span=partial, body_span=partial)
    forged_view = replace(view, clauses=(forged,))

    with pytest.raises(Rejected):
        license_clause(forged, forged_view)


def test_unresolved_opposing_claims_raise_conflict_instead_of_answering():
    view = _view("太郎は花子を見た。太郎は花子を見なかった。")
    _, plan = _request_plan()

    with pytest.raises(Conflict):
        Checker(view, "doc", Meter()).audit(plan)


def test_replayed_proof_returns_the_source_supported_actor():
    view = _view("太郎は花子を見た。")
    request, plan = _request_plan()
    answer = Checker(view, "doc", Meter()).proof(request, plan, _proof(request, view.clauses[0]))

    assert answer == (("agent", "太郎"),)


def test_proof_answer_cannot_swap_in_an_entity_not_bound_by_replay():
    view = _view("太郎は花子を見た。")
    request, plan = _request_plan()
    proof = _proof(request, view.clauses[0])
    last = replace(proof.nodes[-1], answer=(("agent", "花子"),))
    forged = replace(proof, nodes=(*proof.nodes[:-1], last))

    with pytest.raises(Rejected):
        Checker(view, "doc", Meter()).proof(request, plan, forged)


def test_proof_cannot_splice_a_clause_from_another_sovereign():
    view = _view("太郎は花子を見た。")
    request, plan = _request_plan()
    foreign = replace(view.clauses[0], sovereign="another-document")
    proof = _proof(request, view.clauses[0], source_clause=foreign)

    with pytest.raises(Rejected):
        Checker(view, "doc", Meter()).proof(request, plan, proof)


def test_gate_rejects_an_omitted_source_supported_answer():
    view = _view("太郎は花子を見た。")
    request, plan = _request_plan()

    with pytest.raises(Rejected):
        Checker(view, "doc", Meter()).gate(request, plan, [])


def test_gate_accepts_a_complete_replayed_answer_proposal():
    view = _view("太郎は花子を見た。")
    request, plan = _request_plan()
    answer = (("agent", "太郎"),)
    result = Checker(view, "doc", Meter()).gate(
        request, plan, [(answer, _proof(request, view.clauses[0]))]
    )

    assert set(result) == {answer}


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: correction marker leaves the earlier actor answer eligible",
)
def test_correction_does_not_leave_the_superseded_actor_as_an_answer():
    view = _view("太郎は花子を見た。いや、次郎は花子を見た。")
    request, plan = _request_plan()
    proposals = []
    for actor in ("太郎", "次郎"):
        clause = next(c for c in view.clauses if any(r.name == "agent" and r.term == actor for r in c.roles))
        answer = (("agent", actor),)
        proposals.append((answer, _proof(request, clause)))

    result = Checker(view, "doc", Meter()).gate(request, plan, proposals)

    assert set(result) == {(("agent", "次郎"),)}
