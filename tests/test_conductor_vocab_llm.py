"""Wiring of the LLM closed choice into ConductorVocabulary (V2 and the connection checks).
Every provider here is a local fake; no model is contacted."""
from __future__ import annotations

import inspect
import json
import re
import subprocess
from pathlib import Path

import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame
from verantyx.conductor_vocab import ConductorVocabulary, VocabularyResolution
from verantyx.llm_choice import ChoiceLedger, CodexProvider, LLMChooser, ProviderReply
from verantyx.memory_frame import Memory, WriteRejected, witness_class

LINE = re.compile(r"^(\d+): (.*)$")
QUESTION = "Which route for 経路選択?"


def shown_terms(prompt):
    return [json.loads(m.group(2))["term"] for m in map(LINE.match, prompt.split("\n")) if m]


def pick(term):
    return lambda prompt: json.dumps({"choice": shown_terms(prompt).index(term)})


class Fake:
    def __init__(self, *replies, name="fake"):
        self.replies, self.prompts, self.name = list(replies), [], name

    def ask(self, prompt):
        self.prompts.append(prompt)
        item = self.replies.pop(0)
        item = item(prompt) if callable(item) else item
        if isinstance(item, ProviderReply):
            return item
        return ProviderReply.success(item, self.name, "fake-model", "none")


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"2026-10-02T11:00:{self.n % 60:02d}"


def identity(n):
    """Both asks request this order; the chooser itself shifts the second so the two orders differ."""
    return list(range(n))


@pytest.fixture
def unpolluted_memory_ask(monkeypatch):
    """Give the test the real ``Memory.ask(..., evidence_only=...)``.

    ``verantyx.memory_revalidate`` (imported by other test modules) replaces ``Memory.ask`` at import
    time with a wrapper that drops the ``evidence_only`` parameter, so after the full suite has been
    collected the call raises TypeError.  The original is kept in that wrapper's closure; it is put
    back for the duration of the test only.  If it cannot be found the test fails, it is not skipped.
    """
    current = Memory.ask
    if "evidence_only" not in inspect.signature(current).parameters:
        inner = [c.cell_contents for c in (current.__closure__ or ()) if callable(c.cell_contents)
                 and "evidence_only" in inspect.signature(c.cell_contents).parameters]
        if len(inner) != 1:
            pytest.fail("Memory.ask lost evidence_only and the original could not be recovered")
        monkeypatch.setattr(Memory, "ask", inner[0])


def build(tmp_path, provider, **kw):
    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl"), now=Clock()))
    decisions = [frame.add_decision("公開工程", "公開"), frame.add_decision("保管工程", "保管"),
                 frame.add_decision("確認工程", "点検")]
    ledger = ChoiceLedger(tmp_path / "l.jsonl", clock=Clock())
    chooser = LLMChooser(provider, ledger, order_source=identity, **kw)
    vocabulary = ConductorVocabulary(frame, aliases={}, senses={}, chooser=chooser)
    return frame, vocabulary, ledger, chooser, decisions


def adopted(tmp_path, term="保管"):
    fake = Fake(pick(term), pick(term))
    frame, vocabulary, ledger, chooser, decisions = build(tmp_path, fake)
    res = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert res.status == "ADOPTED", res
    return frame, vocabulary, ledger, chooser, decisions, res, fake


# ------------------------------------------------------------------ V2: testimony, not evidence
def test_adopted_alias_witness_is_typed_testimony_and_not_evidence(tmp_path):
    frame, vocabulary, ledger, chooser, _, res, fake = adopted(tmp_path)
    assert res.canonical == "保管" and res.support == "testimony" and res.outcome == "LLM_ADOPTED"
    assert res.chooser_source == "argument" and res.question_kind == "CHOICE"
    record = frame.memory.records[res.record_ids[0]]
    witness = record["witness"]
    assert record["kind"] == "ALIAS" and witness_class(witness) == "testimony"
    assert witness["counts_as_evidence"] is False and witness["mapping_type"] == "LLM_TESTIMONY_MAPPING"
    assert witness["by"] == "llm-choice" and witness["support"] == "testimony"
    assert witness["ledger_decision_id"] == res.ledger_ids[0]
    assert set(res.ledger_ids[1:]) == {a["id"] for a in witness["asks"]} and len(witness["asks"]) == 2
    event = frame.memory.aliases[("agent-option", "出版")]
    assert event["status"] == "ADOPT" and event["by"] == "llm-choice"
    assert event["counts_as_evidence"] is False and event["ledger_decision_id"] == witness["ledger_decision_id"]


