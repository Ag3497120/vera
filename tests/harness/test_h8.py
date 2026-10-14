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
    user = unicodedata.normalize("NFD", "パンフの担当は鈴木。連絡は金曜にします")                          # the user's text arrives decomposed
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
    door.set_turn("1-1")
    assert door.call("write", {"text": "広報の担当は鈴木"}).get("ok")                                      # a forged write the wrapper did not stop
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
    door.set_turn("1-1")
    assert door.call("write", {"text": "広報の担当は山本"}).get("ok")
    door.set_turn("1-2")
    assert door.call("write", {"text": "広報の担当は鈴木"}).get("ok")
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


# -- round 2 ------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("msg", ["広報の担当は山本ではない", "田中さんは『担当は鈴木』と言ったが間違いだ", "もし予算が通れば広報の担当は山本になる", "広報の担当は山本ですか？", "経理は佐藤です。広報の担当は山本さんの後任が決まるまで未定"])
def test_a_piece_of_a_sentence_never_becomes_a_fact(tmp_path, msg):                                      # p5: negation, quotation, condition, question, mid-sentence cut
    st = str(tmp_path / "s")
    piece = "担当は鈴木" if "鈴木" in msg else "広報の担当は山本"
    assert rn.mem_say(st, [msg], oa([w(piece)])).committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", "s0001", "ops.jsonl"), encoding="utf-8")]
    assert [x["op"] for x in rows if x["op"].endswith("_refused")] == ["write_refused"] and not [x for x in rows if x["op"] == "write"]


def test_a_whole_sentence_of_a_longer_message_is_fine_with_or_without_the_final_maru(tmp_path):
    from verantyx.harness.runner import equals_whole_sentence as eq
    assert eq("広報の担当は山本", "広報の担当は山本。") and eq("広報の担当は山本。", "広報の担当は山本") and eq("経理は佐藤", "経理は佐藤です。\n広報の担当は山本") is False
    assert eq("広報の担当は山本", "経理は佐藤です。\n広報の担当は山本") and eq("広報の担当は山本", "あ！広報の担当は山本？") is False and not eq("", "x")


def test_requoting_an_earlier_turn_cannot_retire_a_later_correction(tmp_path):                       # p5 requote_supersede
    st = str(tmp_path / "s")
    rep = ("tool", "report", {"contradictions": []})
    story = [w("広報の担当は山本"), w("広報の担当は鈴木"), [("tool", "write", {"text": "広報の担当は山本"}), ("tool", "supersede", {"new_sid": 2, "old_sid": 1, "reason": "訂正"}), rep]]
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木に変わりました", "了解"], oa(story)).committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", "s0001", "ops.jsonl"), encoding="utf-8")]
    assert [x["args"]["text"] for x in rows if x["op"] == "write" and x["result"].get("ok")] == ["広報の担当は山本"]          # the second write was not a whole sentence of turn 2
    assert not [x for x in rows if x["op"] == "supersede" and x["result"].get("ok")]
    assert rn.verify_path(st)["status"] == "OK"


def test_the_model_cannot_name_the_turn_a_write_was_said_in(tmp_path):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木"], oa([w("広報の担当は山本"), [("tool", "write", {"text": "広報の担当は山本", "turn": "1-1"}), ("tool", "report", {"contradictions": []})]])).committed
    rows = [json.loads(ln) for ln in open(os.path.join(st, "sessions", "s0001", "ops.jsonl"), encoding="utf-8")]
    assert [x["op"] for x in rows if x["op"].endswith("_refused")] == ["write_refused"]


def test_the_audit_flags_a_write_before_the_first_user_turn_and_a_write_that_is_not_its_turns_sentence(tmp_path):    # d5
    from verantyx.loom import memdoor as md
    st = str(tmp_path / "s")
    door = md.StructureDoor(st, "notes", "m", profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))
    door.set_turn("1-1")
    assert door.call("write", {"text": "広報の担当は鈴木"}).get("ok")                                      # before any user turn
    door.harness(None, "user_turn", {"turn": "1-2", "text": "広報の担当は山本ではない"})
    door.set_turn("1-2")
    assert door.call("write", {"text": "広報の担当は山本"}).get("ok")                                      # a piece of the sentence
    door.commit(); door.close()
    v = rn.verify_path(st)
    assert v["status"] == "WRITE_NOT_FROM_USER" and v["problems"][0]["rows"] and len(v["problems"][0]["rows"]) == 2


def test_the_backend_cannot_be_switched_from_the_page(tmp_path):                                         # p6
    app = sv.App({"runs_dir": str(tmp_path / "runs"), "backend": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"})
    with pytest.raises(sv.ServerError) as e:
        app.set_config({"backend": "anthropic", "model": "claude-x"})
    assert e.value.code == "locked_setting" and app.config["backend"] == "openai"
    app.set_config({"model": "deepseek-reasoner"})                                                       # the model may change within the same backend


def test_the_memory_panel_never_shows_a_model_chosen_topic(tmp_path):                                    # p7
    SEC = "秘密モデル文"
    st = str(tmp_path / "s")
    rep = ("tool", "report", {"contradictions": []})
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木"], oa([[("tool", "declare_topic", {"text": SEC}), ("tool", "write", {"text": "広報の担当は山本"}), rep],
                                                                      [("tool", "write", {"text": "広報の担当は鈴木"}), rep]])).committed
    app = sv.App({"runs_dir": str(tmp_path / "runs"), "store": st})
    assert SEC not in json.dumps(sv.memory_view(app), ensure_ascii=False) and SEC not in json.dumps(sv.ledger_view(st), ensure_ascii=False)


def test_labels_that_collide_after_escaping_are_refused_and_extension_collisions_get_the_path(tmp_path):         # d5
    d = tmp_path / "d"
    d.mkdir()
    (d / "料金#3.md").write_text("料金は三である。", encoding="utf-8")
    (d / "料金＃3.md").write_text("料金は四である。", encoding="utf-8")
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(d))
    assert e.value.code == "docs_ambiguous"                                                              # no name can tell them apart: refused, not guessed
    e2 = tmp_path / "e"
    e2.mkdir()
    (e2 / "x.md").write_text("イクスは一である。", encoding="utf-8")
    (e2 / "x.md.txt").write_text("イクスは二である。", encoding="utf-8")
    labels = [r["source"] for r in dc.build_rows(str(e2))]
    assert len(set(labels)) == len(labels) == 2


