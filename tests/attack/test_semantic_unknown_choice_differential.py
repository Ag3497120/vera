import json
import random

from verantyx.semantic_unknown_choice import SemanticUnknownChoice


def _reference_options(report, frame_vocabulary):
    """Small independent inventory model for ordinary mapping reports."""
    unknown = report.get("term", "")
    found = set()

    for candidate in report.get("candidates", ()) or ():
        groups = [candidate.get("term")]
        groups.extend(candidate.get("units", ()) or ())
        for family in candidate.get("families", ()) or ():
            groups.extend(family.get("members", ()) or ())
        groups.extend(candidate.get("options", ()) or ())
        for term in groups:
            if (isinstance(term, str) and term and term.strip()
                    and term != unknown):
                found.add(term)

    for term in frame_vocabulary:
        if isinstance(term, str) and term and term.strip():
            found.add(term)
    return found


def _reference_decision(report, frame_vocabulary, *, selected=None,
                        asks_agree=True):
    """Expected semantic result from the closed-choice contract."""
    options = _reference_options(report, frame_vocabulary)
    if report.get("status") != "CANDIDATES" or not options:
        return "NONE", None
    if asks_agree and selected in options:
        return "ADOPT", selected
    return "UNRESOLVED", None


def _prompt_options(prompt):
    """Read the displayed JSON list so the fake asker can choose by term."""
    result = []
    for line in prompt.splitlines():
        number, separator, payload = line.partition(": ")
        if not separator or not number.isdecimal():
            continue
        item = json.loads(payload)
        if isinstance(item, dict) and isinstance(item.get("term"), str):
            result.append((int(number), item["term"]))
    return result


def _selecting_asker(targets):
    prompts = []

    def asker(prompt):
        prompts.append(prompt)
        index = len(prompts) - 1
        target = targets[index] if index < len(targets) else targets[-1]
        position = next((number for number, term in _prompt_options(prompt)
                         if term == target), None)
        return json.dumps({"choice": position}, ensure_ascii=False)

    asker.prompts = prompts
    return asker


def _fixed_asker(replies):
    prompts = []

    def asker(prompt):
        prompts.append(prompt)
        index = min(len(prompts) - 1, len(replies) - 1)
        return replies[index]

    asker.prompts = prompts
    return asker


def test_differential_generated_closed_choice_cases():
    rng = random.Random(731)
    vocabulary = ["amber", "blue", "cedar", "delta", "", "   "]

    for case_index in range(24):
        unknown = f"unknown-{case_index}"
        candidates = [{
            "term": unknown,
            "units": [rng.choice(vocabulary) for _ in range(3)],
            "families": [{"members": [rng.choice(vocabulary)]}],
            "options": [rng.choice(vocabulary)],
        }]
        frame = [rng.choice(vocabulary) for _ in range(3)]
        report = {"term": unknown, "status": "CANDIDATES",
                  "candidates": candidates}
        choices = sorted(_reference_options(report, frame))

        if not choices:
            asker = _selecting_asker([None])
            expected = _reference_decision(report, frame)
        else:
            selected = choices[rng.randrange(len(choices))]
            asker = _selecting_asker([selected])
            expected = _reference_decision(report, frame, selected=selected)

        observed = SemanticUnknownChoice(asker, seed=case_index).choose(report, frame)
        assert (observed["decision"], observed["option"]) == expected


def test_candidate_and_frame_duplicates_keep_both_origins_and_escape_terms():
    odd = 'line\nbreak: "quoted"'
    report = {
        "term": "mystery",
        "status": "CANDIDATES",
        "candidates": [{
            "term": "mystery",
            "units": ["shared", odd, "shared"],
            "families": [{"members": ["family-term"]}],
            "options": ["option-term"],
        }],
    }
    frame = ["shared", "frame-term", " ", "mystery"]
    asker = _selecting_asker([odd])

    result = SemanticUnknownChoice(asker).choose(report, frame)

    assert (result["decision"], result["option"]) == (
        *_reference_decision(report, frame, selected=odd),
    )
    displayed = dict(_prompt_options(asker.prompts[0]))
    assert set(displayed.values()) == {
        "shared", odd, "family-term", "option-term", "frame-term", "mystery"
    }
    item_by_term = {
        item["term"]: item
        for line in asker.prompts[0].splitlines()
        if (number := line.partition(": ")[0]).isdecimal()
        for item in [json.loads(line.partition(": ")[2])]
    }
    assert item_by_term["shared"]["from"] == ["candidate", "frame"]
    assert item_by_term[odd]["from"] == ["candidate"]
    assert item_by_term["mystery"]["from"] == ["frame"]


