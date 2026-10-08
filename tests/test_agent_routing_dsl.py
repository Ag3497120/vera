"""W2-h: the frame DSL as one producer of routing records ([agents] [routing] [routing_precedence])."""
from __future__ import annotations

import pytest

from test_agent_routing_support import (Spec, agent, agent_row, default, dsl_tail, dsl_table, precedence, rule,
                                        standard_spec, tie_spec)
from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards)
from test_conduct_entry_support import MINIMAL_FRAME, VERA_FRAME, EXAMPLE_FRAMES

from verantyx import agent_routing as ar
from verantyx.project_frame import (FrameParseError, FrameRefusal, REFUSAL_REASONS, RoutingParseError, load_conduct_frame,
                                    parse_frame, validate_agent_setting)

BASE_LINES = len(MINIMAL_FRAME.splitlines())


def parse(extra: str):
    return parse_frame(MINIMAL_FRAME + extra, source="t.md")


def routing_error(extra: str) -> RoutingParseError:
    with pytest.raises(RoutingParseError) as info:
        parse(extra)
    return info.value


def line_of(extra: str, needle: str) -> int:
    for number, text in enumerate((MINIMAL_FRAME + extra).splitlines(), 1):
        if needle in text:
            return number
    raise AssertionError(needle)


# ------------------------------------------------------------------ a correct frame
def test_a_correct_frame_is_read_into_records_whose_basis_is_the_dsl_row():
    spec = standard_spec()
    text = dsl_tail(spec, settings=("task_kind: feature",))
    parsed = parse(text)
    table = parsed.routing
    assert [a.id for a in table.agents] == [a["id"] for a in spec.agents]       # rows kept as written
    assert [r.id for r in table.rules] == [r["id"] for r in spec.rules]
    for record in (*table.agents, *table.rules):
        assert record.basis.kind == "declared_dsl" and record.basis.source == "t.md"
        assert [(MINIMAL_FRAME + text).splitlines()[record.basis.line - 1]] == list(record.basis.witnesses)
    first = table.agents[0]
    assert first.basis.line == line_of(text, "CodexImpl: adapter") and first.concurrency == 1
    assert first.roles == frozenset({"implement"}) and first.lineage == "openai" and first.note is None
    assert {item.key for item in parsed.agent_settings} == {"task_kind"}
    assert {"agents", "routing", "agent_settings"} <= set(parsed.declared_sections)


def test_the_precedence_section_is_read_and_a_note_is_kept_as_an_identifier():
    spec = tie_spec(with_precedence=True)
    spec.agents[0]["note"] = "cheap_and_quick"
    table = parse(dsl_tail(spec)).routing
    assert [(p.id, p.higher, p.lower) for p in table.precedence] == [("P1", "IMPL_FEATURE", "IMPL_SMALL")]
    assert table.precedence[0].basis.kind == "declared_dsl" and table.agents[0].note == "cheap_and_quick"


def test_a_frame_without_the_three_sections_has_no_routing_and_the_old_refusal_shape_is_unchanged():
    assert parse("").routing is None
    assert parse_frame(VERA_FRAME.read_text(encoding="utf-8"), source="v.md").routing is None
    for path in EXAMPLE_FRAMES:
        spec = parse_frame(path.read_text(encoding="utf-8"), source=str(path))
        assert (spec.routing is not None) == ("[agents]" in path.read_text(encoding="utf-8"))
    refusal = FrameRefusal("FRAME_PARSE_ERROR", "fix it", "d", source="s", line=3)
    assert refusal.as_dict() == {"reason": "FRAME_PARSE_ERROR", "missing": "fix it", "detail": "d", "source": "s", "line": 3}
    assert FrameRefusal("ROUTING_INVALID", "m", code="UNKNOWN_KIND").as_dict()["code"] == "UNKNOWN_KIND"
    assert REFUSAL_REASONS[-2:] == ("ROUTING_INVALID", "ROUTING_UNDECIDED")