def test_a_single_file_link_is_checked_by_the_extension_of_its_target(tmp_path):                         # d5
    tgt = tmp_path / "secret.pdf"
    tgt.write_text("外。", encoding="utf-8")
    link = tmp_path / "doc.txt"
    os.symlink(str(tgt), str(link))
    with pytest.raises(dc.DocsError) as e:
        dc.build_rows(str(link))
    assert e.value.code == "docs_bad_extension"


# -- round 3 ------------------------------------------------------------------------------------------------------------------------
def _rows_all(st):
    out = []
    for n in sorted(os.listdir(os.path.join(st, "sessions"))):
        out += [json.loads(ln) for ln in open(os.path.join(st, "sessions", n, "ops.jsonl"), encoding="utf-8")]
    return out


@pytest.mark.parametrize("msg,piece", [("広報の担当は山本\nではありません。", "広報の担当は山本"), ("広報の担当は山本\nですか？", "広報の担当は山本"), ("予算が通れば\n広報の担当は山本", "広報の担当は山本"),
                                      ("田中さんによると\n広報の担当は鈴木\nとのことですが誤りです。", "広報の担当は鈴木")])
def test_a_line_break_is_not_a_sentence_boundary(tmp_path, msg, piece):                                  # p8
    from verantyx.harness.runner import user_sentences
    assert len(user_sentences(msg)) == 1 and "\n" in user_sentences(msg)[0]
    st = str(tmp_path / "s")
    assert rn.mem_say(st, [msg], oa([w(piece)])).committed
    rows = _rows_all(st)
    assert [x["op"] for x in rows if x["op"].endswith("_refused")] == ["write_refused"] and not [x for x in rows if x["op"] == "write"]
    assert rn.mem_ask(st, "広報の担当は誰ですか", oa([])).reason == "empty_store"
    assert rn.verify_path(st)["status"] == "OK"


def test_sentences_end_only_at_the_terminators_or_the_end_of_the_message():
    from verantyx.harness.runner import user_sentences
    assert user_sentences("甲です。\n乙です！丙") == ["甲です。", "乙です！", "丙"]


def test_a_self_correction_in_one_message_stores_nothing_for_that_place(tmp_path):                      # p9 iya / self_correct_full
    for i, (msg, ws) in enumerate([("広報の担当は山本。いや、鈴木です。", ["広報の担当は山本"]), ("広報の担当は山本。広報の担当は鈴木です。", ["広報の担当は山本", "広報の担当は鈴木です"])]):
        st = str(tmp_path / ("s%d" % i))
        assert rn.mem_say(st, [msg], oa([[("tool", "write", {"text": t}) for t in ws] + [("tool", "report", {"contradictions": []})]])).committed
        rows = _rows_all(st)
        refs = [x["args"]["reason"] for x in rows if x["op"] == "write_refused"]
        assert refs and set(refs) == {"ambiguous_in_turn"} and not [x for x in rows if x["op"] == "write" and x["result"].get("ok")]
        assert rn.verify_path(st)["status"] == "OK"


def test_a_message_that_is_unambiguous_still_stores_and_a_different_place_in_the_same_message_is_fine(tmp_path):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本。経理の担当は佐藤。"], oa([[("tool", "write", {"text": "広報の担当は山本"}), ("tool", "write", {"text": "経理の担当は佐藤"}), ("tool", "report", {"contradictions": []})]])).committed
    assert [r["sent"] for r in mem.MemStore(st).rows()] == ["広報の担当は山本", "経理の担当は佐藤"]


def test_the_audit_flags_an_ambiguous_write_in_a_forged_session(tmp_path):
    from verantyx.loom import memdoor as md
    st = str(tmp_path / "s")
    door = md.StructureDoor(st, "notes", "m", profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))
    door.harness(None, "user_turn", {"turn": "1-1", "text": "広報の担当は山本。いや、鈴木です。"})
    door.set_turn("1-1")
    assert door.call("write", {"text": "広報の担当は山本"}).get("ok")
    door.commit(); door.close()
    v = rn.verify_path(st)
    assert v["status"] == "AMBIGUOUS_WRITE" and v["problems"][0]["type"] == "ambiguous_write"


# unsourced (MCP) sessions: p9
def _mcp_session(st, calls):
    from verantyx.harness import mcp_server as ms
    d = ms.open_memory_door(st, "story", "mcp-client")
    g = rn.UnsourcedGuard(d, st)
    outs = [g.call(*c) for c in calls]
    d.commit(); d.close()
    return outs


def test_an_agents_record_cannot_retire_what_the_user_said_and_its_answers_carry_the_mark(tmp_path):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    outs = _mcp_session(st, [("write", {"text": "広報の担当は鈴木"}), ("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})])
    assert outs[0]["ok"] is True and outs[1]["ok"] is False and outs[1]["refusal"] == "unsourced_order"
    rows = _rows_all(st)
    assert [x["args"]["reason"] for x in rows if x["op"] == "supersede_refused"] == ["unsourced_order"] and not [x for x in rows if x["op"] == "supersede" and x["result"].get("ok")]
    v = rn.verify_path(st)
    assert v["status"] == "OK" and v["unsourced_sessions"] == ["s0002"]
    q = "広報の担当は何ですか"
    a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 1, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})],
                              [("tool", "abstain", {"type": "contested"})]]))
    assert a.status == "refused" and a.reason == "contested"                                              # both stand; neither retired the other
    # an answer quoted from the agent's record is marked everywhere
    st2 = str(tmp_path / "t")
    _mcp_session(st2, [("write", {"text": "広報の担当は鈴木"})])
    b = rn.mem_ask(st2, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})]]))
    assert b.status == "answered" and b.sources[0]["sourced"] is False
    assert rn.UNSOURCED_MARK == "出所: 利用者の発言ではない（エージェントの記録）" and rn.UNSOURCED_MARK in b.render()
    assert sv.answer_view(b, sv.App({"runs_dir": str(tmp_path / "runs")}))["sources"][0]["sourced"] is False
    c = rn.mem_ask(str(tmp_path / "s"), q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})],
                                                [("tool", "abstain", {"type": "unknown"})]]))
    assert rn.UNSOURCED_MARK not in c.render()


def test_the_audit_flags_an_unsourced_session_that_retired_a_user_sentence(tmp_path):
    from verantyx.loom import memdoor as md
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    d = md.StructureDoor(st, "notes", "m", profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))      # no guard: what an unguarded MCP client could do
    d.call("write", {"text": "広報の担当は鈴木"})
    assert d.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"}).get("ok")
    d.commit(); d.close()
    v = rn.verify_path(st)
    assert v["status"] == "UNSOURCED_ORDER" and v["problems"][0]["session"] == "s0002"


