"""Shared fixtures for the W2-h routing tests (no tests of its own).

One description of a routing table is kept as plain Python data (``Spec``); two producers turn it into records:
the dictionary producer (``verantyx.agent_routing.table_from_dicts``, which has nothing to do with the frame
DSL) and the DSL producer (rows of text read by ``verantyx.project_frame.parse_frame``).  The tests compare
the decisions the router makes from the two.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from test_conduct_entry_support import MINIMAL_FRAME  # noqa: F401

ALL_KINDS = ["small_fix", "feature", "large_refactor", "test_authoring", "review", "verification", "attack",
             "bulk_generation", "read_large_file", "closed_choice"]


def agent(agent_id: str, *, adapter: str = "codex", lineage: str = "openai", roles=("implement",),
          kinds=("feature", "small_fix"), model: str = "gpt-6-luna", effort: str = "low", concurrency: int = 1,
          note: str | None = None) -> dict[str, Any]:
    return {"id": agent_id, "adapter": adapter, "model": model, "effort": effort, "roles": list(roles),
            "kinds": list(kinds), "lineage": lineage, "concurrency": concurrency, "note": note,
            "witness": f"{agent_id} is a {lineage} agent that the human described"}


def rule(rule_id: str, when: dict[str, str], prefer, reason: str = "the human said so") -> dict[str, Any]:
    return {"id": rule_id, "when": dict(when), "prefer": list(prefer), "reason": reason,
            "witness": f"for {rule_id} the human wrote: {reason}"}


def default(role: str, prefer) -> dict[str, Any]:
    """The role's "otherwise".  In the DSL its row is named DEFAULT; in a record it is the field ``fallback``."""
    return {**rule("DEFAULT", {"role": role}, prefer, f"the fallback for {role}"), "fallback": True}


def precedence(prec_id: str, higher: str, lower: str, reason: str = "the human ordered them") -> dict[str, Any]:
    return {"id": prec_id, "higher": higher, "lower": lower, "reason": reason,
            "witness": f"{prec_id}: {higher} comes before {lower}"}


@dataclass
class Spec:
    agents: list
    rules: list
    precedence: list = field(default_factory=list)

    def permuted(self, which: str) -> "Spec":
        """The same description with its rows in another order (nothing else changes)."""
        if which == "reverse":
            return Spec(self.agents[::-1], self.rules[::-1], self.precedence[::-1])
        k = 2
        rot = lambda xs: xs[k % max(len(xs), 1):] + xs[:k % max(len(xs), 1)]  # noqa: E731
        return Spec(rot(self.agents), rot(self.rules), rot(self.precedence))


def renamed(spec: Spec) -> Spec:
    """The same description with every rule given another name (the way a reader of prose would name them)."""
    names = {}
    for item in spec.rules:
        if not item.get("fallback"):
            names[item["id"]] = "prose_" + item["id"].lower()
    rules = [{**item, "id": ("fallback_for_" + item["when"]["role"]) if item.get("fallback") else names[item["id"]]}
             for item in spec.rules]
    precedence_ = [{**item, "id": "order_" + item["id"].lower(), "higher": names[item["higher"]],
                    "lower": names[item["lower"]]} for item in spec.precedence]
    return Spec(spec.agents, rules, precedence_)


def dict_table(spec: Spec):
    from verantyx.agent_routing import table_from_dicts

    return table_from_dicts(spec.agents, spec.rules, spec.precedence)


def agent_row(item: dict[str, Any]) -> str:
    parts = [f"adapter={item['adapter']}", f"model={item['model']}", f"effort={item['effort']}",
             f"roles={','.join(item['roles'])}", f"kinds={','.join(item['kinds'])}", f"lineage={item['lineage']}",
             f"concurrency={item['concurrency']}"]
    if item.get("note"):
        parts.append(f"note={item['note']}")
    return f"{item['id']}: " + " ".join(parts)


def rule_row(item: dict[str, Any]) -> str:
    when = " & ".join(f"{k}={v}" for k, v in item["when"].items())
    return f"{item['id']}: {when} => {', '.join(item['prefer'])}: {item['reason']}"


def precedence_row(item: dict[str, Any]) -> str:
    return f"{item['id']}: {item['higher']} > {item['lower']}: {item['reason']}"


