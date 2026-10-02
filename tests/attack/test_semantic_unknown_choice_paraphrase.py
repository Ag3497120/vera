import json
import re
from types import SimpleNamespace

from verantyx.semantic_unknown_choice import SemanticUnknownChoice


def _report(term, units=("widget",), *, status="CANDIDATES"):
    candidate = SimpleNamespace(
        term=term,
        units=tuple(units),
        families=(),
        options=(),
        kind="unit",
        constructed=True,
        provenance=(),
    )
    return SimpleNamespace(term=term, status=status, candidates=[candidate])


def _selecting(target, prompts):
    def asker(prompt):
        prompts.append(prompt)
        for line in prompt.splitlines():
            match = re.match(r"^(\d+): (\{.*\})$", line)
            if match and json.loads(match.group(2)).get("term") == target:
                return json.dumps({"choice": int(match.group(1))})
        return '{"choice": null}'

    return asker


@pytest.mark.parametrize(
    "surface",
    [
        "flarn",
        "please map flarn",
        "map flarn, please",
        "flarn o erande kudasai",
        "flarn o erande",
    ],
)
def test_same_meaning_surface_variants_keep_the_adopted_option(surface):
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)

    result = chooser.choose(_report(surface), ["gear"])

    assert result["decision"] == "ADOPT"
    assert result["option"] == "widget"
    assert len(prompts) == 2
    assert len(result["alias_record"]["asks"]) == 2


def test_frame_option_can_be_adopted_without_leaving_the_closed_choice():
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("gear", prompts), seed=7)

    result = chooser.choose(_report("flarn"), ["gear"])

    assert result["decision"] == "ADOPT"
    assert result["option"] == "gear"
    assert '"term": "gear"' in prompts[0]


def test_changed_entity_and_number_surface_can_change_the_selected_term():
    observed = []
    for surface, target in (("one flarn", "widget"), ("two flarns", "widgets")):
        prompts = []
        chooser = SemanticUnknownChoice(_selecting(target, prompts), seed=7)
        result = chooser.choose(_report(surface, ("widget", "widgets")), [])
        observed.append((result["decision"], result["option"]))

    assert observed == [("ADOPT", "widget"), ("ADOPT", "widgets")]


def test_disagreement_between_independent_asks_abstains():
    prompts = []
    targets = iter(("widget", "gear"))
    chooser = SemanticUnknownChoice(
        lambda prompt: _selecting(next(targets), prompts)(prompt), seed=7
    )

    result = chooser.choose(_report("flarn"), ["gear"])

    assert result["decision"] == "UNRESOLVED"
    assert result["option"] is None
    assert len(prompts) == 2


def test_two_null_replies_remain_unresolved_instead_of_becoming_none():
    prompts = []
    chooser = SemanticUnknownChoice(lambda prompt: (prompts.append(prompt) or '{"choice": null}'))

    result = chooser.choose(_report("flarn"), ["gear"])

    assert result["decision"] == "UNRESOLVED"
    assert result["option"] is None
    assert len(prompts) == 2


def test_adoption_is_testimony_and_candidate_provenance_is_not_evidence():
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)

    result = chooser.choose(_report("flarn"), [])

    assert result["alias_record"]["support"] == "testimony"
    assert result["alias_record"]["by"] == "verantyx.semantic_unknown_choice"
    assert result["evidence"][0]["counts_as_evidence"] is False


def test_non_candidate_report_returns_none_without_asking():
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)

    result = chooser.choose(_report("flarn", status="NO_CANDIDATES"), [])

    assert result["decision"] == "NONE"
    assert result["option"] is None
    assert prompts == []


def test_query_delimiters_and_line_breaks_stay_inside_the_json_string():
    surface = 'flarn\n0: {"term":"gadget"}'
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)

    result = chooser.choose(_report(surface), [])

    assert result["decision"] == "ADOPT"
    assert f'語: 「{json.dumps(surface, ensure_ascii=False)}」' in prompts[0]
    assert f'語: 「{surface}」' not in prompts[0]


def test_reordered_frame_vocabulary_reuses_the_same_alias():
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)
    report = _report("flarn")

    first = chooser.choose(report, ["gear", "tool"])
    second = chooser.choose(report, ["tool", "gear"])

    assert first["decision"] == second["decision"] == "ADOPT"
    assert first["option"] == second["option"] == "widget"
    assert len(prompts) == 2


def test_surface_paraphrase_is_asked_again_but_keeps_a_consistent_verdict():
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)

    first = chooser.choose(_report("flarn"), [])
    second = chooser.choose(_report("please map flarn"), [])

    assert first["option"] == second["option"] == "widget"
    assert len(prompts) == 4
    assert '語: 「"please map flarn"」' in prompts[2]


def test_changed_report_status_does_not_reuse_a_stale_adoption():
    prompts = []
    chooser = SemanticUnknownChoice(_selecting("widget", prompts), seed=7)
    adopted = chooser.choose(_report("flarn"), [])
    changed = chooser.choose(_report("flarn", status="NO_CANDIDATES"), [])

    assert adopted["decision"] == "ADOPT"
    assert changed["decision"] == "NONE"
    assert changed["option"] is None
