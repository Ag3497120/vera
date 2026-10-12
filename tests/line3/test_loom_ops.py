"""LOOM-a tests: the 20 operations (18 + weave_span and drop of LOOM-span), their typed refusals, the per-run caps (docs/LINE3_LOOM_DESIGN.md 4, 5.1; T-LOOM-01..09).

A refusal is {"ok": false, "refusal": <type>, "detail": {...}}, never an exception, and it leaves the structure as it was.
"""
import json
import os

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from verantyx.loom.ops import MODEL_OPS, normalize_task
from loom_common import CORPUS, TASKS, TOY, rows, server, task, weaver


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


def refused(r, type):
    assert r["ok"] is False and r["refusal"] == type, r
    return r["detail"]


def structure(srv, w):
    """Everything of the state except the counters (a refused call still counts in its class)."""
    o = srv.runs[w.run_id].run.state.to_obj()
    o.pop("counters")
    return o


# ---------------------------------------------------------------------------------------------------------------
# T-LOOM-03: the probe values of design 2
# ---------------------------------------------------------------------------------------------------------------
def test_probe_postings_and_distinct_units(corpus):
    assert (corpus.n_sentences, len(corpus.tier("RUN").postings), len(corpus.tier("WORD").postings), len(corpus.tier("CHAR").postings)) == (592, 3653, 3557, 1358)
    n = lambda t, u: len(corpus.tier(t).postings.get(u, ()))
    assert [n("RUN", u) for u in ("東京", "日本", "首都")] == [1, 25, 0]
    assert [n("WORD", u) for u in ("東京", "日本", "首都")] == [7, 49, 4]
    for t in ("RUN", "WORD", "CHAR"):
        for u in ("です", "である", "の", "は"):
            assert n(t, u) == 0, (t, u)


def test_probe_pair_and_adhesion_rows(corpus):
    T = corpus.tier("WORD")
    assert (T.n_pair("日本", "首都"), T.p_pair("日本", "首都"), T.p_pair("首都", "日本")) == (2, 2, 0)
    A = corpus.adhesion["WORD"]
    assert A.weighted("日本") == (0, 2880, 89, 110, 34, 0, 13)         # ladder: は の に で と を が
    assert A.weighted("東京") == (0, 0, 0, 55, 0, 0, 0)
    assert A.weighted("首都") == (0,) * 7
    assert A.adj("日本", "の") * 144 == 2880


def test_a_corpus_is_cached_by_its_sha(corpus):
    assert Corpus.load(open(CORPUS, "rb").read()) is corpus


# ---------------------------------------------------------------------------------------------------------------
# begin / task bank
# ---------------------------------------------------------------------------------------------------------------
def test_there_are_exactly_the_20_tools_and_no_rotate_no_undo():
    assert len(MODEL_OPS) == 20 and len(set(MODEL_OPS)) == 20
    assert set(MODEL_OPS) == {"begin", "lookup", "read_sentence", "add", "open_cross", "seat", "seat_run", "weave_span", "unseat", "swap", "extend",
                              "topic", "set_depth", "link", "unlink", "drop", "read", "emit", "abstain", "status"}
    assert "rotate" not in MODEL_OPS and "undo" not in MODEL_OPS and "weave_sentence" not in MODEL_OPS    # weave_sentence: legacy, replay only (LOOM-span)


def test_begin_returns_the_task_without_a_gold_or_a_path(tmp_path):
    srv = server(tmp_path)
    r = srv.begin("demo/tokyo_ca", "claude-haiku-4-5", "r1")
    assert r["ok"] and r["run_id"] == "r1"
    assert r["task"]["mode"] == "constructed_allowed" and r["task"]["tiers"] == ["WORD"] and r["task"]["caps"]["ops"] == 200 and r["task"]["caps"]["lookups"] == 100
    blob = json.dumps(r, ensure_ascii=False)
    assert "gold" not in blob and CORPUS not in blob and "corpus" not in r["task"]
    assert r["header"]["declared_model"] == "claude-haiku-4-5" and r["header"]["stability_mode"] == "strict_npa"
    assert r["header"]["code_index_sha"] is None