def dsl_tail(spec: Spec, *, settings: tuple[str, ...] = ()) -> str:
    lines = []
    if settings:
        lines += ["[agent_settings]", *settings]
    lines += ["[agents]", *[agent_row(a) for a in spec.agents], "[routing]", *[rule_row(r) for r in spec.rules]]
    if spec.precedence:
        lines += ["[routing_precedence]", *[precedence_row(p) for p in spec.precedence]]
    return "\n".join(lines) + "\n"


def dsl_table(spec: Spec):
    """The DSL producer: the table that ``parse_frame`` makes from the rows of the same description."""
    from verantyx.project_frame import parse_frame

    return parse_frame(MINIMAL_FRAME + dsl_tail(spec), source="spec.md").routing


# ---------------------------------------------------------------------------- a reusable description
def standard_spec() -> Spec:
    """Two lineages: openai (codex) implements and generates, anthropic (claude) verifies and reviews."""
    return Spec(
        agents=[
            agent("CodexImpl", roles=("implement",), kinds=("small_fix", "feature", "large_refactor")),
            agent("ClaudeImpl", adapter="claude", lineage="anthropic", model="claude-sonnet-5-5", roles=("implement",),
                  kinds=("small_fix", "feature", "large_refactor")),
            agent("ClaudeVerify", adapter="claude", lineage="anthropic", model="claude-sonnet-5-5",
                  roles=("verify",), kinds=("verification",)),
            agent("CodexVerify", roles=("verify",), kinds=("verification",)),
            agent("ClaudeReview", adapter="claude", lineage="anthropic", model="claude-opus-5-5",
                  roles=("review", "answer"), kinds=("review", "closed_choice")),
            agent("CodexBulk", roles=("generate",), kinds=("bulk_generation",), concurrency=2),
        ],
        rules=[
            rule("IMPL_FEATURE", {"role": "implement", "kind": "feature"}, ["CodexImpl", "ClaudeImpl"]),
            rule("VERIFY_OTHER", {"role": "verify", "kind": "verification"}, ["CodexVerify", "ClaudeVerify"]),
            rule("REVIEW_ANY", {"role": "review", "kind": "review"}, ["ClaudeReview"]),
            default("implement", ["CodexImpl"]),
            default("verify", ["ClaudeVerify"]),
            default("review", ["ClaudeReview"]),
            default("generate", ["CodexBulk"]),
            default("answer", ["ClaudeReview"]),
        ])


def tie_spec(*, with_precedence: bool = False, chain: bool = False) -> Spec:
    """Two implement rules whose heads differ (CodexImpl and ClaudeImpl) for kind=feature size=small."""
    spec = standard_spec()
    spec.rules.append(rule("IMPL_SMALL", {"role": "implement", "size": "small"}, ["ClaudeImpl"]))
    if chain:
        spec.rules.append(rule("IMPL_MID", {"role": "implement", "size": "small", "kind": "feature"}, ["CodexImpl"]))
        spec.precedence += [precedence("P1", "IMPL_FEATURE", "IMPL_MID"), precedence("P2", "IMPL_MID", "IMPL_SMALL")]
    elif with_precedence:
        spec.precedence += [precedence("P1", "IMPL_FEATURE", "IMPL_SMALL")]
    return spec


# ---------------------------------------------------------------------------- a fake LLM for the closed choice
def fake_chooser(picks):
    """An ``LLMChooser`` whose provider names ``picks[n]`` (an agent id) at its n-th call (the last repeats).

    Returns (chooser, prompts): the prompts the provider was asked, in order.  No process is started.
    """
    from verantyx.llm_choice import ChoiceLedger, LLMChooser

    prompts: list[str] = []

    def provider(prompt: str) -> str:
        wanted = picks[min(len(prompts), len(picks) - 1)]
        prompts.append(prompt)
        for line in prompt.splitlines():
            found = re.match(r"^(\d+): (\{.*\})$", line)
            if found and json.loads(found.group(2))["term"] == wanted:
                return json.dumps({"choice": int(found.group(1))})
        return '{"choice": null}'

    return LLMChooser(provider, ChoiceLedger(None), order_source=lambda n: list(range(n))), prompts
