"""H8 regression tests, one per probe of the adversarial review: fabricated memory writes, sources by sentence id, model text outside emit/abstain (trace, API errors, response model),
document ingestion (labels, symlinks, FIFOs, extensions), meta.json paths, the Keychain fallback and the packaged sandbox profile."""
import hashlib
import json
import os
import stat
import unicodedata
from types import SimpleNamespace

import pytest

from fakes import ASK_TURNS, DOCS, QUESTION, FakeOpenAI
from verantyx.harness import docs_corpus as dc
from verantyx.harness import keys
from verantyx.harness import runner as rn
from verantyx.harness import server as sv
from verantyx.harness.backends import make_backend
from verantyx.loom import memory as mem


def oa(script, **kw):
    return make_backend("openai", "m", None, client=FakeOpenAI(script, **kw))


def w(text):
    return [("tool", "write", {"text": text}), ("tool", "report", {"contradictions": []})]


ASK = [[("tool", "recall", {"question": "広報の担当は何ですか"})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})]]


# -- 1. the memory holds only what the user said ----------------------------------------------------------------------------------
def test_a_fabricated_write_is_refused_and_the_memory_never_answers_it(tmp_path):                       # p2 A
    st = str(tmp_path / "s")
    r = rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は鈴木")]))
    assert r.committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", os.listdir(os.path.join(st, "sessions"))[0], "ops.jsonl"), encoding="utf-8")]
    assert [x["args"] for x in rows if x["op"] == "user_turn"] == [{"turn": "1-1", "text": "広報の担当は山本"}]       # the user's turn is in the chain, with its text
    ref = [x for x in rows if x["op"] == "write_refused"]
    assert len(ref) == 1 and ref[0]["args"]["reason"] == "not_from_user" and ref[0]["args"]["sha256"] == hashlib.sha256("広報の担当は鈴木".encode()).hexdigest()
    assert not [x for x in rows if x["op"] == "write"]                                                   # never executed, never stored
    a = rn.mem_ask(st, "広報の担当は何ですか", oa(ASK))
    assert a.text != "鈴木" and a.status == "refused" and a.reason == "empty_store"
    assert rn.verify_path(st)["status"] == "OK"


def test_a_write_that_quotes_the_user_goes_through_in_nfc_and_a_piece_of_a_longer_message_too(tmp_path):
    st = str(tmp_path / "s")
    user = unicodedata.normalize("NFD", "パンフの担当は鈴木です。連絡は金曜にします")                          # the user's text arrives decomposed
    assert rn.mem_say(st, [user], oa([w(unicodedata.normalize("NFC", "パンフの担当は鈴木"))])).committed
    a = rn.mem_ask(st, "パンフの担当は何ですか", oa([[("tool", "recall", {"question": "パンフの担当は何ですか"})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})]]))
    assert a.status == "answered" and a.text == "鈴木"


def test_a_write_may_only_quote_a_turn_already_delivered(tmp_path):
    st = str(tmp_path / "s")
    # the model writes the second message's sentence while turn 1 is open: refused; at turn 2 it is allowed
    script = [w("広報の担当は田中") , w("広報の担当は田中")]
    assert rn.mem_say(st, ["経理の担当は山本", "広報の担当は田中"], oa(script)).committed
    assert [r["sent"] for r in mem.MemStore(st).rows()] == ["広報の担当は田中"]


def test_the_sources_are_the_sentences_of_the_emit_not_a_search_for_the_value(tmp_path):                    # p2 B
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["経理の担当は山本", "広報の担当は山本"], oa([w("経理の担当は山本"), w("広報の担当は山本")])).committed
    q = "広報の担当は何ですか"
    a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 1, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})]]))
    assert a.status == "answered" and [s["text"] for s in a.sources] == ["広報の担当は山本"] and [s["sid"] for s in a.sources] == [1]