def test_adopted_alias_does_not_flow_into_evidence_only_answers(tmp_path, unpolluted_memory_ask):
    frame, vocabulary, *_ , res, fake = adopted(tmp_path)
    alias_id = res.record_ids[0]
    alias_subject = frame.memory.records[alias_id]["slots"]["subject"]
    # a record that IS evidence: a FACT whose witness text is in a file
    sentence = "公開手順の状態は整備済みである。"
    source = tmp_path / "doc.txt"
    source.write_text(sentence + "\n", encoding="utf-8")
    fact = frame.memory.write("FACT", "tester", witness={"kind": "text_in_file", "path": str(source),
                                                         "needle": sentence},
                              subject="公開手順", attribute="状態", value="整備済み")
    question = f"{alias_subject}の語義対応は？"

    plain = frame.memory.ask(question, evidence_only=False)
    assert plain["verdict"] == "ANSWER" and alias_id in plain["records"]
    assert plain["witness_classes"][alias_id] == "testimony"

    strict = frame.memory.ask(question, evidence_only=True)
    assert alias_id not in strict["records"] and strict["verdict"] != "ANSWER"

    # control: the evidence route is alive, only the alias is dropped from it
    control = frame.memory.ask("公開手順の状態は？", evidence_only=True)
    assert control["verdict"] == "ANSWER" and fact["id"] in control["records"]
    assert control["witness_classes"][fact["id"]] == "text_in_file"


def test_second_resolve_is_alias_not_exact_and_frame_terms_do_not_grow(tmp_path):
    frame, vocabulary, ledger, chooser, _, res, fake = adopted(tmp_path)
    before = vocabulary.frame_terms()
    asks_before = len(fake.prompts)
    again = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert again.status == "ALIAS" and again.status != "EXACT" and again.canonical == "保管"
    assert again.support == "testimony" and again.record_ids == res.record_ids
    assert vocabulary.frame_terms() == before and "出版" not in before
    assert len(fake.prompts) == asks_before            # reuse comes from the alias record, not another ask


def test_exact_frame_term_is_never_asked_even_with_a_chooser(tmp_path):
    fake = Fake()
    frame, vocabulary, *_ = build(tmp_path, fake)
    res = vocabulary.resolve("公開")
    assert res.status == "EXACT" and res.support == "frame" and fake.prompts == []


def test_llm_choice_witness_without_a_ledger_decision_is_rejected(tmp_path):
    frame, vocabulary, ledger, chooser, _, res, fake = adopted(tmp_path)
    bad = {"kind": "testimony", "by": "llm-choice", "ledger_decision_id": "no-such-decision",
           "candidate_terms": ["公開", "保管", "点検"], "asks": []}
    with pytest.raises(WriteRejected):
        vocabulary.adopt_alias("別語", "保管", witness=bad)
    # a real decision for another word, or another choice, is not a licence either
    real = dict(bad, ledger_decision_id=res.ledger_ids[0])
    with pytest.raises(WriteRejected):
        vocabulary.adopt_alias("別語", "保管", witness=real)
    with pytest.raises(WriteRejected):
        vocabulary.adopt_alias("出版2", "公開", witness=real)
    with pytest.raises(WriteRejected):
        vocabulary.adopt_alias("別語", "保管", witness=dict(real, candidate_terms=["公開", "保管"]))
    assert not any((r.get("witness") or {}).get("word") in ("別語", "出版2") for r in frame.memory.records.values())


def test_llm_choice_witness_needs_a_chooser(tmp_path):
    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl"), now=Clock()))
    frame.add_decision("公開工程", "公開")
    plain = ConductorVocabulary(frame, aliases={}, senses={})
    with pytest.raises(WriteRejected):
        plain.adopt_alias("出版", "公開", witness={"kind": "testimony", "by": "llm-choice",
                                                   "ledger_decision_id": "x", "candidate_terms": ["公開"]})


