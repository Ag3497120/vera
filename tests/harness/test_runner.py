"""H2: documents -> corpus, `ask`, `verify` / `replay`, the memory (`mem_say` / `mem_ask`).  Fake clients only."""
import json
import os
import shutil
import sys

import pytest

from fakes import ASK_TURNS, DOCS, QUESTION, FakeOpenAI
from verantyx.harness import docs_corpus as dc
from verantyx.harness import runner as rn
from verantyx.harness.backends import make_backend


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    return str(d)


def oa(script):
    return make_backend("openai", "fake-gpt", client=FakeOpenAI(script))


# -- documents ------------------------------------------------------------------------------------------------------------------
def test_sentences_are_split_at_terminators_with_their_closers_and_at_line_breaks():
    text = "彼は「行く。」と言った。次の文！\nこれは？はい。\n\n見出しだけの行\n"
    assert dc.split_sentences(text) == ["彼は「行く。」と言った。", "次の文！", "これは？", "はい。", "見出しだけの行"]


def test_markdown_markers_and_code_fences_are_removed_but_nothing_else_is_rewritten():
    text = "# 見出し\n- 項目は一つ。\n1. 番号付き。\n> 引用。\n```\nコード。\n```\n本文。"
    assert dc.split_sentences(text) == ["見出し", "項目は一つ。", "番号付き。", "引用。", "本文。"]


def test_rows_have_the_loom_shape_and_the_title_is_the_file_name(docs):
    rows = dc.build_rows(docs)
    assert [r["sent"] for r in rows][1] == "青葉堂の旧称は松風庵。"
    r = rows[1]
    assert set(r) == {"sha", "title", "sent", "source"} and r["title"] == "青葉堂" and r["source"] == "青葉堂#1"
    import hashlib
    assert r["sha"] == hashlib.sha256(r["sent"].encode()).hexdigest()
    data, _ = dc.build_corpus(docs)
    assert data == dc.build_corpus(docs)[0]                                     # deterministic bytes


def test_a_directory_is_walked_in_sorted_order_and_hidden_or_foreign_files_are_skipped(tmp_path):
    d = tmp_path / "d"
    (d / "sub").mkdir(parents=True)
    (d / "b.txt").write_text("二番目。", encoding="utf-8")
    (d / "a.md").write_text("一番目。", encoding="utf-8")
    (d / "sub" / "c.txt").write_text("三番目。", encoding="utf-8")
    (d / ".hidden.txt").write_text("隠し。", encoding="utf-8")
    (d / "x.pdf").write_bytes(b"%PDF")
    assert [r["sent"] for r in dc.build_rows(str(d))] == ["一番目。", "二番目。", "三番目。"]


@pytest.mark.parametrize("make,code", [(lambda p: str(p / "nope"), "docs_missing"), (lambda p: str(p), "docs_empty")])
def test_missing_or_empty_documents_are_typed_refusals(tmp_path, make, code):
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(make(tmp_path))
    assert e.value.code == code


def test_a_file_that_is_not_utf8_is_refused(tmp_path):
    f = tmp_path / "bad.txt"
    f.write_bytes("あ".encode("shift_jis"))
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(f))
    assert e.value.code == "docs_not_utf8"


# -- ask ------------------------------------------------------------------------------------------------------------------------
def test_ask_prints_the_quote_with_its_source_sentence_and_the_run_directory(docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa([[b for b in t if b[0] != "text"] for t in ASK_TURNS]), str(tmp_path / "runs"))
    lines = a.render().splitlines()
    assert lines[0] == "答え: 「松風庵」" and lines[1] == "根拠: 青葉堂の旧称は松風庵。（青葉堂#1）" and lines[2] == "run: " + a.run_dir
    assert os.path.isdir(a.run_dir) and a.run_dir.startswith(str(tmp_path / "runs"))