def test_non_candidate_status_abstains_without_asking():
    report = {"term": "mystery", "status": "NO_CANDIDATES",
              "candidates": [{"units": ["alpha"]}]}
    asker = _selecting_asker(["alpha"])

    result = SemanticUnknownChoice(asker).choose(report, ["beta"])

    assert (result["decision"], result["option"]) == _reference_decision(
        report, ["beta"], selected="alpha"
    )
    assert asker.prompts == []
    assert result["alias_record"] is None


def test_empty_candidate_and_frame_inventory_returns_none():
    report = {"term": "mystery", "status": "CANDIDATES",
              "candidates": [{"units": ["mystery", "", "   "]}]}
    asker = _selecting_asker([None])

    result = SemanticUnknownChoice(asker).choose(report, ["", " "])

    assert (result["decision"], result["option"]) == _reference_decision(
        report, ["", " "]
    )
    assert asker.prompts == []


def test_null_or_malformed_answers_remain_unresolved_testimony():
    report = {"term": "mystery", "status": "CANDIDATES",
              "candidates": [{"units": ["alpha", "beta"]}]}
    asker = _fixed_asker(['{"choice": null}', "not-json"])

    result = SemanticUnknownChoice(asker).choose(report, [])

    assert (result["decision"], result["option"]) == _reference_decision(
        report, [], asks_agree=False
    )
    assert len(asker.prompts) == 2
    assert result["alias_record"]["support"] == "testimony"
    assert result["alias_record"]["status"] == "UNRESOLVED"


def test_independent_asks_that_select_different_terms_abstain():
    report = {"term": "mystery", "status": "CANDIDATES",
              "candidates": [{"units": ["alpha", "beta", "gamma"]}]}
    asker = _selecting_asker(["alpha", "beta"])

    result = SemanticUnknownChoice(asker, seed=7).choose(report, [])

    assert (result["decision"], result["option"]) == _reference_decision(
        report, [], asks_agree=False
    )
    assert len(asker.prompts) == 2
    assert result["alias_record"]["choice"] is None


def test_agreed_choice_is_cached_as_testimony_not_evidence():
    report = {"term": "mystery", "status": "CANDIDATES",
              "candidates": [{"kind": "unit", "constructed": True,
                              "provenance": [{"origin": "generated"}],
                              "units": ["alpha", "beta"]}]}
    asker = _selecting_asker(["beta"])
    resolver = SemanticUnknownChoice(asker)

    first = resolver.choose(report, ["gamma"])
    second = resolver.choose(report, ["gamma"])

    assert (first["decision"], first["option"]) == _reference_decision(
        report, ["gamma"], selected="beta"
    )
    assert (second["decision"], second["option"]) == ("ADOPT", "beta")
    assert first["alias_record"] is second["alias_record"]
    assert len(asker.prompts) == 2
    assert first["alias_record"]["support"] == "testimony"
    assert first["evidence"] == [{
        "candidate_index": 0,
        "kind": "unit",
        "constructed": True,
        "counts_as_evidence": False,
        "provenance": [{"origin": "generated"}],
    }]


def test_superseding_reasks_and_links_replacement_record():
    report = {"term": "mystery", "status": "CANDIDATES",
              "candidates": [{"units": ["alpha", "beta"]}]}
    asker = _selecting_asker(["alpha", "alpha", "beta", "beta"])
    resolver = SemanticUnknownChoice(asker)

    original = resolver.choose(report, [])
    replacement = resolver.supersede_alias(report, [])

    assert (original["decision"], original["option"]) == ("ADOPT", "alpha")
    assert (replacement["decision"], replacement["option"]) == ("ADOPT", "beta")
    assert replacement["alias_record"]["supersedes"] == original["alias_record"]["id"]
    assert replacement["alias_record"]["id"] != original["alias_record"]["id"]
    assert len(resolver.alias_history) == 2
    assert len(asker.prompts) == 4


def test_wrong_choice_index_cannot_adopt_a_term_outside_the_displayed_list():
    report = {"term": "mystery", "status": "CANDIDATES",
              "candidates": [{"units": ["alpha", "beta"]}]}
    asker = _fixed_asker(['{"choice": 99}', '{"choice": -1}'])

    result = SemanticUnknownChoice(asker).choose(report, [])

    assert (result["decision"], result["option"]) == _reference_decision(
        report, [], asks_agree=False
    )
    assert result["alias_record"]["choice"] is None
    assert result["evidence"][0]["counts_as_evidence"] is False