def test_llm_choice_witness_cannot_claim_evidence(tmp_path):
    frame, vocabulary, ledger, chooser, _, res, fake = adopted(tmp_path)
    fake2 = Fake(pick("点検"), pick("点検"))
    other = LLMChooser(fake2, ledger, order_source=identity)
    vocab2 = ConductorVocabulary(frame, aliases={}, senses={}, chooser=other)
    d = other.choose("別語", [__import__("verantyx.llm_choice", fromlist=["x"]).ChoiceCandidate(t)
                              for t in ("公開", "保管", "点検")])
    record = vocab2.adopt_alias("別語", "点検", witness={
        "kind": "testimony", "by": "llm-choice", "ledger_decision_id": d.decision_id,
        "candidate_terms": ["公開", "保管", "点検"], "asks": [], "counts_as_evidence": True,
        "mapping_type": "FACT"})
    w = record["witness"]
    assert w["counts_as_evidence"] is False and w["mapping_type"] == "LLM_TESTIMONY_MAPPING"


def test_conductor_answer_through_an_llm_alias_cites_testimony_records(tmp_path, unpolluted_memory_ask):
    # (the words 公開/出版 trip the conductor's outward-publishing guard, so this test uses neutral ones)
    fake = Fake(pick("保管"), pick("保管"))
    frame, vocabulary, ledger, chooser, decisions = build(tmp_path, fake)
    res = vocabulary.resolve("格納", QUESTION, question_kind="CHOICE")
    assert res.status == "ADOPTED"
    policy = frame.add_policy("CHOICE", "経路選択", "保管", decisions[1]["id"])
    reply = frame.answer(AgentQuestion("q", QUESTION, ["格納", "点検"]))
    assert reply.kind == "ANSWER" and reply.answer == "格納", reply
    alias_ids = [rid for rid in reply.record_ids if frame.memory.records[rid]["kind"] == "ALIAS"]
    assert res.record_ids[0] in alias_ids and policy["id"] in reply.record_ids
    assert all(witness_class(frame.memory.records[rid]["witness"]) == "testimony" for rid in alias_ids)
    assert all(frame.memory.records[rid]["witness"]["counts_as_evidence"] is False for rid in alias_ids)
    # the same alias is dropped from the evidence-only view of memory
    subject = frame.memory.records[res.record_ids[0]]["slots"]["subject"]
    assert res.record_ids[0] not in frame.memory.ask(f"{subject}の語義対応は？", evidence_only=True)["records"]


# ------------------------------------------------------------------ connection
def test_default_is_no_llm_and_creates_no_ledger(tmp_path):
    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl"), now=Clock()))
    frame.add_decision("公開工程", "公開")
    frame.add_decision("保管工程", "保管")
    vocabulary = ConductorVocabulary(frame, aliases={}, senses={})
    res = vocabulary.resolve("出版", QUESTION)
    assert res.status == "ESCALATE" and res.reason == "no closed-choice asker is configured"
    assert res.chooser_source == "" and res.outcome == "" and res.canonical is None
    assert vocabulary.effective_chooser() == (None, "")
    assert not (tmp_path / "l.jsonl").exists()


def test_without_a_chooser_a_memory_resolver_is_still_used_as_before(tmp_path):
    prompts = []

    def asker(prompt):
        prompts.append(prompt)
        terms = [json.loads(x)["term"] if x.startswith("{") else x
                 for x in [line.split(": ", 1)[1] for line in prompt.split("候補:\n", 1)[1].split("\n答え", 1)[0].splitlines()]]
        return json.dumps({"choice": terms.index("保管")})

    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl"), asker=asker, now=Clock()))
    frame.add_decision("保管工程", "保管")
    frame.add_decision("公開工程", "公開")
    res = ConductorVocabulary(frame, aliases={}, senses={}).resolve("出版", QUESTION)
    assert res.status == "ADOPTED" and res.canonical == "保管" and len(prompts) == 2
    witness = frame.memory.records[res.record_ids[0]]["witness"]
    assert witness["by"] == "llm-closed-choice" and res.chooser_source == ""


def test_frame_vocab_chooser_attribute_enables_the_path(tmp_path):
    fake = Fake(pick("保管"), pick("保管"))
    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl"), now=Clock()))
    for s, c in (("公開工程", "公開"), ("保管工程", "保管"), ("確認工程", "点検")):
        frame.add_decision(s, c)
    chooser = LLMChooser(fake, ChoiceLedger(tmp_path / "l.jsonl"),
                         order_source=identity)
    frame.vocab_chooser = chooser
    vocabulary = ConductorVocabulary(frame, aliases={}, senses={})
    res = vocabulary.resolve("出版", QUESTION)
    assert res.status == "ADOPTED" and res.chooser_source == "frame"
    assert res.question_kind == "CHOICE" and res.question_kind_source == "classified"