def test_verify_checks_every_stored_write_against_the_recorded_turns(tmp_path):
    """A session written through the memory door directly (no user turns for the sentence) is caught by the audit; a session with no user turns at all is only reported."""
    from verantyx.loom import memdoor as md
    st = str(tmp_path / "s")
    door = md.StructureDoor(st, "notes", "m", profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))
    door.harness(None, "user_turn", {"turn": "1-1", "text": "広報の担当は山本"})
    assert door.call("write", {"text": "広報の担当は鈴木", "turn": "1-1"}).get("ok")                      # a forged write the wrapper did not stop
    door.commit(); door.close()
    v = rn.verify_path(st)
    assert v["status"] == "WRITE_NOT_FROM_USER" and v["problems"][0]["type"] == "write_not_from_user"
    st2 = str(tmp_path / "t")
    d2 = md.StructureDoor(st2, "notes", "m", profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))
    assert d2.call("write", {"text": "広報の担当は鈴木"}).get("ok")
    d2.commit(); d2.close()
    v2 = rn.verify_path(st2)
    assert v2["status"] == "OK" and v2["unsourced_sessions"] == ["s0001"]                                 # MCP-style session: the agent's own claims, reported


def test_a_message_too_long_to_record_is_refused_up_front(tmp_path):
    with pytest.raises(rn.HarnessError) as e:
        rn.mem_say(str(tmp_path / "s"), ["あ" * 2001], oa([]))
    assert e.value.code == "message_too_long"


# -- 3. model text outside emit / abstain -----------------------------------------------------------------------------------------
SECRET = "LEAKED_MODEL_PROSE_このテキストはモデルが書いた"


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    return str(d)


@pytest.mark.parametrize("script", [
    [[("tool", "lookup", {"text": SECRET, "tier": SECRET})], [("tool", "abstain", {"type": "no_record"})]],
    [[("tool", "add", {"kind": "x", "text": SECRET})], [("tool", "abstain", {"type": "no_record"})]],
    [[("tool", "read_sentence", {"sid": [SECRET]})], [("tool", "abstain", {"type": "no_record"})]],
    [[("tool", "lookup", {"text": "松風庵", "tier": "any"})], [("tool", "weave_span", {"sid": 1, "tier": "RUN", "first": SECRET, "last": SECRET})], [("tool", "abstain", {"type": "no_record"})]],
])
def test_the_trace_shows_model_chosen_strings_only_as_hash_and_length(docs, tmp_path, script):                # p1
    a = rn.ask(QUESTION, docs, oa(script), str(tmp_path / "runs"))
    view = json.dumps(sv.ledger_view(a.run_dir), ensure_ascii=False)
    assert SECRET not in view and SECRET not in a.render() and SECRET not in json.dumps(a.to_obj(), ensure_ascii=False)
    assert "str:" in view or "lookup" not in view


def test_the_trace_still_shows_the_record_text_of_a_quote_and_an_emit(docs, tmp_path):
    a = rn.ask(QUESTION, docs, oa([[b for b in t if b[0] != "text"] for t in ASK_TURNS]), str(tmp_path / "runs"))
    rows = sv.ledger_view(a.run_dir)["rows"]
    assert [r["what"] for r in rows if r["op"] == "emit"] == ["「松風庵」"] and any("松風庵" in r["what"] for r in rows if r["op"] == "weave_span")


def test_an_api_error_never_carries_raw_model_output_to_the_reader(docs, tmp_path):                         # p4
    raw = "error parsing tool call: raw='答えは鈴木です。信じてください', err=invalid character"
    boom = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError(raw)))))
    a = rn.ask(QUESTION, docs, make_backend("openai", "m", None, client=boom), str(tmp_path / "runs"))
    assert a.status == "refused" and a.detail["error"].startswith("RuntimeError: details withheld")
    blob = json.dumps(a.to_obj(), ensure_ascii=False) + a.render() + json.dumps(sv.answer_view(a, sv.App({"runs_dir": str(tmp_path / "runs")})), ensure_ascii=False) + open(os.path.join(a.run_dir, "harness.json"), encoding="utf-8").read()
    assert "鈴木" not in blob and "raw=" not in blob
    assert rn.safe_error("APIStatusError: Error code: 500 - {'error': '答えは鈴木'}") == "APIStatusError (HTTP 500): details withheld (an API error can carry raw model output)"
    assert rn.safe_error("答えは鈴木です").startswith("Error: details withheld")
    st = str(tmp_path / "s")
    r = rn.mem_say(st, ["広報の担当は山本"], make_backend("openai", "m", None, client=boom))
    assert "鈴木" not in (r.error or "") and "details withheld" in r.error