def test_begin_refusals(tmp_path):
    srv = server(tmp_path)
    refused(srv.begin("nope", "m"), "unknown_task")
    for bad in ("", "x" * 65, "a\nb", "sk-ant-aaaaaaaaaaaa", None, 3):
        refused(srv.begin("demo/tokyo_ca", bad), "bad_model_id")
    refused(srv.begin("demo/tokyo_ca", "m", "../escape"), "bad_run_id")
    refused(srv.begin("demo/tokyo_ca", "m", "/abs"), "bad_run_id")
    assert srv.begin("demo/tokyo_ca", "m", "dup")["ok"]
    refused(srv.begin("demo/tokyo_ca", "m", "dup"), "run_exists")
    assert not os.path.exists(str(tmp_path / "escape"))
    refused(srv.call("begin", {"task_id": "demo/tokyo_ca"}), "bad_args")


def test_a_task_bank_is_validated(tmp_path):
    with pytest.raises(ValueError):
        normalize_task({"task_id": "a", "text": "t", "lang": "klingon", "mode": "record_only"})
    with pytest.raises(ValueError):
        normalize_task({"task_id": "a", "text": "t", "lang": "prose", "mode": "free"})
    with pytest.raises(ValueError):
        normalize_task({"task_id": "a", "text": "t", "lang": "prose", "mode": "record_only", "tiers": ["CODE"]})
    with pytest.raises(ValueError):
        normalize_task({"task_id": "a", "text": "t", "lang": "code", "mode": "record_only", "tiers": ["WORD"]})
    assert normalize_task({"task_id": "a", "text": "t", "lang": "code", "mode": "record_only"})["tiers"] == ["CODE"]
    assert normalize_task({"task_id": "a", "text": "t", "lang": "prose", "mode": "record_only"})["tiers"] == ["RUN", "WORD", "CHAR"]
    with pytest.raises(ValueError):
        LoomServer([task("x"), task("x")], str(tmp_path / "runs"))
    with pytest.raises(ValueError):
        LoomServer([{"task_id": "y", "text": "t", "lang": "prose", "mode": "record_only"}], str(tmp_path / "runs"))     # no corpus named


def test_unknown_run_and_unknown_tool_leave_no_row(tmp_path):
    srv = server(tmp_path)
    refused(srv.call("status", {"run_id": "nope"}), "unknown_run")
    refused(srv.call("status", {}), "unknown_run")
    refused(srv.call("rotate", {"run_id": "x"}), "unknown_tool")
    assert os.listdir(str(tmp_path / "runs")) == []


# ---------------------------------------------------------------------------------------------------------------
# lookup / read_sentence
# ---------------------------------------------------------------------------------------------------------------
def test_lookup_is_an_exact_match_with_all_postings(tmp_path, corpus):
    w = weaver(server(tmp_path))
    r = w.call("lookup", text="日本", tier="any")
    assert r["ok"] and [m["tier"] for m in r["matches"]] == ["RUN", "WORD"]            # 日本 is not a CHAR unit
    word = r["matches"][1]
    assert word["n"] == 49 and word["sids"] == list(corpus.postings("WORD", "日本")) and len(word["sentences"]) == 5
    assert word["sentences"][0]["sid"] == word["sids"][0] and set(word["sentences"][0]) == {"sid", "source", "text"}
    assert w.call("lookup", text="日本", tier="WORD")["matches"] == [word]
    assert w.call("lookup", text="日", tier="CHAR")["matches"][0]["n"] > 0
    assert w.call("lookup", text="日本の", tier="any")["matches"] == []                  # no substring search
    assert w.call("lookup", text="首都", tier="RUN")["matches"] == []                   # not a RUN unit (design 2)


def test_lookup_refusals(tmp_path):
    w = weaver(server(tmp_path), "demo/tokyo_ca")
    refused(w.call("lookup", text="日本", tier="CHAR"), "tier_not_in_task")
    refused(w.call("lookup", text="日本", tier="CODE"), "tier_not_in_task")
    refused(w.call("lookup", text="日本", tier="JAPANESE"), "bad_args")
    refused(w.call("lookup", text="", tier="WORD"), "bad_args")
    refused(w.call("lookup", text="あ" * 33, tier="WORD"), "bad_args")
    refused(w.call("lookup", text="日本"), "bad_args")
    refused(w.call("lookup", text="日本", tier="WORD", extra=1), "bad_args")
    refused(w.call("lookup", text=3, tier="WORD"), "bad_args")
    wc = weaver(server(tmp_path / "c"), "code/ca")
    refused(wc.call("lookup", text="x", tier="CODE"), "code_index_unavailable")
    refused(wc.call("lookup", text="x", tier="any"), "code_index_unavailable")