def test_argument_chooser_takes_precedence_over_the_frame_attribute(tmp_path):
    frame, vocabulary, ledger, chooser, *_ = build(tmp_path, Fake(pick("保管"), pick("保管")))
    frame.vocab_chooser = object()
    assert vocabulary.effective_chooser() == (chooser, "argument")


@pytest.mark.parametrize("kind", ["CONFIRM", "STATUS", "ORDER", "OTHER", "PERMISSION"])
def test_kinds_without_an_option_role_do_not_ask(tmp_path, kind):
    fake = Fake()
    frame, vocabulary, ledger, chooser, *_ = build(tmp_path, fake)
    res = vocabulary.resolve("出版", "何か", question_kind=kind)
    assert res.status == "ESCALATE" and res.outcome == "NO_ROLE_CANDIDATES" and fake.prompts == []
    assert res.reason == "question kind has no option-mapping role" and res.question_kind_source == "explicit"
    assert ledger.entries() == ()


def test_choice_candidates_exclude_decision_subjects(tmp_path):
    fake = Fake(pick("保管"), pick("保管"))
    frame, vocabulary, ledger, chooser, *_ = build(tmp_path, fake)
    all_terms = {c.term for c in vocabulary.candidates("出版")}
    assert {"公開工程", "保管工程", "確認工程"} <= all_terms          # the unrestricted list has the subjects
    res = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert {c.term for c in res.candidates} == {"公開", "保管", "点検"}
    assert set(shown_terms(fake.prompts[0])) == {"公開", "保管", "点検"}
    assert not any("工程" in t for t in shown_terms(fake.prompts[0]))


def test_prompt_context_is_the_frame_sentences_of_the_candidate(tmp_path):
    fake = Fake(pick("保管"), pick("保管"))
    frame, vocabulary, *_ = build(tmp_path, fake)
    vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    rows = [json.loads(LINE.match(l).group(2)) for l in fake.prompts[0].split("\n") if LINE.match(l)]
    used = {r["term"]: r["used_in"] for r in rows}
    assert used["保管"] == ["保管工程の決定は保管である。"]


def test_single_candidate_is_still_asked_twice(tmp_path):
    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl"), now=Clock()))
    frame.add_decision("公開工程", "公開")
    fake = Fake(pick("公開"), pick("公開"))
    chooser = LLMChooser(fake, ChoiceLedger(tmp_path / "l.jsonl"),
                         order_source=lambda n: list(range(n)))
    vocabulary = ConductorVocabulary(frame, aliases={"辞書別名": "公開"}, senses={}, chooser=chooser)
    assert [c.term for c in vocabulary.candidates("辞書別名")] == ["公開"]
    res = vocabulary.resolve("辞書別名", QUESTION, question_kind="CHOICE")
    assert len(fake.prompts) == 2 and res.status == "ADOPTED" and res.canonical == "公開"
    assert fake.prompts[0] != fake.prompts[1]


def test_too_many_candidates_escalates_without_asking(tmp_path):
    fake = Fake()
    frame, vocabulary, ledger, chooser, *_ = build(tmp_path, fake, max_candidates=2)
    res = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert res.status == "ESCALATE" and res.outcome == "LLM_REFUSED:TOO_MANY_CANDIDATES" and fake.prompts == []


def test_failure_writes_no_alias_event_and_the_word_is_asked_again(tmp_path):
    runner_calls = []

    def runner(argv, **kw):
        runner_calls.append(argv)
        raise subprocess.TimeoutExpired(argv, 1.0)

    provider = CodexProvider(binary="codex-test", runner=runner)
    frame, vocabulary, ledger, chooser, *_ = build(tmp_path, Fake())      # frame/ledger only
    chooser = LLMChooser(provider, ledger, order_source=lambda n: list(range(n)))
    vocabulary = ConductorVocabulary(frame, aliases={}, senses={}, chooser=chooser)
    res = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert res.status == "ESCALATE" and res.outcome == "LLM_FAILED:TIMEOUT" and "TIMEOUT" in res.reason
    assert ("agent-option", "出版") not in frame.memory.aliases
    assert len(runner_calls) == 1

    fixed = Fake(pick("保管"), pick("保管"))
    chooser2 = LLMChooser(fixed, ledger, order_source=identity)
    again = ConductorVocabulary(frame, aliases={}, senses={}, chooser=chooser2).resolve(
        "出版", QUESTION, question_kind="CHOICE")
    assert again.status == "ADOPTED" and len(fixed.prompts) == 2       # the failure did not kill the word