def test_the_run_folder_holds_the_ledger_the_corpus_and_a_record_without_secrets(docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa([[b for b in t if b[0] != "text"] for t in ASK_TURNS]), str(tmp_path / "runs"))
    assert {"ops.jsonl", "HEAD", "meta.json", "corpus.jsonl", "harness.json"} <= set(os.listdir(a.run_dir))
    info = json.load(open(os.path.join(a.run_dir, "harness.json"), encoding="utf-8"))
    assert info["kind"] == "ask" and info["backend"]["backend"] == "openai" and info["evidence"] == "v6" and info["driver_report"]["ended"] == "closed"
    begin = json.loads(open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8").readline())
    assert begin["result"]["evidence_profile"] == {"version": "evidence.v6", "subject_scope": "clause_or_title"}      # the gate is the recorded evidence.v6
    assert begin["result"]["task"]["mode"] == "record_only"


def test_a_question_the_documents_do_not_answer_is_refused_with_the_abstention_type(docs, tmp_path):
    script = [[("tool", "lookup", {"text": "社長", "tier": "any"})], [("tool", "abstain", {"type": "no_record"})]]
    a = rn.ask("青葉堂の社長は誰ですか", docs, oa(script), str(tmp_path / "runs"))
    assert a.status == "refused" and a.reason == "no_record" and a.verified
    first = a.render().splitlines()[0]
    assert first.startswith("分かりません（理由: no_record、") and a.text is None


def test_a_refused_emit_then_an_abstention_names_the_last_refusal_of_the_gate(docs, tmp_path):
    """The model weaves a sentence that does not state what was asked; the gate refuses; the model gives up.  The user sees 「分かりません」 and the gate's reason."""
    script = [[("tool", "weave_span", {"sid": 0, "tier": "RUN", "first": "東京都", "last": "東京都"})], [("tool", "emit", {})], [("tool", "abstain", {"type": "cannot_weave"})]]
    a = rn.ask(QUESTION, docs, oa(script), str(tmp_path / "runs"))
    assert a.status == "refused" and a.reason == "cannot_weave"
    assert a.detail["last_refusal"].startswith("no_evidence") and a.detail["emit_refusals"] == 1
    assert "最後の拒否: no_evidence" in a.render()


def test_a_wrong_but_well_formed_quote_does_not_pass_the_gate(docs, tmp_path):
    """Quoting a real sentence that is about something else (the store owner, not the old name) is refused: the answer must come from a sentence that answers THIS question."""
    script = [[("tool", "weave_span", {"sid": 2, "tier": "RUN", "first": "山田", "last": "山田"})], [("tool", "emit", {})], [("tool", "abstain", {"type": "unknown"})]]
    a = rn.ask(QUESTION, docs, oa(script), str(tmp_path / "runs"))
    assert a.status == "refused" and a.text is None and "山田" not in a.render()


def test_the_turn_limit_and_the_runaway_cap_end_a_run_with_their_own_reason(docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa([[("tool", "status", {})]] * 12), str(tmp_path / "runs"), max_turns=3)
    assert a.reason == "max_turns" and a.verified
    b = rn.ask(QUESTION, docs, oa([[("tool", "status", {})]] * 30), str(tmp_path / "runs"))
    assert b.reason in ("cap_repeat", "cap_status")


def test_an_empty_question_and_a_bad_task_are_refused_before_any_call(docs, tmp_path):
    fake = FakeOpenAI([])
    with pytest.raises(rn.HarnessError) as e:
        rn.ask("   ", docs, make_backend("openai", "m", client=fake), str(tmp_path / "runs"))
    assert e.value.code == "bad_question" and fake.calls == []


# -- verify / replay ------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def finished(docs, tmp_path):
    return rn.ask(QUESTION, docs, oa([[b for b in t if b[0] != "text"] for t in ASK_TURNS]), str(tmp_path / "runs"))


def test_verify_and_replay_of_a_fresh_run_are_ok_and_identical(finished):
    v = rn.verify_path(finished.run_dir)
    assert v["status"] == "OK" and v["kind"] == "loom" and v["rows"] == 7
    r = rn.replay_path(finished.run_dir)
    assert r["status"] == "IDENTICAL" and r["identical"] and r["text"] == "松風庵" and r["rows"] == 7


def test_a_run_folder_moved_elsewhere_still_verifies_because_its_corpus_travels_with_it(finished, tmp_path):
    moved = tmp_path / "elsewhere" / "myrun"
    shutil.copytree(finished.run_dir, str(moved))
    shutil.rmtree(str(tmp_path / "runs" / "_corpora"))                           # the shared corpus copy is gone; the one beside the ledger remains
    assert rn.verify_path(str(moved))["status"] == "OK" and rn.replay_path(str(moved))["status"] == "IDENTICAL"


def test_a_changed_byte_in_the_ledger_is_tampering(finished, tmp_path):
    moved = tmp_path / "t"
    shutil.copytree(finished.run_dir, str(moved))
    p = moved / "ops.jsonl"
    p.write_text(p.read_text(encoding="utf-8").replace("松風庵", "松風菴", 1), encoding="utf-8")
    assert rn.verify_path(str(moved))["status"] == "TAMPERED"


def test_a_changed_corpus_is_an_inputs_mismatch_not_a_pass(finished, tmp_path):
    moved = tmp_path / "c"
    shutil.copytree(finished.run_dir, str(moved))
    (moved / "corpus.jsonl").write_text("{}\n", encoding="utf-8")
    v = rn.verify_path(str(moved))
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "corpus_sha_mismatch"
    assert rn.replay_path(str(moved))["status"] == "INPUTS"


def test_a_folder_that_is_not_a_run_is_not_a_run(tmp_path):
    assert rn.verify_path(str(tmp_path))["status"] == "NOT_A_RUN" and rn.replay_path(str(tmp_path))["status"] == "NOT_A_RUN"


def test_the_bundled_tool_schemas_are_the_ones_the_mcp_door_serves(tmp_path):
    pytest.importorskip("mcp")

    def norm(o):
        if isinstance(o, dict):
            return {k: norm(v) for k, v in o.items() if k != "title"}
        if isinstance(o, list):
            return [norm(x) for x in o]
        return o
    live = rn.live_loom_tool_objects(str(tmp_path))
    bundled = rn.loom_tool_objects()
    assert [t.name for t in bundled] == [t.name for t in live]
    for b, l in zip(bundled, live):
        assert b.description == l.description and norm(b.inputSchema) == norm(l.inputSchema), b.name


def test_the_system_prompt_is_the_measured_weaver_text_and_its_sha_is_in_the_ledger(docs, tmp_path):
    from verantyx.harness import prompting
    a = rn.ask(QUESTION, docs, oa([[("tool", "abstain", {"type": "unknown"})]]), str(tmp_path / "runs"))
    meta = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")][1]
    assert meta["op"] == "harness_meta" and meta["args"]["agent_definition_sha"] == prompting.sha(prompting.loom_prompt())
    assert "You are a weaver at the Vera loom" in prompting.loom_prompt() and "Anything you write as plain text is discarded unread" in prompting.loom_prompt()


# -- the memory -----------------------------------------------------------------------------------------------------------------
STORY_ONE = [[("tool", "declare_topic", {"text": "広報"}), ("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})]]
ANSWER_FIRST = [[("tool", "recall", {"question": "広報の担当は何ですか"})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})]]


def test_a_memory_session_keeps_one_fact_per_write_and_answers_with_the_quote(tmp_path):
    store = str(tmp_path / "store")
    r = rn.mem_say(store, ["広報の担当は山本です"], oa(STORY_ONE))
    assert r.committed and r.session == 1 and r.reports == [{"turn": "1-1", "contradictions": [], "bugs": [], "i": r.reports[0]["i"]}]
    a = rn.mem_ask(store, "広報の担当は何ですか", oa(ANSWER_FIRST))
    assert a.status == "answered" and a.text == "山本" and a.verified and a.sources[0]["text"] == "広報の担当は山本"
    assert rn.verify_path(store)["status"] == "OK" and rn.verify_path(a.run_dir)["status"] == "OK" and rn.replay_path(a.run_dir)["status"] == "IDENTICAL"


def test_two_told_answers_are_contested_not_picked(tmp_path):
    store = str(tmp_path / "store")
    rn.mem_say(store, ["広報の担当は山本", "広報の担当は田中"],
               oa([[("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})],
                   [("tool", "write", {"text": "広報の担当は田中"}), ("tool", "report", {"contradictions": [["1-1", "1-2"]]})]]))
    a = rn.mem_ask(store, "広報の担当は何ですか", oa([[("tool", "recall", {"question": "広報の担当は何ですか"})], [("tool", "abstain", {"type": "contested"})]]))
    assert a.status == "refused" and a.reason == "contested" and sorted(a.detail["contested_values"]) == ["山本", "田中"] and a.text is None


def test_a_memory_that_was_never_told_says_it_does_not_know(tmp_path):
    store = str(tmp_path / "store")
    rn.mem_say(store, ["広報の担当は山本"], oa(STORY_ONE))
    a = rn.mem_ask(store, "経理の担当は何ですか", oa([[("tool", "recall", {"question": "経理の担当は何ですか"})], [("tool", "abstain", {"type": "no_record"})]]))
    assert a.status == "refused" and a.reason == "no_record"


def test_asking_an_empty_memory_is_a_typed_refusal(tmp_path):
    a = rn.mem_ask(str(tmp_path / "empty"), "広報の担当は何ですか", oa([]))
    assert a.status == "refused" and a.reason == "empty_store"


def test_a_session_that_fails_is_not_committed(tmp_path):
    class Boom:
        def __init__(self):
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(lambda **kw: (_ for _ in ()).throw(RuntimeError("down")))})})()
    store = str(tmp_path / "store")
    r = rn.mem_say(store, ["広報の担当は山本"], make_backend("openai", "m", client=Boom()))
    assert not r.committed and r.ended == "api_error" and "down" in (r.error or "")
    assert rn.mem_ask(store, "広報の担当は何ですか", oa([])).reason == "empty_store"


def test_the_memory_prompts_are_frozen_text_with_one_fact_per_write_guidance():
    from verantyx.harness import prompting
    assert "ONE fact as ONE sentence" in prompting.mem_story_prompt() and "END THE TURN WITH `report" in prompting.mem_story_prompt()
    assert "emit" in prompting.mem_question_prompt() and "contested" in prompting.mem_question_prompt()
    assert "一つ" in rn.MEM_GUIDANCE or "1 つ" in rn.MEM_GUIDANCE
