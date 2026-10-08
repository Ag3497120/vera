"""W5-e A-3 attack: the source labels alone should not authenticate a sovereign record.

The probe exercises the public policy path with constructed input only.  The
constructed source is deliberately not treated as evidence by this test; it
checks whether the classifier nevertheless promotes its labels to HUMAN.
"""

from verantyx import basis_policy as bp


def _result(source):
    return {
        "kind": "answer",
        "verdict": "ANSWER",
        "text": "The report says it rained.",
        "door": "chat",
        "sources": [source],
        "evidence": [source["text"]],
        "trace": [],
    }


def test_a3_unverified_memory_sovereign_labels_do_not_make_human_basis():
    variants = [
        ("no_ids", {}),
        ("store_id_only", {"store_id": "unverified-store"}),
        ("confirm_id_only", {"confirm_id": "unverified-confirmation"}),
        ("empty_ids", {"store_id": "", "confirm_id": ""}),
    ]
    observed = []
    for name, identity in variants:
        source = {
            "family": "memory_sovereign",
            "origin": "human_confirmed",
            "source": "caller-claim",
            "text": "The report says it rained.",
            **identity,
        }
        classification = bp.classify_sources([source])
        out, _ = bp.apply_to_ask(
            _result(source), bp.AskPolicy(), query="Did it rain?", mode="legacy", documents=[]
        )
        observed.append((name, classification.policy_basis, out["basis_policy"]["outcome"],
                         out["basis_policy"]["counts"]))

    assert all(basis == bp.UNKNOWN_ORIGIN and outcome == "ABSTAIN"
               for _, basis, outcome, _ in observed), observed