def test_read_sentence(tmp_path, corpus):
    w = weaver(server(tmp_path))
    r = w.call("read_sentence", sid=0)
    assert r["ok"] and r["sid"] == 0 and r["text"] == corpus.space.sentences[0][0]
    assert set(r["units"]) == {"RUN", "WORD", "CHAR"} and r["units"]["WORD"] == list(corpus.tier("WORD").sentence_units[0])
    assert set(weaver(server(tmp_path / "w"), "demo/tokyo_ca").call("read_sentence", sid=3)["units"]) == {"WORD"}
    refused(w.call("read_sentence", sid=592), "unknown_sid")
    refused(w.call("read_sentence", sid=-1), "unknown_sid")
    refused(w.call("read_sentence", sid=True), "bad_args")
    refused(w.call("read_sentence", sid="0"), "bad_args")


# ---------------------------------------------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------------------------------------------
def test_add_record_is_the_postings_exactly(tmp_path, corpus):
    w = weaver(server(tmp_path), "prose/ca")
    r = w.call("add", text="日本", kind="record", tier="WORD")
    assert r == {"ok": True, "uid": "u1", "kind": "record", "surface": "日本",
                 "prov": {"tier": "WORD", "n": 49, "sids": list(corpus.postings("WORD", "日本"))}}
    r2 = w.call("add", text="日本", kind="record", tier="RUN")
    assert r2["uid"] == "u2" and r2["prov"]["n"] == 25 and r2["prov"]["sids"] == list(corpus.postings("RUN", "日本"))
    assert w.call("add", text="日本", kind="record", tier="WORD")["uid"] == "u3"          # the same word twice = two instances


def test_add_record_refusals(tmp_path):
    w = weaver(server(tmp_path), "demo/tokyo_ca")
    d = refused(w.call("add", text="首都", kind="record", tier="RUN"), "tier_not_in_task")
    w2 = weaver(server(tmp_path / "x"), "prose/ca")
    d = refused(w2.call("add", text="首都", kind="record", tier="RUN"), "not_a_record")
    assert d["in_tiers"] == ["WORD"]
    d = refused(w2.call("add", text="日本の", kind="record", tier="WORD"), "not_a_record")
    assert d["in_tiers"] == []
    refused(w2.call("add", text="です", kind="record", tier="WORD"), "not_a_record")
    refused(w2.call("add", text="日本", kind="record"), "bad_args")
    refused(w2.call("add", text="日本", kind="record", tier="XX"), "bad_args")
    refused(w2.call("add", text="日本", kind="weird", tier="WORD"), "bad_args")
    wc = weaver(server(tmp_path / "c"), "code/ca")
    refused(wc.call("add", text="x", kind="record", tier="CODE"), "code_index_unavailable")
    refused(wc.call("add", text="x", kind="record", tier="WORD"), "tier_not_in_task")


def test_add_constructed_is_marked_with_who_and_where(tmp_path):
    w = weaver(server(tmp_path), "prose/ca", model="claude-haiku-4-5")
    w.call("add", text="東京", kind="record", tier="WORD")
    r = w.call("add", text="です", kind="constructed", tier="IGNORED")
    assert r == {"ok": True, "uid": "u2", "kind": "constructed", "surface": "です", "prov": {"by": "claude-haiku-4-5", "at": 2}}


def test_constructed_refusals(tmp_path, corpus):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    assert TOY[0] not in sum((corpus.tiers_holding(t) for t in TOY), [])
    refused(w.call("add", text="日", kind="constructed"), "constructed_shadows_record")        # a CHAR unit
    d = refused(w.call("add", text="日本", kind="constructed"), "constructed_shadows_record")
    assert d["tiers"] == ["RUN", "WORD"]
    for p in ("は", "の", "に", "を", "が", "で", "と"):
        refused(w.call("add", text=p, kind="constructed"), "constructed_is_foundation")
    for bad in ("", "あ い", "a\tb", "a\x00b", "a​b", "x" * 9):
        refused(w.call("add", text=bad, kind="constructed"), "bad_unit_text")
    assert w.call("add", text="x" * 8, kind="constructed")["ok"]
    assert w.call("add", text="。", kind="constructed")["ok"]                                   # punctuation is not a unit in any tier (L-32)
    d = refused(weaver(server(tmp_path / "ro"), "prose/ro").call("add", text="です", kind="constructed"), "constructed_forbidden")
    assert d == {"mode": "record_only"}


