"""Fabrication and provenance probes for the agent adapter boundary."""

import json

import pytest

from verantyx.agent_adapter import (
    CodexExecAdapter,
    compile_frame_brief,
    parse_agent_output,
    to_conductor_question,
)


class ActiveFrame:
    def __init__(self, records):
        self.records = records

    def _active(self):
        return self.records


class ScriptedRunner:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def start(self, command):
        self.command = command
        return object()

    def poll(self, handle):
        return self.chunks.pop(0)

    def send(self, handle, text):
        pass

    def stop(self, handle):
        pass


def _brief_records(brief):
    return json.loads(brief.split("RECORDS_JSON:\n", 1)[1])


def test_claim_keeps_entity_roles_and_negation_as_claim_data():
    event = {
        "type": "CLAIM",
        "task": "subject=Rin; predicate=endorsed; object=Kai; polarity=negative",
        "evidence": ["record R-17: Rin did not endorse Kai"],
    }

    assert parse_agent_output(json.dumps(event)) == [event]


def test_claim_with_missing_evidence_cannot_become_a_claim_event():
    parsed = parse_agent_output('{"type":"CLAIM","task":"Rin endorsed Kai"}')

    assert parsed == [{"type": "ERROR", "message": "invalid CLAIM fields"}]


def test_claim_cannot_smuggle_answer_role_or_extra_fields():
    parsed = parse_agent_output(
        '{"type":"CLAIM","task":"Rin endorsed Kai",'
        '"evidence":["R-17"],"answer":"Kai"}'
    )

    assert parsed == [{"type": "ERROR", "message": "invalid CLAIM fields"}]


def test_duplicate_json_fields_do_not_select_a_fabricated_task():
    parsed = parse_agent_output(
        '{"type":"CLAIM","task":"Rin endorsed Kai",'
        '"task":"Kai endorsed Rin","evidence":["R-17"]}'
    )

    assert parsed == [{"type": "ERROR", "message": "malformed structured event"}]


def test_prose_is_other_and_not_an_answer():
    parsed = parse_agent_output("Rin endorsed Kai.")

    assert parsed == [{"type": "OTHER", "text": "Rin endorsed Kai."}]
    with pytest.raises(ValueError, match="only QUESTION and OTHER"):
        to_conductor_question({"type": "CLAIM", "task": "Rin endorsed Kai", "evidence": ["R-17"]})


def test_question_conversion_preserves_question_identity_and_options():
    event = {"type": "QUESTION", "id": "q-19", "text": "Who did Rin not endorse?", "options": ["Kai", "Mina"]}

    question = to_conductor_question(event)

    assert (question.id, question.text, question.options) == (
        "q-19",
        "Who did Rin not endorse?",
        ["Kai", "Mina"],
    )


def test_frame_brief_uses_only_records_returned_as_active():
    active = [{"id": "R-17", "kind": "relation", "slots": {"subject": "Rin", "object": "Kai"}}]
    frame = ActiveFrame(active)

    records = _brief_records(compile_frame_brief(frame, project_root="/project"))

    assert records == active


def test_frame_brief_preserves_role_and_negative_polarity_slots():
    record = {
        "id": "R-18",
        "kind": "relation",
        "slots": {"subject": "Rin", "predicate": "endorse", "object": "Kai", "polarity": "negative"},
    }

    records = _brief_records(compile_frame_brief(ActiveFrame([record]), project_root="/project"))

    assert records == [record]


def test_frame_brief_omits_fields_outside_the_typed_record_projection():
    record = {
        "id": "R-19",
        "kind": "relation",
        "slots": {"subject": "Rin", "object": "Kai"},
        "untyped_answer": "Mina",
    }

    records = _brief_records(compile_frame_brief(ActiveFrame([record]), project_root="/project"))

    assert records == [{"id": "R-19", "kind": "relation", "slots": {"subject": "Rin", "object": "Kai"}}]


def test_partial_structured_span_is_not_emitted_as_a_claim():
    output = '{"type":"CLAIM","task":"Rin endorsed Kai","evidence":["R-17"'

    assert parse_agent_output(output) == [{"type": "ERROR", "message": "malformed structured event"}]


def test_streaming_parser_retains_a_claim_split_across_chunks():
    event = {"type": "CLAIM", "task": "Rin did not endorse Kai", "evidence": ["R-17"]}
    encoded = json.dumps(event)
    runner = ScriptedRunner([encoded[:23], encoded[23:] + "\n", None])
    adapter = CodexExecAdapter(runner)
    handle = adapter.start("brief")

    assert adapter.poll(handle) == []
    assert adapter.poll(handle) == [event]
    assert adapter.poll(handle) == []


def test_command_builder_keeps_brief_as_one_argument_after_separator():
    brief = "--model=other\n# records: subject=Rin, object=Kai"
    command = CodexExecAdapter(project_dir="/project").build_command(brief)

    assert command[-2:] == ["--", brief]