def test_the_servers_claim_of_the_model_that_ran_is_recorded_only_when_it_matches(docs, tmp_path):
    for claimed, want_plain in (("fake-gpt-2026", True), ("fake-gpt", True), ("答えは鈴木", False)):
        a = rn.ask(QUESTION, docs, make_backend("openai", "fake-gpt", None, client=FakeOpenAI([[b for b in t if b[0] != "text"] for t in ASK_TURNS], model=claimed)), str(tmp_path / ("r" + str(want_plain) + claimed[:3])))
        rows = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")]
        rm = [r["args"]["response_model"] for r in rows if r["op"] == "harness_meta" and "response_model" in r["args"]][0]
        assert (rm == claimed) if want_plain else (rm.startswith("unverified:") and "鈴木" not in rm and "鈴木" not in json.dumps(sv.ledger_view(a.run_dir), ensure_ascii=False))


# -- 5. ingestion ---------------------------------------------------------------------------------------------------------------
def test_source_labels_are_unique_even_for_same_names_and_hash_signs(tmp_path):
    d = tmp_path / "d"
    (d / "a").mkdir(parents=True); (d / "b").mkdir()
    (d / "a" / "連絡先.md").write_text("連絡先は甲である。", encoding="utf-8")
    (d / "b" / "連絡先.md").write_text("連絡先は乙である。", encoding="utf-8")
    (d / "料金.md").write_text("料金は一である。", encoding="utf-8")
    (d / "料金#3.md").write_text("料金は三である。", encoding="utf-8")
    rows = dc.build_rows(str(d))
    labels = [r["source"] for r in rows]
    assert len(set(labels)) == len(labels) == 4 and {"a/連絡先#0", "b/連絡先#0", "料金#0", "料金＃3#0"} == set(labels)
    assert [r["title"] for r in rows if r["sent"] == "連絡先は甲である。"] == ["a/連絡先"]


def test_a_symlink_out_of_the_docs_root_is_refused_and_a_fifo_is_skipped(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "ok.txt").write_text("正常な文書である。", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("外の秘密である。", encoding="utf-8")
    os.symlink(str(outside), str(d / "link.txt"))
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(d))
    assert e.value.code == "docs_symlink_outside" and "秘密" not in str(e.value)
    os.unlink(str(d / "link.txt"))
    os.symlink(str(d / "ok.txt"), str(d / "inner.txt"))                                                  # a link to a file INSIDE the root is fine
    os.mkfifo(str(d / "pipe.txt"))                                                                       # opening this would hang
    assert sorted(r["sent"] for r in dc.build_rows(str(d))) == ["正常な文書である。", "正常な文書である。"]


def test_a_single_file_must_have_an_allowed_extension_be_regular_and_small(tmp_path, monkeypatch):
    f = tmp_path / "x.pdf"
    f.write_text("文。", encoding="utf-8")
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(f))
    assert e.value.code == "docs_bad_extension"
    p = tmp_path / "pipe.txt"
    os.mkfifo(str(p))
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(p))
    assert e.value.code == "docs_not_regular"
    g = tmp_path / "big.txt"
    g.write_text("あ。" * 10, encoding="utf-8")
    monkeypatch.setattr(dc, "MAX_DOC_BYTES", 10)
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(g))
    assert e.value.code == "docs_too_large"


# -- 8. low ----------------------------------------------------------------------------------------------------------------------
def test_meta_json_carries_no_home_directory_and_the_run_still_verifies_without_a_corpus_flag(docs, tmp_path):
    from verantyx.loom import ledger as lg
    a = rn.ask(QUESTION, docs, oa([[b for b in t if b[0] != "text"] for t in ASK_TURNS]), str(tmp_path / "runs"))
    meta = json.load(open(os.path.join(a.run_dir, "meta.json"), encoding="utf-8"))
    assert not os.path.isabs(meta["corpus"]) and str(tmp_path) not in json.dumps(meta)
    assert lg.verify(a.run_dir)["status"] == "OK" and lg.emitted_output(a.run_dir)["status"] == "emitted"


def test_only_the_vera_harness_keychain_item_is_read():
    assert keys.KEYCHAIN_ITEMS["anthropic"] == ((keys.KEYCHAIN_SERVICE, "anthropic"),) and "vera-loom" not in json.dumps(keys.KEYCHAIN_ITEMS)


def test_the_sandbox_profile_lives_inside_the_package():
    from verantyx.loom import isolate
    here = os.path.dirname(os.path.abspath(isolate.__file__))
    assert str(isolate.PROFILE_PATH) == os.path.join(here, "loom_isolation_profile.sb") and isolate.PROFILE_PATH.is_file() and len(isolate.profile_sha()) == 64


