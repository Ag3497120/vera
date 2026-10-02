import json
from types import SimpleNamespace

import pytest

from verantyx.agent_adapter import (
    CodexExecAdapter,
    compile_frame_brief,
    parse_agent_output,
    to_conductor_question,
)


def test_json_layout_and_key_order_do_not_change_question_event():
    compact = '{"type":"QUESTION","id":"q-1","text":"Is it raining?","options":["yes","no"]}'
    spaced = '{  "options": ["yes", "no"], "text": "Is it raining?", "id": "q-1", "type": "QUESTION"  }'

    assert parse_agent_output(compact) == parse_agent_output(spaced) == [
        {"type": "QUESTION", "id": "q-1", "text": "Is it raining?", "options": ["yes", "no"]}
    ]


def test_polite_and_plain_question_phrasings_keep_question_routing():
    polite = parse_agent_output('{"type":"QUESTION","id":"weather","text":"Could you tell me whether it is raining?"}')
    plain = parse_agent_output('{"type":"QUESTION","id":"weather","text":"Is it raining?"}')

    assert [event["type"] for event in (polite[0], plain[0])] == ["QUESTION", "QUESTION"]
    assert [to_conductor_question(event).id for event in (polite[0], plain[0])] == ["weather", "weather"]


def test_plain_prose_paraphrases_remain_other_instead_of_becoming_answers():
    variants = parse_agent_output("Could you tell me whether it is raining?\nIs it raining?")

    assert [event["type"] for event in variants] == ["OTHER", "OTHER"]
    assert [to_conductor_question(event).id for event in variants] == ["adapter-other", "adapter-other"]


def test_changed_entity_and_count_values_are_preserved_as_distinct_claims():
    first = parse_agent_output('{"type":"CLAIM","task":"Mika visited 2 cities","evidence":["Mika visited Osaka"]}')
    changed = parse_agent_output('{"type":"CLAIM","task":"Mika visited 3 cities","evidence":["Mika visited Kyoto"]}')

    assert first[0]["type"] == changed[0]["type"] == "CLAIM"
    assert first[0]["task"] != changed[0]["task"]
    assert first[0]["evidence"] != changed[0]["evidence"]


def test_changed_event_meaning_changes_the_routed_event_type():
    question = parse_agent_output('{"type":"QUESTION","id":"q","text":"Was the gate open?"}')
    claim = parse_agent_output('{"type":"CLAIM","task":"The gate was open","evidence":[]}')

    assert question[0]["type"] == "QUESTION"
    assert claim[0]["type"] == "CLAIM"
    assert to_conductor_question(question[0]).text == "Was the gate open?"
    with pytest.raises(ValueError):
        to_conductor_question(claim[0])


def test_outer_whitespace_is_trimmed_without_changing_question_identity():
    plain = parse_agent_output('{"type":"QUESTION","id":" q:2 ","text":"  Where is the station?  "}')

    assert plain == [{"type": "QUESTION", "id": "q:2", "text": "Where is the station?"}]


def test_duplicate_json_fields_never_select_one_conflicting_meaning():
    events = parse_agent_output('{"type":"QUESTION","id":"q","text":"Safe?","text":"Unsafe?"}')

    assert len(events) == 1
    assert events[0]["type"] == "ERROR"


def test_utf8_bytes_and_text_have_the_same_unicode_event():
    value = '{"type":"QUESTION","id":"jp","text":"駅はどこですか？"}'

    assert parse_agent_output(value.encode("utf-8")) == parse_agent_output(value)


def test_brief_redacts_sensitive_slot_and_ignores_non_frame_fields():
    frame = SimpleNamespace(
        _active=lambda: [
            {
                "id": "r1",
                "kind": "fact",
                "slots": {"password": "sample-value", "summary": "The station is open"},
                "untyped_answer": "ignore this field",
            }
        ]
    )

    brief = compile_frame_brief(frame, project_root="/project")
    records = json.loads(brief.split("RECORDS_JSON:\n", 1)[1])

    assert records == [{"id": "r1", "kind": "fact", "slots": {"password": "[REDACTED]", "summary": "The station is open"}}]
    assert "ignore this field" not in brief


@pytest.mark.xfail(strict=False, reason="DEFECT: forward-slash Windows absolute paths bypass path redaction")
def test_brief_redacts_forward_slash_windows_path_surface_variant():
    frame = SimpleNamespace(
        _active=lambda: [
            {"id": "r1", "kind": "fact", "slots": {"summary": "See C:/private/notes.txt"}}
        ]
    )

    brief = compile_frame_brief(frame, project_root="/project")

    assert "C:/private/notes.txt" not in brief
    assert "[PATH_REDACTED]" in brief


def test_codex_command_keeps_unicode_brief_as_a_single_argument():
    adapter = CodexExecAdapter(executable="codex", project_dir="/project")
    brief = "質問: 駅はどこですか？"

    command = adapter.build_command(brief)

    assert command[-2:] == ["--", brief]
    assert command[0:2] == ["codex", "exec"]