def test_abstention_writes_a_typed_alias_event_and_blocks_a_second_ask(tmp_path):
    fake = Fake(pick("公開"), pick("保管"))
    frame, vocabulary, ledger, chooser, *_ = build(tmp_path, fake)
    res = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert res.status == "ESCALATE" and res.outcome == "LLM_ABSTAINED:DISAGREE" and res.canonical is None
    event = frame.memory.aliases[("agent-option", "出版")]
    assert event["status"] == "UNRESOLVED" and event["by"] == "llm-choice" and event["choice"] is None
    assert event["ledger_decision_id"] == res.ledger_ids[0]
    assert not [r for r in frame.memory.records.values() if r["kind"] == "ALIAS"]
    again = vocabulary.resolve("出版", QUESTION, question_kind="CHOICE")
    assert again.status == "ESCALATE" and "prior alias attempt" in again.reason and len(fake.prompts) == 2


def test_none_selected_is_recorded_as_none_status(tmp_path):
    fake = Fake('{"choice": null}')
    frame, vocabulary, *_ = build(tmp_path, fake)
    res = vocabulary.resolve("天気", QUESTION, question_kind="CHOICE")
    assert res.outcome == "LLM_ABSTAINED:NONE_SELECTED"
    assert frame.memory.aliases[("agent-option", "天気")]["status"] == "NONE"


def test_resolve_options_passes_options_and_kind_through(tmp_path):
    fake = Fake(pick("保管"), pick("保管"))
    frame, vocabulary, *_ = build(tmp_path, fake)
    results = vocabulary.resolve_options(["公開", "出版"], QUESTION)
    assert [r.status for r in results] == ["EXACT", "ADOPTED"]
    assert results[1].question_kind == "CHOICE"
    explicit = vocabulary.resolve_options(["公開"], QUESTION, question_kind="CONFIRM")
    assert explicit[0].status == "EXACT"


def test_cached_adoption_in_a_new_memory_is_checked_against_the_ledger(tmp_path):
    frame, vocabulary, ledger, chooser, _, res, fake = adopted(tmp_path)
    # a fresh memory (no alias yet) sharing the ledger: the chooser answers from its ledger-rebuilt cache
    other = tmp_path / "other"
    other.mkdir()
    frame2 = ProjectFrame(Memory(str(other / "m.jsonl"), now=Clock()))
    for s, c in (("公開工程", "公開"), ("保管工程", "保管"), ("確認工程", "点検")):
        frame2.add_decision(s, c)
    fake2 = Fake()
    chooser2 = LLMChooser(fake2, ChoiceLedger(tmp_path / "l.jsonl"))
    res2 = ConductorVocabulary(frame2, aliases={}, senses={}, chooser=chooser2).resolve(
        "出版", QUESTION, question_kind="CHOICE")
    assert res2.status == "ADOPTED" and res2.outcome == "LLM_ADOPTED_CACHED" and fake2.prompts == []
    assert res2.ledger_ids[0] == res.ledger_ids[0]
    assert [e["type"] for e in chooser2.ledger.entries()][-1] == "reuse"


def test_old_closed_choice_witness_rules_are_unchanged(tmp_path):
    frame, vocabulary, *_ = build(tmp_path, Fake())
    with pytest.raises(WriteRejected):
        vocabulary.adopt_alias("出版", "保管", witness={"kind": "testimony", "by": "llm-closed-choice",
                                                        "candidate_terms": ["保管"], "asks": []})
    with pytest.raises(WriteRejected):
        vocabulary.adopt_alias("出版", "保管", witness={"kind": "testimony", "by": "someone"})
    rec = vocabulary.adopt_alias("出版", "保管", witness={"kind": "testimony", "by": "human:x"})
    assert rec["witness"]["support"] == "testimony" and "ledger_decision_id" not in rec["witness"]
    assert "ledger_decision_id" not in frame.memory.aliases[("agent-option", "出版")]