def test_constructed_text_is_nfc(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    r = w.call("add", text="é", kind="constructed")                                       # e + combining acute -> é (one character)
    assert r["surface"] == "é"


def test_secret_shaped_text_is_refused_and_never_reaches_a_row(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="sec")
    secret = "sk-ant-aaaaaaaaaaaa"
    d = refused(w.call("lookup", text=secret, tier="any"), "secret_shaped_unit")
    refused(w.call("add", text="ghp_" + "a" * 24, kind="constructed"), "secret_shaped_unit")
    refused(w.call("status", y=1), "bad_args")                                                  # not secret, just an unknown argument
    raw = open(str(tmp_path / "runs" / "sec" / "ops.jsonl"), encoding="utf-8").read()
    assert secret not in raw and "ghp_aaaa" not in raw
    rs = rows(tmp_path / "runs" / "sec")
    red = [r for r in rs if "redacted" in r]
    assert len(red) == 2 and all(len(r["args_sha256"]) == 64 for r in red) and "[REDACTED" in json.dumps(red[0]["args"])
    # a redacted row replays: counters and the refusal are reproduced without the secret
    assert lg.verify(tmp_path / "runs" / "sec")["status"] == "OK"
    assert srv.runs["sec"].run.state.counters["lookups"] == 1


def test_a_refused_add_does_not_consume_a_uid(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    refused(w.call("add", text="見つからない語", kind="record", tier="WORD"), "not_a_record")
    assert w.call("add", text="日本", kind="record", tier="WORD")["uid"] == "u1"


# ---------------------------------------------------------------------------------------------------------------
# open_cross
# ---------------------------------------------------------------------------------------------------------------
def test_open_cross_prose(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    r = w.call("open_cross", tier="WORD", L=2)
    assert r["ok"] and r["cid"] == "c1" and r["L"] == 2 and r["seats"] == ["centre"] + ["%s:0" % ax for ax in ("+x", "-x", "+y", "-y", "+z", "-z")]
    assert r["foundation"] == {"+x": "の", "-x": "に", "+y": "で", "-y": "と", "+z": "を", "-z": "が"}
    assert w.call("open_cross", tier="CHAR", L=1)["seats"] == ["centre"]
    for L in (0, 6, -1):
        refused(w.call("open_cross", tier="WORD", L=L), "bad_L")
    refused(w.call("open_cross", tier="WORD", L=2, depth=1), "not_code")
    refused(w.call("open_cross", tier="CODE", L=2), "tier_not_in_task")
    refused(w.call("open_cross", tier="Q", L=2), "bad_args")
    refused(w.call("open_cross", tier="WORD", L="2"), "bad_args")
    refused(weaver(server(tmp_path / "t"), "demo/tokyo_ca").call("open_cross", tier="RUN", L=1), "tier_not_in_task")


def test_open_cross_code(tmp_path):
    w = weaver(server(tmp_path), "code/ca")
    r = w.call("open_cross", tier="CODE", L=8, depth=2)
    assert r["ok"] and r["foundation"] == {} and len(r["seats"]) == 1 + 6 * 8 and r["depth"] == 2
    refused(w.call("open_cross", tier="CODE", L=9), "bad_L")
    refused(w.call("open_cross", tier="CODE", L=2, depth=9), "bad_depth")
    refused(w.call("open_cross", tier="WORD", L=2), "tier_not_in_task")


# ---------------------------------------------------------------------------------------------------------------
# seat / seat_run / unseat / swap / extend / topic / set_depth / link / unlink
# ---------------------------------------------------------------------------------------------------------------
def setup_two(tmp_path, task_id="prose/ca"):
    srv = server(tmp_path)
    w = weaver(srv, task_id)
    u1 = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
    u2 = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=3)["cid"]
    return srv, w, u1, u2, c


def test_seat_and_its_refusals(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    assert w.call("seat", cid=c, seat="centre", uid=u1) == {"ok": True, "cid": c, "seat": "centre", "uid": u1}
    before = structure(srv, w)
    d = refused(w.call("seat", cid=c, seat="centre", uid=u2), "seat_occupied")
    assert d["uid"] == u1
    refused(w.call("seat", cid=c, seat="+x:2", uid=u2), "seat_is_foundation")
    refused(w.call("seat", cid=c, seat="+x:3", uid=u2), "seat_out_of_range")
    refused(w.call("seat", cid=c, seat="+x:9", uid=u2), "seat_out_of_range")
    refused(w.call("seat", cid=c, seat="+x:0", uid=u1), "unit_already_seated")
    refused(w.call("seat", cid="c9", seat="+x:0", uid=u2), "unknown_cid")
    refused(w.call("seat", cid=c, seat="+x:0", uid="u99"), "unknown_uid")
    refused(w.call("seat", cid=c, seat="north", uid=u2), "bad_seat")
    refused(w.call("seat", cid=c, seat="+x:0"), "bad_args")
    assert structure(srv, w) == before                                                           # a refusal changes nothing
    r = w.call("seat", cid=c, seat="+x:1", uid=u2)
    assert r["seat"] == "+x:1"


def test_seat_tier_mismatch_and_constructed_anywhere(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    cr = w.call("open_cross", tier="RUN", L=2)["cid"]
    d = refused(w.call("seat", cid=cr, seat="centre", uid=u1), "tier_mismatch")
    assert d == {"uid": u1, "unit_tier": "WORD", "cross_tier": "RUN"}
    uc = w.call("add", text="Ωa", kind="constructed")["uid"]
    assert w.call("seat", cid=cr, seat="centre", uid=uc)["ok"]                                  # a constructed unit may sit in any cross, centre included
    uc2 = w.call("add", text="Ωb", kind="constructed")["uid"]
    assert w.call("seat", cid=c, seat="-y:0", uid=uc2)["ok"]


def test_seat_with_a_bare_arm(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    r = w.call("seat", cid=c, seat="+x", uid=u1)
    assert r["seat"] == "+x:1"                                                                   # the innermost data seat of L = 3
    assert w.call("seat", cid=c, seat="+x", uid=u2)["seat"] == "+x:0"
    u3 = w.call("add", text="Ωa", kind="constructed")["uid"]
    d = refused(w.call("seat", cid=c, seat="+x", uid=u3), "seat_out_of_range")
    assert d["reason"] == "arm_full"


def test_seat_run_fills_in_reading_order(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    us = [w.call("add", text=t, kind="constructed")["uid"] for t in TOY[:3]]
    c = w.call("open_cross", tier="WORD", L=5)["cid"]                                            # 4 data seats per arm
    r = w.call("seat_run", cid=c, arm="+x", uids=us[:3])
    assert r["seated"] == [{"seat": "+x:1", "uid": us[0]}, {"seat": "+x:2", "uid": us[1]}, {"seat": "+x:3", "uid": us[2]}]
    # prose: the first unit is outermost, the last lands next to the particle (the innermost data seat)
    c2 = w.call("open_cross", tier="WORD", L=5)["cid"]
    wc = weaver(server(tmp_path / "code"), "code/ca")
    cu = [wc.call("add", text=t, kind="constructed")["uid"] for t in ("a", "b", "c")]
    cc = wc.call("open_cross", tier="CODE", L=4)["cid"]
    r = wc.call("seat_run", cid=cc, arm="+x", uids=cu)
    assert [s["seat"] for s in r["seated"]] == ["+x:3", "+x:2", "+x:1"]                          # code: the first unit is innermost


def test_seat_run_refusals_and_atomicity(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    us = [w.call("add", text=t, kind="constructed")["uid"] for t in TOY[:4]]
    w.call("add", text="日本", kind="record", tier="RUN")
    c = w.call("open_cross", tier="WORD", L=3)["cid"]                                            # 2 data seats per arm
    before = structure(srv, w)
    refused(w.call("seat_run", cid=c, arm="+x", uids=us[:3]), "arm_too_short")
    refused(w.call("seat_run", cid=c, arm="+x", uids=[]), "bad_args")
    refused(w.call("seat_run", cid=c, arm="+x:0", uids=us[:1]), "bad_args")
    refused(w.call("seat_run", cid=c, arm="centre", uids=us[:1]), "bad_args")
    refused(w.call("seat_run", cid=c, arm="+x", uids=[us[0], us[0]]), "unit_already_seated")
    refused(w.call("seat_run", cid=c, arm="+x", uids=[us[0], "u99"]), "unknown_uid")
    refused(w.call("seat_run", cid=c, arm="+x", uids=[us[0], "u5"]), "tier_mismatch")               # u5 is a RUN record, the cross is WORD
    assert structure(srv, w) == before
    w.call("seat", cid=c, seat="+x:1", uid=us[3])
    refused(w.call("seat_run", cid=c, arm="+x", uids=us[:2]), "seat_occupied")                  # +x:1 is taken; nothing was seated
    assert srv.runs[w.run_id].run.state.units[us[0]].seated is None


def test_unseat(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    w.call("seat", cid=c, seat="+x:0", uid=u2)
    assert w.call("unseat", cid=c, seat="+x:0") == {"ok": True, "cid": c, "uid": u2}
    assert srv.runs[w.run_id].run.state.units[u2].seated is None
    refused(w.call("unseat", cid=c, seat="+x:0"), "seat_empty")
    refused(w.call("unseat", cid=c, seat="+x:2"), "seat_is_foundation")
    refused(w.call("unseat", cid=c, seat="+x:3"), "seat_out_of_range")
    refused(w.call("unseat", cid=c, seat="+x"), "bad_seat")
    assert w.call("seat", cid=c, seat="+x:0", uid=u2)["ok"]                                       # a replacement leaves two rows


def test_swap_moves_and_exchanges_and_refuses(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    w.call("seat", cid=c, seat="centre", uid=u1)
    w.call("seat", cid=c, seat="+x:0", uid=u2)
    st = srv.runs[w.run_id].run.state
    assert w.call("swap", cid=c, seat_a="centre", seat_b="+x:0")["ok"]
    assert st.crosses[c].centre == u2 and st.crosses[c].arms[0][0] == u1
    assert w.call("swap", cid=c, seat_a="+x:0", seat_b="-z:1")["ok"]                              # a move into an empty seat
    assert st.crosses[c].arms[0][0] is None and st.crosses[c].arms[5][1] == u1 and st.units[u1].seated == [c, "-z:1"]
    assert w.call("swap", cid=c, seat_a="+x:0", seat_b="+y:0")["ok"]                              # two empty seats: allowed, nothing changes
    refused(w.call("swap", cid=c, seat_a="+x:0", seat_b="+x:0"), "same_seat")
    refused(w.call("swap", cid=c, seat_a="+x:2", seat_b="centre"), "seat_is_foundation")
    refused(w.call("swap", cid=c, seat_a="centre", seat_b="+x:2"), "seat_is_foundation")
    refused(w.call("swap", cid=c, seat_a="centre", seat_b="+x:9"), "seat_out_of_range")
    refused(w.call("swap", cid=c, seat_a="centre", seat_b="+x"), "bad_seat")
    # moving the only centre unit out leaves the centre empty as a WORKING state (refused only at read / emit, design 3.2 rule 5)
    assert w.call("swap", cid=c, seat_a="centre", seat_b="+y:0")["ok"]
    assert st.crosses[c].centre is None


def test_extend(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    w.call("seat", cid=c, seat="+x:1", uid=u1)
    assert w.call("extend", cid=c, L2=5) == {"ok": True, "cid": c, "L": 5}
    cr = srv.runs[w.run_id].run.state.crosses[c]
    assert cr.arms[0][3] == u1 and cr.arms[0][4].startswith("\u0000F:") and cr.arms[0][:3] == [None] * 3          # still next to its particle
    for L2 in (5, 4, 6, 0):
        refused(w.call("extend", cid=c, L2=L2), "bad_L")


def test_seated_marks_follow_extend(tmp_path):
    """After extend the seat NAME of a unit changes (k is counted from the outer end): the registry follows."""
    srv, w, u1, u2, c = setup_two(tmp_path)
    w.call("seat", cid=c, seat="+x:1", uid=u1)
    w.call("extend", cid=c, L2=5)
    unit = srv.runs[w.run_id].run.state.units[u1]
    cr = srv.runs[w.run_id].run.state.crosses[c]
    assert cr.arms[0].index(u1) == 3
    assert unit.seated == [c, "+x:3"]                                                 # the registry's seat name follows the shift of k


def test_topic_and_set_depth_and_their_refusals(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    assert w.call("topic", cid=c, on=True)["topic"] is True
    refused(w.call("topic", cid=c, on="yes"), "bad_args")
    refused(w.call("set_depth", cid=c, depth=1), "not_code")
    wc = weaver(server(tmp_path / "code"), "code/ca")
    cc = wc.call("open_cross", tier="CODE", L=2)["cid"]
    refused(wc.call("topic", cid=cc, on=True), "not_prose")
    assert wc.call("set_depth", cid=cc, depth=3)["depth"] == 3
    refused(wc.call("set_depth", cid=cc, depth=9), "bad_depth")
    refused(wc.call("set_depth", cid=cc, depth=-1), "bad_depth")


def test_link_unlink_and_the_thread(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    cs = [w.call("open_cross", tier="WORD", L=1)["cid"] for _ in range(3)]
    assert w.call("link", cid=cs[0])["thread"] == [cs[0]]
    assert w.call("link", cid=cs[1], pos=0)["thread"] == [cs[1], cs[0]]
    assert w.call("link", cid=cs[2], pos=1)["thread"] == [cs[1], cs[2], cs[0]]
    refused(w.call("link", cid=cs[2]), "already_linked")
    refused(w.call("link", cid="c9"), "unknown_cid")
    c4 = w.call("open_cross", tier="WORD", L=1)["cid"]
    refused(w.call("link", cid=c4, pos=4), "bad_pos")
    refused(w.call("link", cid=c4, pos=-1), "bad_pos")
    assert w.call("unlink", cid=cs[2])["thread"] == [cs[1], cs[0]]
    refused(w.call("unlink", cid=cs[2]), "not_linked")
    assert srv.runs[w.run_id].run.state.crosses[cs[2]].linked is False


def test_status_shows_seats_pool_counters_and_the_ledger_head(tmp_path):
    srv, w, u1, u2, c = setup_two(tmp_path)
    w.call("seat", cid=c, seat="centre", uid=u1)
    s = w.call("status")
    assert s["ok"] and s["thread"] == [] and s["pool"] == [u2] and s["surfaces"] == {u1: "東京", u2: "日本"}
    assert s["crosses"][c]["seats"]["centre"] == u1 and s["crosses"][c]["seats"]["+x:2"] == "F:の" and s["crosses"][c]["seats"]["-z:2"] == "F:が"
    assert s["counters"] == {"ops": 4, "lookups": 0, "reads": 0, "emit_attempts": 0, "constructed": 0}
    assert s["ledger_head"] == rows(tmp_path / "runs" / w.run_id)[-2]["sha"]               # the head BEFORE the status row itself
    assert s["caps"]["ops"] == 200


def test_abstain(tmp_path):
    srv = server(tmp_path)
    for t in ("no_record", "cannot_weave", "unknown"):
        w = weaver(srv, "prose/ca", run_id="ab" + t)
        refused(w.call("abstain", type="free text"), "bad_type")
        assert w.call("abstain", type=t) == {"ok": True, "status": "abstained", "type": t}
        assert srv.closed(w.run_id) == ["abstained", t]


def test_a_closed_run_refuses_every_model_call_but_takes_harness_rows(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    w.call("abstain", type="unknown")
    for tool, args in (("status", {}), ("lookup", {"text": "日本", "tier": "any"}), ("add", {"text": "日本", "kind": "record", "tier": "WORD"}),
                       ("emit", {}), ("read", {}), ("abstain", {"type": "unknown"}), ("open_cross", {"tier": "WORD", "L": 1})):
        d = refused(w.call(tool, **args), "run_closed")
        assert d["closed"] == ["abstained", "unknown"]
    assert srv.harness(w.run_id, "free_text_dropped", {"sha256": "0" * 64, "chars": 3})["ok"]
    assert srv.harness(w.run_id, "harness_meta", {"driver": "scripted"})["ok"]
    assert srv.closed(w.run_id) == ["abstained", "unknown"]


def test_harness_rows_are_validated(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    for op, args in (("free_text_dropped", {"sha256": "zz", "chars": 1}), ("free_text_dropped", {"sha256": "0" * 64}),
                     ("harness_meta", {"driver": "carrier pigeon"}), ("harness_meta", {}), ("abandoned", {"reason": "Bad Reason"}),
                     ("lookup", {"text": "x"}), ("grade", {"grade": "pass", "grader": "x"})):
        with pytest.raises(ValueError):
            srv.harness(w.run_id, op, args)
    assert srv.harness(w.run_id, "grade", {"grade": "pass", "grader": "alice"}, actor="human")["ok"]
    with pytest.raises(ValueError):
        srv.harness(w.run_id, "abandoned", {"reason": "x"}, actor="human")


# ---------------------------------------------------------------------------------------------------------------
# the caps fire exactly at the limit (L-LOOM-08)
# ---------------------------------------------------------------------------------------------------------------
def test_ops_cap_fires_after_exactly_200_state_changing_calls_refused_or_not(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    c = w.call("open_cross", tier="WORD", L=1)["cid"]                       # 1
    for _ in range(198):
        assert w.call("topic", cid=c, on=True)["ok"]
    r = w.call("topic", cid=c, on=True)                                       # the 200th
    assert r["ok"]
    d = refused(w.call("topic", cid=c, on=False), "ops_cap")
    assert d == {"limit": 200}
    assert srv.runs[w.run_id].run.state.crosses[c].topic is True              # the refused call changed nothing
    assert w.call("status")["counters"]["ops"] == 200                         # the cap refusal itself does not count
    refused(w.call("add", text="日本", kind="record", tier="WORD"), "ops_cap")
    assert w.call("emit")["refusal"] == "empty_thread"                        # emit / read / lookup / status are other classes
    assert w.call("lookup", text="日本", tier="any")["ok"]


def test_refused_calls_count_in_their_class(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    for _ in range(200):
        w.call("seat", cid="c9", seat="centre", uid="u9")                    # unknown_cid every time
    refused(w.call("seat", cid="c9", seat="centre", uid="u9"), "ops_cap")


def test_lookup_cap_is_shared_by_lookup_and_read_sentence(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    for i in range(50):
        assert w.call("lookup", text="日本", tier="any")["ok"]
        assert w.call("read_sentence", sid=i)["ok"]
    assert refused(w.call("lookup", text="日本", tier="any"), "lookup_cap") == {"limit": 100}
    refused(w.call("read_sentence", sid=0), "lookup_cap")
    assert w.call("add", text="日本", kind="record", tier="WORD")["ok"]


def test_read_cap_is_20_and_emit_cap_is_5_and_abstain_survives_it(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    for _ in range(20):
        assert w.call("read")["ok"]
    assert refused(w.call("read"), "read_cap") == {"limit": 20}
    for _ in range(5):
        assert w.call("emit")["refusal"] == "empty_thread"
    assert refused(w.call("emit"), "emit_cap") == {"limit": 5}
    assert w.call("status")["counters"]["emit_attempts"] == 5
    assert w.call("abstain", type="cannot_weave")["status"] == "abstained"


def test_constructed_cap_is_12_per_run_and_the_text_cap_is_8(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    for i in range(12):
        assert w.call("add", text="Ω%02d" % i, kind="constructed")["ok"]
    assert refused(w.call("add", text="Ω99", kind="constructed"), "constructed_cap") == {"limit": 12}
    assert w.call("add", text="日本", kind="record", tier="WORD")["ok"]                          # records are not limited by it
    assert w.call("status")["counters"]["constructed"] == 12


def test_cross_cap_is_24(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    for _ in range(24):
        assert w.call("open_cross", tier="WORD", L=1)["ok"]
    assert refused(w.call("open_cross", tier="WORD", L=1), "cross_cap") == {"limit": 24}


def test_code_caps_are_larger(tmp_path):
    w = weaver(server(tmp_path), "code/ca")
    caps = w.call("status")["caps"]
    assert (caps["ops"], caps["lookups"], caps["reads"], caps["emit_attempts"], caps["constructed"], caps["unit_chars"], caps["crosses"], caps["max_L"]) \
        == (400, 60, 40, 8, 60, 40, 60, 8)


def test_a_refusal_never_raises_and_always_has_a_type_and_detail(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    calls = [("lookup", {}), ("lookup", {"text": 1, "tier": 2}), ("add", {"text": None, "kind": None}), ("seat", {"cid": 1, "seat": 2, "uid": 3}),
             ("open_cross", {"tier": [], "L": {}}), ("seat_run", {"cid": "c1", "arm": "+x", "uids": "u1"}), ("link", {"cid": "c1", "pos": "0"}),
             ("emit", {"x": 1}), ("abstain", {}), ("status", {"y": 2}), ("extend", {"cid": "c1"}), ("swap", {}), ("unseat", {})]
    for tool, args in calls:
        r = w.call(tool, **args)
        assert r["ok"] is False and isinstance(r["refusal"], str) and isinstance(r["detail"], dict), (tool, r)