# ------------------------------------------------------------------ R1 through the DSL: five different codes, with lines
def test_R1_the_five_rejections_arrive_as_five_codes_with_the_line_of_the_record():
    cases = {}
    spec = standard_spec()
    spec.agents[0]["kinds"].append("interpretive_dance")
    cases["UNKNOWN_KIND"] = (spec, agent_row(spec.agents[0]))
    spec = standard_spec()
    spec.agents[1]["adapter"] = "gemini"
    cases["UNKNOWN_ADAPTER"] = (spec, agent_row(spec.agents[1]))
    spec = standard_spec()
    spec.agents.append(agent("ClaudeVerify", adapter="claude", lineage="anthropic", roles=("verify",)))
    cases["DUPLICATE_AGENT_ID"] = (spec, "ClaudeVerify: adapter=claude model=gpt-6-luna")
    spec = standard_spec()
    spec.rules = [r for r in spec.rules if not (r["id"] == "DEFAULT" and r["when"]["role"] == "answer")]
    cases["MISSING_ROLE_DEFAULT"] = (spec, "ClaudeReview: adapter")
    spec = standard_spec()
    spec.rules.append(rule("SELF", {"role": "review", "independent_of": "review"}, ["ClaudeReview"]))
    cases["INDEPENDENCE_CYCLE"] = (spec, None)
    for code, (broken, needle) in cases.items():
        text = dsl_tail(broken)
        error = routing_error(text)
        assert error.code == code and error.source == "t.md", (code, error)
        assert f"[{code}]" in error.message
        if needle is not None:
            assert error.line == line_of(text, needle)
    assert len(cases) == 5


@pytest.mark.parametrize("code,edit", [
    ("DUPLICATE_RULE_ID", lambda s: s.rules.append(rule("IMPL_FEATURE", {"role": "implement"}, ["CodexImpl"]))),
    ("UNKNOWN_AGENT_REF", lambda s: s.rules.append(rule("X1", {"role": "implement"}, ["Nobody"]))),
    ("PRECEDENCE_CYCLE", lambda s: s.precedence.extend([precedence("P1", "IMPL_FEATURE", "REVIEW_ANY"),
                                                        precedence("P2", "REVIEW_ANY", "IMPL_FEATURE")])),
    ("BAD_VALUE", lambda s: s.agents[0].update(concurrency=0)),
    ("BAD_CONDITION", lambda s: s.rules.append(rule("X1", {"role": "implement", "colour": "red"}, ["CodexImpl"]))),
])
def test_R1_the_checks_of_meaning_are_the_record_layers_and_reach_the_dsl_unchanged(code, edit):
    spec = standard_spec()
    edit(spec)
    assert routing_error(dsl_tail(spec)).code == code


def test_the_dsl_does_not_repeat_the_record_layers_checks():
    import inspect
    from verantyx import project_frame

    source = inspect.getsource(project_frame._routing_from_sections) + inspect.getsource(project_frame._agent_record) + \
        inspect.getsource(project_frame._routing_rule)
    for word in ("TASK_KINDS", "ADAPTERS", "ROLES", "DUPLICATE_AGENT_ID", "DUPLICATE_RULE_ID", "CYCLE",
                 "MISSING_ROLE_DEFAULT", "UNKNOWN_KIND", "UNKNOWN_ADAPTER"):
        assert word not in source


# ------------------------------------------------------------------ the shape of a row (DSL only)
BASE = dsl_tail(standard_spec())


def swapped(old: str, new: str) -> str:
    assert BASE.count(old) == 1, old
    return BASE.replace(old, new)


@pytest.mark.parametrize("code,text", [
    ("MALFORMED_ROW", swapped("IMPL_FEATURE: role=implement & kind=feature => CodexImpl, ClaudeImpl",
                              "IMPL_FEATURE: role=implement & kind=feature -> CodexImpl, ClaudeImpl")),
    ("MALFORMED_ROW", swapped("kinds=review,closed_choice lineage=anthropic", "kinds=review,,closed_choice lineage=anthropic")),
    ("MALFORMED_ROW", swapped("kinds=review,closed_choice lineage=anthropic", "kinds=review,review lineage=anthropic")),
    ("MALFORMED_ROW", swapped("CodexBulk: adapter=codex", "CodexBulk: adapter = codex")),
    ("MALFORMED_ROW", swapped("REVIEW_ANY: role=review & kind=review => ClaudeReview: the human said so",
                              "REVIEW_ANY: role=review & kind=review => ClaudeReview")),
    ("MALFORMED_ROW", swapped("REVIEW_ANY: role=review & kind=review", "REVIEW_ANY: role=review & kind")),
    ("UNKNOWN_FIELD", swapped("concurrency=2", "concurrency=2 speed=fast")),
    ("DUPLICATE_FIELD", swapped("concurrency=2", "concurrency=2 concurrency=3")),
    ("MISSING_FIELD", swapped(" lineage=openai concurrency=2", " concurrency=2")),
])
def test_a_row_of_the_wrong_shape_is_a_typed_error_with_its_line(code, text):
    with pytest.raises(RoutingParseError) as info:
        parse(text)
    assert info.value.code == code and info.value.line > BASE_LINES
    assert isinstance(info.value, FrameParseError)