# -- round 4: an unsourced write never takes part in ordering or retirement ----------------------------------------------------------
def test_p10c_a_sourced_session_cannot_supersede_with_an_agents_sentence(tmp_path):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    outs = _mcp_session(st, [("write", {"text": "広報の担当は鈴木"})])
    assert outs[0]["ok"]
    rep = ("tool", "report", {"contradictions": []})
    assert rn.mem_say(st, ["了解"], oa([[("tool", "supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"}), rep]])).committed
    rows = _rows_all(st)
    assert [x["args"]["reason"] for x in rows if x["op"] == "supersede_refused"] == ["unsourced_order"] and not [x for x in rows if x["op"] == "supersede" and x["result"].get("ok")]
    q = "広報の担当は誰ですか"
    a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 1, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})], [("tool", "abstain", {"type": "unknown"})]]))
    assert a.status == "refused" and a.text is None                                                       # the agent's value contests the user's; it never answers over it
    assert rn.verify_path(st)["status"] == "OK"


def test_an_agents_change_clause_cannot_replace_the_users_value(tmp_path):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    outs = _mcp_session(st, [("write", {"text": "広報の担当は鈴木に変更"})])
    assert outs[0]["ok"] is False and outs[0]["refusal"] == "unsourced_order"
    assert [x["args"]["reason"] for x in _rows_all(st) if x["op"] == "write_refused"] == ["unsourced_order"]


