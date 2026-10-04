"""Executable probes for the W3-c4 document question cross.

Run from the repository root with the configured Python and PYTHONPATH.
The tests use the ticket's read-only r8 placement and temporary documents.
"""
import json
from pathlib import Path

import pytest

from verantyx import cli


R8 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2"
VOLATILE = {"ingest_ms", "elapsed_ms"}


@pytest.fixture
def r8(monkeypatch):
    monkeypatch.setenv("VERA_PLACEMENT", R8)


def write_doc(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def ask(tmp_path, capsys, docs, question, *extra, mode="round5"):
    argv = ["--store", str(tmp_path / "store.json"), "ask", "--mode", mode]
    for doc in docs:
        argv += ["--document", doc]
    argv += list(extra) + ["--", question]
    capsys.readouterr()
    rc = cli.main(argv)
    return rc, json.loads(capsys.readouterr().out)


def without_timing(value):
    if isinstance(value, dict):
        return {k: (0 if k in VOLATILE else without_timing(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [without_timing(v) for v in value]
    return value


def print_summary(label, out):
    qc = out.get("question_cross") or {}
    print(json.dumps({"probe": label, "verdict": out.get("verdict"), "door": out.get("door"),
                      "text": out.get("text"), "question_cross": {k: qc.get(k) for k in ("state", "reason", "mapped_to")},
                      "sources": [{k: s.get(k) for k in ("source", "line", "text", "sentence_id")} for s in out.get("sources", [])],
                      "basis_outcome": (out.get("basis_policy") or {}).get("outcome")},
                     ensure_ascii=False, sort_keys=True))


@pytest.mark.xfail(strict=True, reason='auditor ruling 2026-10-04 (W5-f F-5): the body check is defined on the loaded document text, not the raw Markdown; the evidence text is a substring of the loaded text. Strict xfail records the raw-Markdown expectation of the attack.')
def test_markdown_link_evidence_text_is_a_literal_source_substring(tmp_path, capsys, r8):
    raw = "先生は[本](https://example.org/book)を読んだ。\n"
    path = write_doc(tmp_path, "linked.md", raw)
    rc, out = ask(tmp_path, capsys, [path], "先生は何を読んだ？")
    assert rc == 0
    assert out.get("door") == "question_cross" and out.get("verdict") == "ANSWER", out
    source_text = out["sources"][0]["text"]
    print(json.dumps({"verdict": out["verdict"], "text": out["text"], "source": out["sources"][0],
                      "raw_document_line": raw.rstrip("\n"), "basis_outcome": out.get("basis_policy", {}).get("outcome")},
                     ensure_ascii=False, sort_keys=True))
    assert source_text in raw, {
        "verdict": out["verdict"], "text": out.get("text"), "source": out["sources"][0],
        "raw_document_line": raw.rstrip("\n"), "basis_outcome": out.get("basis_policy", {}).get("outcome"),
    }


def test_removed_url_that_would_make_a_sentence_does_not_reach_an_answer(tmp_path, capsys, r8):
    raw = "先生は本 https://example.org/book を読んだ。\n"
    path = write_doc(tmp_path, "url.txt", raw)
    rc, out = ask(tmp_path, capsys, [path], "先生は何を読んだ？")
    assert rc == 0
    qc = out.get("question_cross") or {}
    print(json.dumps({"verdict": out.get("verdict"), "door": out.get("door"),
                      "question_cross": {k: qc.get(k) for k in ("state", "reason", "mapped_to")}},
                     ensure_ascii=False, sort_keys=True))
    assert "question_cross" in out
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


def test_english_present_evidence_does_not_answer_past_question(tmp_path, capsys, r8):
    path = write_doc(tmp_path, "en.txt", "The clerk reads the newspaper.\n")
    rc, out = ask(tmp_path, capsys, [path], "What did the clerk read?")
    assert rc == 0
    print_summary("English present vs did-read", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


def test_reported_quote_is_not_laundered_as_a_direct_fact(tmp_path, capsys, r8):
    path = write_doc(tmp_path, "quote.txt", "先生は「本を読んだ」と言った。\n")
    rc, out = ask(tmp_path, capsys, [path], "先生は何を読んだ？")
    assert rc == 0
    print_summary("reported quote", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


def test_role_reversal_keeps_the_patient_of_the_named_topic(tmp_path, capsys, r8):
    path = write_doc(tmp_path, "roles.txt", "先生は生徒を見た。\n生徒は先生を見た。\n")
    rc, out = ask(tmp_path, capsys, [path], "先生は誰を見た？")
    assert rc == 0
    print_summary("same predicate, reversed roles", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER" and out.get("text") != "生徒"), out
    if out.get("door") == "question_cross" and out.get("verdict") == "ANSWER":
        assert out["sources"][0]["text"] == "先生は生徒を見た。"


def test_negative_document_sentence_does_not_fill_affirmative_question(tmp_path, capsys, r8):
    path = write_doc(tmp_path, "neg.txt", "校長は本を読まなかった。\n")
    rc, out = ask(tmp_path, capsys, [path], "校長は何を読んだ？")
    assert rc == 0
    print_summary("negative evidence vs affirmative question", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


@pytest.mark.parametrize("sentence,question,label", [
    ("先生は生徒に本を読ませた。", "先生は何を読んだ？", "causative vs active"),
    ("先生は本を読まれた。", "先生は何を読んだ？", "passive vs active"),
    ("先生は昨日本を読んだ。", "先生は何を読んだ？", "time adverb"),
    ("先生は本を読みました。", "先生は何を読んだ？", "polite evidence vs plain question"),
])
def test_voice_time_and_politeness_do_not_create_a_false_fill(tmp_path, capsys, r8, sentence, question, label):
    path = write_doc(tmp_path, "form.txt", sentence + "\n")
    rc, out = ask(tmp_path, capsys, [path], question)
    assert rc == 0
    print_summary(label, out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


@pytest.mark.parametrize("question", ["先生は何を読んだの？", "先生は何を読んだか？", "先生は何を読んだのですか？"])
def test_question_suffix_particles_do_not_get_silently_removed(tmp_path, capsys, r8, question):
    path = write_doc(tmp_path, "ja.txt", "先生は本を読んだ。\n")
    rc, out = ask(tmp_path, capsys, [path], question)
    assert rc == 0
    print_summary("question suffix: " + question, out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


def test_round5_base_answer_is_byte_equivalent_without_later_stage(tmp_path, capsys, r8, monkeypatch):
    doc = write_doc(tmp_path, "base.txt", "先生が生徒に切符を渡した。\n")
    _, with_stage = ask(tmp_path, capsys, [doc], "誰が切符を渡した？")
    assert with_stage.get("verdict") == "ANSWER" and "question_cross" not in with_stage
    monkeypatch.setattr(cli, "_round5_question_cross", lambda result, documents, query: result)
    _, baseline = ask(tmp_path, capsys, [doc], "誰が切符を渡した？")
    assert without_timing(with_stage) == without_timing(baseline)


def test_source_text_for_plain_sentence_is_a_literal_source_substring(tmp_path, capsys, r8):
    raw = "　先生は本を読んだ。　\n"
    path = write_doc(tmp_path, "plain.txt", raw)
    rc, out = ask(tmp_path, capsys, [path], "先生は何を読んだ？")
    assert rc == 0
    print_summary("plain fullwidth-space boundaries", out)
    if out.get("door") == "question_cross" and out.get("verdict") == "ANSWER":
        assert out["sources"][0]["text"] in raw


def test_no_period_at_end_and_fullwidth_space_keep_the_same_sentence(tmp_path, capsys, r8):
    raw = "先生は本を読んだ　\n"
    path = write_doc(tmp_path, "no-period.txt", raw)
    rc, out = ask(tmp_path, capsys, [path], "先生は何を読んだ？")
    assert rc == 0
    print_summary("no final stop, trailing fullwidth space", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER" and out.get("text") != "本"), out
    if out.get("door") == "question_cross" and out.get("verdict") == "ANSWER":
        assert out["sources"][0]["text"] in raw


def test_line_break_inside_sentence_does_not_join_unattested_fragments(tmp_path, capsys, r8):
    path = write_doc(tmp_path, "broken-line.txt", "先生は本を\n読んだ。\n")
    rc, out = ask(tmp_path, capsys, [path], "先生は何を読んだ？")
    assert rc == 0
    print_summary("line break inside sentence", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


def test_period_in_an_abbreviation_does_not_make_a_false_english_subject(tmp_path, capsys, r8):
    path = write_doc(tmp_path, "abbrev.txt", "Mr. Smith gave the map to the student.\n")
    rc, out = ask(tmp_path, capsys, [path], "Who gave the map to the student?")
    assert rc == 0
    print_summary("Mr. Smith sentence split", out)
    assert not (out.get("door") == "question_cross" and out.get("verdict") == "ANSWER"), out


def test_identical_sentence_in_two_documents_keeps_both_sources(tmp_path, capsys, r8):
    first = write_doc(tmp_path, "one.txt", "先生は本を読んだ。\n")
    second = write_doc(tmp_path, "two.txt", "先生は本を読んだ。\n")
    rc, out = ask(tmp_path, capsys, [first, second], "先生は何を読んだ？")
    assert rc == 0
    print_summary("identical evidence in two docs", out)
    if out.get("door") == "question_cross" and out.get("verdict") == "ANSWER":
        assert out["text"] == "本" and {x["source"] for x in out["sources"]} == {"one.txt", "two.txt"}


def test_basis_policy_still_handles_creative_reference_and_confirm_flags(tmp_path, capsys, r8):
    doc = write_doc(tmp_path, "policy.txt", "先生は本を読んだ。\n")
    _, factual = ask(tmp_path, capsys, [doc], "先生は何を読んだ？")
    _, creative = ask(tmp_path, capsys, [doc], "先生は何を読んだ？", "--request-kind", "creative")
    _, reference = ask(tmp_path, capsys, [doc], "先生は何を読んだ？", "--show-generated-reference")
    _, confirm = ask(tmp_path, capsys, [doc], "先生は何を読んだ？", "--confirm", "not-a-generated-claim", "yes")
    for label, result in (("factual", factual), ("creative", creative), ("show-reference", reference), ("invalid-confirm", confirm)):
        print_summary("policy " + label, result)
    assert factual["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS", factual
    assert creative["basis_policy"]["outcome"] == "CONSTRUCTED" and creative.get("constructed") is True, creative
    assert reference["basis_policy"]["outcome"] in {"ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED"}, reference
    assert confirm["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert confirm["verdict"] == "UNKNOWN_CONFIRM_ID" and confirm["wrote"] == 0, confirm


def test_legacy_with_document_is_not_entered_into_the_later_stage(tmp_path, capsys, r8):
    doc = write_doc(tmp_path, "legacy.txt", "先生は本を読んだ。\n")
    rc, out = ask(tmp_path, capsys, [doc], "先生は何を読んだ？", mode="legacy")
    assert rc == 2 and out["verdict"] == "UNKNOWN_ROUTE_CONFIGURATION"
    assert "question_cross" not in out


def test_engine_route_does_not_enter_the_later_stage(tmp_path, capsys, r8):
    argv = ["--store", str(tmp_path / "store.json"), "ask", "--engine", "--federation",
            str(tmp_path / "missing.db"), "--", "Who read the book?"]
    capsys.readouterr()
    rc = cli.main(argv)
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["verdict"] == "UNKNOWN_NOT_LOADED"
    assert "question_cross" not in out


def test_round5_without_a_document_keeps_the_original_abstention(tmp_path, capsys, r8, monkeypatch):
    monkeypatch.setattr(cli, "_round5_question_cross", lambda result, documents, query: result)
    _, baseline = ask(tmp_path, capsys, [], "先生は何を読んだ？")
    monkeypatch.undo()
    _, actual = ask(tmp_path, capsys, [], "先生は何を読んだ？")
    assert actual.get("verdict") in cli._QC_TRIGGER
    assert without_timing(actual) == without_timing(baseline)


def test_non_trigger_abstention_with_document_is_byte_equivalent(tmp_path, capsys, r8, monkeypatch):
    from verantyx.one import Vera

    doc = write_doc(tmp_path, "unsupported.txt", "先生は本を読んだ。\n")
    stub = {"kind": "unknown", "verdict": "UNKNOWN_UNSUPPORTED_EVIDENCE", "text": "",
            "sources": [], "trace": [{"part": "round5", "status": "abstained"}]}
    monkeypatch.setattr(Vera, "ask", lambda self, query: dict(stub))
    _, actual = ask(tmp_path, capsys, [doc], "先生は何を読んだ？")
    monkeypatch.setattr(cli, "_round5_question_cross", lambda result, documents, query: result)
    _, baseline = ask(tmp_path, capsys, [doc], "先生は何を読んだ？")
    assert actual["verdict"] == baseline["verdict"] == "UNKNOWN_UNSUPPORTED_EVIDENCE"
    assert "question_cross" not in actual and without_timing(actual) == without_timing(baseline)