def test_a_sentence_where_an_agent_field_is_expected_is_not_accepted_as_prose():
    legal = parse(swapped("concurrency=2", "concurrency=2 note=fast"))       # an identifier is a legal note
    assert legal.routing.agent("CodexBulk").note == "fast"
    error = routing_error(swapped("concurrency=2", "concurrency=2 note=mostly_good_at_big_refactors_but_slow!"))
    assert error.code == "BAD_VALUE"                                         # prose is not


def test_the_sections_come_together_and_a_missing_one_is_MISSING_SECTION():
    agents_only = "\n".join(line for line in dsl_tail(standard_spec()).splitlines()).split("[routing]")[0]
    assert routing_error(agents_only).code == "MISSING_SECTION"
    routing_only = "[routing]\n" + "\n".join(dsl_tail(standard_spec()).split("[routing]\n")[1].splitlines()) + "\n"
    assert routing_error(routing_only).code == "MISSING_SECTION"
    only_precedence = "[routing_precedence]\nP1: IMPL_FEATURE > REVIEW_ANY: because\n"
    assert routing_error(only_precedence).code == "MISSING_SECTION"


def test_an_explicitly_empty_table_is_EMPTY_TABLE():
    assert routing_error("[agents]\nnone: none\n[routing]\nnone: none\n").code == "EMPTY_TABLE"
    with pytest.raises(FrameParseError) as info:                 # a section left blank is the old, plain error
        parse("[agents]\n[routing]\nnone: none\n")
    assert "empty" in info.value.message and not isinstance(info.value, RoutingParseError)


def test_J3_the_old_agent_settings_that_the_table_replaces_are_rejected_at_the_setting_line():
    for key, value in (("codex_model", "gpt-6-luna"), ("codex_effort", "low"), ("claude_model", "claude-sonnet-5-5"),
                       ("claude_effort", "low"), ("verifier_adapter", "claude"), ("verifier_model", "claude-sonnet-5-5"),
                       ("verifier_effort", "low")):
        text = dsl_tail(standard_spec(), settings=(f"{key}: {value}",))
        error = routing_error(text)
        assert error.code == "AGENT_SETTINGS_CONFLICT" and error.line == line_of(text, f"{key}: {value}")
    ok = dsl_tail(standard_spec(), settings=("task_kind: feature", "max_concurrency: 2", "agent_timeout_seconds: 60",
                                             "verifier_timeout_seconds: 60", "verification_retries: 0"))
    assert parse(ok).routing is not None


def test_J1_task_kind_is_a_closed_setting():
    assert validate_agent_setting("task_kind", "feature") is None
    assert "task_kind must be one of" in validate_agent_setting("task_kind", "wizardry")
    with pytest.raises(FrameParseError) as info:
        parse("[agent_settings]\ntask_kind: wizardry\n")
    assert "task_kind" in info.value.message
    assert parse("[agent_settings]\ntask_kind: attack\n").agent_settings[0].value == "attack"