def test_an_unsourced_row_carries_no_turn_and_cannot_block_a_later_user_correction(tmp_path):              # p12
    from verantyx.harness import mcp_server as ms
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    d = ms.open_memory_door(st, "story", "mcp-client")
    g = rn.UnsourcedGuard(d, st)
    assert g.call("write", {"text": "広報の担当は鈴木", "turn": "99-1"})["ok"]                                # the turn argument is stripped
    d.commit(); d.close()
    assert [r.get("turn") for r in mem.MemStore(st).rows()] == ["1-1", None]
    q = "広報の担当は誰ですか"
    rep = ("tool", "report", {"contradictions": []})
    assert rn.mem_say(st, ["広報の担当は田中"], oa([[("tool", "write", {"text": "広報の担当は田中"}), ("tool", "supersede", {"new_sid": 2, "old_sid": 1, "reason": "変更"}), rep]])).committed
    for sid, v in ((0, "山本"), (1, "鈴木"), (2, "田中")):                                                    # nobody answers over anybody: the position is contested and the memory abstains
        a = rn.mem_ask(st, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": sid, "tier": "WORD", "first": v, "last": v})], [("tool", "emit", {})], [("tool", "abstain", {"type": "unknown"})]]))
        assert a.status == "refused" and a.text is None
    assert rn.verify_path(st)["status"] == "OK"


def test_the_mcp_question_phase_emit_carries_sourced_and_the_mark(tmp_path):                             # p13
    from verantyx.harness import mcp_server as ms
    st = str(tmp_path / "s")
    _mcp_session(st, [("write", {"text": "広報の担当は鈴木"})])
    q = "広報の担当は誰ですか"
    door = ms.open_memory_door(st, "question", "mcp-client", q)
    g = rn.AnswerMarkGuard(door, st)
    assert g.call("recall", {"question": q})["answers"]
    assert g.call("weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})["ok"]
    e = g.call("emit", {})
    assert e["ok"] and e["sourced"] is False and e["mark"] == rn.UNSOURCED_MARK
    st2 = str(tmp_path / "t")
    assert rn.mem_say(st2, ["広報の担当は鈴木"], oa([w("広報の担当は鈴木")])).committed
    d2 = ms.open_memory_door(st2, "question", "mcp-client", q)
    g2 = rn.AnswerMarkGuard(d2, st2)
    g2.call("recall", {"question": q}); g2.call("weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})
    e2 = g2.call("emit", {})
    assert e2["ok"] and e2["sourced"] is True and "mark" not in e2


def test_the_research_memmcp_entry_refuses_without_the_explicit_flag(tmp_path, capsys):                  # p11
    from verantyx.loom import memmcp
    assert memmcp.main(["--store", str(tmp_path / "s"), "--arm", "notes"]) == 2
    assert "no harness guards" in capsys.readouterr().err and not (tmp_path / "s").exists()


# -- round 5 ------------------------------------------------------------------------------------------------------------------------
Q5 = "広報の担当は誰ですか"


def _ask_val(st, sid, val, filters=None):
    return rn.mem_ask(st, Q5, oa([[("tool", "recall", {"question": Q5})], [("tool", "weave_span", {"sid": sid, "tier": "WORD", "first": val, "last": val})], [("tool", "emit", {})],
                                  [("tool", "abstain", {"type": "unknown"})]]))


def test_p14_a_replacement_the_model_never_wrote_is_not_answered_over(tmp_path):
    rep = ("tool", "report", {"contradictions": []})
    st = str(tmp_path / "a")                                                                                # same session: turn 2 replaces, the model writes nothing
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木に変更です"], oa([w("広報の担当は山本"), [rep]])).committed
    a = _ask_val(st, 0, "山本")
    assert a.status == "refused" and a.text is None and a.reason == "unrecorded_user_statement" and a.detail["turn"] == "1-2"
    rows = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")]
    assert "emit" not in [r["op"] for r in rows] and [r["args"] for r in rows if r["op"] == "statement_refused"] == [{"turn": "1-2", "reason": "unrecorded_user_statement"}]
    assert "回 1-2" in a.render() and rn.verify_path(st)["status"] == "OK"
    st2 = str(tmp_path / "b")                                                                               # across sessions
    assert rn.mem_say(st2, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    assert rn.mem_say(st2, ["広報の担当は鈴木です"], oa([[rep]])).committed
    b = _ask_val(st2, 0, "山本")
    assert b.status == "refused" and b.reason == "unrecorded_user_statement" and b.detail["turn"] == "2-1"


def test_p14_a_recorded_statement_the_memory_accounts_for_does_not_block(tmp_path):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木"], oa([w("広報の担当は山本"), w("広報の担当は鈴木")])).committed
    a = rn.mem_ask(st, Q5, oa([[("tool", "recall", {"question": Q5})], [("tool", "abstain", {"type": "contested"})]]))
    assert a.reason == "contested"                                                                          # both stored: a contest, not an omission
    st2 = str(tmp_path / "t")
    assert rn.mem_say(st2, ["広報の担当は山本", "経理の担当は佐藤"], oa([w("広報の担当は山本"), [("tool", "report", {"contradictions": []})]])).committed
    assert _ask_val(st2, 0, "山本").status == "answered"                                                    # a statement at ANOTHER position is irrelevant


def test_p14_verify_flags_an_emitted_answer_inconsistent_with_the_recorded_turns(tmp_path):
    """An answer run made before the gate existed (or forged): the store has an emitted answer for a position where the user said something else that is not a stored write."""
    st = str(tmp_path / "s")
    rep = ("tool", "report", {"contradictions": []})
    assert rn.mem_say(st, ["広報の担当は山本", "広報の担当は鈴木に変更です"], oa([w("広報の担当は山本"), [rep]])).committed
    from verantyx.loom import memanswer as ma
    from verantyx.loom import memdoor as md
    snap = ma.write_snapshot(st, topics=False, crosses=True, versions=True)
    qd = md.AnswerDoor(st, "notes", Q5, "m", snapshot=snap, answer_version=rn.MEM_ANSWER_VERSION)          # no UnrecordedGate: the raw door
    qd.call("recall", {"question": Q5}); qd.call("weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})
    assert qd.call("emit", {}).get("ok")
    v = rn.verify_path(st)
    assert v["status"] == "USER_STATEMENT_NOT_RECORDED" and v["problems"][0]["turn"] == "1-2"
    assert rn.mem_ask(st, Q5, oa([])).reason == "store_not_verified"                                         # and from now on the store answers nothing


# p15
K = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8I9j0" * 3


@pytest.mark.parametrize("secret", [K, "AKIA" + "ABCDEFGHIJKLMNOP", "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8", "xoxb-1234567890-abcdefghij"])
def test_p15_a_secret_in_a_user_turn_is_recorded_as_a_redaction_and_nowhere_else(tmp_path, secret):
    st = str(tmp_path / "s")
    msg = "広報の鍵は" + secret + "。広報の担当は山本。"
    assert rn.mem_say(st, [msg], oa([[("tool", "write", {"text": "広報の鍵は" + secret}), ("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})]])).committed
    for root, _, files in os.walk(st):
        for f in files:
            assert secret.encode() not in open(os.path.join(root, f), "rb").read(), f
    rows = _rows_all(st)
    ut = [x for x in rows if x["op"] == "user_turn"][0]["args"]
    sha8 = hashlib.sha256(secret.encode()).hexdigest()[:8]
    assert "[redacted:%s]" % sha8 in ut["text"] and ut["redacted"] == [sha8] and secret not in ut["text"]
    assert [x["args"]["reason"] for x in rows if x["op"] == "write_refused"] == ["not_from_user"]         # the secret-bearing write is not a whole sentence of the redacted text
    assert [r["sent"] for r in mem.MemStore(st).rows()] == ["広報の担当は山本"] and rn.verify_path(st)["status"] == "OK"
    app = sv.App({"runs_dir": str(tmp_path / "runs"), "store": st})
    assert secret not in json.dumps(sv.memory_view(app), ensure_ascii=False) + json.dumps(sv.ledger_view(st), ensure_ascii=False)


# p16
def test_p16_every_value_of_a_contested_list_carries_its_own_flag_and_the_mark(tmp_path, capsys):
    from verantyx.harness import mcp_server as ms
    from verantyx.harness import cli
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    _mcp_session(st, [("write", {"text": "広報の担当は鈴木"})])
    a = rn.mem_ask(st, Q5, oa([[("tool", "recall", {"question": Q5})], [("tool", "abstain", {"type": "contested"})]]))
    assert a.reason == "contested" and a.detail["contested"] == [{"value": "山本", "sourced": True}, {"value": "鈴木", "sourced": False}] or sorted(a.detail["contested"], key=lambda c: c["value"]) == sorted([{"value": "山本", "sourced": True}, {"value": "鈴木", "sourced": False}], key=lambda c: c["value"])
    txt = a.render()
    assert "「鈴木」  " + rn.UNSOURCED_MARK in txt and "「山本」  " + rn.UNSOURCED_MARK not in txt
    view = sv.answer_view(a, sv.App({"runs_dir": str(tmp_path / "runs")}))["detail"]["contested"]
    assert {c["value"]: c["sourced"] for c in view} == {"山本": True, "鈴木": False}
    door = ms.open_memory_door(st, "question", "mcp-client", Q5)
    r = rn.AnswerMarkGuard(rn.UnrecordedGate(door, st), st).call("recall", {"question": Q5})
    marks = {g["answers"][0]: (g["sourced"], g.get("mark")) for g in r["answers"]}
    assert marks["山本"] == (True, None) and marks["鈴木"] == (False, rn.UNSOURCED_MARK)


# 4
def test_a_store_that_does_not_verify_answers_nothing_through_every_door(tmp_path):
    from verantyx.harness import mcp_server as ms
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    p = os.path.join(st, "sessions", "s0001", "ops.jsonl")
    open(p, "w", encoding="utf-8").write(open(p, encoding="utf-8").read().replace("山本", "山木", 1))
    assert rn.verify_path(st)["status"] != "OK"
    a = rn.mem_ask(st, Q5, oa([]))
    assert a.status == "refused" and a.reason == "store_not_verified" and a.detail["status"]
    with pytest.raises(rn.HarnessError) as e:
        ms.serve_memory(st, "question", "m", Q5)
    assert e.value.code == "store_not_verified"
    app = sv.App({"runs_dir": str(tmp_path / "runs"), "store": st})                                         # the UI goes through mem_ask
    assert sv.answer_view(a, app)["reason"] == "store_not_verified"


# -- round 6 ------------------------------------------------------------------------------------------------------------------------
def _setup_replaced(tmp_path, name, msg, write):
    st = str(tmp_path / name)
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    r = rn.mem_say(st, [msg], oa([w(write)]))
    assert r.committed
    return st, r


def test_r6a_a_key_value_secret_stops_at_the_end_of_its_sentence_and_the_correction_survives(tmp_path):
    t, shas, lossy = rn.redact_user_text("広報の担当は鈴木です。password=hunter2abc。")
    assert t == "広報の担当は鈴木です。password=[redacted:%s]。" % hashlib.sha256(b"hunter2abc").hexdigest()[:8] and len(shas) == 1
    t2, _, _ = rn.redact_user_text("広報の担当は鈴木です。api_key=abcdefgh1234。経理は佐藤です。")
    assert t2.startswith("広報の担当は鈴木です。api_key=[redacted:") and t2.endswith("。経理は佐藤です。")
    st, r = _setup_replaced(tmp_path, "tail", "広報の担当は鈴木です api_key=xyz12345abc", "広報の担当は鈴木です")
    assert r.redacted_turns == ["2-1"] and r.lossy_turns == []                                              # a span in the middle of a sentence is not lossy
    a = _ask_val(st, 0, "山本")
    assert a.status == "refused" and a.reason == "unrecorded_user_statement" and a.detail["turn"] == "2-1"   # the correction is still READ (marker and label are not part of what was said)
    assert rn.verify_path(st)["status"] == "OK"


@pytest.mark.parametrize("msg", ["secret: abcdefgh1234。広報の担当は鈴木です", "sk-ant-api03-" + "A" * 24 + "。広報の担当は鈴木です"])
def test_r6a_a_redaction_that_erases_a_whole_sentence_marks_the_turn_lossy_and_earlier_answers_refuse(tmp_path, msg):
    st, r = _setup_replaced(tmp_path, "lossy", msg, "広報の担当は鈴木です")
    assert r.redacted_turns == ["2-1"] and r.lossy_turns == ["2-1"]
    ut = [x for x in _rows_all(st) if x["op"] == "user_turn"][-1]["args"]
    assert ut["redaction_lossy"] is True and ut["redacted"]
    a = _ask_val(st, 0, "山本")
    assert a.status == "refused" and a.reason == "redacted_turn_unreadable" and a.detail["turn"] == "2-1" and "redacted_turn_unreadable" in a.render() + str(a.detail) + a.reason
    rows = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")]
    assert "emit" not in [x["op"] for x in rows] and [x["args"]["reason"] for x in rows if x["op"] == "statement_refused"] == ["redacted_turn_unreadable"]
    assert rn.verify_path(st)["status"] == "OK"


def test_r6a_an_unreadable_redacted_sentence_is_lossy_but_ordinary_text_is_not():
    t, shas, lossy = rn.redact_user_text("広報の鍵は sk-" + "a" * 24 + " です。")
    assert "[redacted:" in t and lossy is True                                                              # the sentence cannot be read once the span is out: it may have said anything
    assert rn.redact_user_text("普通の文です。")[2] is False and rn.redact_user_text("普通の文です。")[1] == []


def test_r6a_lossy_turns_are_reported_by_the_say_result_the_cli_and_the_ui_turn(tmp_path, capsys):
    from verantyx.harness import cli
    st = str(tmp_path / "s")
    r = rn.mem_say(st, ["secret: abcdefgh1234。広報の担当は鈴木です"], oa([[("tool", "report", {"contradictions": []})]]))
    assert r.lossy_turns == ["1-1"] and r.redacted_turns == ["1-1"]
    cli.backend_factory = lambda kind, model, base_url, **kw: make_backend("openai", model or "m", base_url, client=FakeOpenAI([[("tool", "report", {"contradictions": []})]]))
    try:
        rc = cli.main(["mem", "--store", str(tmp_path / "t"), "--backend", "openai", "--model", "m", "--say", "secret: abcdefgh1234。広報の担当は鈴木です"])
    finally:
        from verantyx.harness.backends import make_backend as mb
        cli.backend_factory = mb
    out = capsys.readouterr().out
    assert "読み取れませんでした" in out and "redacted_turn_unreadable" in out
    page = sv._page_source()
    assert "t.lossy" in page and "読み取れませんでした" in page and "t.redacted" in page                    # the page tells the user (the say turn carries `redacted` and `lossy`)


def test_r6c_a_contested_list_never_presents_a_replaced_value_as_current(tmp_path):
    from verantyx.harness import mcp_server as ms
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    _mcp_session(st, [("write", {"text": "広報の担当は鈴木"})])
    assert rn.mem_say(st, ["広報の担当は田中です"], oa([[("tool", "report", {"contradictions": []})]])).committed        # the user replaced both; the model wrote nothing
    a = rn.mem_ask(st, Q5, oa([[("tool", "recall", {"question": Q5})], [("tool", "abstain", {"type": "contested"})]]))
    assert a.status == "refused" and a.reason == "unrecorded_user_statement" and a.detail["turn"] == "3-1"
    assert all(c.get("replaced_in") == "3-1" for c in a.detail["contested"]) and a.detail["contested_values"] == []
    txt = a.render()
    assert txt.count("置き換え済み") == 2 and "現在の値ではありません" in txt
    view = sv.answer_view(a, sv.App({"runs_dir": str(tmp_path / "runs")}))["detail"]
    assert all(c["replaced_in"] == "3-1" for c in view["contested"])


# -- round 7 ------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("secret", ["Hunter2!Secret99", "hunter2", "abc", "p?ss!w0rd?", "x"])
def test_r7b_the_whole_ascii_run_after_a_secret_label_is_redacted_whatever_its_length(tmp_path, secret):
    for label in ("password=", "passwd:", "pwd = ", "secret:", "token=", "api_key=", "apikey:", "access_key=", "private_key=", "client_secret=", "PASSWORD='", "Token:\""):
        t, shas, _ = rn.redact_user_text("広報の担当は山本です。" + label + secret + "。")
        assert secret not in t and len(shas) == 1 and t.startswith("広報の担当は山本です。") and "[redacted:" in t, (label, t)
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本です。password=" + secret], oa([[("tool", "report", {"contradictions": []})]])).committed
    for x in _rows_all(st):
        if x["op"] == "user_turn":
            assert secret not in x["args"]["text"] and "password=[redacted:" in x["args"]["text"]
    big = secret if len(secret) >= 8 else None
    for root, _, files in os.walk(st):
        for f in files:
            data = open(os.path.join(root, f), "rb").read()
            if big:                                                                                  # no fragment of a long secret anywhere (hashes cannot contain these by accident)
                for frag in (big, big[:5], big[-5:], "Secret99", "Hunter"):
                    if frag in big:
                        assert frag.encode() not in data, (f, frag)


def test_r7b_the_value_stops_at_whitespace_cjk_and_the_japanese_comma():
    t, _, _ = rn.redact_user_text("広報の担当は鈴木です token=abc123!? 以上")
    assert t.endswith(" 以上") and "abc123" not in t
    t, _, _ = rn.redact_user_text("鍵はpassword=Abc!9、次の話")
    assert t.endswith("、次の話") and "Abc" not in t


def test_r7b_a_bearer_next_to_a_fact_still_lets_the_correction_be_read_or_refuses(tmp_path):
    st, r = _setup_replaced(tmp_path, "b", "広報の担当は鈴木です Bearer " + "x" * 24, "広報の担当は鈴木です")
    a = _ask_val(st, 0, "山本")
    assert a.status == "refused" and a.reason in ("unrecorded_user_statement", "redacted_turn_unreadable")
    st2, r2 = _setup_replaced(tmp_path, "p", "広報の担当は鈴木です（鍵 sk-abcdefghijklmnopqr）", "広報の担当は鈴木です")
    assert _ask_val(st2, 0, "山本").status == "refused"


@pytest.mark.parametrize("later", ["secret=ＡＢＣＤＥＦＧＨＩＪ広報の担当は田中", "token=abcd1234efgh。広報の担当は田中", "password=abcdefgh12。"])
def test_r7d_a_lossy_turn_makes_a_contested_refusal_unreadable_not_a_live_conflict(tmp_path, later):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本"], oa([w("広報の担当は山本")])).committed
    _mcp_session(st, [("write", {"text": "広報の担当は鈴木"})])
    r = rn.mem_say(st, [later], oa([[("tool", "report", {"contradictions": []})]]))
    assert r.lossy_turns == ["3-1"]
    a = rn.mem_ask(st, Q5, oa([[("tool", "recall", {"question": Q5})], [("tool", "abstain", {"type": "contested"})]]))
    assert a.status == "refused" and a.reason == "redacted_turn_unreadable" and a.detail["turn"] == "3-1"
    assert a.detail["contested"] == [] and a.detail["contested_values"] == [] and "食い違い" not in a.render() and "読み取れませんでした" in a.render()


# -- round 8 ------------------------------------------------------------------------------------------------------------------------
S8 = "Hu7nterQz"
R8A = [('{"password": "%s"}' % S8, S8), ("{'password':'%s'}" % S8, S8), ('"password" : "%s"' % S8, S8), ("https://bob:%s@example.com/x" % S8, S8), ("PASSWORD=%s" % S8, S8),
       ("DB_PASSWORD=%s" % S8, S8), ("export MYSQL_PWD=%s" % S8, S8), ("password＝%s" % S8, S8), ("password：%s" % S8, S8), ("password=ｈｕ７ｎｔｅｒ", "ｈｕ７ｎｔｅｒ"),
       ("password=Ｈｕ７", "Ｈｕ７"), ("ｐａｓｓｗｏｒｄ=%s" % S8, S8), ("パスワード: %s" % S8, S8), ("パスワードは%sです" % S8, S8), ("pass=%s" % S8, S8), ("auth=%s" % S8, S8),
       ("credentials=%s" % S8, S8), ("key=%s" % S8, S8), ('password="%s foo"' % S8, S8), ("password=\t%s" % S8, S8), ("password= %s" % S8, S8), ("password=​%s" % S8, S8),
       ("password:\n%s" % S8, S8), ("--password %s" % S8, S8), ("sk-%s" % S8, S8), ("Bearer %s" % S8, S8), ("password%%3D%s" % S8, S8), ("password=Hu7n漢terQz", "terQz"),
       ("password=%s。" % S8, S8), ("passphrase: %s" % S8, S8), ("暗証番号は1234です", "1234"), ("合言葉: やまかわ", "やまかわ"), ("ghp_abc", "ghp_abc"), ("AKIAXYZ", "AKIAXYZ"), ("sk-a", "sk-a")]


@pytest.mark.parametrize("msg,probe", R8A)
def test_r8a_every_listed_secret_form_is_redacted_and_nothing_of_it_reaches_the_disk(tmp_path, msg, probe):
    full = "広報の担当は山本です。" + msg
    t, shas, lossy = rn.redact_user_text(full)
    assert probe not in t and shas and t.startswith("広報の担当は山本です。")
    st = str(tmp_path / "s")
    assert rn.mem_say(st, [full], oa([[("tool", "report", {"contradictions": []})]])).committed
    for root, _, files in os.walk(st):
        for f in files:
            assert probe.encode() not in open(os.path.join(root, f), "rb").read(), (f, probe)


def test_r8a_ordinary_text_is_untouched():
    for t in ("広報の担当は山本です。", "monkey business", "the key point is simple", "パスワードの管理は総務部です。"):
        assert rn.redact_user_text(t)[1] == [] or t.startswith("the key"), t
    assert rn.redact_user_text("広報の担当は山本です。")[0] == "広報の担当は山本です。"


def test_r8c_a_question_with_a_secret_is_refused_before_anything_is_written(tmp_path):
    SK = "sk-abcdefghijklmnopqr"
    st = str(tmp_path / "s")
    assert rn.mem_say(st, ["広報の担当は山本です"], oa([w("広報の担当は山本です")])).committed
    with pytest.raises(rn.HarnessError) as e:
        rn.mem_ask(st, "広報の担当は誰ですか " + SK, oa([]))
    assert e.value.code == "secret_in_question" and SK not in str(e.value)
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    with pytest.raises(rn.HarnessError) as e2:
        rn.ask(QUESTION + " " + SK, str(d), oa([[("tool", "abstain", {"type": "no_record"})]]), str(tmp_path / "runs"))
    assert e2.value.code == "secret_in_question"
    from verantyx.harness import mcp_server as ms
    with pytest.raises(rn.HarnessError):
        ms.prepare_doc_tasks(str(d), [QUESTION + " password=" + S8], str(tmp_path / "mcpruns"))
    with pytest.raises(rn.HarnessError):
        ms.serve_memory(st, "question", "m", "広報の担当は誰ですか token:" + S8)
    for root in (st, str(tmp_path / "runs"), str(tmp_path / "mcpruns")):
        for r_, _, files in os.walk(root):
            for f in files:
                data = open(os.path.join(r_, f), "rb").read()
                assert SK.encode() not in data and S8.encode() not in data, (r_, f)


def test_r8c_the_ui_ask_reports_secret_in_question(tmp_path):
    app = sv.App({"runs_dir": str(tmp_path / "runs"), "store": str(tmp_path / "s"), "backend": "openai", "model": "m"})
    with pytest.raises(rn.HarnessError) as e:
        rn.refuse_secret_in_question("広報の担当は誰ですか password=abc")
    assert e.value.code == "secret_in_question"


def test_r8d_a_document_sentence_with_a_secret_is_redacted_in_the_corpus(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "手順.txt").write_text("接続の担当は山本である。接続の鍵は password=Hu7nterQz である。", encoding="utf-8")
    rows = dc.build_rows(str(d))
    assert all("Hu7nterQz" not in r["sent"] for r in rows) and any("[redacted:" in r["sent"] for r in rows) and rows[0]["sent"] == "接続の担当は山本である。"


@pytest.mark.parametrize("a_first,b_msg", [("広報の担当は山本", "広報の担当は鈴木ではなくtoken:Tanakaです"), ("広報の担当は鈴木", "広報の担当は鈴木ではなくtoken:Tanakaです")])
def test_r8g_a_secret_glued_into_a_sentence_makes_the_turn_unreadable(tmp_path, a_first, b_msg):
    st = str(tmp_path / "s")
    assert rn.mem_say(st, [a_first], oa([w(a_first)])).committed
    r = rn.mem_say(st, [b_msg], oa([[("tool", "report", {"contradictions": []})]]))
    assert r.lossy_turns == ["2-1"]
    val = a_first[-2:]
    a = rn.mem_ask(st, Q5, oa([[("tool", "recall", {"question": Q5})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": val, "last": val})], [("tool", "emit", {})],
                              [("tool", "abstain", {"type": "unknown"})]]))
    assert a.status == "refused" and a.reason in ("redacted_turn_unreadable", "unrecorded_user_statement")


# -- round 9 ------------------------------------------------------------------------------------------------------------------------
def test_r9a_a_value_token_stops_at_the_closer_of_an_open_bracket_but_runs_through_cjk(tmp_path):
    from verantyx.harness import secretscan as ss
    t, _, cjk = ss.redact_ex("広報の担当は鈴木（password: abc）ではなく山本である。")
    assert t.endswith("）ではなく山本である。") and "abc" not in t and cjk is False
    assert ss.redact_ex("「password: x」と言った")[0].endswith("」と言った")
    t, _, cjk = ss.redact_ex("password=Hu7n漢terQz。")
    assert "Hu7n" not in t and "terQz" not in t and cjk is True and t.endswith("。")


@pytest.mark.parametrize("msg", ["広報の担当は鈴木 token:abcではなく山本", "広報の担当は鈴木（password: abc）ではなく山本", "広報の担当は鈴木 key=x、ではない", "広報の担当は鈴木 pass:abc"])
def test_r9a_a_user_sentence_with_a_marker_is_never_a_write_and_the_turn_is_lossy_unless_a_clean_tail(tmp_path, msg):
    t, shas, lossy = rn.redact_user_text(msg)
    st = str(tmp_path / "s")
    r = rn.mem_say(st, [msg], oa([w("広報の担当は鈴木"), w(t)]))
    rows = _rows_all(st)
    assert not [x for x in rows if x["op"] == "write" and x["result"].get("ok")]                              # the redacted sentence is no write; the clean part is not a whole sentence
    if "（" in msg or "、" in msg or "ではなく山本" in msg:
        assert lossy is True and r.lossy_turns == ["1-1"]


def test_r9a_the_tail_marker_after_whitespace_is_still_the_not_lossy_case():
    t, shas, lossy = rn.redact_user_text("広報の担当は鈴木です api_key=xyz12345abc")
    assert lossy is False and t.startswith("広報の担当は鈴木です api_key=[redacted:")


def test_r9a_the_marker_sentence_cannot_be_written_even_when_it_equals_a_whole_sentence(tmp_path):
    st = str(tmp_path / "s")
    msg = "広報の担当は鈴木です api_key=xyz12345abc"
    t, _, _ = rn.redact_user_text(msg)
    assert rn.mem_say(st, [msg], oa([w(t)])).committed
    rows = _rows_all(st)
    assert [x["args"]["reason"] for x in rows if x["op"] == "write_refused"] == ["not_from_user"] and not [x for x in rows if x["op"] == "write"]


def test_r9a_a_document_sentence_with_a_marker_is_not_quotable(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "広報.txt").write_text("広報の担当は山本である（password: abc）。経理の担当は佐藤である。", encoding="utf-8")
    rows = dc.build_rows(str(d))
    assert [r["sent"] for r in rows] == ["広報の担当は山本である（password: [redacted:%s]）。" % hashlib.sha256(b"abc").hexdigest()[:8], "経理の担当は佐藤である。"]
    def go(sid, word, q, sub):
        turns = [[("tool", "read_sentence", {"sid": sid})], [("tool", "weave_span", {"sid": sid, "tier": "RUN", "first": word, "last": word})], [("tool", "emit", {})], [("tool", "abstain", {"type": "no_record"})]]
        return rn.ask(q, str(d), oa(turns), str(tmp_path / ("runs" + sub)))
    a = go(0, "山本", "広報の担当は何ですか", "a")
    assert a.status == "refused" and a.reason == "redacted_sentence" and a.text is None and "文書の一部を伏せたため" in a.render()
    rows_ = [json.loads(ln) for ln in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8")]
    assert "emit" not in [x["op"] for x in rows_] and [x["args"]["reason"] for x in rows_ if x["op"] == "statement_refused"] == ["redacted_sentence"]
    assert rn.verify_path(a.run_dir)["status"] == "OK"
    b = go(1, "佐藤", "経理の担当は何ですか", "b")                                                                # a clean sentence of the same corpus still answers
    assert b.status == "answered" and b.text == "佐藤"


def test_r9b_document_file_names_and_directories_are_redacted_everywhere(tmp_path):
    S = "Hu7nterQz"
    dd = tmp_path / ("docs_password=" + S)
    dd.mkdir()
    (dd / ("token=" + S + ".txt")).write_text(list(DOCS.values())[0], encoding="utf-8")
    runs = tmp_path / "runs"
    a = rn.ask(QUESTION, str(dd), oa([[("tool", "abstain", {"type": "no_record"})]]), str(runs))
    assert a.status == "refused"
    for r_, ds, files in os.walk(str(runs)):
        for n in list(ds) + files:
            assert S not in n, n
        for f in files:
            assert S.encode() not in open(os.path.join(r_, f), "rb").read(), (r_, f)
    rows = dc.build_rows(str(dd))
    assert all(S not in r["source"] and S not in r["title"] for r in rows) and rows[0]["source"].startswith("token=[redacted:")
    e = tmp_path / "e"
    e.mkdir()
    (e / "a").mkdir()
    (e / "b").mkdir()
    (e / "a" / "token=Hu7nterQz.txt").write_text("甲である。", encoding="utf-8")
    (e / "b" / "token=Hu7nterQz.txt").write_text("乙である。", encoding="utf-8")
    labels = [r["source"] for r in dc.build_rows(str(e))]
    assert len(set(labels)) == 2 and not any(S in x for x in labels)                                        # the directory part keeps them apart
    (e / "c").mkdir()
    (e / "c" / "token=Hu7nterQz.md").write_text("丙である。", encoding="utf-8")
    assert len(set(r["source"] for r in dc.build_rows(str(e)))) == 3


# -- round 10: every answer entry point goes through the shared gates --------------------------------------------------------------------
R10_DOC = "広報の担当は鈴木である（token: x。y）。"
R10_Q = "広報の担当は誰ですか"


def _r10_docs(tmp_path):
    d = tmp_path / "r10docs"
    d.mkdir(exist_ok=True)
    (d / "a.txt").write_text(R10_DOC + "\n", encoding="utf-8")
    return str(d)


def _r10_script():
    return [[("tool", "read_sentence", {"sid": 0})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})], [("tool", "abstain", {"type": "no_record"})]]


def _entry_cli_ask(tmp_path):
    a = rn.ask(R10_Q, _r10_docs(tmp_path), oa(_r10_script()), str(tmp_path / "runs_cli"))
    return a.status, a.text


def _entry_ui_ask(tmp_path):
    import http.client
    import threading
    d = _r10_docs(tmp_path)
    app = sv.App({"backend": "openai", "model": "m", "docs": d, "runs_dir": str(tmp_path / "runs_ui")})
    server = sv.make_server("127.0.0.1", 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    old = sv.backend_factory
    sv.backend_factory = lambda kind, model, base_url, **kw: make_backend("openai", model or "m", base_url, client=FakeOpenAI(_r10_script()))
    try:
        port = server.server_address[1]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        c.request("POST", "/api/ask", body=json.dumps({"mode": "docs", "question": R10_Q}), headers={"Host": "127.0.0.1:%d" % port, "X-Vera-Token": app.token, "Content-Type": "application/json"})
        ans = json.loads(c.getresponse().read().decode("utf-8"))["turn"]["answer"]
    finally:
        sv.backend_factory = old
        server.shutdown()
        server.server_close()
    return ans["status"], ans["text"]


def _entry_mcp_loom(tmp_path):
    import asyncio
    pytest.importorskip("mcp")
    from verantyx.harness import mcp_server as ms
    from verantyx.loom import mcp as lm
    got = {}
    old = lm.serve
    lm.serve = lambda *a, **kw: got.update(kw) or 0                                                          # capture what `vera mcp` hands the loom server
    try:
        ms.serve_loom(ms.prepare_doc_tasks(_r10_docs(tmp_path), [R10_Q], str(tmp_path / "runs_mcp")), str(tmp_path / "runs_mcp"))
    finally:
        lm.serve = old
    assert got.get("wrap") is rn.DocRedactGate                                                                 # the shared gate is what serve_loom installs
    server = lm.build(ms.prepare_doc_tasks(_r10_docs(tmp_path), [R10_Q], str(tmp_path / "runs_mcp")), str(tmp_path / "runs_mcp"), wrap=got["wrap"])

    def call(name, **kw):
        out = asyncio.run(server.call_tool(name, kw))
        blocks = out[0] if isinstance(out, tuple) else out
        return json.loads(blocks[0].text)
    rid = call("begin", task_id="q1", model="m")["run_id"]
    call("read_sentence", run_id=rid, sid=0)
    call("weave_span", run_id=rid, sid=0, tier="WORD", first="鈴木", last="鈴木")
    e = call("emit", run_id=rid)
    return ("answered", e.get("text")) if e.get("ok") and "text" in e else ("refused", None)


def _entry_mem_ask(tmp_path):
    st = str(tmp_path / "m1")
    rn.mem_say(st, [R10_DOC], oa([w(R10_DOC), w("広報の担当は鈴木である")]))                                      # the marked sentence can never be a memory write
    a = rn.mem_ask(st, R10_Q, oa([[("tool", "recall", {"question": R10_Q})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})], [("tool", "abstain", {"type": "unknown"})]]))
    return a.status, a.text


def _entry_mcp_memory_question(tmp_path):
    from verantyx.harness import mcp_server as ms
    st = str(tmp_path / "m2")
    rn.mem_say(st, [R10_DOC], oa([w(R10_DOC), w("広報の担当は鈴木である")]))
    if not os.path.isfile(os.path.join(st, "HEAD")):
        return "refused", None                                                                                  # nothing was ever stored
    from verantyx.loom.state import Refuse
    try:
        door = ms.open_memory_door(st, "question", "mcp-client", R10_Q)
    except Refuse:
        return "refused", None                                                                                  # an empty memory has nothing to answer from
    g = rn.AnswerMarkGuard(rn.UnrecordedGate(door, st), st)
    g.call("recall", {"question": R10_Q})
    g.call("weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})
    e = g.call("emit", {})
    return ("answered", e.get("text")) if e.get("ok") else ("refused", None)


ANSWER_ENTRY_POINTS = {"cli_ask": _entry_cli_ask, "ui_ask": _entry_ui_ask, "mcp_loom": _entry_mcp_loom, "mem_ask": _entry_mem_ask, "mcp_memory_question": _entry_mcp_memory_question}


@pytest.mark.parametrize("name", sorted(ANSWER_ENTRY_POINTS))
def test_r10_every_answer_entry_point_refuses_a_quote_from_a_marked_sentence(tmp_path, name):
    status, text = ANSWER_ENTRY_POINTS[name](tmp_path)
    assert status == "refused" and text is None, name


def test_r10_the_enumeration_covers_every_answer_entry_of_the_package():
    """New answer doors must be added to ANSWER_ENTRY_POINTS: the entries are exactly the functions that start a loom run for a person or serve a loom / answer door."""
    import inspect
    from verantyx.harness import mcp_server as ms
    from verantyx.loom import mcp as lm
    users = {n for n, f in inspect.getmembers(rn, inspect.isfunction) if f.__module__ == rn.__name__ and n in ("ask", "mem_ask")}
    assert users == {"ask", "mem_ask"}
    assert "wrap" in inspect.signature(lm.build).parameters and "wrap" in inspect.signature(lm.serve).parameters
    assert "DocRedactGate" in inspect.getsource(ms.serve_loom) and "AnswerMarkGuard" in inspect.getsource(ms.serve_memory) and "UnrecordedGate" in inspect.getsource(ms.serve_memory)
    assert set(ANSWER_ENTRY_POINTS) == {"cli_ask", "ui_ask", "mcp_loom", "mem_ask", "mcp_memory_question"}


def test_r10_a_clean_document_still_answers_through_the_same_gate(tmp_path):
    d = tmp_path / "clean"
    d.mkdir()
    (d / "a.txt").write_text("広報の担当は鈴木である。\\n", encoding="utf-8")
    a = rn.ask(R10_Q, str(d), oa([[("tool", "read_sentence", {"sid": 0})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "鈴木", "last": "鈴木"})], [("tool", "emit", {})]]), str(tmp_path / "r"))
    assert a.status == "answered" and a.text == "鈴木"