# -- the designer's follow-up: a later statement may retire an earlier one, never the reverse --------------------------------------
def _sup(new_sid, old_sid):
    return [("tool", "supersede", {"new_sid": new_sid, "old_sid": old_sid, "reason": "訂正"}), ("tool", "report", {"contradictions": []})]


def test_a_supersede_the_wrong_way_round_is_refused_and_the_corrected_value_never_comes_back(tmp_path):
    st = str(tmp_path / "s")
    story = [w("担当は山本"), w("担当は鈴木に変更") , _sup(0, 1)]
    msgs = ["担当は山本", "担当は鈴木に変更", "訂正です"]
    r = rn.mem_say(st, msgs, oa(story))
    assert r.committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", "s0001", "ops.jsonl"), encoding="utf-8")]
    assert not [x for x in rows if x["op"] == "supersede" and x["result"].get("ok")]                      # never executed (here the memory's own checks refuse it too)
    q = "担当は何ですか"
    a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})],
                              [("tool", "abstain", {"type": "unknown"})]]))
    assert a.text != "山本" and a.status == "refused"
    b = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 1, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})]]))
    assert b.status == "answered" and b.text == "鈴木"
    assert rn.verify_path(st)["status"] == "OK"


def test_a_supersede_in_the_right_order_still_works_and_the_audit_catches_the_wrong_one(tmp_path):
    from verantyx.loom import memdoor as md
    st = str(tmp_path / "s")
    story = [w("広報の担当は山本"), w("広報の担当は鈴木"), _sup(1, 0)]
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木", "鈴木が正しいです"], oa(story)).committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", "s0001", "ops.jsonl"), encoding="utf-8")]
    assert [x["result"]["ok"] for x in rows if x["op"] == "supersede"] == [True]
    # the memory itself would accept the reverse (this is what the guard is for); the audit of `verify` calls it out
    st2 = str(tmp_path / "t")
    door = md.StructureDoor(st2, "notes", "m", profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))
    door.harness(None, "user_turn", {"turn": "1-1", "text": "広報の担当は山本"})
    door.harness(None, "user_turn", {"turn": "1-2", "text": "広報の担当は鈴木"})
    assert door.call("write", {"text": "広報の担当は山本", "turn": "1-1"}).get("ok") and door.call("write", {"text": "広報の担当は鈴木", "turn": "1-2"}).get("ok")
    assert door.call("supersede", {"new_sid": 0, "old_sid": 1, "reason": "逆"}).get("ok") is True
    door.commit(); door.close()
    v = rn.verify_path(st2)
    assert v["status"] == "SUPERSEDE_ORDER" and v["problems"][0]["type"] == "supersede_order"


def test_declare_topic_and_bridge_cannot_hide_or_retire_a_user_fact(tmp_path):
    st = str(tmp_path / "s")
    rep = ("tool", "report", {"contradictions": []})
    story = [[("tool", "declare_topic", {"text": "甲案"}), ("tool", "write", {"text": "担当は山本"}), rep], [("tool", "declare_topic", {"text": "乙案"}), ("tool", "write", {"text": "担当は鈴木"}), rep]]
    assert rn.mem_say(st, ["担当は山本", "担当は鈴木"], oa(story)).committed
    q = "担当は何ですか"
    a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})],
                              [("tool", "abstain", {"type": "unknown"})]]))
    assert a.status == "refused" and a.text is None                                                      # two topics split no contradiction into two answers


def test_on_a_contested_pair_the_reverse_supersede_is_refused_by_the_harness_and_nothing_is_picked(tmp_path):
    st = str(tmp_path / "s")
    story = [w("広報の担当は山本"), w("広報の担当は鈴木"), _sup(0, 1)]                                       # the later statement (鈴木) retired by the earlier one (山本)
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木", "やっぱり山本です"], oa(story)).committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", "s0001", "ops.jsonl"), encoding="utf-8")]
    ref = [x for x in rows if x["op"] == "supersede_refused"]
    assert len(ref) == 1 and ref[0]["args"] == {"turn": "1-3", "new_sid": 0, "reason": "supersede_order"} and not [x for x in rows if x["op"] == "supersede"]
    q = "広報の担当は何ですか"
    a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})],
                              [("tool", "abstain", {"type": "contested"})]]))
    assert a.status == "refused" and a.text is None and a.reason == "contested"