def test_load_conduct_frame_turns_a_routing_problem_into_ROUTING_INVALID_with_its_code(tmp_path):
    spec = standard_spec()
    spec.agents[0]["adapter"] = "gemini"
    path = tmp_path / "frame.md"
    path.write_text(MINIMAL_FRAME + dsl_tail(spec), encoding="utf-8")
    with pytest.raises(FrameRefusal) as info:
        load_conduct_frame(path)
    refusal = info.value
    assert (refusal.reason, refusal.code) == ("ROUTING_INVALID", "UNKNOWN_ADAPTER")
    assert refusal.as_dict()["code"] == "UNKNOWN_ADAPTER" and refusal.line is not None and "UNKNOWN_ADAPTER" in refusal.missing
    path.write_text(MINIMAL_FRAME + "[agents]\n[routing]\nnone: none\n", encoding="utf-8")
    with pytest.raises(FrameRefusal) as info:
        load_conduct_frame(path)
    assert info.value.reason == "FRAME_PARSE_ERROR" and info.value.code is None      # a plain empty section is the old error


def test_the_conduct_frame_carries_the_table_and_a_frame_without_agents_carries_none(tmp_path):
    path = tmp_path / "frame.md"
    path.write_text(MINIMAL_FRAME + dsl_tail(standard_spec()), encoding="utf-8")
    assert load_conduct_frame(path).routing is not None
    path.write_text(MINIMAL_FRAME, encoding="utf-8")
    assert load_conduct_frame(path).routing is None


def test_the_sample_frame_reads_and_routes_the_four_agents_in_two_lineages():
    path = next(p for p in EXAMPLE_FRAMES if p.stem == "routing_two_lineages")
    table = parse_frame(path.read_text(encoding="utf-8"), source=str(path)).routing
    assert len(table.agents) == 4 and {a.lineage for a in table.agents} == {"openai", "anthropic"}
    assert sum(1 for r in table.rules if not r.fallback) >= 6
    request = ar.RoutingRequest("j", "implement", "feature", "small")
    chosen = ar.route(table, request)
    assert (chosen.agent_id, chosen.decided_by) == ("CodexImpl", "rule:IMPL_FEATURE")
    verifier = ar.route(table, ar.RoutingRequest("j", "verify", "verification", "small", used_lineages={"implement": ("openai",)}))
    assert verifier.agent_id == "ClaudeVerify" and table.agent("ClaudeVerify").adapter == "claude"
    same = ar.route(table, ar.RoutingRequest("j", "verify", "verification", "small", used_lineages={"implement": ("anthropic",)}))
    assert same.agent_id is None and same.undecided_reason == "NO_VIABLE_CANDIDATE"


def test_the_two_producers_make_equal_tables_up_to_their_basis():
    spec = tie_spec(with_precedence=True)
    from_dsl, from_dict = dsl_table(spec), ar.table_from_dicts(spec.agents, spec.rules, spec.precedence)

    def stripped(table):
        return ([(a.id, a.adapter, a.model, a.effort, a.roles, a.kinds, a.lineage, a.concurrency, a.note) for a in table.agents],
                [(r.id, r.conditions, r.preference, r.reason) for r in table.rules],
                [(p.id, p.higher, p.lower, p.reason) for p in table.precedence])

    assert stripped(from_dsl) == stripped(from_dict)


# ------------------------------------------------------------------ round 2: the DSL asks for what its form asks for
def test_the_dsl_row_named_DEFAULT_makes_a_fallback_record_and_no_other_row_does():
    table = parse(dsl_tail(standard_spec())).routing
    assert {r.id for r in table.rules if r.fallback} == {"DEFAULT"}
    assert sum(1 for r in table.rules if r.fallback) == 5 and all(r.id == "DEFAULT" for r in table.rules if r.fallback)
    assert not any(r.fallback for r in table.rules if r.id != "DEFAULT")


@pytest.mark.parametrize("missing", ["model", "effort", "concurrency"])
def test_the_dsl_still_requires_model_effort_and_concurrency_on_every_agent_row(missing):
    row = agent_row(standard_spec().agents[0])
    cut = " ".join(token for token in row.split(" ") if not token.startswith(missing + "="))
    text = dsl_tail(standard_spec()).replace(row, cut)
    error = routing_error(text)
    assert error.code == "MISSING_FIELD" and error.line == line_of(text, "CodexImpl: adapter") and missing in error.message


