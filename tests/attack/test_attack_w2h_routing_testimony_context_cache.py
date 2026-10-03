# W5-a: copied from attacks/W2-h/test_attack_routing_testimony_context_cache.py; unchanged
"""W2-h attack: a cached tie result ignores changed candidate testimony."""
from __future__ import annotations

from verantyx.agent_routing import RoutingRequest, route, table_from_dicts
from verantyx.llm_choice import ChoiceLedger, LLMChooser, ProviderReply


class Replies:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        return ProviderReply.success(next(self.answers))


def table(reason_a: str, reason_b: str):
    agents = [
        {"id": "A", "adapter": "codex", "roles": ["implement"], "kinds": ["feature"],
         "lineage": "one", "witness": "A is an implementation agent."},
        {"id": "B", "adapter": "claude", "roles": ["implement"], "kinds": ["feature"],
         "lineage": "two", "witness": "B is an implementation agent."},
    ]
    rules = [
        {"id": "PICK_A", "when": {"role": "implement", "kind": "feature"}, "prefer": ["A"],
         "reason": reason_a, "witness": "The human's routing rule for A."},
        {"id": "PICK_B", "when": {"role": "implement", "kind": "feature"}, "prefer": ["B"],
         "reason": reason_b, "witness": "The human's routing rule for B."},
        {"id": "DEFAULT", "when": {"role": "implement"}, "prefer": ["A"], "fallback": True,
         "reason": "Use A otherwise.", "witness": "The human's fallback rule."},
    ]
    return table_from_dicts(agents, rules)


def test_routing_tie_cache_reuses_old_choice_after_candidate_reasons_change(tmp_path):
    # First testimony favors A. If asked again after the declared reasons flip, both fresh replies favor B.
    provider = Replies(['{"choice":0}', '{"choice":1}', '{"choice":1}', '{"choice":0}'])
    orders = iter(([0, 1], [1, 0], [0, 1], [1, 0]))
    chooser = LLMChooser(provider, ChoiceLedger(tmp_path / "routing_choice.jsonl"),
                         order_source=lambda n: next(orders))
    request = RoutingRequest("job", "implement", "feature", "small")

    first = route(table("A is the clear best fit.", "B is less suitable."), request,
                  chooser_factory=lambda: chooser)
    second = route(table("A is less suitable.", "B is the clear best fit."), request,
                   chooser_factory=lambda: chooser)

    assert first.agent_id == "A" and first.testimony["cached"] is False
    # A current-input decision would re-ask and choose B; the cache instead returns the stale A testimony.
    assert second.agent_id == "B", (
        f"actual agent_id={second.agent_id!r}, cached={second.testimony['cached']!r}, "
        f"provider_asks={len(provider.prompts)}, current reasons favor B"
    )