def test_the_dsl_still_requires_a_reason_on_a_rule_row_and_a_precedence_row():
    base = dsl_tail(tie_spec(with_precedence=True))
    for old, new in (("IMPL_FEATURE: role=implement & kind=feature => CodexImpl, ClaudeImpl: the human said so",
                      "IMPL_FEATURE: role=implement & kind=feature => CodexImpl, ClaudeImpl:   "),
                     ("P1: IMPL_FEATURE > IMPL_SMALL: the human ordered them", "P1: IMPL_FEATURE > IMPL_SMALL:")):
        assert base.count(old) == 1
        error = routing_error(base.replace(old, new))
        assert error.code == "MISSING_FIELD" and "reason" in error.message


# ------------------------------------------------------------------ round 3: the token form is the row's limit, not the record's
@pytest.mark.parametrize("old,new", [
    ("CodexBulk: adapter=codex", "Sonnet 5.5: adapter=codex"),            # an id with a space
    ("CodexBulk: adapter=codex", "ソネット: adapter=codex"),                 # an id that is not an ASCII token
    ("lineage=anthropic", "lineage=Claude系"),                             # a lineage that is not an ASCII token
])
def test_R1_names_the_dsl_refuses_an_id_or_lineage_it_cannot_write_as_a_row_token_as_MALFORMED_ROW(old, new):
    text = BASE.replace(old, new, 1)
    assert text != BASE
    error = routing_error(text)
    assert error.code == "MALFORMED_ROW" and error.line > BASE_LINES
    # the same words are fine in the record layer (tests/test_agent_routing.py: names_...), so the limit is the DSL's


def test_the_dsl_still_requires_kinds_and_lineage_in_a_row_even_though_a_record_may_leave_them_unsaid():
    error = routing_error(swapped("kinds=review,closed_choice lineage=anthropic", "lineage=anthropic"))
    assert error.code == "MISSING_FIELD" and "kinds" in str(error)
    error = routing_error(swapped(" lineage=openai concurrency=2", " concurrency=2"))
    assert error.code == "MISSING_FIELD" and "lineage" in str(error)


# ------------------------------------------------------------------ round 4 (F9): a rule row with no role=
def _luna_spec() -> Spec:
    """'Attack goes to Luna', with no role in the rule; Luna reviews and reads (the DSL row says its roles)."""
    return Spec(
        agents=[agent("Luna", roles=("review", "read"), kinds=("attack", "read_large_file"), lineage="openai")],
        rules=[rule("ATTACK", {"kind": "attack"}, ["Luna"], "攻撃は Luna"),
               default("review", ["Luna"]), default("read", ["Luna"])])


def test_R0_role_a_dsl_row_with_no_role_is_read_and_decides_like_the_same_description_from_a_dictionary():
    spec = _luna_spec()
    from_dsl, from_dict = dsl_table(spec), ar.table_from_dicts(spec.agents, spec.rules, spec.precedence)
    attack = [item for item in from_dsl.rules if item.id == "ATTACK"][0]
    assert attack.role is None and attack.basis.kind == "declared_dsl" and attack.basis.line > BASE_LINES
    request = ar.RoutingRequest("job1", "review", "attack", "small")
    one, other = ar.route(from_dsl, request), ar.route(from_dict, request)
    assert one.agent_id == "Luna" and one.decided_by == "rule:ATTACK" and one.essence() == other.essence()
    assert one.role_fit == {"Luna": "declared"}
    spec_in_frame = parse(dsl_tail(spec))
    assert [item.role for item in spec_in_frame.routing.rules if item.id == "ATTACK"] == [None]


def test_R1_role_the_dsl_still_requires_roles_on_an_agent_row():
    row = agent_row(standard_spec().agents[0])
    cut = " ".join(token for token in row.split(" ") if not token.startswith("roles="))
    text = dsl_tail(standard_spec()).replace(row, cut)
    error = routing_error(text)
    assert error.code == "MISSING_FIELD" and "roles" in error.message and error.line == line_of(text, "CodexImpl: adapter")


def test_R1_role_a_dsl_row_with_no_role_and_an_independent_of_is_BAD_CONDITION_from_the_record_layer():
    spec = _luna_spec()
    spec.rules.append(rule("LOOP", {"kind": "attack", "independent_of": "implement"}, ["Luna"]))
    error = routing_error(dsl_tail(spec))
    assert error.code == "BAD_CONDITION" and error.line > BASE_LINES
